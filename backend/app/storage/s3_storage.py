"""S3-compatible object storage backend (Cloudflare R2 / AWS S3)."""

from typing import BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.base import (
    StorageConfigurationError,
    StorageError,
    StoredObjectInfo,
)


class S3CompatibleStorage:
    """S3-compatible storage backend configured for private bucket access."""

    def __init__(
        self,
        *,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        bucket_name: str | None,
        timeout_seconds: int = 15,
        region_name: str = "auto",
    ) -> None:
        if not all([endpoint_url, access_key_id, secret_access_key, bucket_name]):
            raise StorageConfigurationError(
                "Object storage is not configured. Set R2 credentials and bucket."
            )

        self.bucket_name = bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
            config=Config(
                signature_version="s3v4",
                connect_timeout=timeout_seconds,
                read_timeout=timeout_seconds,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

    def upload_file(
        self,
        *,
        file_obj: BinaryIO,
        storage_key: str,
        content_type: str,
    ) -> StoredObjectInfo:
        """Upload a file stream to a private S3-compatible bucket."""
        file_obj.seek(0, 2)
        file_size = file_obj.tell()
        file_obj.seek(0)
        try:
            self._client.upload_fileobj(
                file_obj,
                self.bucket_name,
                storage_key,
                ExtraArgs={"ContentType": content_type},
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Failed to upload file to object storage.") from exc

        return StoredObjectInfo(
            storage_key=storage_key,
            content_type=content_type,
            file_size=file_size,
        )

    def delete_file(self, storage_key: str) -> None:
        """Delete an object from the bucket."""
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=storage_key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Failed to delete file from object storage.") from exc

    def get_metadata(self, storage_key: str) -> StoredObjectInfo:
        """Fetch object metadata via HeadObject."""
        try:
            resp = self._client.head_object(
                Bucket=self.bucket_name,
                Key=storage_key,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Failed to retrieve file metadata.") from exc

        return StoredObjectInfo(
            storage_key=storage_key,
            content_type=resp.get("ContentType", "application/octet-stream"),
            file_size=int(resp.get("ContentLength", 0)),
        )

    def generate_presigned_download_url(
        self,
        storage_key: str,
        *,
        download_filename: str,
        expires_in_seconds: int,
        disposition: str = "attachment",
        content_type: str | None = None,
    ) -> str:
        """Generate a short-lived signed GET URL with Content-Disposition."""
        safe_name = download_filename.replace('"', "")
        safe_disposition = "inline" if disposition == "inline" else "attachment"
        params = {
            "Bucket": self.bucket_name,
            "Key": storage_key,
            "ResponseContentDisposition": f'{safe_disposition}; filename="{safe_name}"',
        }
        if content_type:
            params["ResponseContentType"] = content_type
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Failed to generate download URL.") from exc

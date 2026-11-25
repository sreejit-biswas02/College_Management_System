# College Management System — Secure File Uploads & Cloudflare R2 Storage

## 1. Storage Architecture

- **Provider-Independent Abstraction:** `backend/app/storage/base.py` defines the `StorageBackend` protocol (`upload_file`, `delete_file`, `get_metadata`, `generate_presigned_download_url`).
- **S3-Compatible Implementation:** `backend/app/storage/s3_storage.py` implements `S3CompatibleStorage` using `boto3` (`s3v4` signatures, configurable timeouts, private bucket access).
- **Database Metadata (`stored_files`):** `backend/app/models/stored_file.py` stores `original_filename`, unique random `storage_key`, `content_type`, `file_size`, `uploaded_by`, `entity_type`, `entity_id`, and `is_active`. Binary file contents are **never** stored in PostgreSQL or local disk.

---

## 2. Cloudflare R2 Setup Guide (Manual Steps)

1. Log in to the **Cloudflare Dashboard** -> **R2 Object Storage**.
2. Click **Create bucket** (e.g., `college-management-files`), keeping **Public Access disabled** (private bucket).
3. Go to **Manage R2 API Tokens** -> **Create API Token** with **Object Read & Write** permissions scoped to that bucket.
4. Copy your **Account ID**, **Access Key ID**, and **Secret Access Key** into `backend/.env` (never commit `.env`):
   ```env
   STORAGE_PROVIDER=r2
   R2_ACCOUNT_ID=<your-account-id>
   R2_ACCESS_KEY_ID=<your-access-key-id>
   R2_SECRET_ACCESS_KEY=<your-secret-access-key>
   R2_BUCKET_NAME=college-management-files
   R2_ENDPOINT_URL=https://<your-account-id>.r2.cloudflarestorage.com
   SIGNED_URL_EXPIRE_SECONDS=300
   MAX_DOCUMENT_UPLOAD_BYTES=10485760
   MAX_ASSIGNMENT_UPLOAD_BYTES=20971520
   ```

---

## 3. Upload, Validation & Download Workflows

- **Validation (`app/storage/validation.py`):**
  - Allowed extensions: `.pdf`, `.doc`, `.docx`, `.txt`, `.jpg`, `.jpeg`, `.png`.
  - Enforces max size (`10 MB` general/submissions, `20 MB` assignment attachments), rejects empty files, sanitizes filenames against path traversal, verifies declared MIME type, and checks magic-byte signatures (`%PDF-`, PNG, JPEG, DOC, DOCX, UTF-8 TXT).
  - Generates random UUID `storage_key`s (`assignments/{id}/{uuid}{ext}` or `submissions/{id}/{uuid}{ext}`).
- **Authorization & Signed Downloads:**
  - `GET /api/v1/files/{file_id}` verifies active status and user authorization (Admin, assigned Faculty, or enrolled/owning Student) before generating a short-lived presigned URL (`300s` default). The signed URL acts as a temporary bearer link for that download.
- **Safe Deletion:**
  - `DELETE /api/v1/files/{file_id}` deletes the object from R2 **first** and only marks `is_active = False` in PostgreSQL after storage confirms deletion.

---

## 4. Known Limitations & Future Enhancements

- **Malware Scanning:** Magic-byte validation prevents extension spoofing, but does **not** scan for embedded malware/macros. Production deployments should integrate ClamAV or an async object-scan pipeline before marking files clean.
- **Orphaned Object Cleanup:** If a DB commit fails after R2 upload, immediate cleanup is attempted (`storage.delete_file`); a scheduled reconciliation job comparing R2 keys against `stored_files` is recommended for long-term hygiene.

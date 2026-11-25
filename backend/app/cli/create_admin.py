"""Bootstrap CLI for creating an initial ADMIN account."""

import argparse
import getpass
import os
import sys

from pydantic import ValidationError

from app.database.connection import SessionLocal
from app.schemas.auth import AdminCreateRequest
from app.services.auth_service import EmailAlreadyExistsError, create_admin_user


def main() -> int:
    """Parse CLI arguments and create an administrator account."""
    parser = argparse.ArgumentParser(
        description="Create an administrator account for College Management System.",
    )
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--full-name", required=True, help="Admin full name")
    args = parser.parse_args()

    password = os.environ.get("ADMIN_INITIAL_PASSWORD") or getpass.getpass(
        "Admin password: "
    )
    try:
        payload = AdminCreateRequest(
            email=args.email,
            full_name=args.full_name,
            password=password,
        )
    except ValidationError as exc:
        sys.stderr.write(f"Validation error: {exc}\n")
        return 1

    db = SessionLocal()
    try:
        user = create_admin_user(db, payload)
        sys.stdout.write(f"Admin user created: id={user.id}, email={user.email}\n")
        return 0
    except EmailAlreadyExistsError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

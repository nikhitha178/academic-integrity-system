import sys
from pathlib import Path
from getpass import getpass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from backend.app.database import SessionLocal
from backend.app.models import User
from backend.app.services.auth import hash_password

USERNAME = "reviewer_000001"


def main():
    password = getpass("Enter a new reviewer password: ")
    confirmation = getpass("Confirm the password: ")

    if password != confirmation:
        print("Passwords do not match. No changes made.")
        return

    if not 12 <= len(password) <= 128:
        print("Password must contain 12 to 128 characters. No changes made.")
        return

    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(User.username == USERNAME)
        )

        if user is None:
            print("Reviewer account not found. No changes made.")
            return

        if not user.is_active:
            print("Reviewer account is inactive. No changes made.")
            return

        if user.password_hash:
            print("A password is already configured. No changes made.")
            return

        user.password_hash = hash_password(password)
        db.commit()

    print("Reviewer password configured successfully.")


if __name__ == "__main__":
    main()

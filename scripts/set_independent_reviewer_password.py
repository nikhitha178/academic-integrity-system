import sys
from pathlib import Path
from getpass import getpass

# Make the project root importable before importing backend.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from backend.app.database import SessionLocal
from backend.app.models import User
from backend.app.services.auth import hash_password

USERNAME = "ind_reviewer_000001"


def main():
    password = getpass("Enter a new password for ind_reviewer_000001: ")
    confirm_password = getpass("Confirm the password: ")

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match. No changes made.")
        return

    db = SessionLocal()
    try:
        user = db.scalar(
            select(User).where(User.username == USERNAME)
        )

        if user is None:
            print("Reviewer account not found. No changes made.")
            return

        if not user.is_active:
            print("Account is inactive. No changes made.")
            return

        if user.role != "Independent Appeal Reviewer":
            print("Incorrect account role. No changes made.")
            return

        if user.password_hash:
            print("A password is already configured. No changes made.")
            return

        user.password_hash = hash_password(password)
        db.commit()
        print("Password configured successfully for ind_reviewer_000001.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

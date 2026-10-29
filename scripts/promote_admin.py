"""Promote an existing local account to catalog administrator."""

from sqlalchemy import select

from app import models
from app.database import SessionLocal


def main() -> None:
    username = input("Username to promote: ").strip()
    if not username:
        raise SystemExit("A username is required.")
    with SessionLocal() as db:
        user = db.execute(select(models.User).where(models.User.username == username)).scalars().first()
        if not user:
            raise SystemExit("No account with that username was found.")
        user.is_admin = True
        db.commit()
    print(f"Promoted {username} to catalog administrator.")


if __name__ == "__main__":
    main()

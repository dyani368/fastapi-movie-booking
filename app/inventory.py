from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def release_expired_holds(db: Session, screening_id: int) -> None:
    screening = db.execute(
        select(models.Screening).where(models.Screening.id == screening_id).with_for_update()
    ).scalars().first()
    if screening is None:
        return
    now = datetime.now(timezone.utc)
    expired = db.execute(
        select(models.Booking)
        .where(models.Booking.screening_id == screening_id, models.Booking.status == "pending", models.Booking.expires_at <= now)
        .with_for_update()
    ).scalars().all()
    for booking in expired:
        screening.seats_reserved -= booking.seats_booked
        movie = db.execute(select(models.Movie).where(models.Movie.id == screening.movie_id).with_for_update()).scalar_one()
        movie.seats_available += booking.seats_booked
        booking.status = "expired"
        booking.expires_at = None

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from datetime import datetime, timezone

from app.database import Base

class Movie(Base):
    __tablename__ = "movies" 
    __table_args__ = (CheckConstraint("seats_available >= 0", name="ck_movies_seats_nonnegative"),)

    id : Mapped[int] = mapped_column(primary_key = True, index = True)
    title: Mapped[str] = mapped_column(nullable = False)
    director: Mapped[str] = mapped_column(nullable = False)
    seats_available: Mapped[int] = mapped_column(nullable = False)

    bookings : Mapped[list[Booking]] = relationship(back_populates="movie", cascade="all, delete-orphan")

    poster_file: Mapped[str | None] = mapped_column(default = "default_poster.jpg")

    @property 
    def poster_path(self) -> str:
        if self.poster_file:
            return f"/media/posters/{self.poster_file}"
        return "/static/images/default_movie.jpg"

class User(Base):
    __tablename__ = "users"

    id : Mapped[int] = mapped_column(primary_key = True, index = True)
    is_admin: Mapped[bool] = mapped_column(default=False) 
    username : Mapped[str] = mapped_column(unique = True,  nullable = False)
    email : Mapped[str] = mapped_column(unique = True,  nullable = False)
    phone_number: Mapped[str | None] = mapped_column(nullable=True)
    hashed_password : Mapped[str] = mapped_column(nullable = False)
    
    bookings : Mapped[list[Booking]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Booking(Base):
    __tablename__ = "booking"
    __table_args__ = (CheckConstraint("seats_booked > 0", name="ck_booking_seats_positive"),)

    id : Mapped[int] = mapped_column(primary_key = True, index = True)
    seats_booked : Mapped[int] = mapped_column(nullable=False)
    show_time : Mapped[str] = mapped_column(nullable = False)

    # Store integers (IDs) on the database disk:
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    movie_id : Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)

    # Load Python objects in memory:
    user : Mapped[User] = relationship(back_populates="bookings")
    movie : Mapped[Movie] = relationship(back_populates="bookings")


class SmsDelivery(Base):
    __tablename__ = "sms_deliveries"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_sms_deliveries_booking_id"),
        CheckConstraint(
            "status IN ('pending', 'queued', 'sent', 'delivered', 'failed', 'undelivered', 'send_failed')",
            name="ck_sms_deliveries_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("booking.id", ondelete="SET NULL"), nullable=True, index=True)
    message_uuid: Mapped[str | None] = mapped_column(unique=True, nullable=True, index=True)
    destination: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="pending", nullable=False)
    error_code: Mapped[str | None] = mapped_column(nullable=True)
    last_sequence: Mapped[int | None] = mapped_column(nullable=True)
    last_event_hash: Mapped[str | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

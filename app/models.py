from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (CheckConstraint("seats_available >= 0", name="ck_movies_seats_nonnegative"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    director: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown")
    seats_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    poster_file: Mapped[str | None] = mapped_column(String, default="default_poster.jpg")
    tmdb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    overview: Mapped[str | None] = mapped_column(Text)
    release_date: Mapped[str | None] = mapped_column(String(20))
    rating: Mapped[float | None]
    tmdb_poster_path: Mapped[str | None] = mapped_column(String(500))

    screenings: Mapped[list[Screening]] = relationship(back_populates="movie", cascade="all, delete-orphan")

    @property
    def poster_path(self) -> str:
        if self.tmdb_poster_path:
            return f"https://image.tmdb.org/t/p/w500{self.tmdb_poster_path}"
        if self.poster_file and self.poster_file != "default_poster.jpg":
            return f"/media/posters/{self.poster_file}"
        return "/static/images/default_movie.jpg"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    bookings: Mapped[list[Booking]] = relationship(back_populates="user")


class Screening(Base):
    __tablename__ = "screenings"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_screening_capacity_positive"),
        CheckConstraint("seats_reserved >= 0 AND seats_reserved <= capacity", name="ck_screening_inventory_valid"),
        CheckConstraint("price_paise > 0", name="ck_screening_price_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    auditorium: Mapped[str] = mapped_column(String(100), nullable=False, default="Screen 1")
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    seats_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=25000)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    movie: Mapped[Movie] = relationship(back_populates="screenings")
    bookings: Mapped[list[Booking]] = relationship(back_populates="screening")

    @property
    def seats_available(self) -> int:
        return max(0, self.capacity - self.seats_reserved)


class Booking(Base):
    __tablename__ = "booking"
    __table_args__ = (
        CheckConstraint("seats_booked > 0", name="ck_booking_seats_positive"),
        CheckConstraint("status IN ('pending', 'confirmed', 'cancelled', 'expired', 'failed', 'payment_review')", name="ck_booking_status_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    seats_booked: Mapped[int] = mapped_column(Integer, nullable=False)
    show_time: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    calendar_event_id: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Kept alongside screening_id to upgrade databases created by the earlier schema.
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id"), index=True)
    user: Mapped[User] = relationship(back_populates="bookings")
    screening: Mapped[Screening] = relationship(back_populates="bookings")

    @property
    def movie(self) -> Movie:
        return self.screening.movie


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_event_id: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CalendarCredential(Base):
    __tablename__ = "calendar_credentials"
    __table_args__ = (UniqueConstraint("user_id", name="uq_calendar_credential_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

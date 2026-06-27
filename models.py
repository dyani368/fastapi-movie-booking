from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from database import Base

class Movie(Base):
    __tablename__ = "movies" 

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
    is_admin: Mapped[bool] = mapped_column(default=True) 
    username : Mapped[str] = mapped_column(unique = True,  nullable = False)
    email : Mapped[str] = mapped_column(unique = True,  nullable = False)
    hashed_password : Mapped[str] = mapped_column(nullable = False)
    
    bookings : Mapped[list[Booking]] = relationship(back_populates="user", cascade="all, delete-orphan")

class Booking(Base):
    __tablename__ = "booking"

    id : Mapped[int] = mapped_column(primary_key = True, index = True)
    seats_booked : Mapped[int] = mapped_column(nullable=False)
    show_time : Mapped[str] = mapped_column(nullable = False)

    # Store integers (IDs) on the database disk:
    user_id : Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    movie_id : Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)

    # Load Python objects in memory:
    user : Mapped[User] = relationship(back_populates="bookings")
    movie : Mapped[Movie] = relationship(back_populates="bookings")
    


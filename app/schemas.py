from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    director: str = Field(default="Unknown", max_length=255)
    seats_available: int = Field(ge=0, default=0)


class MovieResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    director: str
    seats_available: int
    poster_path: str
    overview: str | None = None
    release_date: str | None = None
    rating: float | None = None


class MovieUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    director: str | None = Field(default=None, min_length=1, max_length=255)
    seats_available: int | None = Field(default=None, ge=0)


class TMDBMovieImport(BaseModel):
    tmdb_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=255)
    overview: str | None = Field(default=None, max_length=5000)
    release_date: str | None = Field(default=None, max_length=20)
    rating: float | None = Field(default=None, ge=0, le=10)
    poster_path: str | None = Field(default=None, max_length=500, pattern=r"^/.*$")


class CalendarCallbackPayload(BaseModel):
    state: str = Field(min_length=20, max_length=100)
    code: str = Field(min_length=1, max_length=4096)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


class UserPrivate(UserPublic):
    email: str
    is_admin: bool = False


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)


class Token(BaseModel):
    access_token: str
    token_type: str


class ScreeningCreate(BaseModel):
    starts_at: datetime
    auditorium: str = Field(default="Screen 1", max_length=100)
    capacity: int = Field(gt=0, le=1000)
    price_paise: int = Field(gt=0, le=10000000)


class ScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    movie_id: int
    starts_at: datetime
    auditorium: str
    capacity: int
    seats_reserved: int
    seats_available: int
    price_paise: int
    currency: str
    movie: MovieResponse | None = None


class BookingCreate(BaseModel):
    screening_id: int
    seats_booked: int = Field(ge=1, le=8)


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    screening_id: int
    seats_booked: int
    status: str
    amount_paise: int
    expires_at: datetime | None
    razorpay_order_id: str | None
    razorpay_payment_id: str | None
    calendar_event_id: str | None
    screening: ScreeningResponse


class PaymentOrderResponse(BaseModel):
    booking: BookingResponse
    key_id: str
    order_id: str
    amount: int
    currency: str

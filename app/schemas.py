from pydantic import BaseModel, ConfigDict, Field, EmailStr
from typing import Literal

SHOW_TIMES = ("12:00 PM", "3:30 PM", "7:00 PM", "10:15 PM")

class MovieBase(BaseModel):
    title: str = Field(min_length =1, max_length = 20)
    director: str = Field(min_length = 1)
    seats_available: int = Field(ge=0)

class MovieCreate(MovieBase):
    seats_available: int = Field(gt=0)

class MovieResponse(MovieBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    poster_path: str

class MovieUpdate(BaseModel):
    title: str|None = Field(default=None, min_length=1, max_length=20)
    director: str|None = Field(default=None, min_length=1)
    seats_available: int|None = Field(default=None, ge=1)

class UserBase(BaseModel):
    username : str = Field(min_length = 3, max_length = 15)
    email : EmailStr
    phone_number: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$")

class UserCreate(UserBase):
    password : str = Field(min_length = 8)

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str = Field(min_length = 3, max_length = 15)

class UserPrivate(UserPublic):
    email: str
    phone_number: str | None = None

class UserUpdate(BaseModel):
    username: str|None = Field(default=None, min_length=1, max_length=15)
    email: str|None = Field(default=None, min_length=1)
    phone_number: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$")
    password: str|None = Field(default=None,min_length=8)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: int | None = None

class BookingBase(BaseModel):
    movie_id : int 
    seats_booked : int = Field(ge=1)
    show_time: Literal["12:00 PM", "3:30 PM", "7:00 PM", "10:15 PM"]

class BookingCreate(BookingBase):
    pass

class BookingResponse(BookingBase):
    model_config = ConfigDict(from_attributes=True)

    id : int
    user_id: int
    
    user: UserPublic
    movie : MovieResponse

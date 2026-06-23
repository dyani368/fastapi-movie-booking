from pydantic import BaseModel, ConfigDict, Field, EmailStr
from datetime import datetime

class MovieBase(BaseModel):
    title: str = Field(min_length =1, max_length = 20)
    director: str = Field(min_length = 1)
    seats_available: int = Field(ge=1)

class MovieCreate(MovieBase):
    pass

class MovieResponse(MovieBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date_posted : str = Field(default_factory=lambda: datetime.now().strftime("%B %d, %Y"))
    poster_path: str

class MovieUpdate(BaseModel):
    title: str|None = Field(default=None, min_length=1, max_length=20)
    director: str|None = Field(default=None, min_length=1)
    seats_available: int|None = Field(default=None, ge=1)

class UserBase(BaseModel):
    username : str = Field(min_length = 3, max_length = 15)
    email : EmailStr

class UserCreate(UserBase):
    password : str = Field(min_length = 8)

class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str = Field(min_length = 3, max_length = 15)

class UserPrivate(UserPublic):
    email: str

class UserUpdate(BaseModel):
    username: str|None = Field(default=None, min_length=1, max_length=15)
    email: str|None = Field(default=None, min_length=1)
    password: str|None = Field(default=None,min_length=8)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: int | None = None

class BookingBase(BaseModel):
    user_id : int 
    movie_id : int 
    seats_booked : int = Field(ge=1)
    show_time : str

class BookingCreate(BookingBase):
    pass

class BookingResponse(BookingBase):
    model_config = ConfigDict(from_attributes=True)

    id : int
    
    user: UserPublic
    movie : MovieResponse



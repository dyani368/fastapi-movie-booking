import os
import secrets
import hmac
import hashlib
from fastapi import FastAPI, Request, HTTPException, status, Depends, Form, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import Annotated 
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session 
from sqlalchemy.exc import IntegrityError

from app.schemas import UserCreate, SHOW_TIMES
from app import models
from app.database import get_db
from app.config import settings
from app.routers import movies, users, bookings
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_from_cookie,
    get_admin_user,
    get_optional_current_user,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

app = FastAPI()
app.include_router(movies.router, prefix="/api/movies", tags=["movies"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["bookings"])

app.mount("/static", StaticFiles(directory=os.path.join(PROJECT_DIR, "static")), name="static")
app.mount("/media", StaticFiles(directory=os.path.join(PROJECT_DIR, "media")), name="media")

templates = Jinja2Templates(directory=os.path.join(PROJECT_DIR, "templates"))


def validate_csrf(
    request: Request,
    csrf_token: Annotated[str, Form(alias="_csrf")],
) -> None:
    cookie_token = request.cookies.get("csrf_token", "")
    try:
        nonce, signature = cookie_token.split(".", maxsplit=1)
    except ValueError:
        nonce, signature = "", ""
    expected = hmac.new(settings.secret_key.get_secret_value().encode(), nonce.encode(), hashlib.sha256).hexdigest()
    if (
        not nonce
        or len(cookie_token) > 256
        or not hmac.compare_digest(cookie_token, csrf_token)
        or not hmac.compare_digest(signature, expected)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def issue_csrf_token() -> str:
    nonce = secrets.token_urlsafe(32)
    signature = hmac.new(settings.secret_key.get_secret_value().encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"

@app.get("/health")
def health(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable"
        ) from exc
    
    return {"status": "healthy"}

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    csrf_token = request.cookies.get("csrf_token") or issue_csrf_token()
    request.state.csrf_token = csrf_token
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000;includeSubDomains"
    if not request.cookies.get("csrf_token"):
        response.set_cookie("csrf_token", csrf_token, httponly=False, secure=settings.secure_cookies, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response

@app.get("/", include_in_schema=False)
def root(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User | None, Depends(get_optional_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
):
    skip = (page - 1) * 3
    result = db.execute(select(models.Movie).offset(skip).limit(3))
    movie_list = result.scalars().all()
    total_movies = db.execute(select(func.count(models.Movie.id))).scalar()
    total_pages = max(1, (total_movies + 2) // 3)

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "movies": movie_list,
            "title": "Home",
            "current_user": current_user,
            "page": page,
            "total_pages": total_pages,
        },
    )

@app.get("/movies/new", include_in_schema=False)
def create_movie_form(request: Request, current_user: Annotated[models.User, Depends(get_admin_user)]):
    return templates.TemplateResponse(request, "create_movie.html", {"title": "Add Movie", "current_user": current_user})
    
@app.post("/movies/new", include_in_schema=False)
def create_movie_html(
    _: Annotated[None, Depends(validate_csrf)],
    current_user: Annotated[models.User, Depends(get_admin_user)],
    title: Annotated[str, Form(min_length=1, max_length=20)],
    director: Annotated[str, Form(min_length=1, max_length=120)],
    seats_available: Annotated[int, Form(gt=0)],
    db: Annotated[Session, Depends(get_db)],
):
    new_movie = models.Movie(title=title, director=director, seats_available=seats_available)
    db.add(new_movie)
    db.commit()
    db.refresh(new_movie)
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/movies/{movie_id}", include_in_schema=False)
def get_movie(request: Request, movie_id: int, db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User | None, Depends(get_optional_current_user)]):
    result = db.execute(select(models.Movie).where(models.Movie.id == movie_id))
    movie = result.scalars().first()
    if movie:
        visible_bookings = [b for b in movie.bookings if current_user and (current_user.is_admin or b.user_id == current_user.id)]
        return templates.TemplateResponse(request, "movie.html", {"movie": movie, "title": movie.title, "current_user": current_user, "visible_bookings": visible_bookings, "show_times": SHOW_TIMES})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")

@app.get("/register", include_in_schema=False)
def get_register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})

def user_form_translator(
    username: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> UserCreate:
    return UserCreate(username=username, email=email, password=password)

@app.post("/register", include_in_schema=False)
def register_html(
    _: Annotated[None, Depends(validate_csrf)],
    user_data: Annotated[UserCreate, Depends(user_form_translator)],
    db: Annotated[Session, Depends(get_db)],
):
    result1 = db.execute(select(models.User).where(models.User.username == user_data.username))
    if result1.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
        
    result2 = db.execute(select(models.User).where(models.User.email == user_data.email))
    if result2.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email already registered")

    new_user = models.User(username=user_data.username, email=user_data.email, hashed_password=hash_password(user_data.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", include_in_schema=False)
def get_login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})

@app.post("/login", include_in_schema=False)
def login_html(
    _: Annotated[None, Depends(validate_csrf)],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    user = db.execute(select(models.User).where(models.User.username == username)).scalars().first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return response

@app.post("/logout", include_in_schema=False)
def logout(_: Annotated[None, Depends(validate_csrf)]):
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token", secure=settings.secure_cookies, httponly=True, samesite="lax")
    return response

@app.get("/movies/{movie_id}/edit", include_in_schema=False)
def get_movie_form(request: Request, movie_id: int, current_user: Annotated[models.User, Depends(get_admin_user)], db: Annotated[Session, Depends(get_db)]):
    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id)).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")
    return templates.TemplateResponse(request, "edit_movie.html", {"movie": movie, "current_user": current_user})

@app.post("/movies/{movie_id}/edit", include_in_schema=False)
def edit_movie_html(
    _: Annotated[None, Depends(validate_csrf)],
    current_user: Annotated[models.User, Depends(get_admin_user)],
    movie_id: int,
    title: Annotated[str, Form(min_length=1, max_length=20)],
    director: Annotated[str, Form(min_length=1, max_length=120)],
    seats_available: Annotated[int, Form(ge=0)],
    db: Annotated[Session, Depends(get_db)],
):
    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id).with_for_update()).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    movie.title = title
    movie.director = director
    if db.execute(select(models.Booking.id).where(models.Booking.movie_id == movie.id).limit(1)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Seat inventory cannot be changed after a booking exists")
    movie.seats_available = seats_available
    db.commit()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
@app.post("/movies/{movie_id}/delete", include_in_schema=False)
def delete_movie(_: Annotated[None, Depends(validate_csrf)], current_user: Annotated[models.User, Depends(get_admin_user)], movie_id: int, db: Annotated[Session, Depends(get_db)]):
    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id)).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    db.delete(movie)
    db.commit()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)     

@app.post("/movies/{movie_id}/book", include_in_schema=False)
def book_movie_html(
    _: Annotated[None, Depends(validate_csrf)],
    movie_id: int,
    show_time: Annotated[str, Form()],
    seats_booked: Annotated[int, Form()],
    current_user: Annotated[models.User, Depends(get_current_user_from_cookie)],
    db: Annotated[Session, Depends(get_db)],
):
    if show_time not in SHOW_TIMES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid showtime")
    if current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admins not allowed to book")

    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id).with_for_update()).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    if seats_booked < 1 or movie.seats_available < seats_booked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="not enough seats")
    
    movie.seats_available -= seats_booked

    booking = models.Booking(user_id=current_user.id, movie_id=movie.id, seats_booked=seats_booked, show_time=show_time)
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return RedirectResponse(url=f"/movies/{movie_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/my-bookings", include_in_schema=False)
def my_bookings_html(request: Request, current_user: Annotated[models.User, Depends(get_current_user_from_cookie)]):
    return templates.TemplateResponse(request, "my_bookings.html", {"bookings": current_user.bookings, "current_user": current_user})

@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = (
        exception.detail
        if exception.detail
        else "An error occurred. Please check your request and try again."
    )
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": message},
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exception.status_code,
            "title": exception.status_code,
            "message": message,
        },
        status_code=exception.status_code,
    )


@app.exception_handler(IntegrityError)
def database_conflict_handler(request: Request, exception: IntegrityError):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "The request conflicts with existing data"})
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": status.HTTP_409_CONFLICT, "title": "Conflict", "message": "The request conflicts with existing data. Please refresh and try again."},
        status_code=status.HTTP_409_CONFLICT,
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exception.errors()},
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Please check your input and try again.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


import os
from fastapi import FastAPI, Request, HTTPException, status, Depends, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import Annotated 
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session 

from schemas import UserCreate

import models
from database import Base, engine, get_db

from routers import movies, users, bookings

from auth import hash_password, verify_password, create_access_token, get_current_user, get_current_user_from_cookie, get_admin_user, get_optional_current_user

# Get the absolute path of the directory containing main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()
app.include_router(movies.router, prefix="/api/movies", tags=["movies"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["bookings"])

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/media", StaticFiles(directory ="media"), name = "media")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/health")
def health(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail = "Database unavailable"
        ) from exc
    
    return {"status" : "healthy"}




@app.get("/", include_in_schema = False)
def root(
    request: Request,
     db: Annotated[Session, Depends(get_db)],
      current_user: Annotated[models.User | None, Depends(get_optional_current_user)],
      page: int = 1):

    skip = (page-1) * 3
    result = db.execute(select(models.Movie).offset(skip).limit(3))

    movie_list = result.scalars().all()

    total_movies = db.execute(select(func.count(models.Movie.id))).scalar()

    total_pages = (total_movies + 2)//3
    return templates.TemplateResponse(request,
                "home.html",
                 {
                    "movies": movie_list,
                     "title": "Home",
                     "current_user": current_user,
                     "page": page,
                     "total_pages": total_pages
                     })

@app.get("/movies/new", include_in_schema = False)
def create_movie_form(request: Request):
    return templates.TemplateResponse(request, "create_movie.html", {"title":"Add Movie"})
    
@app.post("/movies/new", include_in_schema = False)
def create_movie_html(
    title: Annotated[str, Form()],
    director: Annotated[str, Form()],
    seats_available: Annotated[int, Form()],
    db: Annotated[Session, Depends(get_db)]
):
    new_movie = models.Movie(title=title, director=director, seats_available=seats_available)

    db.add(new_movie)
    db.commit()
    db.refresh(new_movie)

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/movies/{movie_id}", include_in_schema = False)
def get_movie(request: Request, movie_id : int, db: Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.Movie).where(models.Movie.id == movie_id))

    movie = result.scalars().first()

    if movie:
        return templates.TemplateResponse(request,"movie.html", {"movie": movie, "title": movie.title})
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")


@app.get("/register", include_in_schema=False)
def get_register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})

def user_form_translator(
    username: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()]
) -> UserCreate:
    return UserCreate(username=username, email=email, password=password)

@app.post("/register", include_in_schema=False)
def register_html(
    user_data: Annotated[UserCreate, Depends(user_form_translator)],
    db: Annotated[Session, Depends(get_db)]
):

   result1 = db.execute(select(models.User).where(models.User.username==user_data.username))
   if result1.scalars().first():
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    
   result2 = db.execute(select(models.User).where(models.User.email==user_data.email))
   if result2.scalars().first():
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email already registered")

   new_user = models.User(username=user_data.username, email=user_data.email, hashed_password=hash_password(user_data.password))

   db.add(new_user)
   db.commit()
   db.refresh(new_user)

   return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", include_in_schema=False)
def get_login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title" : "Login"})

@app.post("/login", include_in_schema=False)
def login_html(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)]
):
    user = db.execute(select(models.User).where(models.User.username==username)).scalars().first()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}  # Standard requirement for 401 token responses
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True
    )

    return response
    
@app.post("/logout", include_in_schema=False)
def logout():

     response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

     response.delete_cookie(key="access_token")

     return response


@app.get("/movies/{movie_id}/edit", include_in_schema=False)
def get_movie_form(request: Request, movie_id: int, db: Annotated[Session, Depends(get_db)]):
    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id)).scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")
    
    return templates.TemplateResponse(request,"edit_movie.html", {"movie":movie})

@app.post("/movies/{movie_id}/edit", include_in_schema=False)
def edit_movie_html(
    current_user: Annotated[models.User, Depends(get_admin_user)],
    movie_id: int,
    title: Annotated[str, Form()],
    director: Annotated[str, Form()],
    seats_available: Annotated[int, Form()],
    db: Annotated[Session, Depends(get_db)]
):
    
    movie = db.execute(select(models.Movie).where(models.Movie.id==movie_id)).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    movie.title = title
    movie.director = director
    movie.seats_available = seats_available

    db.commit()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
@app.post("/movies/{movie_id}/delete", include_in_schema=False)
def delete_movie(current_user: Annotated[models.User, Depends(get_admin_user)], movie_id: int, db: Annotated[Session, Depends(get_db)]):
    movie=db.execute(select(models.Movie).where(models.Movie.id==movie_id)).scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    db.delete(movie)
    db.commit()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)     

@app.post("/movies/{movie_id}/book", include_in_schema=False)
def book_movie_html(
    movie_id: int,
    show_time: Annotated[str, Form()],
    seats_booked: Annotated[int, Form()],
    current_user: Annotated[models.User, Depends(get_current_user_from_cookie)],
    db: Annotated[Session, Depends(get_db)]
):

    if current_user.is_admin == True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail = "admins not allowed to book")

    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id)).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    if movie.seats_available < seats_booked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="not enough seats")
    
    movie.seats_available -= seats_booked

    booking = models.Booking(user_id = current_user.id, movie_id = movie.id, seats_booked = seats_booked, show_time = show_time)

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return RedirectResponse(url=f"/movies/{movie_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/my-bookings", include_in_schema= False)
def my_bookings_html(request, current_user: Annotated[models.User, Depends(get_current_user_from_cookie)]):
    return templates.TemplateResponse(request, "my_bookings.html", {"bookings": current_user.bookings})


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

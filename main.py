import os
from fastapi import FastAPI, Request, HTTPException, status, Depends, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from typing import Annotated 
from sqlalchemy import select
from sqlalchemy.orm import Session 

import models
from database import Base, engine, get_db

from routers import movies, users, bookings

Base.metadata.create_all(bind=engine)

# Get the absolute path of the directory containing main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()
app.include_router(movies.router, prefix="/api/movies", tags=["movies"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["bookings"])

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/media", StaticFiles(directory ="media"), name = "media")

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", include_in_schema = False)
def root(request: Request, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Movie))

    movie_list = result.scalars().all()
    return templates.TemplateResponse(request,"home.html", {"movies": movie_list, "title": "Home"})

@app.get("/movies/{movie_id}", include_in_schema = False)
def get_movie(request: Request, movie_id : int, db: Annotated[Session, Depends(get_db)]):

    result = db.execute(select(models.Movie).where(models.Movie.id == movie_id))

    movie = result.scalars().first()

    if movie:
        return templates.TemplateResponse(request,"movie.html", {"movie": movie, "title": movie.title})
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")

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

@app.get("/movies/{movie_id}/edit", include_in_schema=False)
def get_movie_form(request: Request, movie_id: int, db: Annotated[Session, Depends(get_db)]):
    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id)).scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")
    
    return templates.TemplateResponse(request,"edit_movie.html", {"movie":movie})

@app.post("/movies/{movie_id}/edit", include_in_schema=False)
def edit_movie_html(
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
def delete_movie(movie_id: int, db: Annotated[Session, Depends(get_db)]):
    movie=db.execute(select(models.Movie).where(models.Movie.id==movie_id)).scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    db.delete(movie)
    db.commit()

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)     

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

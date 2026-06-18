from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Annotated

import models
from database import get_db
from schemas import MovieResponse, MovieCreate, MovieUpdate


router = APIRouter()

@router.get("", response_model = list[MovieResponse])
def get_movies_api(db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Movie))

    movies_list = result.scalars().all()

    return movies_list

@router.get("/{movie_id}", response_model = MovieResponse)
def get_movie_api(movie_id: int, db: Annotated[Session, Depends(get_db)]):
    
    result = db.execute(select(models.Movie).where(movie_id == models.Movie.id))

    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")

    return movie

@router.post(
    "", 
    response_model = MovieResponse, 
    status_code = status.HTTP_201_CREATED)
def create_movie_api(movie : MovieCreate, db: Annotated[Session, Depends(get_db)]):
    
    new_movie = models.Movie(title = movie.title, director = movie.director, seats_available = movie.seats_available)

    db.add(new_movie)
    db.commit()
    db.refresh(new_movie)

    return new_movie

@router.patch("/{movie_id}", response_model=MovieResponse)
def update_movie_api(movie_id: int, movie_data: MovieUpdate, db: Annotated[Session, Depends(get_db)]):
    movie = db.execute(select(models.Movie).where(models.Movie.id==movie_id)).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    update_data=movie_data.model_dump(exclude_unset=True)

    for key,value in update_data.items():
        setattr(movie,key,value)
    
    db.commit()
    db.refresh(movie)

    return movie

@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie_api(movie_id: int, db: Annotated[Session, Depends(get_db)]):

    movie=db.execute(select(models.Movie).where(movie_id==models.Movie.id)).scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    db.delete(movie)
    db.commit()


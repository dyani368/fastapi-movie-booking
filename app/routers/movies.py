from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from typing import Annotated
from datetime import datetime, timezone

from app import models
from app.database import get_db
from app.schemas import MovieResponse, MovieCreate, MovieUpdate, ScreeningCreate, ScreeningResponse
from app.auth import get_current_user
from app.inventory import as_utc, release_expired_holds

router = APIRouter()

@router.get("", response_model = list[MovieResponse])
def get_movies_api(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    available_only: bool = False,
):
    query = select(models.Movie)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(or_(models.Movie.title.ilike(term), models.Movie.director.ilike(term)))
    result = db.execute(query.order_by(models.Movie.title))
    movies_list = result.scalars().all()
    response = []
    now = datetime.now(timezone.utc)
    for movie in movies_list:
        screenings = db.execute(select(models.Screening).where(models.Screening.movie_id == movie.id, models.Screening.starts_at > now)).scalars().all()
        for screening in screenings:
            release_expired_holds(db, screening.id)
        available = sum(screening.seats_available for screening in screenings)
        if available_only and available <= 0:
            continue
        response.append(MovieResponse.model_validate(movie).model_copy(update={"seats_available": available}))
    db.commit()
    return response


@router.get("/{movie_id}/screenings", response_model=list[ScreeningResponse])
def get_screenings(movie_id: int, db: Annotated[Session, Depends(get_db)]):
    if not db.get(models.Movie, movie_id):
        raise HTTPException(status_code=404, detail="Movie not found")
    now = datetime.now(timezone.utc)
    screenings = db.execute(
        select(models.Screening).where(models.Screening.movie_id == movie_id, models.Screening.starts_at > now).order_by(models.Screening.starts_at)
    ).scalars().all()
    for screening in screenings:
        if as_utc(screening.starts_at) > now:
            release_expired_holds(db, screening.id)
    db.commit()
    return db.execute(select(models.Screening).where(models.Screening.movie_id == movie_id, models.Screening.starts_at > now).order_by(models.Screening.starts_at)).scalars().all()


@router.post("/{movie_id}/screenings", response_model=ScreeningResponse, status_code=201)
def create_screening(movie_id: int, payload: ScreeningCreate, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if payload.starts_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="starts_at must include a timezone offset")
    movie = db.execute(select(models.Movie).where(models.Movie.id == movie_id).with_for_update()).scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    screening = models.Screening(movie_id=movie.id, starts_at=payload.starts_at.astimezone(timezone.utc), auditorium=payload.auditorium, capacity=payload.capacity, price_paise=payload.price_paise)
    movie.seats_available += payload.capacity
    db.add(screening)
    db.commit()
    db.refresh(screening)
    return screening

@router.get("/{movie_id}", response_model = MovieResponse)
def get_movie_api(movie_id: int, db: Annotated[Session, Depends(get_db)]):
    
    result = db.execute(select(models.Movie).where(movie_id == models.Movie.id))

    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="movie not found")

    now = datetime.now(timezone.utc)
    screenings = db.execute(select(models.Screening).where(models.Screening.movie_id == movie.id, models.Screening.starts_at > now)).scalars().all()
    for screening in screenings:
        release_expired_holds(db, screening.id)
    db.commit()
    available = sum(screening.seats_available for screening in screenings)
    return MovieResponse.model_validate(movie).model_copy(update={"seats_available": available})

@router.post(
    "", 
    response_model = MovieResponse, 
    status_code = status.HTTP_201_CREATED)
def create_movie_api(movie : MovieCreate, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    new_movie = models.Movie(title = movie.title, director = movie.director, seats_available = movie.seats_available)

    db.add(new_movie)
    db.commit()
    db.refresh(new_movie)

    return new_movie


@router.patch("/{movie_id}", response_model=MovieResponse)
def update_movie_api(movie_id: int, movie_data: MovieUpdate, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    movie = db.execute(select(models.Movie).where(models.Movie.id==movie_id).with_for_update()).scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    update_data=movie_data.model_dump(exclude_unset=True, exclude_none=True)

    if "seats_available" in update_data:
        has_bookings = db.execute(select(models.Booking.id).join(models.Screening).where(models.Screening.movie_id == movie.id).limit(1)).first()
        if has_bookings:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Seat inventory cannot be changed after a booking exists")

    for key,value in update_data.items():
        setattr(movie,key,value)
    
    db.commit()
    db.refresh(movie)

    return movie

@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie_api(movie_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    movie=db.execute(select(models.Movie).where(movie_id==models.Movie.id)).scalars().first()

    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    has_bookings = db.execute(select(models.Booking.id).join(models.Screening).where(models.Screening.movie_id == movie.id).limit(1)).first()
    if has_bookings:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A movie with booking history cannot be deleted")

    db.delete(movie)
    db.commit()

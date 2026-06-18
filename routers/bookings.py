from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Annotated

import models
from database import get_db
from schemas import  BookingCreate, BookingResponse

router = APIRouter()

@router.get("", response_model = list[BookingResponse])
def get_bookings_api(db: Annotated[Session, Depends(get_db)]):

    result=db.execute(select(models.Booking))

    return result.scalars().all()


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking_api(booking_id: int, db: Annotated[Session, Depends(get_db)]):
    
    result = db.execute(select(models.Booking).where(models.Booking.id == booking_id))

    booking = result.scalars().first()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="booking not found")

    return booking

@router.post(
    "",
    response_model = BookingResponse,
    status_code = status.HTTP_201_CREATED
)
def create_booking(booking: BookingCreate, db: Annotated[Session, Depends(get_db)]):

    result1 = db.execute(select(models.User).where(models.User.id==booking.user_id))
    if not result1.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    result2 = db.execute(select(models.Movie).where(models.Movie.id==booking.movie_id))
    movie = result2.scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    if movie.seats_available < booking.seats_booked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="not enough seats available")
    
    movie.seats_available -= booking.seats_booked

    new_booking = models.Booking(user_id=booking.user_id, movie_id=booking.movie_id, seats_booked=booking.seats_booked, show_time=booking.show_time)

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    return new_booking

    
@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking_api(booking_id: int, db: Annotated[Session, Depends(get_db)]):

    result=db.execute(select(models.Booking).where(models.Booking.id==booking_id))
    booking = result.scalars().first()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    
    movie = booking.movie
    movie.seats_available += booking.seats_booked

    db.delete(booking)
    db.commit()
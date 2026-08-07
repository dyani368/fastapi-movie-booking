from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Annotated

from app import models
from app.database import get_db
from app.schemas import BookingCreate, BookingResponse
from app.auth import get_current_user

router = APIRouter()

@router.get("", response_model = list[BookingResponse])
def get_bookings_api(current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if current_user.is_admin:
        result = db.execute(select(models.Booking))
    else:
        result = db.execute(select(models.Booking).where(models.Booking.user_id == current_user.id))

    return result.scalars().all()

@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking_api(booking_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    
    result = db.execute(select(models.Booking).where(models.Booking.id == booking_id))

    booking = result.scalars().first()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="booking not found")

    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this booking")

    return booking

@router.post(
    "",
    response_model = BookingResponse,
    status_code = status.HTTP_201_CREATED
)
def create_booking(booking: BookingCreate, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):

    if current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot create bookings")

    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot create booking for another user")

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
def delete_booking_api(booking_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):

    result=db.execute(select(models.Booking).where(models.Booking.id==booking_id))
    booking = result.scalars().first()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this booking")
    
    movie = booking.movie
    movie.seats_available += booking.seats_booked

    db.delete(booking)
    db.commit()

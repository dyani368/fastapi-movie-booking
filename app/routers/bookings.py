from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Annotated

from app import models
from app.database import get_db
from app.schemas import BookingCreate, BookingResponse
from app.auth import get_current_user
from app.services.sms import send_booking_confirmation

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

    result2 = db.execute(select(models.Movie).where(models.Movie.id==booking.movie_id).with_for_update())
    movie = result2.scalars().first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    
    if booking.seats_booked < 1 or movie.seats_available < booking.seats_booked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="not enough seats available")
    
    movie.seats_available -= booking.seats_booked

    new_booking = models.Booking(user_id=current_user.id, movie_id=booking.movie_id, seats_booked=booking.seats_booked, show_time=booking.show_time)

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    send_booking_confirmation(db, new_booking, current_user, movie)
    
    return new_booking

@router.get("/{booking_id}/sms-status")
def get_sms_status(booking_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    booking = db.get(models.Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="booking not found")
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this booking")
    delivery = db.execute(select(models.SmsDelivery).where(models.SmsDelivery.booking_id == booking_id)).scalars().first()
    if not delivery:
        return {"booking_id": booking_id, "status": "not_sent"}
    return {"booking_id": booking_id, "status": delivery.status, "error_code": delivery.error_code, "updated_at": delivery.updated_at}

@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_booking_api(booking_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):

    result=db.execute(select(models.Booking).where(models.Booking.id==booking_id).with_for_update())
    booking = result.scalars().first()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this booking")
    
    movie = db.execute(select(models.Movie).where(models.Movie.id == booking.movie_id).with_for_update()).scalars().first()
    if movie is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Movie no longer exists")
    movie.seats_available += booking.seats_booked

    db.delete(booking)
    db.commit()

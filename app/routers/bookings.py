from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.config import settings
from app.inventory import as_utc, release_expired_holds
from app.schemas import BookingCreate, BookingResponse, PaymentOrderResponse
from app.services import create_razorpay_order, iso_expiry

router = APIRouter()


@router.get("", response_model=list[BookingResponse])
def get_bookings(current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    query = select(models.Booking).options(joinedload(models.Booking.screening).joinedload(models.Screening.movie))
    if not current_user.is_admin:
        query = query.where(models.Booking.user_id == current_user.id)
    bookings = db.execute(query.order_by(models.Booking.created_at.desc())).scalars().unique().all()
    for booking in bookings:
        if booking.status == "pending":
            release_expired_holds(db, booking.screening_id)
    db.commit()
    return bookings


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    booking = db.execute(
        select(models.Booking).options(joinedload(models.Booking.screening).joinedload(models.Screening.movie)).where(models.Booking.id == booking_id)
    ).scalars().first()
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(403, "Not authorized to view this booking")
    return booking


@router.post("", response_model=PaymentOrderResponse, status_code=201)
async def create_booking(
    payload: BookingCreate,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if current_user.is_admin:
        raise HTTPException(403, "Admin accounts cannot book tickets")
    if idempotency_key:
        if len(idempotency_key) > 120:
            raise HTTPException(422, "Idempotency-Key must be 120 characters or fewer")
        prior = db.execute(select(models.Booking).where(models.Booking.idempotency_key == idempotency_key)).scalars().first()
        if prior:
            if prior.user_id != current_user.id:
                raise HTTPException(409, "Idempotency key already used")
            if prior.status in {"pending", "confirmed"} and prior.razorpay_order_id:
                return PaymentOrderResponse(booking=prior, key_id=settings.razorpay_key_id or "", order_id=prior.razorpay_order_id, amount=prior.amount_paise, currency="INR")
            raise HTTPException(409, "A booking request with this key is already being processed")

    screening = db.execute(select(models.Screening).where(models.Screening.id == payload.screening_id).with_for_update()).scalars().first()
    if not screening:
        raise HTTPException(404, "Screening not found")
    if idempotency_key:
        prior = db.execute(select(models.Booking).where(models.Booking.idempotency_key == idempotency_key)).scalars().first()
        if prior:
            if prior.user_id != current_user.id:
                raise HTTPException(409, "Idempotency key already used")
            if prior.status in {"pending", "confirmed"} and prior.razorpay_order_id:
                return PaymentOrderResponse(booking=prior, key_id=settings.razorpay_key_id or "", order_id=prior.razorpay_order_id, amount=prior.amount_paise, currency="INR")
            raise HTTPException(409, "A booking request with this key is already being processed")
    release_expired_holds(db, screening.id)
    if as_utc(screening.starts_at) <= datetime.now(timezone.utc):
        db.commit()
        raise HTTPException(409, "This screening has already started")
    if screening.seats_available < payload.seats_booked:
        db.commit()
        raise HTTPException(409, "Not enough tickets remain for this screening")

    screening.seats_reserved += payload.seats_booked
    movie = db.execute(select(models.Movie).where(models.Movie.id == screening.movie_id).with_for_update()).scalar_one()
    movie.seats_available -= payload.seats_booked
    booking = models.Booking(
        user_id=current_user.id,
        movie_id=screening.movie_id,
        screening_id=screening.id,
        seats_booked=payload.seats_booked,
        show_time=as_utc(screening.starts_at).strftime("%I:%M %p"),
        amount_paise=screening.price_paise * payload.seats_booked,
        status="pending",
        created_at=datetime.now(timezone.utc),
        expires_at=iso_expiry(settings.booking_hold_minutes),
        idempotency_key=idempotency_key,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    try:
        order = await create_razorpay_order(booking.amount_paise, f"booking_{booking.id}")
    except Exception:
        screening = db.execute(select(models.Screening).where(models.Screening.id == booking.screening_id).with_for_update()).scalar_one()
        booking.status = "cancelled"
        booking.expires_at = None
        screening.seats_reserved -= booking.seats_booked
        movie = db.execute(select(models.Movie).where(models.Movie.id == screening.movie_id).with_for_update()).scalar_one()
        movie.seats_available += booking.seats_booked
        db.commit()
        raise
    booking.razorpay_order_id = order["id"]
    db.commit()
    db.refresh(booking)
    db.refresh(screening)
    booking.screening = screening
    return PaymentOrderResponse(booking=booking, key_id=order.get("key_id") or settings.razorpay_key_id or "", order_id=order["id"], amount=booking.amount_paise, currency="INR")


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(booking_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    booking = db.execute(select(models.Booking).where(models.Booking.id == booking_id).with_for_update()).scalars().first()
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(403, "Not authorized to cancel this booking")
    if booking.status != "pending":
        raise HTTPException(409, "Only an unpaid booking hold can be cancelled in this demo")
    screening = db.execute(select(models.Screening).where(models.Screening.id == booking.screening_id).with_for_update()).scalar_one()
    screening.seats_reserved -= booking.seats_booked
    movie = db.execute(select(models.Movie).where(models.Movie.id == screening.movie_id).with_for_update()).scalar_one()
    movie.seats_available += booking.seats_booked
    booking.status = "cancelled"
    booking.expires_at = None
    db.commit()

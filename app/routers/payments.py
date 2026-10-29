import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.services import parse_event, verify_checkout_signature, verify_webhook_signature

router = APIRouter()


def apply_payment(db: Session, booking: models.Booking, payment_id: str) -> None:
    if booking.status == "confirmed":
        if booking.razorpay_payment_id and booking.razorpay_payment_id != payment_id:
            raise HTTPException(409, "Booking already has a different successful payment")
        return
    if booking.status == "pending":
        booking.status = "confirmed"
        booking.expires_at = None
        booking.razorpay_payment_id = payment_id
        return
    # A late payment must never silently consume inventory that may have been resold.
    booking.status = "payment_review"
    booking.razorpay_payment_id = payment_id


@router.post("/verify")
def verify_payment(
    body: dict,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    order_id = body.get("razorpay_order_id")
    payment_id = body.get("razorpay_payment_id")
    signature = body.get("razorpay_signature")
    if not all(isinstance(value, str) and value for value in (order_id, payment_id, signature)):
        raise HTTPException(422, "Payment verification fields are required")
    booking = db.execute(select(models.Booking).where(models.Booking.razorpay_order_id == order_id).with_for_update()).scalars().first()
    if not booking or booking.user_id != current_user.id:
        raise HTTPException(404, "Payment order not found")
    if not verify_checkout_signature(order_id, payment_id, signature):
        raise HTTPException(400, "Payment signature is invalid")
    apply_payment(db, booking, payment_id)
    db.commit()
    return {"booking_id": booking.id, "status": booking.status}


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
    event_id: Annotated[str | None, Header(alias="X-Razorpay-Event-Id")] = None,
):
    body = await request.body()
    if not verify_webhook_signature(body, signature):
        raise HTTPException(400, "Invalid Razorpay webhook signature")
    payload = parse_event(body)
    event = payload.get("event", "unknown")
    dedupe_key = event_id or hashlib.sha256(body).hexdigest()
    if db.execute(select(models.ProcessedWebhook.id).where(models.ProcessedWebhook.provider_event_id == dedupe_key)).first():
        return {"status": "duplicate_ignored"}
    entity = (payload.get("payload", {}).get("payment", {}).get("entity") or {})
    order_id = entity.get("order_id")
    payment_id = entity.get("id")
    if event == "payment.captured" and order_id and payment_id:
        booking = db.execute(select(models.Booking).where(models.Booking.razorpay_order_id == order_id).with_for_update()).scalars().first()
        if booking:
            if entity.get("amount") == booking.amount_paise and entity.get("currency") == "INR":
                apply_payment(db, booking, payment_id)
            else:
                booking.status = "payment_review"
                booking.expires_at = None
                booking.razorpay_payment_id = payment_id
    elif event == "payment.failed" and order_id:
        booking = db.execute(select(models.Booking).where(models.Booking.razorpay_order_id == order_id).with_for_update()).scalars().first()
        if booking and booking.status == "pending":
            booking.status = "failed"
            booking.expires_at = None
            screening = db.execute(select(models.Screening).where(models.Screening.id == booking.screening_id).with_for_update()).scalar_one()
            screening.seats_reserved -= booking.seats_booked
            movie = db.execute(select(models.Movie).where(models.Movie.id == screening.movie_id).with_for_update()).scalar_one()
            movie.seats_available += booking.seats_booked
    db.add(models.ProcessedWebhook(provider_event_id=dedupe_key, event_type=event))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate_ignored"}
    return {"status": "processed"}

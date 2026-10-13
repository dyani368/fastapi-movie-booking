from __future__ import annotations

import base64
import hashlib
import hmac
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models
from app.config import settings

logger = logging.getLogger(__name__)
PLIVO_MESSAGE_URL = "https://api.plivo.com/v1/Account/{auth_id}/Message/"


def validate_plivo_signature(url: str, nonce: str, signature: str, auth_token: str) -> bool:
    """Validate Plivo's V2 signature for a webhook URL and nonce."""
    digest = hmac.new(auth_token.encode(), f"{url}{nonce}".encode(), hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)


def send_booking_confirmation(db: Session, booking: models.Booking, user: models.User, movie: models.Movie) -> None:
    """Send a best-effort confirmation; SMS failures never undo a committed booking."""
    if not user.phone_number:
        return
    token = settings.plivo_auth_token.get_secret_value() if settings.plivo_auth_token else None
    if not all((settings.plivo_auth_id, token, settings.plivo_source_number, settings.plivo_status_callback_url)):
        logger.info("SMS skipped: Plivo is not fully configured")
        return

    payload = {
        "src": settings.plivo_source_number,
        "dst": user.phone_number,
        "text": f"Booking confirmed: {movie.title}, {booking.seats_booked} seat(s), {booking.show_time}. Booking #{booking.id}.",
        "url": settings.plivo_status_callback_url,
        "method": "POST",
        "log": "false",
    }
    message_uuid: str | None = None
    status_value = "send_failed"
    error_code: str | None = None
    try:
        with httpx.Client(timeout=10.0, auth=(settings.plivo_auth_id, token)) as client:
            response = client.post(PLIVO_MESSAGE_URL.format(auth_id=settings.plivo_auth_id), data=payload)
        response.raise_for_status()
        body = response.json()
        uuids = body.get("message_uuid") or body.get("message_uuids") or []
        message_uuid = uuids[0] if uuids else None
        status_value = "queued"
        if not message_uuid:
            logger.warning("Plivo accepted request without a message UUID for booking %s", booking.id)
    except httpx.HTTPStatusError as exc:
        error_code = str(exc.response.status_code)
        logger.warning("Plivo SMS request failed with HTTP %s for booking %s", error_code, booking.id)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("Plivo SMS request failed (%s) for booking %s", type(exc).__name__, booking.id)

    try:
        delivery = None
        if message_uuid:
            delivery = db.execute(select(models.SmsDelivery).where(models.SmsDelivery.message_uuid == message_uuid)).scalars().first()
        if delivery is None:
            delivery = db.execute(select(models.SmsDelivery).where(models.SmsDelivery.booking_id == booking.id)).scalars().first()
        if delivery is None:
            delivery = models.SmsDelivery(booking_id=booking.id, status=status_value)
            db.add(delivery)
        delivery.message_uuid = message_uuid or delivery.message_uuid
        delivery.destination = user.phone_number
        # A callback can arrive before the send response is persisted; do not regress it.
        if delivery.status in ("pending", "send_failed"):
            delivery.status = status_value
            delivery.error_code = error_code
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Could not persist SMS delivery state for booking %s", booking.id)

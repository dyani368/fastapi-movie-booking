from __future__ import annotations

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.database import get_db
from app.services.sms import validate_plivo_signature

logger = logging.getLogger(__name__)
router = APIRouter()
VALID_STATUSES = {"queued", "sent", "failed", "delivered", "undelivered"}


@router.post("/plivo/sms")
async def plivo_sms_status(request: Request, db: Session = Depends(get_db)):
    token = settings.plivo_auth_token.get_secret_value() if settings.plivo_auth_token else None
    canonical_url = settings.plivo_status_callback_url
    signature = request.headers.get("X-Plivo-Signature-V2") or request.headers.get("X-Plivo-Signature-Ma-V2")
    nonce = request.headers.get("X-Plivo-Signature-V2-Nonce")
    if not token or not canonical_url or not signature or not nonce:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Plivo signature")
    if not validate_plivo_signature(canonical_url, nonce, signature, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Plivo signature")

    form = await request.form()
    message_uuid = str(form.get("MessageUUID", ""))
    event_status = str(form.get("Status", "")).lower()
    if not message_uuid or event_status not in VALID_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid Plivo delivery event")
    error_code = str(form.get("ErrorCode") or "") or None
    raw_sequence = form.get("Sequence")
    try:
        sequence = int(raw_sequence) if raw_sequence not in (None, "") else None
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid callback sequence")
    fingerprint = hashlib.sha256(json.dumps([message_uuid, event_status, error_code, sequence], separators=(",", ":")).encode()).hexdigest()

    delivery = db.execute(select(models.SmsDelivery).where(models.SmsDelivery.message_uuid == message_uuid).with_for_update()).scalars().first()
    if delivery:
        duplicate = (sequence is not None and delivery.last_sequence is not None and sequence <= delivery.last_sequence) or (sequence is None and fingerprint == delivery.last_event_hash)
        if duplicate:
            return {"ok": True, "duplicate": True}
    else:
        delivery = models.SmsDelivery(message_uuid=message_uuid)
        db.add(delivery)
    delivery.status = event_status
    delivery.error_code = error_code
    delivery.last_sequence = sequence if sequence is not None else delivery.last_sequence
    delivery.last_event_hash = fingerprint
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Two concurrent retries can race to insert the same event UUID; acknowledge it.
        logger.info("Duplicate Plivo callback acknowledged")
        return {"ok": True, "duplicate": True}
    return {"ok": True, "duplicate": False}

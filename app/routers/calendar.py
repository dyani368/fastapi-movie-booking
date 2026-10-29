import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.inventory import as_utc
from app.schemas import CalendarCallbackPayload

router = APIRouter()
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.get_secret_value().encode() + b"cinebook-calendar").digest())
    return Fernet(key)


@router.get("/connect")
def connect_calendar(current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth credentials are not configured")
    state = secrets.token_urlsafe(32)
    db.add(models.OAuthState(state=state, user_id=current_user.id, expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    db.commit()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": CALENDAR_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params), "state": state}


@router.post("/callback")
async def calendar_callback(
    payload: CalendarCallbackPayload,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth credentials are not configured")
    oauth_state = db.execute(select(models.OAuthState).where(models.OAuthState.state == payload.state).with_for_update()).scalars().first()
    if not oauth_state or as_utc(oauth_state.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(400, "OAuth state is invalid or expired")
    if oauth_state.user_id != current_user.id:
        raise HTTPException(403, "Calendar authorization was started by a different account")
    user_id = oauth_state.user_id
    db.delete(oauth_state)
    db.commit()
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post("https://oauth2.googleapis.com/token", data={
            "code": payload.code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        })
    if response.is_error:
        raise HTTPException(502, "Google authorization-code exchange failed")
    token = response.json()
    credential = db.execute(select(models.CalendarCredential).where(models.CalendarCredential.user_id == user_id).with_for_update()).scalars().first()
    refresh_token = token.get("refresh_token")
    if not refresh_token and credential:
        refresh_token = _fernet().decrypt(credential.refresh_token.encode()).decode()
    if not refresh_token:
        raise HTTPException(502, "Google did not issue a refresh token; reconnect and grant offline access")
    encrypted = _fernet().encrypt(refresh_token.encode()).decode()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 3600)))
    if credential:
        credential.refresh_token = encrypted
        credential.access_token = _fernet().encrypt(token["access_token"].encode()).decode() if token.get("access_token") else None
        credential.access_token_expires_at = expires_at
    else:
        encrypted_access = _fernet().encrypt(token["access_token"].encode()).decode() if token.get("access_token") else None
        db.add(models.CalendarCredential(user_id=user_id, refresh_token=encrypted, access_token=encrypted_access, access_token_expires_at=expires_at))
    db.commit()
    return {"connected": True}


async def access_token(db: Session, credential: models.CalendarCredential) -> str:
    now = datetime.now(timezone.utc)
    expiry = credential.access_token_expires_at
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if credential.access_token and expiry and expiry > now + timedelta(minutes=1):
        return _fernet().decrypt(credential.access_token.encode()).decode()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth credentials are not configured")
    refresh = _fernet().decrypt(credential.refresh_token.encode()).decode()
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        })
    if response.is_error:
        raise HTTPException(502, "Google access token refresh failed")
    token = response.json()
    credential.access_token = _fernet().encrypt(token["access_token"].encode()).decode()
    credential.access_token_expires_at = now + timedelta(seconds=int(token.get("expires_in", 3600)))
    db.commit()
    return token["access_token"]


@router.get("/status")
def calendar_status(current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    connected = db.execute(select(models.CalendarCredential.id).where(models.CalendarCredential.user_id == current_user.id)).first() is not None
    return {"connected": connected, "configured": bool(settings.google_client_id and settings.google_client_secret)}


@router.post("/bookings/{booking_id}/event")
async def add_booking_to_calendar(booking_id: int, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    booking = db.execute(
        select(models.Booking).options(selectinload(models.Booking.screening).selectinload(models.Screening.movie))
        .where(models.Booking.id == booking_id, models.Booking.user_id == current_user.id).with_for_update()
    ).scalars().first()
    if not booking:
        raise HTTPException(404, "Booking not found")
    if booking.status != "confirmed":
        raise HTTPException(409, "Only confirmed bookings can be added to Calendar")
    if booking.calendar_event_id:
        return {"event_id": booking.calendar_event_id, "created": False}
    credential = db.execute(select(models.CalendarCredential).where(models.CalendarCredential.user_id == current_user.id).with_for_update()).scalars().first()
    if not credential:
        raise HTTPException(409, "Connect your Google Calendar first")
    token = await access_token(db, credential)
    starts_at = booking.screening.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    event = {
        "id": "cb" + base64.b32hexencode(hashlib.sha256(f"cinebook-booking-{booking.id}".encode()).digest()).decode().lower().rstrip("="),
        "summary": f"{booking.screening.movie.title} — Cinebook",
        "description": f"Booking #{booking.id} · {booking.seats_booked} ticket(s) · {booking.screening.auditorium}",
        "start": {"dateTime": starts_at.isoformat()},
        "end": {"dateTime": (starts_at + timedelta(hours=3)).isoformat()},
    }
    event_url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(event_url, headers={"Authorization": f"Bearer {token}"}, json=event)
        if response.status_code == 409:
            response = await client.get(f"{event_url}/{event['id']}", headers={"Authorization": f"Bearer {token}"})
    if response.is_error:
        raise HTTPException(502, "Google Calendar could not create this event")
    booking.calendar_event_id = response.json()["id"]
    db.commit()
    return {"event_id": booking.calendar_event_id, "created": True}

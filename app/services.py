import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)


def require_razorpay() -> tuple[str, str]:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(status_code=503, detail="Razorpay test credentials are not configured")
    if "_test_" not in settings.razorpay_key_id:
        raise HTTPException(status_code=503, detail="Only Razorpay test-mode keys are accepted by this demo")
    return settings.razorpay_key_id, settings.razorpay_key_secret.get_secret_value()


async def create_razorpay_order(amount_paise: int, receipt: str) -> dict:
    key_id, secret = require_razorpay()
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                "https://api.razorpay.com/v1/orders",
                auth=(key_id, secret),
                json={"amount": amount_paise, "currency": "INR", "receipt": receipt},
            )
    except httpx.HTTPError as exc:
        logger.warning("Razorpay order request failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not reach Razorpay. Check the backend connection and retry.") from exc
    if response.is_error:
        try:
            provider_error = response.json().get("error", {})
            error_code = provider_error.get("code") if isinstance(provider_error, dict) else None
        except (ValueError, AttributeError):
            error_code = None
        logger.warning("Razorpay order rejected: HTTP %s, code=%s", response.status_code, error_code or "unavailable")
        raise HTTPException(status_code=502, detail="Razorpay could not create the payment order")
    return response.json()


def verify_checkout_signature(order_id: str, payment_id: str, signature: str) -> bool:
    _, secret = require_razorpay()
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    secret = settings.razorpay_webhook_secret
    if secret is None or not signature:
        return False
    expected = hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def tmdb_search(query: str) -> list[dict]:
    if settings.tmdb_api_key is None:
        raise HTTPException(status_code=503, detail="TMDB API key is not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://api.themoviedb.org/3/search/movie",
            params={"api_key": settings.tmdb_api_key.get_secret_value(), "query": query, "include_adult": "false"},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="TMDB movie search failed")
    return response.json().get("results", [])


async def tmdb_movie_details(tmdb_id: int) -> dict:
    if settings.tmdb_api_key is None:
        raise HTTPException(status_code=503, detail="TMDB API key is not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}",
            params={"api_key": settings.tmdb_api_key.get_secret_value(), "append_to_response": "credits"},
        )
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="TMDB movie was not found")
    if response.is_error:
        raise HTTPException(status_code=502, detail="TMDB movie details could not be loaded")
    return response.json()


def iso_expiry(minutes: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def parse_event(body: bytes) -> dict:
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook body")

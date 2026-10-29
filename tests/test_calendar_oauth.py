from datetime import datetime, timedelta, timezone

from pydantic import SecretStr

from app import models
from app.config import settings


def test_google_oauth_state_is_persisted_for_signed_in_user(as_member, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", SecretStr("client-secret"))
    response = as_member.get("/api/calendar/connect")

    assert response.status_code == 200
    data = response.json()
    assert "calendar.events" in data["authorization_url"]
    assert "access_type=offline" in data["authorization_url"]
    state = data["state"]
    with as_member.factory() as db:
        saved = db.get(models.OAuthState, state)
        assert saved.user_id == as_member.member_id


def test_google_oauth_callback_cannot_be_completed_by_another_user(client, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", SecretStr("client-secret"))
    state_value = "0123456789abcdefghijklmnopqrstuv"
    with client.factory() as db:
        state = models.OAuthState(state=state_value, user_id=client.member_id, expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        db.add(state)
        db.commit()
        other = models.User(username="calendar_other", email="calendar_other@example.com", hashed_password="unused")
        db.add(other)
        db.commit()
        db.refresh(other)
        client.active_user["user"] = other.id

    response = client.post("/api/calendar/callback", json={"state": state_value, "code": "google-auth-code"})
    assert response.status_code == 403

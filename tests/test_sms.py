import httpx
from pydantic import SecretStr

from app import models
from app.config import settings
from app.services import sms


def _configured(monkeypatch):
    monkeypatch.setattr(settings, "plivo_auth_id", "test-auth-id")
    monkeypatch.setattr(settings, "plivo_auth_token", SecretStr("test-auth-token"))
    monkeypatch.setattr(settings, "plivo_source_number", "+14155550100")
    monkeypatch.setattr(settings, "plivo_status_callback_url", "http://testserver/webhooks/plivo/sms")


def test_booking_sms_records_queued_delivery(as_member, monkeypatch):
    _configured(monkeypatch)

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["auth"] == ("test-auth-id", "test-auth-token")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, data):
            assert url.endswith("/Account/test-auth-id/Message/")
            assert data["dst"] == "+14155552671"
            assert data["url"] == settings.plivo_status_callback_url
            return httpx.Response(202, json={"message_uuid": ["message-123"]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(sms.httpx, "Client", FakeClient)
    with as_member.factory() as db:
        user = db.get(models.User, as_member.member_id)
        user.phone_number = "+14155552671"
        movie = db.get(models.Movie, as_member.movie_id)
        booking = models.Booking(user_id=user.id, movie_id=movie.id, seats_booked=1, show_time="7:00 PM")
        db.add(booking)
        db.commit()
        db.refresh(booking)
        sms.send_booking_confirmation(db, booking, user, movie)
        delivery = db.query(models.SmsDelivery).filter_by(booking_id=booking.id).one()
        assert delivery.status == "queued"
        assert delivery.message_uuid == "message-123"


def test_plivo_callback_signature_updates_delivery_and_ignores_replay(as_member, monkeypatch):
    _configured(monkeypatch)
    nonce = "callback-nonce"
    signature = sms.base64.b64encode(
        sms.hmac.new(b"test-auth-token", (settings.plivo_status_callback_url + nonce).encode(), sms.hashlib.sha256).digest()
    ).decode()
    headers = {
        "X-Plivo-Signature-V2": signature,
        "X-Plivo-Signature-V2-Nonce": nonce,
    }
    event = {"MessageUUID": "message-123", "Status": "delivered", "Sequence": "2"}

    response = as_member.post("/webhooks/plivo/sms", data=event, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "duplicate": False}
    replay = as_member.post("/webhooks/plivo/sms", data={**event, "Status": "failed"}, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True
    with as_member.factory() as db:
        delivery = db.query(models.SmsDelivery).filter_by(message_uuid="message-123").one()
        assert delivery.status == "delivered"
        assert delivery.last_sequence == 2


def test_plivo_callback_rejects_invalid_signature(as_member, monkeypatch):
    _configured(monkeypatch)
    response = as_member.post(
        "/webhooks/plivo/sms",
        data={"MessageUUID": "message-123", "Status": "delivered"},
        headers={"X-Plivo-Signature-V2": "invalid", "X-Plivo-Signature-V2-Nonce": "nonce"},
    )
    assert response.status_code == 403

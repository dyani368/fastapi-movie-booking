import hashlib
import hmac
import json

from app import models


def _booking(client, key):
    response = client.post(
        "/api/bookings",
        headers={"Idempotency-Key": key},
        json={"screening_id": client.screening_id, "seats_booked": 1},
    )
    assert response.status_code == 201
    return response.json()["booking"]


def test_checkout_signature_confirms_booking(as_member):
    booking = _booking(as_member, "checkout-verification")
    order_id = booking["razorpay_order_id"]
    payment_id = "pay_test_123"
    signature = hmac.new(b"checkout-secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()

    response = as_member.post("/api/payments/verify", json={
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "razorpay_signature": signature,
    })

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


def test_bad_checkout_signature_is_rejected(as_member):
    booking = _booking(as_member, "bad-checkout-signature")
    response = as_member.post("/api/payments/verify", json={
        "razorpay_order_id": booking["razorpay_order_id"],
        "razorpay_payment_id": "pay_test_forged",
        "razorpay_signature": "not-a-signature",
    })
    assert response.status_code == 400
    with as_member.factory() as db:
        assert db.get(models.Booking, booking["id"]).status == "pending"


def test_webhook_signature_and_duplicate_event_handling(as_member):
    booking = _booking(as_member, "webhook-dedupe")
    body = json.dumps({
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": "pay_webhook_123",
            "order_id": booking["razorpay_order_id"],
            "amount": booking["amount_paise"],
            "currency": "INR",
        }}},
    }, separators=(",", ":")).encode()
    signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": "evt_test_123"}

    first = as_member.post("/api/payments/webhook", content=body, headers=headers)
    second = as_member.post("/api/payments/webhook", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate_ignored"
    with as_member.factory() as db:
        assert db.get(models.Booking, booking["id"]).status == "confirmed"
        assert db.query(models.ProcessedWebhook).count() == 1


def test_webhook_rejects_invalid_signature(as_member):
    response = as_member.post(
        "/api/payments/webhook",
        content=b'{"event":"payment.captured"}',
        headers={"X-Razorpay-Signature": "invalid"},
    )
    assert response.status_code == 400

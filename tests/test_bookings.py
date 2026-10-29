from datetime import datetime, timedelta, timezone

from app import models


def _inventory(client):
    with client.factory() as db:
        return db.get(models.Screening, client.screening_id).seats_available


def _book(client, seats=1, key="test-booking-key"):
    return client.post(
        "/api/bookings",
        headers={"Idempotency-Key": key},
        json={"screening_id": client.screening_id, "seats_booked": seats},
    )


def test_booking_uses_authenticated_user_and_creates_payment_order(as_member):
    response = as_member.post(
        "/api/bookings",
        headers={"Idempotency-Key": "unique-create"},
        json={"user_id": 99999, "screening_id": as_member.screening_id, "seats_booked": 2},
    )

    assert response.status_code == 201
    assert response.json()["booking"]["user_id"] == as_member.member_id
    assert response.json()["booking"]["status"] == "pending"
    assert response.json()["amount"] == 50000
    assert _inventory(as_member) == 1


def test_booking_cannot_overdraw_screening_inventory(as_member):
    response = _book(as_member, seats=4)
    assert response.status_code == 409
    assert _inventory(as_member) == 3


def test_booking_rejects_zero_seats(as_member):
    response = _book(as_member, seats=0)
    assert response.status_code == 422
    assert _inventory(as_member) == 3


def test_cancel_restores_inventory_once(as_member):
    created = _book(as_member, seats=2, key="cancel-once")
    booking_id = created.json()["booking"]["id"]

    assert as_member.delete(f"/api/bookings/{booking_id}").status_code == 204
    assert _inventory(as_member) == 3
    assert as_member.delete(f"/api/bookings/{booking_id}").status_code == 409
    assert _inventory(as_member) == 3


def test_user_cannot_cancel_another_users_booking(client):
    client.active_user["user"] = client.member_id
    created = _book(client, key="other-user-booking")
    with client.factory() as db:
        other = models.User(username="other", email="other@example.com", hashed_password="unused")
        db.add(other)
        db.commit()
        db.refresh(other)
        client.active_user["user"] = other.id

    response = client.delete(f"/api/bookings/{created.json()['booking']['id']}")

    assert response.status_code == 403
    assert _inventory(client) == 2


def test_same_idempotency_key_replays_order_for_same_user(as_member):
    first = _book(as_member, key="stable-order")
    second = _book(as_member, key="stable-order")
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["order_id"] == first.json()["order_id"]
    assert _inventory(as_member) == 2


def test_pending_hold_expiration_releases_inventory(client):
    client.active_user["user"] = client.member_id
    created = _book(client, seats=2, key="expire-hold")
    booking_id = created.json()["booking"]["id"]
    with client.factory() as db:
        booking = db.get(models.Booking, booking_id)
        booking.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    response = client.get(f"/api/movies/{client.movie_id}/screenings")
    assert response.status_code == 200
    assert _inventory(client) == 3
    with client.factory() as db:
        assert db.get(models.Booking, booking_id).status == "expired"


def test_api_docs_are_available(client):
    assert client.get("/docs").status_code == 200


def test_public_movie_api_does_not_expose_customer_data(as_member):
    _book(as_member, key="private-user-check")
    response = as_member.get(f"/api/movies/{as_member.movie_id}")
    assert response.status_code == 200
    assert "member@example.com" not in response.text

from app import models


def _inventory(client):
    with client.factory() as db:
        return db.get(models.Movie, client.movie_id).seats_available


def test_booking_uses_authenticated_user_and_reduces_inventory(as_member):
    response = as_member.post(
        "/api/bookings",
        json={"user_id": 99999, "movie_id": as_member.movie_id, "seats_booked": 2, "show_time": "7:00 PM"},
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == as_member.member_id
    assert _inventory(as_member) == 1


def test_booking_cannot_overdraw_inventory(as_member):
    response = as_member.post(
        "/api/bookings",
        json={"movie_id": as_member.movie_id, "seats_booked": 4, "show_time": "7:00 PM"},
    )

    assert response.status_code == 400
    assert _inventory(as_member) == 3


def test_booking_rejects_zero_seats(as_member):
    response = as_member.post(
        "/api/bookings",
        json={"movie_id": as_member.movie_id, "seats_booked": 0, "show_time": "7:00 PM"},
    )

    assert response.status_code == 422
    assert _inventory(as_member) == 3


def test_cancel_restores_inventory_once(as_member):
    created = as_member.post(
        "/api/bookings",
        json={"movie_id": as_member.movie_id, "seats_booked": 2, "show_time": "7:00 PM"},
    )
    booking_id = created.json()["id"]

    assert as_member.delete(f"/api/bookings/{booking_id}").status_code == 204
    assert _inventory(as_member) == 3
    assert as_member.delete(f"/api/bookings/{booking_id}").status_code == 404
    assert _inventory(as_member) == 3


def test_user_cannot_cancel_another_users_booking(client):
    client.active_user["user"] = client.member_id
    created = client.post(
        "/api/bookings",
        json={"movie_id": client.movie_id, "seats_booked": 1, "show_time": "7:00 PM"},
    )
    with client.factory() as db:
        other = models.User(username="other", email="other@example.com", hashed_password="unused")
        db.add(other)
        db.commit()
        db.refresh(other)
        client.active_user["user"] = other.id

    response = client.delete(f"/api/bookings/{created.json()['id']}")

    assert response.status_code == 403
    assert _inventory(client) == 2


def test_html_catalog_mutations_require_an_admin(client):
    page = client.get("/movies/new")
    assert page.status_code == 401
    token = client.cookies["csrf_token"]

    response = client.post("/movies/new", data={
        "_csrf": token,
        "title": "Injected Film",
        "director": "Attacker",
        "seats_available": 20,
    })

    assert response.status_code == 401
    assert _inventory(client) == 3


def test_html_mutations_reject_missing_csrf_token(client):
    page = client.get("/movies/new")
    token = client.cookies["csrf_token"]

    response = client.post("/movies/new", data={
        "_csrf": "forged-token",
        "title": "Injected Film",
        "director": "Attacker",
        "seats_available": 20,
    })

    assert page.status_code == 401
    assert response.status_code == 403
    assert _inventory(client) == 3


def test_public_movie_page_does_not_reveal_customer_email(as_member):
    as_member.post(
        "/api/bookings",
        json={"movie_id": as_member.movie_id, "seats_booked": 1, "show_time": "7:00 PM"},
    )
    as_member.cookies.clear()

    page = as_member.get(f"/movies/{as_member.movie_id}")

    assert page.status_code == 200
    assert "member@example.com" not in page.text

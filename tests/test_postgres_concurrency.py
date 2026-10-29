import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import models
from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.config import settings


@pytest.mark.skipif(not os.getenv("MOVIE_BOOKING_TEST_DB_URL"), reason="PostgreSQL test database is not configured")
def test_only_one_concurrent_request_can_book_the_last_seat(monkeypatch):
    engine = create_engine(os.environ["MOVIE_BOOKING_TEST_DB_URL"], pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    suffix = uuid4().hex
    with factory() as db:
        user = models.User(username=f"race_{suffix}", email=f"{suffix}@example.com", hashed_password="unused")
        movie = models.Movie(title="Race Test", director="Test", seats_available=1)
        db.add_all([user, movie])
        db.commit()
        db.refresh(user)
        db.refresh(movie)
        screening = models.Screening(movie_id=movie.id, starts_at=datetime.now(timezone.utc) + timedelta(days=1), auditorium="Race Test", capacity=1, seats_reserved=0, price_paise=10000)
        db.add(screening)
        db.commit()
        db.refresh(screening)
        user_id, movie_id = user.id, movie.id
        screening_id = screening.id

    async def fake_create_order(amount_paise, receipt):
        return {"id": f"order_{receipt}", "key_id": "rzp_test_demo"}

    monkeypatch.setattr("app.routers.bookings.create_razorpay_order", fake_create_order)
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_demo")

    def override_db():
        with factory() as db:
            yield db

    def override_user():
        with factory() as db:
            yield db.get(models.User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    barrier = Barrier(2)

    def book_last_seat():
        with TestClient(app) as client:
            barrier.wait()
            return client.post("/api/bookings", json={
                "screening_id": screening_id,
                "seats_booked": 1,
            }, headers={"Idempotency-Key": f"race-{uuid4().hex}"}).status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: book_last_seat(), range(2)))
        assert sorted(results) == [201, 409]
        with factory() as db:
            movie = db.get(models.Movie, movie_id)
            booking_count = db.scalar(select(func.count()).select_from(models.Booking).where(models.Booking.screening_id == screening_id))
            assert movie.seats_available == 0
            assert booking_count == 1
    finally:
        app.dependency_overrides.clear()
        with factory() as db:
            db.query(models.Booking).filter(models.Booking.screening_id == screening_id).delete(synchronize_session=False)
            db.query(models.Screening).filter(models.Screening.id == screening_id).delete(synchronize_session=False)
            movie = db.get(models.Movie, movie_id)
            user = db.get(models.User, user_id)
            if movie:
                db.delete(movie)
            if user:
                db.delete(user)
            db.commit()
        engine.dispose()

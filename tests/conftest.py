import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pydantic import SecretStr

from app import models
from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    with factory() as db:
        member = models.User(username="member", email="member@example.com", hashed_password="unused")
        admin = models.User(username="admin", email="admin@example.com", hashed_password="unused", is_admin=True)
        movie = models.Movie(title="Test Film", director="Test Director", seats_available=3)
        db.add_all([member, admin, movie])
        db.commit()
        db.refresh(member)
        db.refresh(admin)
        db.refresh(movie)
        screening = models.Screening(movie_id=movie.id, starts_at=datetime.now(timezone.utc) + timedelta(days=1), auditorium="Test Screen", capacity=3, seats_reserved=0, price_paise=25000)
        db.add(screening)
        db.commit()
        db.refresh(screening)
        member_id, admin_id, movie_id = member.id, admin.id, movie.id
        screening_id = screening.id

    async def fake_create_order(amount_paise, receipt):
        return {"id": f"order_{receipt}", "key_id": settings.razorpay_key_id}

    monkeypatch.setattr("app.routers.bookings.create_razorpay_order", fake_create_order)
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_demo")
    monkeypatch.setattr(settings, "razorpay_key_secret", SecretStr("checkout-secret"))
    monkeypatch.setattr(settings, "razorpay_webhook_secret", SecretStr("webhook-secret"))

    active_user = {"user": None}

    def override_db():
        with factory() as db:
            yield db

    def override_user():
        with factory() as db:
            yield db.get(models.User, active_user["user"])

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as test_client:
        test_client.factory = factory
        test_client.active_user = active_user
        test_client.member_id = member_id
        test_client.admin_id = admin_id
        test_client.movie_id = movie_id
        test_client.screening_id = screening_id
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def as_member(client):
    client.active_user["user"] = client.member_id
    return client

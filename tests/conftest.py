import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.auth import get_current_user
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client():
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
        member_id, admin_id, movie_id = member.id, admin.id, movie.id

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
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def as_member(client):
    client.active_user["user"] = client.member_id
    return client

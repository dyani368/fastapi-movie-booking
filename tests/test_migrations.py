from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import settings


def test_fresh_database_migration_creates_schema(tmp_path):
    database_url = "sqlite:///" + (tmp_path / "fresh.sqlite3").as_posix()
    previous_url = settings.database_url
    settings.database_url = database_url
    try:
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
    finally:
        settings.database_url = previous_url

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert {"users", "movies", "booking", "alembic_version"} <= set(inspector.get_table_names())
    assert "ck_movies_seats_nonnegative" in {item["name"] for item in inspector.get_check_constraints("movies")}
    assert "ck_booking_seats_positive" in {item["name"] for item in inspector.get_check_constraints("booking")}
    engine.dispose()

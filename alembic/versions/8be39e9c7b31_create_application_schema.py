"""Create the application schema for fresh databases.

Revision ID: 8be39e9c7b31
Revises: 394980305d16
"""
from alembic import op
import sqlalchemy as sa

from app.models import Base

revision = "8be39e9c7b31"
down_revision = "394980305d16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)

    inspector = sa.inspect(bind)
    if "poster_file" not in {column["name"] for column in inspector.get_columns("movies")}:
        op.add_column("movies", sa.Column("poster_file", sa.String(), nullable=True))

    inspector = sa.inspect(bind)
    checks = {item["name"] for item in inspector.get_check_constraints("movies")}
    if "ck_movies_seats_nonnegative" not in checks:
        with op.batch_alter_table("movies") as batch:
            batch.create_check_constraint("ck_movies_seats_nonnegative", "seats_available >= 0")

    checks = {item["name"] for item in sa.inspect(bind).get_check_constraints("booking")}
    if "ck_booking_seats_positive" not in checks:
        with op.batch_alter_table("booking") as batch:
            batch.create_check_constraint("ck_booking_seats_positive", "seats_booked > 0")


def downgrade() -> None:
    # This compatibility migration may have adopted tables that predate Alembic.
    # Dropping any of them here could destroy customer data, so rollback is intentionally a no-op.
    pass

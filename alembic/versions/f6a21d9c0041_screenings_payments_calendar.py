"""Add dated screenings, booking payment state, and integration records."""

from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

from app import models

revision = "f6a21d9c0041"
down_revision = "e290aeb4301b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Create dependent tables before adding the screening reference to legacy bookings.
    for table in (models.Screening.__table__, models.ProcessedWebhook.__table__, models.OAuthState.__table__, models.CalendarCredential.__table__):
        if table.name not in tables:
            table.create(bind=bind)

    def add_columns(table_name: str, columns: list[sa.Column]) -> None:
        existing = {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table_name, column)

    add_columns("movies", [
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("release_date", sa.String(length=20), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("tmdb_poster_path", sa.String(length=500), nullable=True),
    ])
    add_columns("booking", [
        sa.Column("screening_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("razorpay_order_id", sa.String(length=100), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(length=100), nullable=True),
        sa.Column("calendar_event_id", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    ])

    # Preserve old movie-wide inventory and attach existing tickets to a dated screening.
    movies = bind.execute(sa.text("SELECT id, seats_available FROM movies")).mappings().all()
    now = datetime.now(timezone.utc)
    for movie in movies:
        bookings = bind.execute(sa.text("SELECT id, seats_booked FROM booking WHERE movie_id = :movie_id"), {"movie_id": movie["id"]}).mappings().all()
        if not bookings and movie["seats_available"] <= 0:
            continue
        capacity = max(int(movie["seats_available"] or 0) + sum(int(row["seats_booked"]) for row in bookings), 1)
        screening_id = bind.execute(
            sa.insert(models.Screening.__table__).values(
                movie_id=movie["id"], starts_at=now + timedelta(days=1), auditorium="Screen 1",
                capacity=capacity, seats_reserved=sum(int(row["seats_booked"]) for row in bookings),
                price_paise=25000, currency="INR",
            )
        ).inserted_primary_key[0]
        for booking in bookings:
            bind.execute(sa.text("UPDATE booking SET screening_id=:screening_id, status='confirmed', amount_paise=0, created_at=:created_at WHERE id=:id"), {
                "screening_id": screening_id, "created_at": now, "id": booking["id"],
            })

    bind.execute(sa.text("UPDATE booking SET status='confirmed' WHERE status IS NULL"))
    bind.execute(sa.text("UPDATE booking SET amount_paise=0 WHERE amount_paise IS NULL"))
    bind.execute(sa.text("UPDATE booking SET created_at=:created_at WHERE created_at IS NULL"), {"created_at": now})

    booking_columns = {column["name"]: column for column in sa.inspect(bind).get_columns("booking")}
    screening_fk = any(
        fk.get("referred_table") == "screenings" and fk.get("constrained_columns") == ["screening_id"]
        for fk in sa.inspect(bind).get_foreign_keys("booking")
    )
    checks = {item["name"] for item in sa.inspect(bind).get_check_constraints("booking")}
    if (
        booking_columns["screening_id"]["nullable"]
        or booking_columns["status"]["nullable"]
        or booking_columns["amount_paise"]["nullable"]
        or booking_columns["created_at"]["nullable"]
        or not screening_fk
        or "ck_booking_status_valid" not in checks
    ):
        with op.batch_alter_table("booking") as batch:
            if booking_columns["screening_id"]["nullable"]:
                batch.alter_column("screening_id", existing_type=sa.Integer(), nullable=False)
            if booking_columns["status"]["nullable"]:
                batch.alter_column("status", existing_type=sa.String(length=20), nullable=False, server_default="pending")
            if booking_columns["amount_paise"]["nullable"]:
                batch.alter_column("amount_paise", existing_type=sa.Integer(), nullable=False, server_default="0")
            if booking_columns["created_at"]["nullable"]:
                batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            if not screening_fk:
                batch.create_foreign_key("fk_booking_screening_id_screenings", "screenings", ["screening_id"], ["id"])
            if "ck_booking_status_valid" not in checks:
                batch.create_check_constraint("ck_booking_status_valid", "status IN ('pending', 'confirmed', 'cancelled', 'expired', 'failed', 'payment_review')")

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("movies")}
    movie_uniques = {tuple(item["column_names"]) for item in inspector.get_unique_constraints("movies")}
    if "ix_movies_tmdb_id" not in indexes and ("tmdb_id",) not in movie_uniques:
        op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("booking")}
    for name, column in (("ix_booking_screening_id", "screening_id"), ("ix_booking_status", "status")):
        if name not in indexes:
            op.create_index(name, "booking", [column])
    inspector = sa.inspect(bind)
    unique_columns = {tuple(item["column_names"]) for item in inspector.get_unique_constraints("booking")}
    unique_columns.update(tuple(index["column_names"]) for index in inspector.get_indexes("booking") if index.get("unique"))
    for name, column in (
        ("uq_booking_idempotency_key", "idempotency_key"),
        ("uq_booking_razorpay_order_id", "razorpay_order_id"),
        ("uq_booking_razorpay_payment_id", "razorpay_payment_id"),
    ):
        if (column,) not in unique_columns:
            op.create_index(name, "booking", [column], unique=True)


def downgrade() -> None:
    # Preserve bookings, webhook receipts, and OAuth credentials when rolling back.
    pass

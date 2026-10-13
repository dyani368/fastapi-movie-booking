"""Add optional user phone numbers and SMS delivery tracking."""

from alembic import op
import sqlalchemy as sa

from app.models import Base

revision = "c41f0f63a2e1"
down_revision = "8be39e9c7b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "phone_number" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("phone_number", sa.String(), nullable=True))
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sms_deliveries" in inspector.get_table_names():
        op.drop_table("sms_deliveries")
    if "phone_number" in {column["name"] for column in sa.inspect(bind).get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("phone_number")

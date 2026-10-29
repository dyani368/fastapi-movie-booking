"""Remove unused SMS provider schema."""

from alembic import op
import sqlalchemy as sa

revision = "e290aeb4301b"
down_revision = "c41f0f63a2e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sms_deliveries" in inspector.get_table_names():
        op.drop_table("sms_deliveries")
    if "phone_number" in {column["name"] for column in sa.inspect(bind).get_columns("users")}:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("phone_number")


def downgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(), nullable=True))

"""Persist structured citations on assistant messages."""
from alembic import op
import sqlalchemy as sa

revision = "20261031_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("messages")}
    if "citations_json" in columns:
        return
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("messages")}
    if "citations_json" not in columns:
        return
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("citations_json")

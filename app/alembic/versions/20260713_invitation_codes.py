"""add invitation codes

Revision ID: 20260713_invitation_codes
Revises: 20260708_student_practice
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_invitation_codes"
down_revision = "20260708_student_practice"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invitation_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("used_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
    )
    op.create_index("ix_invitation_codes_code", "invitation_codes", ["code"], unique=True)
    op.create_index("ix_invitation_codes_created_by", "invitation_codes", ["created_by"])
    op.create_index("ix_invitation_codes_used_by", "invitation_codes", ["used_by"])


def downgrade():
    op.drop_index("ix_invitation_codes_used_by", table_name="invitation_codes")
    op.drop_index("ix_invitation_codes_created_by", table_name="invitation_codes")
    op.drop_index("ix_invitation_codes_code", table_name="invitation_codes")
    op.drop_table("invitation_codes")

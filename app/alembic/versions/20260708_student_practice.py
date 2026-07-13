"""student practice and document generation

Revision ID: 20260708_student_practice
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "20260708_student_practice"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(20), nullable=False, server_default="student"))
    with op.batch_alter_table("question_banks") as batch:
        batch.add_column(sa.Column("source_type", sa.String(20), nullable=False, server_default="document"))
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="ready"))
    with op.batch_alter_table("questions") as batch:
        batch.add_column(sa.Column("source_type", sa.String(20), nullable=False, server_default="manual"))
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(255), nullable=False, unique=True),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("parse_status", sa.String(20), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("source_documents.id"), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("single_count", sa.Integer(), nullable=False),
        sa.Column("multiple_count", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.Text()),
        sa.Column("draft_questions", sa.JSON()),
        sa.Column("bank_id", sa.Integer(), sa.ForeignKey("question_banks.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_quiz_items_question_submitted", "quiz_items", ["question_id", "submitted_at"])
    op.create_unique_constraint("ux_quiz_items_session_question", "quiz_items", ["session_id", "question_id"])


def downgrade():
    op.drop_constraint("ux_quiz_items_session_question", "quiz_items", type_="unique")
    op.drop_index("ix_quiz_items_question_submitted", table_name="quiz_items")
    op.drop_table("generation_jobs")
    op.drop_table("source_documents")
    with op.batch_alter_table("questions") as batch:
        batch.drop_column("source_type")
    with op.batch_alter_table("question_banks") as batch:
        batch.drop_column("status")
        batch.drop_column("source_type")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("role")

"""add agent tables

Revision ID: 202606220003
Revises: 202606220002
Create Date: 2026-06-22 00:00:03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202606220003"
down_revision: Union[str, None] = "202606220002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. generated_documents
    op.create_table(
        "generated_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_documents_id"), "generated_documents", ["id"], unique=False)
    op.create_index(op.f("ix_generated_documents_repository_id"), "generated_documents", ["repository_id"], unique=False)

    # 2. generated_pr_reviews
    op.create_table(
        "generated_pr_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("review", sa.Text(), nullable=False),
        sa.Column("issues_found", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_pr_reviews_id"), "generated_pr_reviews", ["id"], unique=False)
    op.create_index(op.f("ix_generated_pr_reviews_repository_id"), "generated_pr_reviews", ["repository_id"], unique=False)

    # 3. generated_test_files
    op.create_table(
        "generated_test_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("tests", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_test_files_id"), "generated_test_files", ["id"], unique=False)
    op.create_index(op.f("ix_generated_test_files_repository_id"), "generated_test_files", ["repository_id"], unique=False)


def downgrade() -> None:
    # 3. generated_test_files
    op.drop_index(op.f("ix_generated_test_files_repository_id"), table_name="generated_test_files")
    op.drop_index(op.f("ix_generated_test_files_id"), table_name="generated_test_files")
    op.drop_table("generated_test_files")

    # 2. generated_pr_reviews
    op.drop_index(op.f("ix_generated_pr_reviews_repository_id"), table_name="generated_pr_reviews")
    op.drop_index(op.f("ix_generated_pr_reviews_id"), table_name="generated_pr_reviews")
    op.drop_table("generated_pr_reviews")

    # 1. generated_documents
    op.drop_index(op.f("ix_generated_documents_repository_id"), table_name="generated_documents")
    op.drop_index(op.f("ix_generated_documents_id"), table_name="generated_documents")
    op.drop_table("generated_documents")

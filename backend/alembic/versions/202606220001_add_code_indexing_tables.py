"""add code indexing tables

Revision ID: 202606220001
Revises: 202606180001
Create Date: 2026-06-22 00:00:01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "202606220001"
down_revision: Union[str, None] = "202606180001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "code_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "file_path", name="uq_code_file_repository_path"),
    )
    op.create_index(op.f("ix_code_files_id"), "code_files", ["id"], unique=False)
    op.create_index(op.f("ix_code_files_repository_id"), "code_files", ["repository_id"], unique=False)

    op.create_table(
        "code_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["code_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "chunk_index", name="uq_code_chunk_file_index"),
    )
    op.create_index(op.f("ix_code_chunks_file_id"), "code_chunks", ["file_id"], unique=False)
    op.create_index(op.f("ix_code_chunks_id"), "code_chunks", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_code_chunks_id"), table_name="code_chunks")
    op.drop_index(op.f("ix_code_chunks_file_id"), table_name="code_chunks")
    op.drop_table("code_chunks")
    op.drop_index(op.f("ix_code_files_repository_id"), table_name="code_files")
    op.drop_index(op.f("ix_code_files_id"), table_name="code_files")
    op.drop_table("code_files")

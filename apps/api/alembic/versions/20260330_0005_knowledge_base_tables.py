"""Add knowledge base tables for RAG (kb_documents, kb_chunks with pgvector).

Revision ID: 20260330_0005
Revises: 20260323_0004
Create Date: 2026-03-30 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR, JSONB
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "20260330_0005"
down_revision: str | None = "20260323_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- kb_documents ---
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),

        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),

        sa.Column("content_hash", sa.String(64), nullable=False),

        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),

        sa.Column(
            "chunk_count",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),

        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'processing'"),
        ),

        sa.Column("error_message", sa.Text, nullable=True),

        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),

        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),

        sa.CheckConstraint(
            "status IN ('processing', 'ready', 'error')",
            name="ck_kb_documents_status",
        ),

        sa.UniqueConstraint(
            "content_hash",
            name="uq_kb_documents_content_hash",
        ),
    )

    op.create_index(
        "idx_kb_documents_status",
        "kb_documents",
        ["status"],
    )

    # --- kb_chunks ---
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "document_id",
            sa.BigInteger,
            sa.ForeignKey("kb_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("heading_path", sa.String(1000), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("content_tsv", TSVECTOR, nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column(
            "metadata",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_kb_chunks_document_chunk",
        ),
    )

    op.create_index("idx_kb_chunks_document_id", "kb_chunks", ["document_id"])

    op.create_index(
        "idx_kb_chunks_content_tsv",
        "kb_chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )

    op.create_index(
        "idx_kb_chunks_embedding",
        "kb_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 128},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.execute("DROP EXTENSION IF EXISTS vector")

"""Create the frozen initial baseline schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _json_type() -> sa.JSON:
    """Return the baseline's portable JSON type without importing application models."""
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _entity_columns() -> tuple[sa.Column, sa.Column, sa.Column]:
    """Return the fixed columns shared by the baseline ORM entities."""
    return (
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_entity_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "oauth_accounts",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("access_token_enc", sa.String(length=4096), nullable=True),
        sa.Column("refresh_token_enc", sa.String(length=4096), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_account_id",
            name="uq_oauth_provider_account",
        ),
    )
    op.create_index(
        "ix_oauth_accounts_user_id",
        "oauth_accounts",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "personas",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personas_user_id", "personas", ["user_id"], unique=False)

    op.create_table(
        "prompt_templates",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prompt_templates_user_id",
        "prompt_templates",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_prompt_templates_user_scope",
        "prompt_templates",
        ["user_id", "scope"],
        unique=False,
    )

    op.create_table(
        "provider_credentials",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("api_key_enc", sa.String(length=4096), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_credentials_user_id",
        "provider_credentials",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "worlds",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("era", sa.String(length=200), nullable=False),
        sa.Column("races", _json_type(), nullable=False),
        sa.Column("nations", _json_type(), nullable=False),
        sa.Column("taboos", _json_type(), nullable=False),
        *_entity_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worlds_user_id", "worlds", ["user_id"], unique=False)

    op.create_table(
        "characters",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("world_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("greeting", sa.Text(), nullable=False),
        sa.Column("speech_style", sa.Text(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False),
        sa.Column("tags", _json_type(), nullable=False),
        *_entity_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_characters_user_id", "characters", ["user_id"], unique=False)
    op.create_index("ix_characters_world_id", "characters", ["world_id"], unique=False)

    op.create_table(
        "glossary_terms",
        sa.Column("world_id", sa.String(length=36), nullable=False),
        sa.Column("term", sa.String(length=200), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_glossary_terms_world_id",
        "glossary_terms",
        ["world_id"],
        unique=False,
    )

    op.create_table(
        "lorebooks",
        sa.Column("world_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lorebooks_world_id", "lorebooks", ["world_id"], unique=False)

    op.create_table(
        "model_configs",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("credential_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["provider_credentials.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_model_configs_is_default",
        "model_configs",
        ["is_default"],
        unique=False,
    )
    op.create_index(
        "ix_model_configs_user_default",
        "model_configs",
        ["user_id", "is_default"],
        unique=False,
    )
    op.create_index(
        "ix_model_configs_user_id",
        "model_configs",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "works",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("world_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("synopsis", sa.Text(), nullable=False),
        sa.Column("genre", sa.String(length=120), nullable=False),
        sa.Column("tags", _json_type(), nullable=False),
        *_entity_columns(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_works_user_id", "works", ["user_id"], unique=False)
    op.create_index("ix_works_world_id", "works", ["world_id"], unique=False)

    op.create_table(
        "chapters",
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content_doc", _json_type(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "index", name="uq_chapter_work_index"),
    )
    op.create_index("ix_chapters_user_id", "chapters", ["user_id"], unique=False)
    op.create_index("ix_chapters_work_id", "chapters", ["work_id"], unique=False)

    op.create_table(
        "chat_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("persona_id", sa.String(length=36), nullable=True),
        sa.Column("model_config_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_config_id"],
            ["model_configs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chat_sessions_character_id",
        "chat_sessions",
        ["character_id"],
        unique=False,
    )
    op.create_index(
        "ix_chat_sessions_user_id",
        "chat_sessions",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "lore_entries",
        sa.Column("lorebook_id", sa.String(length=36), nullable=False),
        sa.Column("keywords", _json_type(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("scan_depth", sa.Integer(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(
            ["lorebook_id"],
            ["lorebooks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_lore_entries_enabled",
        "lore_entries",
        ["enabled"],
        unique=False,
    )
    op.create_index(
        "ix_lore_entries_lorebook_id",
        "lore_entries",
        ["lorebook_id"],
        unique=False,
    )

    op.create_table(
        "work_characters",
        sa.Column("work_id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("role_in_work", sa.String(length=60), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["work_id"], ["works.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id", "character_id", name="uq_work_character"),
    )
    op.create_index(
        "ix_work_characters_character_id",
        "work_characters",
        ["character_id"],
        unique=False,
    )
    op.create_index(
        "ix_work_characters_work_id",
        "work_characters",
        ["work_id"],
        unique=False,
    )

    op.create_table(
        "memories",
        sa.Column("chat_session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cover_up_to_message_id", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(
            ["chat_session_id"],
            ["chat_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memories_chat_session_id",
        "memories",
        ["chat_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_memories_session",
        "memories",
        ["chat_session_id"],
        unique=False,
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("chat_session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("parent_message_id", sa.String(length=36), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("meta", _json_type(), nullable=False),
        *_entity_columns(),
        sa.ForeignKeyConstraint(
            ["chat_session_id"],
            ["chat_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_message_id"],
            ["messages.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_chat_session_id",
        "messages",
        ["chat_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_messages_session_created",
        "messages",
        ["chat_session_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_messages_user_id", "messages", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("memories")
    op.drop_table("work_characters")
    op.drop_table("lore_entries")
    op.drop_table("chat_sessions")
    op.drop_table("chapters")
    op.drop_table("works")
    op.drop_table("model_configs")
    op.drop_table("lorebooks")
    op.drop_table("glossary_terms")
    op.drop_table("characters")
    op.drop_table("worlds")
    op.drop_table("provider_credentials")
    op.drop_table("prompt_templates")
    op.drop_table("personas")
    op.drop_table("oauth_accounts")
    op.drop_table("users")

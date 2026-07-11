"""Alembic baseline reproducibility tests."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = BACKEND_DIR / "app" / "db" / "migrations"
INITIAL_REVISION = MIGRATIONS_DIR / "versions" / "0001_initial.py"
ROOT_DB = BACKEND_DIR / "data" / "app.db"

BASELINE_TABLES = {
    "chapters",
    "characters",
    "chat_sessions",
    "glossary_terms",
    "lore_entries",
    "lorebooks",
    "memories",
    "messages",
    "model_configs",
    "oauth_accounts",
    "personas",
    "prompt_templates",
    "provider_credentials",
    "users",
    "work_characters",
    "works",
    "worlds",
}
HEAD_TABLES = BASELINE_TABLES | {"entries", "alembic_version"}


def _file_fingerprint(path: Path) -> tuple[int, int, str] | None:
    if not path.exists():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def _index_map(inspector, table_name: str) -> dict[str, dict]:  # noqa: ANN001
    return {index["name"]: index for index in inspector.get_indexes(table_name)}


def _unique_map(inspector, table_name: str) -> dict[str, set[str]]:  # noqa: ANN001
    return {
        constraint["name"]: set(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
    }


def _foreign_key_map(inspector, table_name: str) -> dict[tuple[str, ...], dict]:  # noqa: ANN001
    return {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspector.get_foreign_keys(table_name)
    }


def test_initial_revision_is_static() -> None:
    source = INITIAL_REVISION.read_text(encoding="utf-8")
    tree = ast.parse(source)

    application_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            application_imports.extend(
                name.name for name in node.names if name.name == "app" or name.name.startswith("app.")
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "app" or node.module.startswith("app."):
                application_imports.append(node.module)

    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not application_imports
    assert "Base.metadata" not in source
    assert "create_all" not in called_attributes
    assert "drop_all" not in called_attributes

    assignments = {
        target.id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}
    }
    assert assignments == {"revision": "0001_initial", "down_revision": None}


def test_initial_revision_compiles_for_postgresql(monkeypatch, capsys) -> None:  # noqa: ANN001
    from app.config import get_settings

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://migration:migration@localhost/migration",
    )
    get_settings.cache_clear()

    try:
        command.upgrade(_alembic_config(), "head", sql=True)
        sql = capsys.readouterr().out
        assert "CREATE TABLE users" in sql
        assert "CREATE TABLE messages" in sql
        assert "CREATE TABLE entries" in sql
        assert "JSONB" in sql
        assert "DROP TABLE" not in sql
    finally:
        get_settings.cache_clear()


def test_migration_round_trip_uses_isolated_sqlite_db(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    from app.config import get_settings

    migration_db = (tmp_path / "migration.db").resolve()
    assert migration_db != ROOT_DB.resolve()

    database_url = f"sqlite+aiosqlite:///{migration_db.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    assert get_settings().DATABASE_URL == database_url

    root_db_before = _file_fingerprint(ROOT_DB)
    config = _alembic_config()

    try:
        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{migration_db.as_posix()}")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == HEAD_TABLES

        oauth_uniques = _unique_map(inspector, "oauth_accounts")
        chapter_uniques = _unique_map(inspector, "chapters")
        work_character_uniques = _unique_map(inspector, "work_characters")
        assert oauth_uniques["uq_oauth_provider_account"] == {
            "provider",
            "provider_account_id",
        }
        assert chapter_uniques["uq_chapter_work_index"] == {"work_id", "index"}
        assert work_character_uniques["uq_work_character"] == {
            "work_id",
            "character_id",
        }

        user_indexes = _index_map(inspector, "users")
        message_indexes = _index_map(inspector, "messages")
        model_config_indexes = _index_map(inspector, "model_configs")
        prompt_indexes = _index_map(inspector, "prompt_templates")
        assert user_indexes["ix_users_email"]["unique"] == 1
        assert user_indexes["ix_users_email"]["column_names"] == ["email"]
        assert message_indexes["ix_messages_session_created"]["column_names"] == [
            "chat_session_id",
            "created_at",
        ]
        assert model_config_indexes["ix_model_configs_user_default"]["column_names"] == [
            "user_id",
            "is_default",
        ]
        assert prompt_indexes["ix_prompt_templates_user_scope"]["column_names"] == [
            "user_id",
            "scope",
        ]

        character_foreign_keys = _foreign_key_map(inspector, "characters")
        session_foreign_keys = _foreign_key_map(inspector, "chat_sessions")
        message_foreign_keys = _foreign_key_map(inspector, "messages")
        assert character_foreign_keys[("user_id",)]["referred_table"] == "users"
        assert character_foreign_keys[("user_id",)]["options"]["ondelete"] == "CASCADE"
        assert character_foreign_keys[("world_id",)]["referred_table"] == "worlds"
        assert character_foreign_keys[("world_id",)]["options"]["ondelete"] == "SET NULL"
        assert session_foreign_keys[("model_config_id",)]["referred_table"] == "model_configs"
        assert session_foreign_keys[("model_config_id",)]["options"]["ondelete"] == "SET NULL"
        assert message_foreign_keys[("parent_message_id",)]["referred_table"] == "messages"
        assert message_foreign_keys[("parent_message_id",)]["options"]["ondelete"] == "SET NULL"

        entry_columns = {column["name"] for column in inspector.get_columns("entries")}
        assert {
            "id",
            "user_id",
            "scope_kind",
            "scope_id",
            "subject_type",
            "subject_id",
            "subject_data",
            "type",
            "status",
            "content",
            "data",
            "provenance",
            "confidence",
            "priority",
            "created_at_chapter_id",
            "superseded_by_entry_id",
            "accepted_at",
            "rejected_at",
            "superseded_at",
            "created_at",
            "updated_at",
        }.issubset(entry_columns)
        entry_indexes = _index_map(inspector, "entries")
        assert entry_indexes["ix_entries_owner_scope"]["column_names"] == [
            "user_id",
            "scope_kind",
            "scope_id",
        ]
        assert entry_indexes["ix_entries_owner_status_type"]["column_names"] == [
            "user_id",
            "status",
            "type",
        ]
        assert entry_indexes["ix_entries_owner_type"]["column_names"] == [
            "user_id",
            "type",
        ]
        assert entry_indexes["ix_entries_owner_subject"]["column_names"] == [
            "user_id",
            "subject_type",
            "subject_id",
        ]
        entry_checks = {
            constraint["name"] for constraint in inspector.get_check_constraints("entries")
        }
        assert {
            "ck_entries_scope_kind",
            "ck_entries_type",
            "ck_entries_status",
            "ck_entries_content_nonempty",
            "ck_entries_confidence",
            "ck_entries_priority",
            "ck_entries_not_self_superseded",
        }.issubset(entry_checks)
        entry_foreign_keys = _foreign_key_map(inspector, "entries")
        assert entry_foreign_keys[("user_id",)]["referred_table"] == "users"
        assert entry_foreign_keys[("user_id",)]["options"]["ondelete"] == "CASCADE"
        assert entry_foreign_keys[("created_at_chapter_id",)]["referred_table"] == "chapters"
        assert entry_foreign_keys[("created_at_chapter_id",)]["options"]["ondelete"] == "SET NULL"
        assert entry_foreign_keys[("superseded_by_entry_id",)]["referred_table"] == "entries"
        assert entry_foreign_keys[("superseded_by_entry_id",)]["options"]["ondelete"] == "RESTRICT"
        engine.dispose()

        command.downgrade(config, "0001_initial")
        engine = create_engine(f"sqlite:///{migration_db.as_posix()}")
        assert set(inspect(engine).get_table_names()) == BASELINE_TABLES | {"alembic_version"}
        engine.dispose()

        command.downgrade(config, "base")
        engine = create_engine(f"sqlite:///{migration_db.as_posix()}")
        assert BASELINE_TABLES.isdisjoint(inspect(engine).get_table_names())
        engine.dispose()

        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{migration_db.as_posix()}")
        assert set(inspect(engine).get_table_names()) == HEAD_TABLES
        engine.dispose()
    finally:
        assert _file_fingerprint(ROOT_DB) == root_db_before
        get_settings.cache_clear()

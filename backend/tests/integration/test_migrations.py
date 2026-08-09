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
ENTRY_STORE_REVISION = MIGRATIONS_DIR / "versions" / "0002_entry_store.py"
EDIT_DIFF_REVISION = MIGRATIONS_DIR / "versions" / "0003_edit_diff_capture.py"
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
ENTRY_STORE_TABLES = BASELINE_TABLES | {"entries", "alembic_version"}
HEAD_TABLES = ENTRY_STORE_TABLES | {"edit_diff_captures"}


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
        assert "CREATE TABLE edit_diff_captures" in sql
        assert "JSONB" in sql
        assert "DROP TABLE" not in sql
        # 0003 is additive only: no existing table is altered.
        assert "ALTER TABLE" not in sql
        # Portability (design §8.2): no dialect-specific predicate or index form.
        assert "NULLS NOT DISTINCT" not in sql
        assert "IS DISTINCT FROM" not in sql
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

        capture_columns = {
            column["name"]: column for column in inspector.get_columns("edit_diff_captures")
        }
        assert set(capture_columns) == {
            "id",
            "user_id",
            "source_kind",
            "entry_id",
            "chapter_id",
            "sequence",
            "before_state",
            "after_state",
            "before_text",
            "after_text",
            "before_sha256",
            "after_sha256",
            "before_chars",
            "after_chars",
            "producer",
            "context",
            "settled_at",
            "created_at",
            "updated_at",
        }
        # "pending" is not a state value; it is settled_at IS NULL (design §8.1).
        assert "payload_state" not in capture_columns
        assert capture_columns["before_state"]["nullable"] is False
        assert capture_columns["after_state"]["nullable"] is True
        assert capture_columns["before_sha256"]["nullable"] is False
        assert capture_columns["after_sha256"]["nullable"] is True
        assert capture_columns["settled_at"]["nullable"] is True

        capture_checks = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("edit_diff_captures")
        }
        assert {
            "ck_edit_diff_captures_source_kind",
            "ck_edit_diff_captures_before_state",
            "ck_edit_diff_captures_after_state",
            "ck_edit_diff_captures_one_source",
            "ck_edit_diff_captures_sequence",
            "ck_edit_diff_captures_before_chars",
            "ck_edit_diff_captures_after_chars",
            "ck_edit_diff_captures_before_payload",
            "ck_edit_diff_captures_after_payload",
            "ck_edit_diff_captures_settled",
            "ck_edit_diff_captures_entry_settled",
        } == capture_checks
        # The size cap is a code constant, not a schema contract (design §11.1).
        capture_ddl = "".join(
            constraint["sqltext"]
            for constraint in inspector.get_check_constraints("edit_diff_captures")
        )
        assert "100000" not in capture_ddl
        assert "100_000" not in capture_ddl

        capture_uniques = _unique_map(inspector, "edit_diff_captures")
        assert capture_uniques["uq_edit_diff_captures_entry_sequence"] == {
            "entry_id",
            "sequence",
        }
        assert capture_uniques["uq_edit_diff_captures_chapter_sequence"] == {
            "chapter_id",
            "sequence",
        }
        capture_indexes = _index_map(inspector, "edit_diff_captures")
        assert capture_indexes["ix_edit_diff_captures_user_id"]["column_names"] == ["user_id"]
        assert capture_indexes["ix_edit_diff_captures_owner_created"]["column_names"] == [
            "user_id",
            "created_at",
        ]
        assert capture_indexes["ix_edit_diff_captures_owner_kind_settled"][
            "column_names"
        ] == ["user_id", "source_kind", "settled_at"]

        capture_foreign_keys = _foreign_key_map(inspector, "edit_diff_captures")
        for column in ("user_id", "entry_id", "chapter_id"):
            assert capture_foreign_keys[(column,)]["options"]["ondelete"] == "CASCADE"
        assert capture_foreign_keys[("user_id",)]["referred_table"] == "users"
        assert capture_foreign_keys[("entry_id",)]["referred_table"] == "entries"
        assert capture_foreign_keys[("chapter_id",)]["referred_table"] == "chapters"
        engine.dispose()

        command.downgrade(config, "0002_entry_store")
        engine = create_engine(f"sqlite:///{migration_db.as_posix()}")
        assert set(inspect(engine).get_table_names()) == ENTRY_STORE_TABLES
        engine.dispose()

        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{migration_db.as_posix()}")
        assert set(inspect(engine).get_table_names()) == HEAD_TABLES
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


def test_edit_diff_revision_is_the_single_additive_head() -> None:
    """0003 is one new revision on top of a still-frozen 0001/0002 chain."""
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_alembic_config())
    assert list(script.get_heads()) == ["0003_edit_diff_capture"]

    revision = script.get_revision("0003_edit_diff_capture")
    assert revision.down_revision == "0002_entry_store"

    source = EDIT_DIFF_REVISION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    # Additive only: one create_table plus its indexes, no ALTER of any kind.
    assert called_attributes & {"create_table", "drop_table"} == {
        "create_table",
        "drop_table",
    }
    assert not called_attributes & {
        "add_column",
        "alter_column",
        "drop_column",
        "drop_constraint",
        "execute",
        "batch_alter_table",
    }
    assert "edit_diff_captures" in source

    # The two frozen revisions know nothing about this feature.
    for frozen in (INITIAL_REVISION, ENTRY_STORE_REVISION):
        frozen_source = frozen.read_text(encoding="utf-8")
        assert "edit_diff" not in frozen_source
        assert "0003" not in frozen_source


def test_edit_diff_revision_leaves_existing_ddl_untouched(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    """Applying 0003 must not change one byte of any pre-existing table's DDL."""
    from app.config import get_settings

    migration_db = (tmp_path / "additive.db").resolve()
    assert migration_db != ROOT_DB.resolve()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{migration_db.as_posix()}")
    get_settings.cache_clear()

    root_db_before = _file_fingerprint(ROOT_DB)
    config = _alembic_config()

    def _table_ddl() -> dict[str, str]:
        engine = create_engine(f"sqlite:///{migration_db.as_posix()}")
        try:
            with engine.connect() as connection:
                rows = connection.exec_driver_sql(
                    "SELECT name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
                ).fetchall()
        finally:
            engine.dispose()
        return {name: sql for name, sql in rows if sql is not None}

    try:
        command.upgrade(config, "0002_entry_store")
        before = _table_ddl()
        assert "edit_diff_captures" not in before

        command.upgrade(config, "head")
        after = _table_ddl()

        new_objects = set(after) - set(before)
        assert new_objects == {
            "edit_diff_captures",
            "ix_edit_diff_captures_user_id",
            "ix_edit_diff_captures_owner_created",
            "ix_edit_diff_captures_owner_kind_settled",
        }
        for name, ddl in before.items():
            assert after[name] == ddl, f"0003 altered pre-existing object {name}"
    finally:
        assert _file_fingerprint(ROOT_DB) == root_db_before
        get_settings.cache_clear()

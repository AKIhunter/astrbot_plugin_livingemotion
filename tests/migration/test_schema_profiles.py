"""Migration accepts only reviewed exact profiles, including the retained v2."""

import sqlite3

import pytest

from astrbot_plugin_livingemotion.storage.legacy_import import (
    KNOWN_SCHEMAS, SCHEMA_VERSION, MigrationError, _target_info, schema_hash,
)
from astrbot_plugin_livingemotion.storage.schema import MIGRATIONS, migrate


@pytest.mark.parametrize("version", [2, 3, 4, 5, 6])
def test_exact_known_profiles_remain_supported(version):
    db = sqlite3.connect(":memory:")
    try:
        migrate(db, MIGRATIONS[:version])
        db.execute("INSERT INTO runtime_meta VALUES('instance_id','synthetic-instance')")
        db.commit()
        assert schema_hash(db) == KNOWN_SCHEMAS[version]
        assert _target_info(db)["schema_version"] == version
    finally:
        db.close()


@pytest.mark.parametrize("sql", [
    "PRAGMA user_version=4",
    "PRAGMA user_version=7",
    "CREATE TABLE arbitrary(id INTEGER)",
    "CREATE TRIGGER arbitrary AFTER INSERT ON runtime_meta BEGIN SELECT 1; END",
    "ALTER TABLE owner_states ADD COLUMN unexpected TEXT",
    "DROP INDEX energy_owner_time",
    "DROP INDEX emotion_retention",
])
def test_version_number_cannot_authorize_unknown_schema(sql):
    db = sqlite3.connect(":memory:")
    try:
        migrate(db)
        db.execute("INSERT INTO runtime_meta VALUES('instance_id','synthetic-instance')")
        db.execute(sql)
        with pytest.raises(MigrationError, match="target_schema_incompatible"):
            _target_info(db)
    finally:
        db.close()


def test_reviewed_profiles_cover_the_current_runtime_version():
    assert SCHEMA_VERSION == len(MIGRATIONS)
    assert set(KNOWN_SCHEMAS) == set(range(2, SCHEMA_VERSION + 1))

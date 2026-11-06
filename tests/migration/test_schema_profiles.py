"""Migration accepts only reviewed exact profiles, including the retained v2."""

import sqlite3

import pytest

from astrbot_plugin_livingemotion.storage.legacy_import import (
    KNOWN_SCHEMAS, MigrationError, _target_info, schema_hash,
)
from astrbot_plugin_livingemotion.storage.schema import MIGRATIONS, migrate


@pytest.mark.parametrize("version", [2, 3])
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
    "CREATE TABLE arbitrary(id INTEGER)",
    "ALTER TABLE owner_states ADD COLUMN unexpected TEXT",
    "DROP INDEX energy_owner_time",
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

from django.db import migrations


INDEX_NAME = "copilot_chunk_text_fulltext"
TABLE_NAME = "copilot_retrievalchunk"
EXPECTED_COLUMN = "searchable_text"
EXPECTED_CONSTRAINTS = {
    "copilot_chunk_ordinal_unique": "UNIQUE",
    "copilot_chunk_tokens_positive": "CHECK",
    "copilot_chunk_chars_positive": "CHECK",
}


def _validate_chunk_table(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            [TABLE_NAME],
        )
        columns = {name: str(data_type).lower() for name, data_type in cursor.fetchall()}
        cursor.execute(
            "SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            [TABLE_NAME],
        )
        constraints = {name: str(kind).upper() for name, kind in cursor.fetchall()}
    required_columns = {
        "id", "generation_id", "document_id", "document_version_id", "ordinal",
        "searchable_text", "content_digest", "token_count", "character_count", "created_at",
    }
    if not required_columns.issubset(columns):
        raise RuntimeError(f"Incompatible {TABLE_NAME} columns; manual review required")
    if columns[EXPECTED_COLUMN] not in {"text", "mediumtext", "longtext"}:
        raise RuntimeError(f"Incompatible {TABLE_NAME}.{EXPECTED_COLUMN} type; manual review required")
    for name, expected_type in EXPECTED_CONSTRAINTS.items():
        if constraints.get(name) != expected_type:
            raise RuntimeError(f"Incompatible or missing {TABLE_NAME} constraint {name}; manual review required")


def _mysql_index_definition(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT INDEX_TYPE, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME "
            "FROM information_schema.STATISTICS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s "
            "ORDER BY SEQ_IN_INDEX",
            [TABLE_NAME, INDEX_NAME],
        )
        return tuple(cursor.fetchall())


def ensure_fulltext_index(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    _validate_chunk_table(schema_editor)
    definition = _mysql_index_definition(schema_editor)
    if not definition:
        schema_editor.execute(
            f"CREATE FULLTEXT INDEX {INDEX_NAME} ON {TABLE_NAME} ({EXPECTED_COLUMN})"
        )
        definition = _mysql_index_definition(schema_editor)
    expected = (("FULLTEXT", 1, 1, EXPECTED_COLUMN),)
    normalized = tuple((str(kind).upper(), int(non_unique), int(sequence), column) for kind, non_unique, sequence, column in definition)
    if normalized != expected:
        raise RuntimeError(
            f"Incompatible existing {INDEX_NAME} definition on {TABLE_NAME}; manual review required"
        )


def remove_fulltext_index(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    definition = _mysql_index_definition(schema_editor)
    if definition:
        schema_editor.execute(f"ALTER TABLE {TABLE_NAME} DROP INDEX {INDEX_NAME}")


class Migration(migrations.Migration):
    # MySQL FULLTEXT DDL auto-commits. Keeping it in a separate, idempotent,
    # definition-validating migration makes the expected partial state resumable.
    atomic = False
    dependencies = [("copilot", "0001_initial")]
    operations = [migrations.RunPython(ensure_fulltext_index, remove_fulltext_index)]

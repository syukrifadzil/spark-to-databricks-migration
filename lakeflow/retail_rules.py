"""Bronze schemas, silver projections and validation rules, all derived from the landing contract.

Plain Python that only builds SQL text, so the Lakeflow pipeline imports it on Databricks and the
unit tests import it locally. Every rule is a SQL predicate that is true when a row passes.

Rule names and logic mirror data/generators/validate.py (row_problems): one rule per column and
check, named <entity>.<column>.<check> with check one of required, type, domain, range. A
quarantined row's reasons therefore line up with the anomaly manifest, and silver built from the
valid rows can be compared with the generator's _expected/ state.
"""
import json

SQL_TYPES = {"string": "STRING", "timestamp": "TIMESTAMP", "decimal": "DECIMAL(18,2)", "integer": "INT"}

# Well-formed values, matching the validator: parse_ts (exact ISO shape and a real date and time),
# DECIMAL_RE and INTEGER_RE. Character classes avoid backslashes, which SQL literals would unescape.
FORMATS = {
    "timestamp": ("{c} RLIKE '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}T[0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}}Z$'"
                  " AND try_cast({c} AS TIMESTAMP) IS NOT NULL"),
    "decimal": "{c} RLIKE '^-?[0-9]+[.][0-9]{{2}}$'",
    "integer": "{c} RLIKE '^-?[0-9]+$'",
}
METADATA_COLUMNS = ["_source_file", "_ingested_at"]


def load_contract(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _columns(contract, entity):
    return contract["entities"][entity]["columns"] + contract["feed_columns"]


def _literal(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def bronze_schema(contract, entity):
    """DDL schema with every contracted column as a string: bronze stores values as received."""
    return ", ".join(f"`{c['name']}` STRING" for c in _columns(contract, entity))


def column_rules(entity, col):
    name, c = col["name"], f"`{col['name']}`"
    rules = {}
    if col.get("required"):
        rules[f"{entity}.{name}.required"] = f"{c} IS NOT NULL"
    parsed = f"{c} IS NOT NULL"
    if col["type"] in FORMATS:
        fmt = FORMATS[col["type"]].format(c=c)
        rules[f"{entity}.{name}.type"] = f"{c} IS NULL OR ({fmt})"
        parsed = f"{c} IS NOT NULL AND {fmt}"
    # Domain and range are only judged on present, well-formed values, as in the validator.
    domain = []
    if "allowed" in col:
        domain.append(f"{c} IN ({', '.join(map(_literal, col['allowed']))})")
    if "pattern" in col:
        domain.append(f"{c} RLIKE {_literal('^(?:' + col['pattern'] + ')$')}")
    if domain:
        rules[f"{entity}.{name}.domain"] = f"NOT ({parsed}) OR ({' AND '.join(domain)})"
    value = f"try_cast({c} AS {SQL_TYPES[col['type']]})"
    if "min" in col:
        rules[f"{entity}.{name}.range"] = f"NOT ({parsed}) OR {value} >= {col['min']}"
    if "min_exclusive" in col:
        rules[f"{entity}.{name}.range"] = f"NOT ({parsed}) OR {value} > {col['min_exclusive']}"
    return rules


def entity_rules(contract, entity):
    """{rule name: SQL predicate} for one entity. Each predicate is wrapped in coalesce(..., false)
    so that a row is always either valid or quarantined, never neither because of a null."""
    rules = {}
    for col in _columns(contract, entity):
        rules.update(column_rules(entity, col))
    return {name: f"coalesce({pred}, false)" for name, pred in rules.items()}


def failed_rules_sql(rules):
    """SQL expression for the array of rule names a row fails; empty when the row is valid."""
    return "array_compact(array(" + ", ".join(f"IF({p}, NULL, {_literal(n)})" for n, p in rules.items()) + "))"


def typed_columns(contract, entity):
    """Silver projection: contracted columns cast to their contract types, then lineage columns."""
    cols = [f"`{c['name']}`" if c["type"] == "string" else
            f"try_cast(`{c['name']}` AS {SQL_TYPES[c['type']]}) AS `{c['name']}`"
            for c in _columns(contract, entity)]
    return cols + METADATA_COLUMNS

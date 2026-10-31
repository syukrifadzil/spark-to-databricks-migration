"""Static checks tying the dbt project to the data contract. No dbt installation needed."""
from pathlib import Path

from data.generators import common

DBT = Path(__file__).resolve().parents[2] / "dbt"


def test_every_contract_business_rule_has_a_dbt_test():
    for rule in common.load_contract()["business_rules"]:
        path = DBT / "tests" / "business" / (rule["name"].replace(".", "_") + ".sql")
        assert path.exists(), f"no dbt test for {rule['name']}"


def test_no_model_writes_outside_the_target_schema():
    # Ownership (ADR 0001): every model builds in retail_gold, the profile's target schema.
    for path in (DBT / "models").rglob("*"):
        if path.suffix in (".sql", ".yml"):
            assert "schema=" not in path.read_text().replace(" ", ""), path
    assert "+schema" not in (DBT / "dbt_project.yml").read_text()

"""Retail bronze and silver: Lakeflow Declarative Pipeline source.

For each entity in the landing contract:

    landing CSV --Auto Loader--> retail_bronze.<entity>          every row as received, as strings
    bronze --rules fail-------> retail_silver.<entity>_quarantine  original values plus failed rules
    bronze --rules pass, cast--> retail_silver.<entity>          current state via AUTO CDC (SCD 1)

Rules come from lakeflow/retail_rules.py, built from data/contracts/retail_contract.json, so the
expectations and the quarantine filter cannot drift apart. Settings are read from the pipeline
configuration (databricks.yml since Phase 05; lakeflow/pipeline.json for the Phase 03 setup).
See phases/phase_03_lakeflow_bronze_silver/EXPLANATION.md.
"""
import sys

from pyspark import pipelines as dp
from pyspark.sql import functions as F

conf = spark.conf.get  # noqa: F821 - spark is provided by the pipeline runtime
sys.path.append(conf("retail.code_root"))
import retail_rules as rr  # noqa: E402

CONTRACT = rr.load_contract(conf("retail.contract_path"))
LANDING = conf("retail.landing_path")
BRONZE = conf("retail.bronze_schema", "retail_bronze")
SILVER = conf("retail.silver_schema", "retail_silver")


def define_entity(entity):
    rules = rr.entity_rules(CONTRACT, entity)
    bronze = f"{BRONZE}.{entity}"

    @dp.table(name=bronze, comment=f"Every {entity} row as received from landing, values as strings.")
    def bronze_table():
        return (spark.readStream.format("cloudFiles")  # noqa: F821
                .option("cloudFiles.format", "csv")
                .option("header", "true")
                # The schema is fixed by the contract; columns a file adds are kept here, not dropped.
                .option("rescuedDataColumn", "_rescued_data")
                .schema(rr.bronze_schema(CONTRACT, entity))
                .load(f"{LANDING}/batch_*/{entity}.csv")
                .select("*",
                        F.col("_metadata.file_path").alias("_source_file"),
                        F.col("_metadata.file_modification_time").alias("_file_modified_at"),
                        F.current_timestamp().alias("_ingested_at")))

    @dp.table(name=f"{SILVER}.{entity}_quarantine",
              comment=f"{entity} rows that failed a contract rule, with the names of the failed rules.")
    def quarantine_table():
        return (spark.readStream.table(bronze)  # noqa: F821
                .withColumn("_failed_rules", F.expr(rr.failed_rules_sql(rules)))
                .filter(F.size("_failed_rules") > 0))

    @dp.temporary_view(name=f"{entity}_valid")
    @dp.expect_all_or_drop(rules)
    def valid_view():
        return spark.readStream.table(bronze)  # noqa: F821

    @dp.temporary_view(name=f"{entity}_typed")
    def typed_view():
        return spark.readStream.table(f"{entity}_valid").selectExpr(*rr.typed_columns(CONTRACT, entity))  # noqa: F821

    dp.create_streaming_table(name=f"{SILVER}.{entity}",
                              comment=f"Current state of each {entity} record: latest valid version by key.")
    dp.create_auto_cdc_flow(
        target=f"{SILVER}.{entity}",
        source=f"{entity}_typed",
        keys=[CONTRACT["entities"][entity]["primary_key"]],
        # Latest version wins by (source_updated_at, event_id), as the contract defines; event_id
        # breaks ties, so late arrivals and replays cannot change the result.
        sequence_by=F.struct("source_updated_at", "event_id"),
        stored_as_scd_type=1,
    )


for name in CONTRACT["entities"]:
    define_entity(name)

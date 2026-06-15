"""
PySpark benchmark job for Dataproc — Task 5.
Submit with:
  gcloud dataproc jobs submit pyspark dataproc_benchmark.py \
    --cluster=tbd-cluster \
    --region=europe-west1 \
    -- gs://tbd-2026l-325144-data/phase2/group_03/small/
"""

import gc
import json
import logging
import sys
import time

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("tbd-benchmark")

GCS_BASE    = sys.argv[1] if len(sys.argv) > 1 else "gs://tbd-2026l-325144-data/phase2/group_03/small/small/"
EVENTS      = GCS_BASE + "events.parquet"
DIMENSION   = GCS_BASE + "dimension.parquet"
RESULTS_OUT = GCS_BASE + "dataproc_results.json"

N_REPS = 3

spark = SparkSession.builder.appName("TBDPhase2Dataproc").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

log.info(f"Spark version      : {spark.version}")
log.info(f"Default parallelism: {spark.sparkContext.defaultParallelism}")
log.info(f"Events path        : {EVENTS}")


def timed(func, n=N_REPS):
    times = []
    result = None
    for _ in range(n):
        gc.collect()
        spark.catalog.clearCache()
        t0 = time.perf_counter()
        result = func()
        times.append(time.perf_counter() - t0)
    times.sort()
    return times[len(times) // 2], result   # median


def q1():
    return (
        spark.read.parquet(EVENTS)
        .filter(
            (F.col("event_ts") >= "2026-01-15") &
            (F.col("event_ts") <= "2026-01-31") &
            (F.col("sensor_type") == "thermometer") &
            (F.col("battery_level") < 0.3)
        )
        .groupBy("country")
        .agg(
            F.count("measurement_id").alias("n_readings"),
            F.avg("metric_1").alias("avg_metric"),
            F.avg("wifi_signal").alias("avg_signal"),
            F.sum(F.when(F.col("is_stable") == False, 1).otherwise(0)).alias("unstable_count"),
        )
        .orderBy(F.desc("n_readings"))
        .collect()
    )


def q2():
    events = spark.read.parquet(EVENTS)
    dim    = spark.read.parquet(DIMENSION)
    return (
        events.join(dim, on="device_id", how="inner")
        .groupBy("location", "hardware_model")
        .agg(
            F.count("measurement_id").alias("n_readings"),
            F.avg("battery_level").alias("avg_battery"),
            F.min("battery_level").alias("min_battery"),
            F.avg("metric_1").alias("avg_metric"),
            F.sum("metric_2").alias("total_metric2"),
            F.avg(F.col("is_stable").cast("int")).alias("stability_rate"),
        )
        .orderBy(F.desc("n_readings"))
        .collect()
    )


def q3():
    return (
        spark.read.parquet(EVENTS)
        .groupBy("device_id")
        .agg(
            F.count("measurement_id").alias("n_readings"),
            F.avg("battery_level").alias("avg_battery"),
            F.min("battery_level").alias("min_battery"),
            F.avg("wifi_signal").alias("avg_signal"),
            F.max("event_ts").alias("last_seen"),
        )
        .orderBy(F.desc("n_readings"))
        .limit(100)
        .collect()
    )


results = []
for name, func in [("Q1_selective_agg", q1), ("Q2_join_agg", q2), ("Q3_high_card_top_k", q3)]:
    log.info(f"Running {name} ({N_REPS} reps)...")
    median_s, rows = timed(func)
    row = {
        "library_engine": "PySpark",
        "mode": "dataproc",
        "query_name": name,
        "data_format": "parquet",
        "layout": "default",
        "median_time_s": round(median_s, 4),
        "result_rows": len(rows),
        "peak_memory_mb": None,
        "notes": f"Dataproc cluster — {spark.sparkContext.defaultParallelism} default parallelism",
    }
    results.append(row)
    log.info(f"RESULT {name}: {row['median_time_s']}s | rows={row['result_rows']}")

# Write results as JSON to GCS
results_json = json.dumps(results, indent=2)
log.info("ALL RESULTS:\n" + results_json)

results_json = json.dumps(results, indent=2)
spark.sparkContext.parallelize([results_json], 1) \
    .saveAsTextFile(RESULTS_OUT)
log.info(f"Results saved to {RESULTS_OUT}")

spark.stop()

"""
Standalone data generation script for TBD Phase 2 — Group 3 (IoT telemetry).
Generates the medium-scale dataset (10M rows) outside of Jupyter to avoid
kernel memory limits.

Run from the project root:
    python generate_medium_dataset.py

Output is written to:
    data/phase2_26L/group_03/medium/
"""

import gc
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl
import psutil

# ── Configuration ─────────────────────────────────────────────────────────────
GROUP_ID = 3
SCALE    = "small"
N_ROWS   = 2_000_000
SEED     = 42

CARD = {
    "name": "IoT telemetry",
    "feature": "device time series",
    "stress": "time filters and rolling/window logic",
}

OUTPUT_DIR            = Path("data/phase2_26L") / f"group_{GROUP_ID:02d}" / SCALE
EVENTS_PATH           = OUTPUT_DIR / "events.parquet"
PARTITIONED_EVENTS_DIR = OUTPUT_DIR / "events_partitioned"
OPTIMIZED_EVENTS_PATH = OUTPUT_DIR / "events_optimized.parquet"
DIMENSION_PATH        = OUTPUT_DIR / "dimension.parquet"
CSV_EVENTS_PATH       = OUTPUT_DIR / "events_q1_flat.csv"
MANIFEST_PATH         = OUTPUT_DIR / "manifest.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(SEED)

print(f"Group : {GROUP_ID} — {CARD['name']}")
print(f"Scale : {SCALE} ({N_ROWS:,} rows)")
print(f"Seed  : {SEED}")
print(f"Output: {OUTPUT_DIR.resolve()}")
print(f"RAM   : {psutil.virtual_memory().total / 2**30:.1f} GiB available")
print()


# ── Generator functions ───────────────────────────────────────────────────────
def skewed_ids(rng, n, max_id, hot_fraction=0.02, hot_probability=0.50):
    hot_count = max(1, int(max_id * hot_fraction))
    ids = rng.integers(hot_count + 1, max_id + 1, size=n)
    hot_mask = rng.random(n) < hot_probability
    ids[hot_mask] = rng.integers(1, hot_count + 1, size=hot_mask.sum())
    return ids


def random_tag_lists(rng, n, vocabulary=None, min_tags=1, max_tags=3):
    vocabulary = np.array(
        vocabulary or ["ai", "cloud", "spark", "polars", "duckdb", "sql", "etl", "security", "mlops"]
    )
    counts  = rng.integers(min_tags, max_tags + 1, size=n)
    tag_ids = rng.integers(0, len(vocabulary), size=(n, max_tags))
    return [[str(vocabulary[tag_ids[i, j]]) for j in range(counts[i])] for i in range(n)]


def generate_base_events(n, rng):
    print(f"  generating {n:,} base events …")
    start   = np.datetime64("2026-01-01T00:00:00", "s")
    end     = np.datetime64("2026-04-01T00:00:00", "s")
    seconds = int((end - start) / np.timedelta64(1, "s"))
    event_ts = (
        start + rng.integers(0, seconds, size=n).astype("timedelta64[s]")
    ).astype("datetime64[us]")

    df = pl.DataFrame({
        "event_id":  np.arange(1, n + 1),
        "entity_id": skewed_ids(rng, n, max_id=200_000),
        "event_ts":  event_ts,
        "category":  rng.choice(["A", "B", "C", "D", "E", "F"], size=n),
        "country":   rng.choice(["PL", "DE", "FR", "UK", "US", "IN", "BR"], size=n),
        "device":    rng.choice(["mobile", "desktop", "tablet"], size=n, p=[0.65, 0.25, 0.10]),
        "metric_1":  rng.lognormal(mean=4.0, sigma=1.0, size=n).round(3),
        "metric_2":  rng.integers(0, 10_000, size=n),
        "tags":      random_tag_lists(rng, n),
    })
    return df.with_columns(pl.col("event_ts").dt.date().alias("event_date"))


def customize_for_variant(df, rng):
    df = df.rename({"entity_id": "device_id", "event_id": "measurement_id"})
    iot_vocabulary = [
        "normal", "overheating", "low_battery",
        "offline_alert", "high_vibration", "maintenance_mode",
    ]
    n = len(df)
    df = df.with_columns([
        pl.Series("sensor_type",   rng.choice(["thermometer", "hygrometer", "pressure_sensor", "accelerometer"], size=n)),
        pl.Series("battery_level", rng.uniform(0.05, 1.0, size=n).round(2)),
        pl.Series("wifi_signal",   rng.integers(-90, -30, size=n)),
        pl.Series("work_mode",     rng.choice(["eco", "performance", "balanced"], size=n, p=[0.7, 0.2, 0.1])),
        pl.Series("is_stable",     rng.choice([True, False], size=n, p=[0.95, 0.05])),
        pl.Series("tags",          random_tag_lists(rng, n, vocabulary=iot_vocabulary)),
    ])
    df = df.with_columns(
        pl.when(pl.col("sensor_type") == "accelerometer")
        .then(pl.col("metric_1") * 2)
        .otherwise(pl.col("metric_1"))
        .alias("metric_1")
    )
    return df.drop(["category", "device"])


def generate_dimension_table(rng):
    num_devices = 200_000
    print(f"  generating dimension table ({num_devices:,} devices) …")
    return pl.DataFrame({
        "device_id":        np.arange(1, num_devices + 1),
        "location":         rng.choice(["Warsaw_Hub", "Berlin_Factory", "London_Office", "Paris_Lab"], size=num_devices),
        "hardware_model":   rng.choice(["SensorPro-2000", "EcoLite-v2", "Industrial-X1"], size=num_devices),
        "last_service_date": rng.choice(
            np.arange(np.datetime64("2026-01-01"), np.datetime64("2026-04-01"), dtype="datetime64[D]"),
            size=num_devices,
        ),
        "priority_level":   rng.integers(1, 6, size=num_devices),
    })


# ── Generate ──────────────────────────────────────────────────────────────────
t0 = time.perf_counter()

print("Step 1/6  generating events …")
base   = generate_base_events(N_ROWS, rng)
events = customize_for_variant(base, rng)
del base
gc.collect()
print(f"          done — shape {events.shape}")

print("Step 2/6  writing events.parquet …")
events.write_parquet(EVENTS_PATH, compression="zstd")
print(f"          {EVENTS_PATH}  ({EVENTS_PATH.stat().st_size / 2**20:.1f} MB)")

print("Step 3/6  writing partitioned events …")
events.write_parquet(PARTITIONED_EVENTS_DIR, partition_by="event_date", compression="zstd")
print(f"          {PARTITIONED_EVENTS_DIR}/")

print("Step 4/6  writing optimized events (sorted by event_ts, row_group=100k) …")
events.sort(["event_ts"]).write_parquet(
    OPTIMIZED_EVENTS_PATH,
    compression="zstd",
    row_group_size=100_000,
)
print(f"          {OPTIMIZED_EVENTS_PATH}  ({OPTIMIZED_EVENTS_PATH.stat().st_size / 2**20:.1f} MB)")

print("Step 5/6  writing Q1 flat CSV baseline (columns needed by Q1 only) …")
q1_cols = ["measurement_id", "event_ts", "country", "sensor_type", "battery_level", "wifi_signal", "is_stable", "metric_1"]
events.select(q1_cols).write_csv(CSV_EVENTS_PATH)
print(f"          {CSV_EVENTS_PATH}  ({CSV_EVENTS_PATH.stat().st_size / 2**20:.1f} MB)")

print("Step 6/6  generating and writing dimension table …")
dimension = generate_dimension_table(rng)
dimension.write_parquet(DIMENSION_PATH, compression="zstd")
print(f"          {DIMENSION_PATH}  ({DIMENSION_PATH.stat().st_size / 2**20:.1f} MB)")

elapsed = time.perf_counter() - t0

# ── Manifest ──────────────────────────────────────────────────────────────────
manifest = {
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "group_id": GROUP_ID,
    "variant": CARD,
    "scale": SCALE,
    "rows": int(events.height),
    "run_seed": SEED,
    "paths": {
        "events":             str(EVENTS_PATH),
        "events_partitioned": str(PARTITIONED_EVENTS_DIR),
        "events_optimized":   str(OPTIMIZED_EVENTS_PATH),
        "events_csv_q1":      str(CSV_EVENTS_PATH),
        "dimension":          str(DIMENSION_PATH),
    },
    "environment": {
        "python":           platform.python_version(),
        "polars":           pl.__version__,
        "numpy":            np.__version__,
        "cpu_logical_cores": psutil.cpu_count(logical=True),
        "ram_gib":          round(psutil.virtual_memory().total / 2**30, 2),
    },
    "generation_time_s": round(elapsed, 1),
}
MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

print()
print("=" * 50)
print(f"Done in {elapsed:.1f}s")
print(json.dumps(manifest, indent=2))

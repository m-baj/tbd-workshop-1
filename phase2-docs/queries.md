## 🔍 Query Definitions & Performance Hypotheses

### **Query 1: Selective filter + aggregation (predicate pushdown sensitive)**

**Intent:** Find all thermometer readings in a narrow 2-week time window with critically low battery, aggregated by country.

```sql
SELECT
    country,
    COUNT(*)                                           AS n_readings,
    AVG(metric_1)                                      AS avg_metric,
    AVG(wifi_signal)                                   AS avg_signal,
    SUM(CASE WHEN is_stable = false THEN 1 ELSE 0 END) AS unstable_count
FROM events
WHERE event_ts BETWEEN '2026-01-15' AND '2026-01-31'
  AND sensor_type = 'thermometer'
  AND battery_level < 0.3
GROUP BY country
ORDER BY n_readings DESC;

```

* **Covers:** Selective filter + aggregation, sensitive to predicate pushdown and row-group pruning.
* **Hypotheses:**
* **What it tests:** Efficiency in pushing time range and categorical filters into the Parquet reader to skip row groups before materializing data.
* **Expected winner:** **DuckDB** — due to aggressive Parquet predicate pushdown and projection pruning. Polars lazy should be a close second.
* **Most memory:** **Pandas (default)** — reads all columns and rows before filtering in Python.
* **Layout Impact:** **High.** Optimized Parquet (sorted by `event_ts`) should allow DuckDB/Polars to skip the vast majority of data.



---

### **Query 2: Join with dimension table + low-cardinality group-by**

**Intent:** Enrich every reading with device metadata and summarize fleet health per location and hardware model.

```sql
SELECT
    d.location,
    d.hardware_model,
    COUNT(*)                        AS n_readings,
    AVG(e.battery_level)            AS avg_battery,
    MIN(e.battery_level)            AS min_battery,
    AVG(e.metric_1)                 AS avg_metric,
    SUM(e.metric_2)                 AS total_metric2,
    AVG(CAST(e.is_stable AS INT))   AS stability_rate
FROM events e
INNER JOIN dimension d ON e.device_id = d.device_id
GROUP BY d.location, d.hardware_model
ORDER BY n_readings DESC;

```

* **Covers:** Join with dimension table, group-by aggregation on low-cardinality result (12 groups).
* **Hypotheses:**
* **What it tests:** Hash join performance with a large build side (200k-row dimension table) and full scan of the fact table.
* **Expected winner:** **DuckDB or Polars** — both use vectorized hash joins. DuckDB may lead by avoiding Python object overhead entirely.
* **Most memory:** **Pandas** — must fully materialize both DataFrames before joining. PySpark local mode also shows high materialization overhead.
* **Layout Impact:** **Low.** `device_id` is the key but is accessed randomly. Projection pushdown matters more here.



---

### **Query 3: High-cardinality group-by + top-k**

**Intent:** Identify the 100 most active devices in the fleet with their health summary.

```sql
SELECT
    device_id,
    COUNT(*)            AS n_readings,
    AVG(battery_level)  AS avg_battery,
    MIN(battery_level)  AS min_battery,
    AVG(wifi_signal)    AS avg_signal,
    MAX(event_ts)       AS last_seen
FROM events
GROUP BY device_id
ORDER BY n_readings DESC
LIMIT 100;

```

* **Covers:** High-cardinality group-by (200k groups, skewed), top-k / sorting.
* **Hypotheses:**
* **What it tests:** Aggregation hash-table performance under high cardinality and skew (hot devices). The bottleneck is the group-by itself, not the final sort.
* **Expected winner:** **Polars or DuckDB** — both utilize parallel vectorized aggregation. Polars lazy will optimize projection to read only necessary columns.
* **Most memory:** **Pandas** — allocates a Python dict-backed accumulator with up to 200k keys. This is where Pandas degrades fastest at scale.
* **Layout Impact:** **Slight.** Sorting by `device_id` improves cache locality for the aggregator, but a full scan is still required.



---

## 📊 Summary Table

| Query Name | Classes Covered | Expected Winner | Layout Sensitive? |
| --- | --- | --- | --- |
| **Q1: Low-battery alert** | selective filter + agg, pruning | **DuckDB** | **Yes** — sort by `event_ts` |
| **Q2: Fleet health** | join + low-cardinality group-by | **DuckDB / Polars** | **No** |
| **Q3: Top-100 devices** | high-cardinality group-by + top-k | **Polars / DuckDB** | **Slightly** |
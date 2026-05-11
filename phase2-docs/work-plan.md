## 📋 Project Plan: Data Engine Performance Comparison

### 🤝 Shared Prerequisite

*Time: 30–60 min (everyone together)*

* **Agree on Query Definitions:** Define 3 specific queries, column names, filter values, and expected outputs.
* **Benchmark Protocol:** Agree on the `benchmark_helper` interface (structure of `benchmark_results` rows).
* **Scale Decision:** Finalize the dataset size (recommend **Medium = 10M rows**).
* **Data Distribution:** One person generates data, others pull it using the shared manifest.

---

## 🧑‍💻 Roles & Task Allocation

### **Person A — Pandas + DuckDB + File Layout**

*Focus: SQL-adjacent engines and physical storage analysis.*

| Task | Details |
| --- | --- |
| **Benchmark Helper** | Implement the timing/memory measurement framework (cell-19) for everyone. |
| **Task 2** | Pandas default backend × 3 queries. |
| **Task 2** | Pandas PyArrow backend × 3 queries. |
| **Task 2** | DuckDB × 3 queries. |
| **Task 2.5** | **File format & layout experiment:** Default Parquet vs. Optimized vs. CSV/JSONL. |
| **Task 4** | DuckDB thread scalability (1, 4, 8, 20 threads). |
| **Final Answers** | Answer Q1 (DataFrame vs SQL) and Q8 (Pandas backend comparison). |
| **Assembly** | Collect all `benchmark_results` rows into the final table. |

---

### **Person B — Polars (all modes) + Execution Analysis**

*Focus: Polars engine deep-dive and execution strategies.*

| Task | Details |
| --- | --- |
| **Task 2** | Polars eager × 3 queries. |
| **Task 2** | Polars lazy `collect()` × 3 queries. |
| **Task 2** | Polars streaming `collect(engine="streaming")` × 3 queries. |
| **Task 3.1** | **Full execution mode comparison:** Add `sink_parquet()` variant, measure memory per mode. |
| **Task 3.2** | Identify and justify one Polars limitation vs Spark. |
| **Final Answers** | Answer Q2 (memory-sensitive query), Q3 (lazy impact), Q4 (streaming memory), Q5 (sink vs collect). |

---

### **Person C — PySpark local + Dataproc + Decision Boundary**

*Focus: Distributed execution and infrastructure scaling.*

| Task | Details |
| --- | --- |
| **Task 2** | PySpark local (`local[*]`) × 3 queries. |
| **Task 4** | PySpark scalability: `local[1]`, `local[2]`, `local[*]`. Explain non-linear scaling. |
| **Task 5** | **Cloud Execution:** Upload data to GCS, run PySpark on Dataproc (GCP), compare vs. local. |
| **Task 3.3** | **Decision boundary:** Synthesize results from everyone to write the boundary statement. |
| **Final Answers** | Answer Q6 (local Spark behavior) and Q7 (when to move to cluster). |

---

## 🔄 Coordination Points

1. **Kick-off:** Joint query design meeting (30 min) before anyone starts coding.
2. **Protocol:** Person A must share the `benchmark_helper` code early so B and C use the same measurement logic.
3. **Data Sharing:** Everyone sends median times and peak memory numbers to Person C for the Decision Boundary analysis.
4. **Submission:** Everyone sends their `benchmark_results` rows to Person A for final table assembly.

---

## ⚖️ Workload Balance Matrix

| Person | Implementation | Analysis/Writing | Infrastructure |
| --- | --- | --- | --- |
| **A** | 3 engines × 3 queries | 2 final answers + assembly | Low |
| **B** | 1 engine × 3 modes | **4 final answers + 2 analysis tasks** | Low |
| **C** | 1 engine × 3 queries | 2 final answers + Decision Boundary | **High (Dataproc/GCS)** |

> **Note:** The lighter query load for Person C is offset by cloud setup. Person B's lighter implementation is balanced by more intensive execution analysis.
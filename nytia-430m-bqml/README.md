# Nytia Health — 430M Production-Scale Pipeline (BigQuery ML)

Production-scale run of the complication risk prediction pipeline on the
**full 430,981,696-record** sponsor dataset, executed entirely in BigQuery.

## Why this is separate from the 200K/500K work

| | 200K / 500K work | 430M work (this folder) |
|---|---|---|
| Account | Account B | elchuri.s@northeastern.edu |
| Project | gcp-poc-492901 | secure-totality-493616-b7 |
| Region | northamerica-northeast1 | **US** |
| Dataset | wellness_data | nytia_us_work |
| Approach | Cloud Run + Docker + FastAPI | **Pure BigQuery ML (SQL only)** |

The full dataset lives in the sponsor project (`northeastgroup4t`) in the **US**
region. Because BigQuery cannot write query results across regions, all work
runs in a **US-region dataset** (`nytia_us_work`) inside our own project.

## Data safety

- The sponsor source table is **READ-ONLY**. Every query only `SELECT`s from it.
- **Nothing is created, updated, or deleted** in the sponsor project.
- All outputs (silver, gold, model, predictions) are written to
  `secure-totality-493616-b7.nytia_us_work` — our own project.
- Query **cost is billed to our project** (the job runner), not the sponsor.

## Key data-quality note

The `c_val_sle` (sleep current value) column in the source has a trailing
newline character (values are `0-400\n`, etc.). We `TRIM()` it in the Silver
step. The source data is never altered.

## Pipeline steps

| Step | File | Output | Runtime |
|------|------|--------|---------|
| 1 | `sql/01_silver_validation.sql` | `silver_validated` (430M) | ~34s |
| 2 | `sql/02_gold_features.sql` | `gold_features` (430M) | ~23s |
| 3 | `sql/03_train_model.sql` | `xgb_risk_model` (full feature set) | ~78 min |
| 4 | `sql/04_evaluate.sql` | evaluation metrics | ~seconds |
| 5 | `sql/05_batch_score.sql` | `predictions_full` + `shap_sample_50k` | ~1-2 min |
| 6 | `sql/06_raw_only_model.sql` | `xgb_raw_only` (final reported model) | ~115 min |
| 7 | `sql/07_determinism_check.sql` | text determinism check | ~1-2 min |

The **final reported model is `xgb_raw_only`** (Step 6): XGBoost trained on the
16 raw wellness dimensions only. Step 3 trains on the full feature set including
the two compound counts and is retained for reference.

## How to run

All queries use `--location=US`. Run in order:

```bash
bq query --use_legacy_sql=false --location=US < sql/01_silver_validation.sql
bq query --use_legacy_sql=false --location=US < sql/02_gold_features.sql
bq query --use_legacy_sql=false --location=US < sql/03_train_model.sql
bq query --use_legacy_sql=false --location=US < sql/04_evaluate.sql
bq query --use_legacy_sql=false --location=US < sql/05_batch_score.sql
bq query --use_legacy_sql=false --location=US < sql/06_raw_only_model.sql
bq query --use_legacy_sql=false --location=US < sql/07_determinism_check.sql
```

## Results (full 430M)

Risk tier distribution:

| Tier | Count | % |
|------|-------|---|
| Low | 30,498,928 | 7.08% |
| Moderate | 172,872,014 | 40.11% |
| High | 227,610,754 | 52.81% |

Final model metrics (`xgb_raw_only`, 16 wellness dimensions, full 430M, held-out test set):

| Metric | Value |
|--------|-------|
| Accuracy | 0.945 |
| Precision | 0.959 |
| Recall | 0.759 |
| F1-score | 0.791 |
| AUC-ROC | 0.992 |

Feature importance (ML.GLOBAL_EXPLAIN) is distributed evenly across all 16
dimensions (0.199–0.232 each), with trajectory (`dif_`) features ranking
slightly above current-value (`c_val_`) features — the model draws on every
dimension rather than any single signal.

Text determinism check (Step 7): `status_assessment` is 100% deterministic
from the features (429,981,696 unique feature combos = 429,981,696 unique
combos-plus-text), confirming the dataset is rule-generated.

All result CSVs are in `results/`:
- `risk_distribution.csv`
- `model_metrics_raw_only.csv` (final reported model)
- `feature_importance_raw_only.csv` (final reported model)
- `model_metrics.csv`, `feature_importance.csv`, `model_comparison.csv`, `confusion_matrix.csv` (full-feature reference run)

## Note on interpretation

The risk tier is currently computed from the wellness dimensions rather than
from observed clinical events. The reported model (`xgb_raw_only`) is trained on
the raw dimensions only, so it infers the tier from its components rather than
reading it directly. Genuine complication prediction requires real clinical
outcome labels (e.g. diagnoses, hospitalizations); the pipeline accepts these
with only a change to the label column.

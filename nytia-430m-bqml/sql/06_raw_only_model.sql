-- ============================================================
-- Nytia Health 430M Pipeline — Step 6: Leakage-Free Model
-- Trains XGBoost on the 16 raw wellness dimensions ONLY,
-- excluding the two compound count features that the risk tier
-- is derived from. This is the model reported as the final result.
-- Target : secure-totality-493616-b7.nytia_us_work.xgb_raw_only
-- Region : US
-- Runtime: ~115 min on full 430M
-- ============================================================

CREATE OR REPLACE MODEL `secure-totality-493616-b7.nytia_us_work.xgb_raw_only`
OPTIONS(
  model_type='BOOSTED_TREE_CLASSIFIER',
  input_label_cols=['risk_tier'],
  max_iterations=50,
  learn_rate=0.1,
  max_tree_depth=6,
  subsample=0.8,
  enable_global_explain=TRUE
) AS
SELECT
  dif_nutri_enc, dif_obesic_enc, dif_sleep_enc, dif_depre_enc,
  dif_wellr_enc, dif_anti_stress_enc, dif_anti_smoke_enc, dif_move_enc,
  c_val_nut_enc, c_val_obe_enc, c_val_sle_enc, c_val_dep_enc, c_val_wel_enc,
  c_val_anti_stress_enc, c_val_anti_smoke_enc, c_val_movement_enc,
  risk_tier
  -- NOTE: total_declining_count and critical_cval_count are intentionally
  -- EXCLUDED here so the model infers risk from raw dimensions only.
FROM `secure-totality-493616-b7.nytia_us_work.gold_features`;


-- Evaluate (held-out 80/20 split)
SELECT
  ROUND(accuracy, 4)  AS accuracy,
  ROUND(precision, 4) AS precision,
  ROUND(recall, 4)    AS recall,
  ROUND(f1_score, 4)  AS f1_score,
  ROUND(roc_auc, 4)   AS roc_auc
FROM ML.EVALUATE(MODEL `secure-totality-493616-b7.nytia_us_work.xgb_raw_only`);

-- Feature importance (should be evenly distributed across all 16 dimensions)
SELECT feature, ROUND(attribution, 4) AS importance
FROM ML.GLOBAL_EXPLAIN(MODEL `secure-totality-493616-b7.nytia_us_work.xgb_raw_only`)
ORDER BY attribution DESC;

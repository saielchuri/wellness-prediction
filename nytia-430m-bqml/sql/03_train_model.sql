-- ============================================================
-- Nytia Health 430M Pipeline — Step 3: Train BQML Model
-- Boosted Tree (XGBoost) trained on the full 430M Gold table
-- Target : secure-totality-493616-b7.nytia_us_work.xgb_risk_model
-- Region : US
-- Cost   : billed to secure-totality-493616-b7 (the project running
--          the job), NOT the sponsor project.
-- max_iterations=50 keeps training time/cost reasonable; the data is
-- rule-based and converges quickly.
-- ============================================================

CREATE OR REPLACE MODEL `secure-totality-493616-b7.nytia_us_work.xgb_risk_model`
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
  total_declining_count, critical_cval_count,
  risk_tier
FROM `secure-totality-493616-b7.nytia_us_work.gold_features`;

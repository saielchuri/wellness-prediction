-- ============================================================
-- Nytia Health 430M Pipeline — Step 5: Batch Score + Sample Export
-- Region : US
-- ============================================================

-- 5a. Batch score ALL 430M records (writes predictions to your project)
CREATE OR REPLACE TABLE `secure-totality-493616-b7.nytia_us_work.predictions_full` AS
SELECT *
FROM ML.PREDICT(
  MODEL `secure-totality-493616-b7.nytia_us_work.xgb_risk_model`,
  (SELECT
     dif_nutri_enc, dif_obesic_enc, dif_sleep_enc, dif_depre_enc,
     dif_wellr_enc, dif_anti_stress_enc, dif_anti_smoke_enc, dif_move_enc,
     c_val_nut_enc, c_val_obe_enc, c_val_sle_enc, c_val_dep_enc, c_val_wel_enc,
     c_val_anti_stress_enc, c_val_anti_smoke_enc, c_val_movement_enc,
     total_declining_count, critical_cval_count, risk_tier
   FROM `secure-totality-493616-b7.nytia_us_work.gold_features`)
);

-- Verify predicted distribution
SELECT
  predicted_risk_tier,
  COUNT(*) AS count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM `secure-totality-493616-b7.nytia_us_work.predictions_full`
GROUP BY predicted_risk_tier ORDER BY predicted_risk_tier;


-- 5b. Stratified 50K sample for Python SHAP analysis
CREATE OR REPLACE TABLE `secure-totality-493616-b7.nytia_us_work.shap_sample_50k` AS
WITH ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY risk_tier ORDER BY RAND()) AS rn
  FROM `secure-totality-493616-b7.nytia_us_work.gold_features`
)
SELECT * EXCEPT(rn)
FROM ranked
WHERE (risk_tier = 0 AND rn <= 16667)
   OR (risk_tier = 1 AND rn <= 16667)
   OR (risk_tier = 2 AND rn <= 16666);

SELECT risk_tier, COUNT(*) AS count
FROM `secure-totality-493616-b7.nytia_us_work.shap_sample_50k`
GROUP BY risk_tier ORDER BY risk_tier;

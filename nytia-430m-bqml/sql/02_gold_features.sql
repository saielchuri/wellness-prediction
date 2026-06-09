-- ============================================================
-- Nytia Health 430M Pipeline — Step 2: Silver → Gold
-- Ordinal encoding + decline flags + compound features + risk tier
-- Source : secure-totality-493616-b7.nytia_us_work.silver_validated
-- Target : secure-totality-493616-b7.nytia_us_work.gold_features
-- Region : US
-- Note   : c_val_nut_enc is INCLUDED (the earlier zero-variance
--          observation was a 200K sampling artifact, confirmed by sponsor).
-- ============================================================

CREATE OR REPLACE TABLE `secure-totality-493616-b7.nytia_us_work.gold_features` AS
WITH encoded AS (
  SELECT
    CASE dif_nutri WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_nutri_enc,
    CASE dif_obesic WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_obesic_enc,
    CASE dif_sleep WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_sleep_enc,
    CASE dif_depre WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_depre_enc,
    CASE dif_wellr WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_wellr_enc,
    CASE dif_anti_stress WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_anti_stress_enc,
    CASE dif_anti_smoke WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_anti_smoke_enc,
    CASE dif_move WHEN '(-1000)-(-250)' THEN 1 WHEN '(-250)-0' THEN 2 WHEN '0-250' THEN 3 WHEN '250-1000' THEN 4 END AS dif_move_enc,
    CASE c_val_nut WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_nut_enc,
    CASE c_val_obe WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_obe_enc,
    CASE c_val_sle WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_sle_enc,
    CASE c_val_dep WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_dep_enc,
    CASE c_val_wel WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_wel_enc,
    CASE c_val_anti_stress WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_anti_stress_enc,
    CASE c_val_anti_smoke WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_anti_smoke_enc,
    CASE c_val_movement WHEN '0-400' THEN 1 WHEN '400-600' THEN 2 WHEN '600-1000' THEN 3 END AS c_val_movement_enc,
    recommendations, status_assessment
  FROM `secure-totality-493616-b7.nytia_us_work.silver_validated`
),
flagged AS (
  SELECT *,
    CASE WHEN dif_nutri_enc <= 2 THEN 1 ELSE 0 END AS declining_nutrition,
    CASE WHEN dif_obesic_enc <= 2 THEN 1 ELSE 0 END AS declining_obesity,
    CASE WHEN dif_sleep_enc <= 2 THEN 1 ELSE 0 END AS declining_sleep,
    CASE WHEN dif_depre_enc <= 2 THEN 1 ELSE 0 END AS declining_depression,
    CASE WHEN dif_wellr_enc <= 2 THEN 1 ELSE 0 END AS declining_wellbeing,
    CASE WHEN dif_anti_stress_enc <= 2 THEN 1 ELSE 0 END AS declining_anti_stress,
    CASE WHEN dif_anti_smoke_enc <= 2 THEN 1 ELSE 0 END AS declining_anti_smoke,
    CASE WHEN dif_move_enc <= 2 THEN 1 ELSE 0 END AS declining_movement
  FROM encoded
),
derived AS (
  SELECT *,
    (declining_nutrition + declining_obesity + declining_sleep + declining_depression
     + declining_wellbeing + declining_anti_stress + declining_anti_smoke + declining_movement) AS total_declining_count,
    (CASE WHEN c_val_nut_enc=1 THEN 1 ELSE 0 END + CASE WHEN c_val_obe_enc=1 THEN 1 ELSE 0 END
     + CASE WHEN c_val_sle_enc=1 THEN 1 ELSE 0 END + CASE WHEN c_val_dep_enc=1 THEN 1 ELSE 0 END
     + CASE WHEN c_val_wel_enc=1 THEN 1 ELSE 0 END + CASE WHEN c_val_anti_stress_enc=1 THEN 1 ELSE 0 END
     + CASE WHEN c_val_anti_smoke_enc=1 THEN 1 ELSE 0 END + CASE WHEN c_val_movement_enc=1 THEN 1 ELSE 0 END) AS critical_cval_count
  FROM flagged
)
SELECT *,
  CASE
    WHEN total_declining_count <= 3 AND critical_cval_count <= 1 THEN 0
    WHEN total_declining_count <= 4 AND critical_cval_count <= 3 THEN 1
    ELSE 2
  END AS risk_tier
FROM derived;

-- Verify risk distribution (full 430M)
SELECT
  risk_tier,
  CASE risk_tier WHEN 0 THEN 'Low' WHEN 1 THEN 'Moderate' WHEN 2 THEN 'High' END AS label,
  COUNT(*) AS count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM `secure-totality-493616-b7.nytia_us_work.gold_features`
GROUP BY risk_tier ORDER BY risk_tier;

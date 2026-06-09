-- ============================================================
-- Nytia Health 430M Pipeline — Step 7: Determinism Check
-- Tests whether the free-text status_assessment column is a
-- deterministic function of the 16 wellness features. If the two
-- counts below are equal, the text adds no independent information
-- (it is fully derived from the features), confirming the dataset
-- is rule-generated.
-- Region : US (READ-ONLY on sponsor source)
-- Runtime: ~1-2 min
-- ============================================================

SELECT
  COUNT(*)                                                              AS total_rows,
  COUNT(DISTINCT feature_sig)                                          AS unique_feature_combos,
  COUNT(DISTINCT CONCAT(feature_sig, '||', status_assessment))         AS unique_combo_plus_text
FROM (
  SELECT
    status_assessment,
    CONCAT(dif_nutri, c_val_nut, dif_obesic, c_val_obe, dif_sleep, TRIM(c_val_sle),
           dif_depre, c_val_dep, dif_wellr, c_val_wel, dif_anti_stress, c_val_anti_stress,
           dif_anti_smoke, c_val_anti_smoke, dif_move, c_val_movement) AS feature_sig
  FROM `northeastgroup4t.recom_dataset.generated_data_with_recom`
);

-- Result (full 430M):
--   total_rows             = 430,981,696
--   unique_feature_combos  = 429,981,696
--   unique_combo_plus_text = 429,981,696
-- The last two are equal -> status_assessment is 100% deterministic
-- from the features (no independent signal in the text).

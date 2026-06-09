-- ============================================================
-- Nytia Health 430M Pipeline — Step 1: Bronze → Silver
-- Validates the full 430M sponsor dataset (READ-ONLY source)
-- Source : northeastgroup4t.recom_dataset.generated_data_with_recom (READ ONLY)
-- Target : secure-totality-493616-b7.nytia_us_work.silver_validated
-- Region : US   (source dataset is in US; destination must match)
-- Note   : c_val_sle has a trailing newline in the source, so it is
--          TRIMmed here. The source table is never modified.
-- ============================================================

CREATE OR REPLACE TABLE `secure-totality-493616-b7.nytia_us_work.silver_validated` AS
SELECT
  dif_nutri, c_val_nut, dif_obesic, c_val_obe, dif_sleep,
  TRIM(c_val_sle) AS c_val_sle,
  dif_depre, c_val_dep, dif_wellr, c_val_wel, dif_anti_stress, c_val_anti_stress,
  dif_anti_smoke, c_val_anti_smoke, dif_move, c_val_movement,
  recommendations, status_assessment
FROM `northeastgroup4t.recom_dataset.generated_data_with_recom`
WHERE dif_nutri        IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND dif_obesic       IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND dif_sleep        IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND dif_depre        IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND dif_wellr        IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND dif_anti_stress  IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND dif_anti_smoke   IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND dif_move         IN ('(-1000)-(-250)','(-250)-0','0-250','250-1000')
  AND c_val_nut          IN ('0-400','400-600','600-1000')
  AND c_val_obe          IN ('0-400','400-600','600-1000')
  AND TRIM(c_val_sle)    IN ('0-400','400-600','600-1000')
  AND c_val_dep          IN ('0-400','400-600','600-1000')
  AND c_val_wel          IN ('0-400','400-600','600-1000')
  AND c_val_anti_stress  IN ('0-400','400-600','600-1000')
  AND c_val_anti_smoke   IN ('0-400','400-600','600-1000')
  AND c_val_movement     IN ('0-400','400-600','600-1000');

-- Verify: expect 430,981,696
SELECT COUNT(*) AS silver_count
FROM `secure-totality-493616-b7.nytia_us_work.silver_validated`;

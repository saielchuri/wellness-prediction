-- ============================================================
-- Nytia Health 430M Pipeline — Step 4: Evaluate Model
-- Region : US
-- ============================================================

-- 4a. Overall performance metrics
SELECT
  ROUND(accuracy, 4)  AS accuracy,
  ROUND(precision, 4) AS precision,
  ROUND(recall, 4)    AS recall,
  ROUND(f1_score, 4)  AS f1_score,
  ROUND(roc_auc, 4)   AS roc_auc
FROM ML.EVALUATE(MODEL `secure-totality-493616-b7.nytia_us_work.xgb_risk_model`);

-- 4b. Global feature importance (which features drive predictions)
SELECT *
FROM ML.GLOBAL_EXPLAIN(MODEL `secure-totality-493616-b7.nytia_us_work.xgb_risk_model`)
ORDER BY attribution DESC;

-- 4c. Confusion matrix
SELECT *
FROM ML.CONFUSION_MATRIX(MODEL `secure-totality-493616-b7.nytia_us_work.xgb_risk_model`);

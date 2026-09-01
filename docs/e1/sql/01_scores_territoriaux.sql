SELECT geographic_code, geographic_name, score, risk_level
FROM analytics_risk_scores
WHERE geographic_level = 'department'
  AND reference_period = '2025-02'
  AND model_is_active = TRUE
ORDER BY score DESC
LIMIT 10;

SELECT scores.geographic_code,
       scores.geographic_name,
       scores.score,
       factors.indicator_code,
       factors.contribution
FROM analytics_risk_scores AS scores
JOIN analytics_score_factors AS factors
  ON factors.geographic_level = scores.geographic_level
 AND factors.geographic_code = scores.geographic_code
 AND factors.reference_period = scores.reference_period
 AND factors.model_code = scores.model_code
 AND factors.model_version = scores.model_version
WHERE scores.geographic_level = 'region'
  AND scores.reference_period = '2025-02'
  AND scores.model_is_active = TRUE
  AND factors.indicator_code = 'taux_pauvrete'
ORDER BY factors.contribution DESC
LIMIT 200;

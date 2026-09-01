SELECT reference_period, value_numeric, variation_numeric, variation_unit
FROM analytics_observations
WHERE geographic_level = 'department'
  AND geographic_code = '59'
  AND indicator_code = 'dossiers_surendettement_1000_habitants'
  AND reference_period >= '2024-01'
  AND reference_period <= '2025-12'
ORDER BY reference_period
LIMIT 200;

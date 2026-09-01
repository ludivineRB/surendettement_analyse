SELECT AVG(value_numeric) AS average_value
FROM analytics_macro_regions
WHERE reference_year = 2022
  AND indicator_code = 'part_familles_monoparentales'
LIMIT 1;

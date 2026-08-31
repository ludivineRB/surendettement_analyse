# Synthèse du benchmark

## FAIT DOCUMENTÉ

Parser benchmarks measure parsing; SQLGlot validation is the security boundary.

## MESURE DU POC

Métriques LLM : `{"decision_accuracy": 1.0, "sql_syntax_validity_rate": 1.0, "schema_conformity_rate": 1.0, "execution_accuracy": 1.0, "business_accuracy": 1.0, "correct_treatment_rate": 1.0, "refusal_precision": 1.0, "refusal_recall": 1.0, "clarification_accuracy": 1.0, "dangerous_request_blocking_rate": 1.0, "prompt_injection_blocking_rate": 1.0, "latency_mean_ms": 0.0021790319806314074, "latency_p50_ms": 0.0011584997992031276, "latency_p95_ms": 0.005909008905291557, "input_tokens_mean": 0, "output_tokens_mean": 0, "total_tokens_mean": 0, "total_tokens": 0, "call_count": 32, "calls_per_question": 1.0, "estimated_cost_mean": null, "estimated_cost_p95": null, "sample_size_warning": "\u00c9chantillon trop petit pour une preuve statistique robuste."}`
Parseurs mesurés : 6.

## ESTIMATION

No CO2e estimate and no cost estimate without documented dated factors.

## RECOMMANDATION

LLM decision -> SQLGlot guard -> read-only SQLite -> oracle comparison.

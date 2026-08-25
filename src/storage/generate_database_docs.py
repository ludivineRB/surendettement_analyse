"""Generate a deterministic DBML MPD from PostgreSQL catalog metadata.

Only schema metadata is queried. No application-table rows are read.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


DEFAULT_CONTAINER = "surendettement_staging_validation-postgres-1"
DEFAULT_OUTPUT = Path("database-doc/physical/mpd.dbml")
DEFAULT_METADATA_OUTPUT = Path("database-doc/extracted/metadata.json")
DEFAULT_SCHEMA_OUTPUT = Path("database-doc/extracted/schema.sql")
DEFAULT_DICTIONARY_OUTPUT = Path("database-doc/dictionary/data-dictionary.md")
SCHEMAS = ("assistant", "public")

CATALOG_SQL = r"""
WITH relations AS (
    SELECT n.nspname AS schema_name,
           c.relname AS relation_name,
           c.relkind AS relation_kind
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname IN ('assistant', 'public')
       AND c.relkind IN ('r', 'p', 'v', 'm')
), columns AS (
    SELECT n.nspname AS schema_name,
           c.relname AS relation_name,
           a.attnum AS ordinal,
           a.attname AS column_name,
           pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
           a.attnotnull AS not_null,
           COALESCE(pg_get_expr(d.adbin, d.adrelid), '') AS default_value
      FROM pg_attribute a
      JOIN pg_class c ON c.oid = a.attrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
 LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
     WHERE n.nspname IN ('assistant', 'public')
       AND c.relkind IN ('r', 'p', 'v', 'm')
       AND a.attnum > 0
       AND NOT a.attisdropped
), constraints_ AS (
    SELECT n.nspname AS schema_name,
           c.relname AS relation_name,
           con.conname AS constraint_name,
           con.contype AS constraint_type,
           pg_get_constraintdef(con.oid, true) AS definition
      FROM pg_constraint con
      JOIN pg_class c ON c.oid = con.conrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname IN ('assistant', 'public')
), indexes AS (
    SELECT schemaname AS schema_name,
           tablename AS relation_name,
           indexname AS index_name,
           indexdef AS definition
      FROM pg_indexes
     WHERE schemaname IN ('assistant', 'public')
), sequences AS (
    SELECT schemaname AS schema_name,
           sequencename AS sequence_name,
           data_type,
           start_value,
           increment_by,
           min_value,
           max_value,
           cycle
      FROM pg_sequences
     WHERE schemaname IN ('assistant', 'public')
), triggers AS (
    SELECT n.nspname AS schema_name,
           c.relname AS relation_name,
           t.tgname AS trigger_name,
           pg_get_triggerdef(t.oid, true) AS definition
      FROM pg_trigger t
      JOIN pg_class c ON c.oid = t.tgrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname IN ('assistant', 'public')
       AND NOT t.tgisinternal
), types AS (
    SELECT n.nspname AS schema_name,
           t.typname AS type_name,
           t.typtype AS type_kind,
           COALESCE(string_agg(e.enumlabel, ',' ORDER BY e.enumsortorder), '') AS enum_values
      FROM pg_type t
      JOIN pg_namespace n ON n.oid = t.typnamespace
 LEFT JOIN pg_enum e ON e.enumtypid = t.oid
     WHERE n.nspname IN ('assistant', 'public')
       AND t.typtype IN ('e', 'd')
  GROUP BY n.nspname, t.typname, t.typtype
), views AS (
    SELECT schemaname AS schema_name,
           viewname AS view_name,
           definition
      FROM pg_views
     WHERE schemaname IN ('assistant', 'public')
)
SELECT json_build_object(
    'relations', COALESCE((SELECT json_agg(relations ORDER BY schema_name, relation_name)
                             FROM relations), '[]'::json),
    'columns', COALESCE((SELECT json_agg(columns ORDER BY schema_name, relation_name, ordinal)
                           FROM columns), '[]'::json),
    'constraints', COALESCE((SELECT json_agg(constraints_ ORDER BY schema_name, relation_name, constraint_name)
                               FROM constraints_), '[]'::json),
    'indexes', COALESCE((SELECT json_agg(indexes ORDER BY schema_name, relation_name, index_name)
                           FROM indexes), '[]'::json),
    'sequences', COALESCE((SELECT json_agg(sequences ORDER BY schema_name, sequence_name)
                             FROM sequences), '[]'::json),
    'triggers', COALESCE((SELECT json_agg(triggers ORDER BY schema_name, relation_name, trigger_name)
                            FROM triggers), '[]'::json),
    'types', COALESCE((SELECT json_agg(types ORDER BY schema_name, type_name)
                         FROM types), '[]'::json),
    'views', COALESCE((SELECT json_agg(views ORDER BY schema_name, view_name)
                         FROM views), '[]'::json)
);
"""

FK_RE = re.compile(
    r"FOREIGN KEY \((?P<columns>[^)]+)\) REFERENCES "
    r"(?:(?P<schema>[\w]+)\.)?(?P<table>[\w]+)\s*\((?P<targets>[^)]+)\)"
)
PK_RE = re.compile(r"PRIMARY KEY \((?P<columns>[^)]+)\)")
UNIQUE_RE = re.compile(r"UNIQUE \((?P<columns>[^)]+)\)")

TABLE_DEFINITIONS = {
    "source_documents": "Documents sources collectés et versions d'extraction.",
    "indicators": "Catalogue opérationnel des indicateurs.",
    "observations": "Mesures extraites d'un document pour un territoire et une période.",
    "pipeline_runs": "Exécutions et contrôles qualité des pipelines.",
    "dim_region": "Référentiel analytique des régions.",
    "dim_department": "Référentiel analytique des départements.",
    "dim_period": "Référentiel des périodes annuelles et mensuelles.",
    "dim_indicator": "Catalogue analytique multi-sources des indicateurs.",
    "fact_bdf_statinfo": "Faits mensuels issus de Banque de France Stat Info.",
    "fact_insee_macro": "Faits macroéconomiques départementaux issus de l'INSEE.",
    "fact_macro_override": "Corrections analytiques explicites et traçables.",
    "fact_surendettement": "Ancien fait départemental de surendettement.",
    "surendettement_data": "Ancien stockage générique région-année-indicateur.",
    "risk_score_models": "Modèles de score de risque versionnés.",
    "risk_score_indicator_configs": "Poids et règles d'un indicateur dans un modèle.",
    "risk_scores": "Scores calculés par territoire, période et modèle.",
    "risk_score_details": "Contributions des indicateurs à un score.",
    "assistant_conversation": "Conversations d'un utilisateur avec l'assistant Django.",
    "assistant_conversationmessage": "Messages et résultats enregistrés dans une conversation.",
    "assistant_ragsource": "Sources documentaires du corpus RAG Django.",
    "assistant_ragdocument": "Documents logiques du corpus RAG Django.",
    "assistant_ragdocumentversion": "Versions approuvées des documents RAG Django.",
    "assistant_ragchunk": "Fragments recherchables d'une version de document RAG.",
    "assistant_ragindexrun": "Exécutions d'indexation du corpus RAG Django.",
    "corpus_chunks": "Fragments recherchables du corpus de l'Assistant API.",
    "sql_executions": "Audit des générations et exécutions de SQL.",
    "schema_migrations": "Registre technique des migrations appliquées.",
    "schema_deprecations": "Registre des objets analytiques dépréciés.",
    "pipeline_metadata": "Métadonnées techniques de construction de l'entrepôt.",
}

COLUMN_DEFINITIONS = {
    "id": "Identifiant technique de l'occurrence.",
    "code": "Code métier stable.",
    "name": "Nom de l'occurrence.",
    "title": "Titre lisible.",
    "label": "Libellé métier.",
    "description": "Description fonctionnelle.",
    "created_at": "Date et heure de création.",
    "updated_at": "Date et heure de dernière mise à jour.",
    "started_at": "Date et heure de début du traitement.",
    "finished_at": "Date et heure de fin du traitement.",
    "reference_year": "Année de référence de la mesure.",
    "reference_period": "Période de référence de la mesure ou du document.",
    "reference_month_number": "Numéro du mois dans l'année de référence.",
    "value": "Valeur numérique de la mesure.",
    "value_numeric": "Valeur numérique de l'observation.",
    "value_text": "Valeur textuelle lorsque la mesure n'est pas numérique.",
    "status": "État courant selon le cycle de vie de l'objet.",
    "is_active": "Indique si l'objet est actif.",
    "content": "Contenu textuel enregistré.",
    "password": "Empreinte du mot de passe gérée par Django.",
    "email": "Adresse électronique de l'utilisateur.",
    "username": "Identifiant de connexion de l'utilisateur.",
    "generated_sql": "Instruction SQL générée par l'assistant.",
    "search_vector": "Vecteur PostgreSQL utilisé pour la recherche plein texte.",
}


def _catalog(container: str) -> dict:
    command = [
        "docker",
        "exec",
        "-i",
        container,
        "sh",
        "-c",
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
        "-X -A -t -v ON_ERROR_STOP=1",
    ]
    completed = subprocess.run(
        command,
        input=CATALOG_SQL,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "PostgreSQL extraction failed")
    return json.loads(completed.stdout.strip())


def _schema_dump(container: str) -> str:
    command = [
        "docker",
        "exec",
        container,
        "sh",
        "-c",
        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
        "--schema-only --no-owner --no-privileges "
        "--schema=assistant --schema=public",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "PostgreSQL schema dump failed")
    normalized = completed.stdout.replace("\r\n", "\n")
    stable_lines = [
        line
        for line in normalized.splitlines()
        if not line.startswith(("\\restrict ", "\\unrestrict "))
    ]
    return "\n".join(stable_lines).rstrip() + "\n"


def _write_if_changed(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == content:
        return f"unchanged: {path}"
    path.write_text(content, encoding="utf-8")
    return f"updated: {path}"


def _column_list(definition: str, pattern: re.Pattern[str]) -> set[str]:
    match = pattern.search(definition)
    if not match:
        return set()
    return {item.strip().strip('"') for item in match.group("columns").split(",")}


def _dbml_type(pg_type: str) -> str:
    return pg_type.replace(" ", "_") if pg_type in {
        "timestamp with time zone",
        "timestamp without time zone",
        "double precision",
    } else pg_type


def build_dbml(metadata: dict) -> str:
    relations = {
        (item["schema_name"], item["relation_name"]): item
        for item in metadata["relations"]
    }
    columns: dict[tuple[str, str], list[dict]] = defaultdict(list)
    constraints: dict[tuple[str, str], list[dict]] = defaultdict(list)
    indexes: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in metadata["columns"]:
        columns[(item["schema_name"], item["relation_name"])].append(item)
    for item in metadata["constraints"]:
        constraints[(item["schema_name"], item["relation_name"])].append(item)
    for item in metadata["indexes"]:
        indexes[(item["schema_name"], item["relation_name"])].append(item)

    output = [
        "// Generated from PostgreSQL catalogs; do not edit manually.",
        "// Source schemas: assistant, public. Temporary schemas are inventoried separately.",
        "",
    ]
    references: list[str] = []
    for key in sorted(relations):
        relation = relations[key]
        schema, table = key
        table_constraints = constraints[key]
        primary = set().union(*(
            _column_list(item["definition"], PK_RE)
            for item in table_constraints if item["constraint_type"] == "p"
        ))
        unique = set().union(*(
            _column_list(item["definition"], UNIQUE_RE)
            for item in table_constraints if item["constraint_type"] == "u"
        ))
        kind = {"v": "view", "m": "materialized view", "p": "partitioned table"}.get(
            relation["relation_kind"], "table"
        )
        output.append(f'Table "{schema}"."{table}" {{')
        for column in columns[key]:
            flags = []
            name = column["column_name"]
            if name in primary:
                flags.append("pk")
            if name in unique:
                flags.append("unique")
            if column["not_null"]:
                flags.append("not null")
            default = column["default_value"]
            if default and "nextval(" not in default:
                escaped = default.replace('"', '\\"')
                flags.append(f'note: "default: {escaped}"')
            suffix = f" [{', '.join(flags)}]" if flags else ""
            output.append(f'  "{name}" {_dbml_type(column["data_type"])}{suffix}')
        notes = [f"PostgreSQL {kind}"]
        notes.extend(
            f'{item["constraint_name"]}: {item["definition"]}'
            for item in table_constraints if item["constraint_type"] == "c"
        )
        output.append(f'  Note: "{"; ".join(notes).replace(chr(34), chr(92) + chr(34))}"')
        important_indexes = [
            item for item in indexes[key]
            if "_pkey" not in item["index_name"] and " UNIQUE INDEX " not in item["definition"]
        ]
        if important_indexes:
            output.append("  indexes {")
            for item in important_indexes:
                match = re.search(r"USING (\w+) \((.+)\)$", item["definition"])
                if match:
                    expression = match.group(2)
                    output.append(
                        f'    ({expression}) [name: "{item["index_name"]}", '
                        f'note: "using {match.group(1)}"]'
                    )
            output.append("  }")
        output.extend(["}", ""])
        for item in table_constraints:
            if item["constraint_type"] != "f":
                continue
            match = FK_RE.search(item["definition"])
            if not match:
                continue
            source_columns = ", ".join(
                f'"{value.strip().strip(chr(34))}"'
                for value in match.group("columns").split(",")
            )
            target_columns = ", ".join(
                f'"{value.strip().strip(chr(34))}"'
                for value in match.group("targets").split(",")
            )
            target_schema = match.group("schema") or schema
            references.append(
                f'Ref "{item["constraint_name"]}": '
                f'"{schema}"."{table}".({source_columns}) > '
                f'"{target_schema}"."{match.group("table")}".({target_columns})'
            )
    output.extend(sorted(references))
    return "\n".join(output).rstrip() + "\n"


def _table_source(schema: str, table: str) -> str:
    if schema == "assistant":
        return "Assistant API"
    if table.startswith(("auth_", "django_")):
        return "Application Django"
    if table.startswith("assistant_"):
        return "Application Django / Assistant"
    if "bdf" in table or table in {"source_documents", "observations"}:
        return "Banque de France / pipeline"
    if "insee" in table:
        return "INSEE / pipeline"
    if table.startswith("risk_score"):
        return "Calcul de score"
    if table.startswith("dim_"):
        return "Référentiel conformé"
    if table.startswith("analytics_"):
        return "Vue de publication"
    return "Application / pipeline interne"


def _table_status(table: str) -> str:
    if table in {
        "fact_surendettement",
        "v_surendettement_annual",
        "v_surendettement_with_insee_macro",
    }:
        return "Déprécié"
    if table == "surendettement_data":
        return "Historique"
    return "Actif"


def _sensitivity(schema: str, table: str, column: str) -> str:
    if table == "auth_user":
        if column == "password":
            return "Sensible"
        return "Personnel"
    if table in {"django_session", "assistant_conversationmessage"}:
        return "Sensible"
    if table in {"assistant_conversation", "django_admin_log"}:
        return "Personnel"
    if table == "sql_executions" and column in {
        "actor_id", "question", "generated_sql", "interpretation_json"
    }:
        return "Potentiellement personnel/sensible"
    if schema == "assistant" or table.startswith("assistant_rag"):
        return "Interne"
    if table.startswith(("fact_", "dim_", "analytics_", "v_")):
        return "Public"
    return "Interne"


def _definition(column: str) -> str:
    if column in COLUMN_DEFINITIONS:
        return COLUMN_DEFINITIONS[column]
    readable = column.replace("_id", "").replace("_", " ")
    if column.endswith("_id"):
        return f"Identifiant de référence vers {readable}."
    if column.endswith("_code"):
        return f"Code de {readable.removesuffix(' code')}."
    if column.endswith("_json") or column in {"metadata", "response_metadata", "citations"}:
        return f"Structure JSON contenant {readable.replace(' json', '')}."
    if column.endswith("_at"):
        return f"Date et heure de {readable.removesuffix(' at')}."
    if column.startswith("is_"):
        return f"Indique si {readable.removeprefix('is ')}."
    return f"Champ {readable} de l'objet documenté."


def _escape_markdown(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_dictionary(metadata: dict) -> str:
    constraints: dict[tuple[str, str], list[dict]] = defaultdict(list)
    columns: dict[tuple[str, str], list[dict]] = defaultdict(list)
    indexes: dict[tuple[str, str], list[dict]] = defaultdict(list)
    relations = {
        (item["schema_name"], item["relation_name"]): item
        for item in metadata["relations"]
    }
    for item in metadata["constraints"]:
        constraints[(item["schema_name"], item["relation_name"])].append(item)
    for item in metadata["columns"]:
        columns[(item["schema_name"], item["relation_name"])].append(item)
    for item in metadata["indexes"]:
        indexes[(item["schema_name"], item["relation_name"])].append(item)

    lines = [
        "# Dictionnaire de données",
        "",
        "Généré depuis les catalogues PostgreSQL. Aucune ligne métier n'est lue.",
        "Les exemples sont limités aux défauts déclarés dans le schéma ; sinon",
        "ils sont indiqués « Non extrait » afin de ne pas créer de donnée fictive.",
        "",
    ]
    for key in sorted(relations):
        schema, table = key
        relation = relations[key]
        kind = {"r": "table", "p": "table partitionnée", "v": "vue", "m": "vue matérialisée"}[
            relation["relation_kind"]
        ]
        lines.extend([
            f"## `{schema}.{table}`",
            "",
            f"**Type :** {kind}  ",
            f"**Définition :** {TABLE_DEFINITIONS.get(table, f'Objet PostgreSQL {table}.')}  ",
            f"**Source :** {_table_source(schema, table)}  ",
            f"**Statut :** {_table_status(table)}",
            "",
            "| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ])
        table_constraints = constraints[key]
        for column in columns[key]:
            name = column["column_name"]
            relevant = [
                item for item in table_constraints
                if re.search(rf"\b{re.escape(name)}\b", item["definition"])
            ]
            relevant_unique_indexes = [
                item for item in indexes[key]
                if "CREATE UNIQUE INDEX" in item["definition"]
                and re.search(rf"\b{re.escape(name)}\b", item["definition"])
            ]
            key_labels = []
            for item in relevant:
                label = {"p": "PK", "f": "FK", "u": "Unique"}.get(item["constraint_type"])
                if label and label not in key_labels:
                    key_labels.append(label)
            if relevant_unique_indexes and not any(
                label.startswith("Unique") for label in key_labels
            ):
                key_labels.append("Unique (index, composite possible)")
            rules = [
                item["definition"] for item in relevant
                if item["constraint_type"] in {"c", "f", "u"}
            ]
            if column["default_value"]:
                rules.append(f"DEFAULT {column['default_value']}")
            rules.extend(
                f"INDEX UNIQUE {item['index_name']}: {item['definition']}"
                for item in relevant_unique_indexes
                if not any(
                    constraint["constraint_name"] == item["index_name"]
                    for constraint in relevant
                )
            )
            example = column["default_value"] or "Non extrait"
            row = [
                f"`{name}`",
                _definition(name),
                f"`{column['data_type']}`",
                "Oui" if column["not_null"] else "Non",
                ", ".join(key_labels) or "—",
                _table_source(schema, table),
                f"`{example}`" if example != "Non extrait" else example,
                "; ".join(rules) or "Aucune contrainte spécifique déclarée",
                _sensitivity(schema, table, name),
                _table_status(table),
            ]
            lines.append("| " + " | ".join(_escape_markdown(value) for value in row) + " |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT
    )
    parser.add_argument("--schema-output", type=Path, default=DEFAULT_SCHEMA_OUTPUT)
    parser.add_argument(
        "--dictionary-output", type=Path, default=DEFAULT_DICTIONARY_OUTPUT
    )
    args = parser.parse_args()
    metadata = _catalog(args.container)
    print(_write_if_changed(args.output, build_dbml(metadata)))
    metadata_content = json.dumps(
        metadata, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    print(_write_if_changed(args.metadata_output, metadata_content))
    print(_write_if_changed(args.schema_output, _schema_dump(args.container)))
    print(_write_if_changed(args.dictionary_output, build_dictionary(metadata)))


if __name__ == "__main__":
    main()

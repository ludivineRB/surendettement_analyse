--
-- PostgreSQL database dump
--


-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: assistant; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA assistant;


--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: corpus_chunks; Type: TABLE; Schema: assistant; Owner: -
--

CREATE TABLE assistant.corpus_chunks (
    chunk_id character(64) NOT NULL,
    source_id character varying(200) NOT NULL,
    source_url text NOT NULL,
    source_title text NOT NULL,
    publisher character varying(100) NOT NULL,
    reference_period character varying(100) NOT NULL,
    geographic_scope character varying(200) NOT NULL,
    section text NOT NULL,
    ordinal integer NOT NULL,
    content text NOT NULL,
    content_sha256 character(64) NOT NULL,
    source_sha256 character(64) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    indexed_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (((setweight(to_tsvector('french'::regconfig, COALESCE(source_title, ''::text)), 'A'::"char") || setweight(to_tsvector('french'::regconfig, COALESCE(section, ''::text)), 'A'::"char")) || setweight(to_tsvector('french'::regconfig, COALESCE(content, ''::text)), 'B'::"char"))) STORED,
    CONSTRAINT corpus_chunks_ordinal_check CHECK ((ordinal >= 0))
);


--
-- Name: schema_migrations; Type: TABLE; Schema: assistant; Owner: -
--

CREATE TABLE assistant.schema_migrations (
    version character varying(64) NOT NULL,
    applied_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: sql_executions; Type: TABLE; Schema: assistant; Owner: -
--

CREATE TABLE assistant.sql_executions (
    execution_id uuid NOT NULL,
    request_id uuid NOT NULL,
    actor_id character varying(128),
    question text NOT NULL,
    interpretation_json text DEFAULT '{}'::text NOT NULL,
    schema_version character varying(64) NOT NULL,
    generated_sql text NOT NULL,
    validation_status character varying(32) NOT NULL,
    validation_error character varying(512),
    duration_ms integer,
    row_count integer,
    plan_cost double precision,
    prompt_version character varying(64) NOT NULL,
    model_version character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: dim_department; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_department (
    departement_code text NOT NULL,
    departement_name text,
    region_name text,
    is_metropolitan_scope integer NOT NULL,
    region_code text
);


--
-- Name: dim_indicator; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_indicator (
    indicator_key text NOT NULL,
    source_system text NOT NULL,
    indicator_code text NOT NULL,
    indicator_name text,
    indicator_group text,
    unit text,
    aggregation_rule text
);


--
-- Name: dim_region; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_region (
    region_code character varying(16) NOT NULL,
    region_name character varying(255) NOT NULL,
    is_metropolitan_scope boolean NOT NULL
);


--
-- Name: fact_insee_macro; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fact_insee_macro (
    reference_year integer NOT NULL,
    departement_code text NOT NULL,
    indicator_key text NOT NULL,
    value real NOT NULL,
    source_dataset text,
    pipeline_version text
);


--
-- Name: v_insee_macro_region; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_insee_macro_region AS
 SELECT m.reference_year,
    r.region_code,
    r.region_name,
    i.indicator_code,
    i.indicator_name,
    i.indicator_group,
    i.aggregation_rule,
    sum(m.value) AS value
   FROM (((public.fact_insee_macro m
     JOIN public.dim_department d ON ((d.departement_code = m.departement_code)))
     JOIN public.dim_region r ON (((r.region_code)::text = d.region_code)))
     JOIN public.dim_indicator i ON ((i.indicator_key = m.indicator_key)))
  WHERE (i.source_system = 'insee_macro'::text)
  GROUP BY m.reference_year, r.region_code, r.region_name, i.indicator_code, i.indicator_name, i.indicator_group, i.aggregation_rule;


--
-- Name: v_insee_macro_region_selected; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_insee_macro_region_selected AS
 WITH ratio_definitions(indicator_code, indicator_name, indicator_group, numerator_code, denominator_code) AS (
         VALUES ('part_population_0014'::text,'Part de la population de 0 à 14 ans'::text,'démographie'::text,'P22_POP0014'::text,'P22_POP'::text), ('part_population_1529'::text,'Part de la population de 15 à 29 ans'::text,'démographie'::text,'P22_POP1529'::text,'P22_POP'::text), ('part_population_3044'::text,'Part de la population de 30 à 44 ans'::text,'démographie'::text,'P22_POP3044'::text,'P22_POP'::text), ('part_population_4559'::text,'Part de la population de 45 à 59 ans'::text,'démographie'::text,'P22_POP4559'::text,'P22_POP'::text), ('part_population_6074'::text,'Part de la population de 60 à 74 ans'::text,'démographie'::text,'P22_POP6074'::text,'P22_POP'::text), ('part_population_7589'::text,'Part de la population de 75 à 89 ans'::text,'démographie'::text,'P22_POP7589'::text,'P22_POP'::text), ('part_population_90p'::text,'Part de la population de 90 ans ou plus'::text,'démographie'::text,'P22_POP90P'::text,'P22_POP'::text), ('taux_activite_1564'::text,'Taux d’activité des 15 à 64 ans'::text,'emploi_chômage'::text,'P22_ACT1564'::text,'P22_POP1564'::text), ('taux_emploi_1564'::text,'Taux d’emploi des 15 à 64 ans'::text,'emploi_chômage'::text,'P22_ACTOCC1564'::text,'P22_POP1564'::text), ('taux_chomage_1564'::text,'Taux de chômage des 15 à 64 ans'::text,'emploi_chômage'::text,'P22_CHOM1564'::text,'P22_ACT1564'::text), ('part_residences_principales'::text,'Part des résidences principales'::text,'logement'::text,'P22_RP'::text,'P22_LOG'::text), ('part_residences_secondaires'::text,'Part des résidences secondaires'::text,'logement'::text,'P22_RSECOCC'::text,'P22_LOG'::text), ('part_logements_vacants'::text,'Part des logements vacants'::text,'logement'::text,'P22_LOGVAC'::text,'P22_LOG'::text), ('part_proprietaires'::text,'Part des résidences principales occupées par des propriétaires'::text,'logement'::text,'P22_RP_PROP'::text,'P22_RP'::text), ('part_locataires'::text,'Part des résidences principales occupées par des locataires'::text,'logement'::text,'P22_RP_LOC'::text,'P22_RP'::text), ('part_menages_seuls'::text,'Part des ménages d’une personne'::text,'familles'::text,'C22_MENPSEUL'::text,'C22_MEN'::text), ('part_familles_monoparentales'::text,'Part des familles monoparentales'::text,'familles'::text,'C22_FAMMONO'::text,'C22_FAM'::text), ('part_sans_diplome'::text,'Part des personnes sans diplôme ou titulaires au plus du CEP'::text,'formation'::text,'P22_NSCOL15P_DIPLMIN'::text,'P22_NSCOL15P'::text), ('part_diplomees_bac5'::text,'Part des diplômés Bac +5 ou plus'::text,'formation'::text,'P22_NSCOL15P_SUP5'::text,'P22_NSCOL15P'::text)
        ), derived AS (
         SELECT numerator.reference_year,
            numerator.region_code,
            numerator.region_name,
            definitions.indicator_code,
            definitions.indicator_name,
            definitions.indicator_group,
            'derived_ratio'::text AS aggregation_rule,
            (((100.0)::double precision * numerator.value) / NULLIF(denominator.value, (0)::double precision)) AS value
           FROM ((ratio_definitions definitions
             JOIN public.v_insee_macro_region numerator ON ((numerator.indicator_code = definitions.numerator_code)))
             JOIN public.v_insee_macro_region denominator ON (((denominator.reference_year = numerator.reference_year) AND ((denominator.region_code)::text = (numerator.region_code)::text) AND (denominator.indicator_code = definitions.denominator_code))))
        )
 SELECT v_insee_macro_region.reference_year,
    v_insee_macro_region.region_code,
    v_insee_macro_region.region_name,
    v_insee_macro_region.indicator_code,
    v_insee_macro_region.indicator_name,
    v_insee_macro_region.indicator_group,
    v_insee_macro_region.aggregation_rule,
    v_insee_macro_region.value
   FROM public.v_insee_macro_region
UNION ALL
 SELECT derived.reference_year,
    derived.region_code,
    derived.region_name,
    derived.indicator_code,
    derived.indicator_name,
    derived.indicator_group,
    derived.aggregation_rule,
    derived.value
   FROM derived;


--
-- Name: analytics_macro_regions; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.analytics_macro_regions AS
 SELECT reference_year,
    region_name,
    indicator_code,
    indicator_name,
    indicator_group,
    aggregation_rule,
    value AS value_numeric
   FROM public.v_insee_macro_region_selected;


--
-- Name: risk_score_models; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.risk_score_models (
    id integer NOT NULL,
    code character varying(128) NOT NULL,
    name character varying(255) NOT NULL,
    version character varying(64) NOT NULL,
    description text,
    normalization_method character varying(64) NOT NULL,
    minimum_coverage_ratio numeric(8,6) NOT NULL,
    is_active boolean NOT NULL,
    configuration_json text NOT NULL,
    created_at character varying(32) NOT NULL,
    updated_at character varying(32) NOT NULL,
    CONSTRAINT ck_risk_score_models_coverage CHECK (((minimum_coverage_ratio >= (0)::numeric) AND (minimum_coverage_ratio <= (1)::numeric)))
);


--
-- Name: risk_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.risk_scores (
    id integer NOT NULL,
    risk_score_model_id integer NOT NULL,
    geographic_level character varying(32) NOT NULL,
    geographic_code character varying(64) NOT NULL,
    geographic_name character varying(255),
    reference_period character varying(16) NOT NULL,
    score numeric(12,8),
    risk_level character varying(32),
    coverage_ratio numeric(8,6) NOT NULL,
    status character varying(32) NOT NULL,
    missing_indicators_json text NOT NULL,
    warnings_json text NOT NULL,
    calculated_at character varying(32) NOT NULL,
    created_at character varying(32) NOT NULL,
    updated_at character varying(32) NOT NULL,
    CONSTRAINT ck_risk_scores_coverage CHECK (((coverage_ratio >= (0)::numeric) AND (coverage_ratio <= (1)::numeric))),
    CONSTRAINT ck_risk_scores_score CHECK (((score IS NULL) OR ((score >= (0)::numeric) AND (score <= (100)::numeric)))),
    CONSTRAINT ck_risk_scores_status CHECK (((status)::text = ANY ((ARRAY['valid'::character varying, 'partial'::character varying, 'insufficient_data'::character varying, 'error'::character varying])::text[])))
);


--
-- Name: analytics_model_comparisons; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.analytics_model_comparisons AS
 SELECT score_a.geographic_level,
    score_a.geographic_code,
    score_a.geographic_name,
    score_a.reference_period,
    model_a.code AS model_code,
    model_a.version AS version_a,
    model_b.version AS version_b,
    score_a.score AS score_a,
    score_b.score AS score_b,
    (score_b.score - score_a.score) AS score_change
   FROM (((public.risk_scores score_a
     JOIN public.risk_score_models model_a ON ((model_a.id = score_a.risk_score_model_id)))
     JOIN public.risk_scores score_b ON ((((score_b.geographic_level)::text = (score_a.geographic_level)::text) AND ((score_b.geographic_code)::text = (score_a.geographic_code)::text) AND ((score_b.reference_period)::text = (score_a.reference_period)::text))))
     JOIN public.risk_score_models model_b ON (((model_b.id = score_b.risk_score_model_id) AND ((model_b.code)::text = (model_a.code)::text) AND ((model_b.version)::text > (model_a.version)::text))));


--
-- Name: indicators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.indicators (
    id integer NOT NULL,
    code character varying(128) NOT NULL,
    label character varying(512) NOT NULL,
    category character varying(255),
    description text,
    default_unit character varying(64),
    created_at character varying(32) NOT NULL,
    updated_at character varying(32) NOT NULL
);


--
-- Name: observations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.observations (
    id integer NOT NULL,
    source_document_id integer NOT NULL,
    indicator_id integer NOT NULL,
    idempotence_key character varying(64) NOT NULL,
    indicator_code character varying(128) NOT NULL,
    region_code character varying(16) NOT NULL,
    reference_period character varying(7) NOT NULL,
    geographic_level character varying(64) NOT NULL,
    geographic_code character varying(64),
    geographic_name character varying(255),
    value_numeric double precision,
    value_text text,
    unit character varying(64),
    observation_type character varying(64),
    comparison_period character varying(32),
    variation_numeric double precision,
    variation_unit character varying(64),
    page_number integer,
    source_label character varying(512),
    source_fragment text,
    extraction_method character varying(64) NOT NULL,
    confidence_score double precision,
    created_at character varying(32) NOT NULL,
    updated_at character varying(32) NOT NULL
);


--
-- Name: analytics_observations; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.analytics_observations AS
 SELECT observation.id,
    observation.indicator_code,
    indicator.label AS indicator_label,
    observation.geographic_level,
    observation.geographic_code,
    observation.geographic_name,
    observation.region_code,
    observation.reference_period,
    observation.value_numeric,
    observation.unit,
    observation.observation_type,
    observation.comparison_period,
    observation.variation_numeric,
    observation.variation_unit,
    observation.confidence_score,
    observation.updated_at
   FROM (public.observations observation
     JOIN public.indicators indicator ON ((indicator.id = observation.indicator_id)));


--
-- Name: pipeline_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pipeline_runs (
    id integer NOT NULL,
    pipeline_name character varying(128) NOT NULL,
    status character varying(32) NOT NULL,
    started_at character varying(32) NOT NULL,
    finished_at character varying(32),
    configuration_json text NOT NULL,
    step_results_json text NOT NULL,
    quality_report_json text NOT NULL,
    error_message text,
    CONSTRAINT ck_pipeline_runs_status CHECK (((status)::text = ANY ((ARRAY['running'::character varying, 'success'::character varying, 'failed'::character varying, 'quality_failed'::character varying])::text[])))
);


--
-- Name: analytics_pipeline_status; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.analytics_pipeline_status AS
 SELECT id,
    pipeline_name,
    status,
    started_at,
    finished_at
   FROM public.pipeline_runs;


--
-- Name: analytics_risk_scores; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.analytics_risk_scores AS
 SELECT rs.id,
    rs.geographic_level,
    rs.geographic_code,
    rs.geographic_name,
    rs.reference_period,
    rs.score,
    rs.risk_level,
    rs.coverage_ratio,
    rs.status,
    model.code AS model_code,
    model.version AS model_version,
    model.is_active AS model_is_active,
    rs.calculated_at
   FROM (public.risk_scores rs
     JOIN public.risk_score_models model ON ((model.id = rs.risk_score_model_id)));


--
-- Name: risk_score_details; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.risk_score_details (
    id integer NOT NULL,
    risk_score_id integer NOT NULL,
    indicator_id integer,
    indicator_code character varying(128) NOT NULL,
    raw_value numeric(20,8) NOT NULL,
    unit character varying(64),
    population_min numeric(20,8) NOT NULL,
    population_max numeric(20,8) NOT NULL,
    normalized_value numeric(12,8) NOT NULL,
    configured_weight numeric(12,8) NOT NULL,
    effective_weight numeric(12,8) NOT NULL,
    contribution numeric(12,8) NOT NULL,
    direction character varying(16) NOT NULL,
    source_observation_id integer,
    created_at character varying(32) NOT NULL,
    updated_at character varying(32) NOT NULL,
    CONSTRAINT ck_risk_score_details_configured_weight CHECK ((configured_weight > (0)::numeric)),
    CONSTRAINT ck_risk_score_details_effective_weight CHECK ((effective_weight > (0)::numeric)),
    CONSTRAINT ck_risk_score_details_normalized CHECK (((normalized_value >= (0)::numeric) AND (normalized_value <= (1)::numeric)))
);


--
-- Name: analytics_score_factors; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.analytics_score_factors AS
 SELECT detail.id,
    score.geographic_level,
    score.geographic_code,
    score.geographic_name,
    score.reference_period,
    model.code AS model_code,
    model.version AS model_version,
    detail.indicator_code,
    detail.raw_value,
    detail.unit,
    detail.normalized_value,
    detail.configured_weight,
    detail.effective_weight,
    detail.contribution,
    detail.direction
   FROM ((public.risk_score_details detail
     JOIN public.risk_scores score ON ((score.id = detail.risk_score_id)))
     JOIN public.risk_score_models model ON ((model.id = score.risk_score_model_id)));


--
-- Name: assistant_conversation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_conversation (
    id bigint NOT NULL,
    title character varying(200) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    user_id integer NOT NULL,
    kind character varying(16) NOT NULL
);


--
-- Name: assistant_conversation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.assistant_conversation ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.assistant_conversation_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assistant_conversationmessage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_conversationmessage (
    id bigint NOT NULL,
    role character varying(16) NOT NULL,
    content text NOT NULL,
    method character varying(16) NOT NULL,
    request_id uuid,
    citations jsonb NOT NULL,
    created_at timestamp with time zone NOT NULL,
    conversation_id bigint NOT NULL,
    category character varying(48) NOT NULL,
    response_metadata jsonb NOT NULL,
    generated_sql text NOT NULL,
    feedback character varying(16) NOT NULL
);


--
-- Name: assistant_conversationmessage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.assistant_conversationmessage ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.assistant_conversationmessage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assistant_ragchunk; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_ragchunk (
    id bigint NOT NULL,
    ordinal integer NOT NULL,
    title character varying(300) NOT NULL,
    section character varying(500) NOT NULL,
    content text NOT NULL,
    content_sha256 character varying(64) NOT NULL,
    page_number integer,
    territory character varying(200) NOT NULL,
    reference_period character varying(32) NOT NULL,
    indicator_code character varying(120) NOT NULL,
    source_url character varying(200) NOT NULL,
    search_vector tsvector,
    created_at timestamp with time zone NOT NULL,
    document_version_id bigint NOT NULL,
    CONSTRAINT assistant_ragchunk_ordinal_check CHECK ((ordinal >= 0)),
    CONSTRAINT assistant_ragchunk_page_number_check CHECK ((page_number >= 0))
);


--
-- Name: assistant_ragchunk_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.assistant_ragchunk ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.assistant_ragchunk_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assistant_ragdocument; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_ragdocument (
    id bigint NOT NULL,
    slug character varying(200) NOT NULL,
    title character varying(300) NOT NULL,
    document_type character varying(32) NOT NULL,
    source_url character varying(200) NOT NULL,
    is_active boolean NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    source_id bigint NOT NULL
);


--
-- Name: assistant_ragdocument_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.assistant_ragdocument ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.assistant_ragdocument_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assistant_ragdocumentversion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_ragdocumentversion (
    id bigint NOT NULL,
    version_label character varying(100) NOT NULL,
    source_path character varying(500) NOT NULL,
    sha256 character varying(64) NOT NULL,
    approved_at timestamp with time zone NOT NULL,
    chunking_algorithm_version character varying(100) NOT NULL,
    indexed_at timestamp with time zone NOT NULL,
    document_id bigint NOT NULL
);


--
-- Name: assistant_ragdocumentversion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.assistant_ragdocumentversion ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.assistant_ragdocumentversion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assistant_ragindexrun; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_ragindexrun (
    id bigint NOT NULL,
    status character varying(16) NOT NULL,
    manifest_path character varying(500) NOT NULL,
    chunking_algorithm_version character varying(100) NOT NULL,
    started_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    documents_created integer NOT NULL,
    versions_created integer NOT NULL,
    documents_skipped integer NOT NULL,
    chunks_created integer NOT NULL,
    error_message text NOT NULL,
    CONSTRAINT assistant_ragindexrun_chunks_created_check CHECK ((chunks_created >= 0)),
    CONSTRAINT assistant_ragindexrun_documents_created_check CHECK ((documents_created >= 0)),
    CONSTRAINT assistant_ragindexrun_documents_skipped_check CHECK ((documents_skipped >= 0)),
    CONSTRAINT assistant_ragindexrun_versions_created_check CHECK ((versions_created >= 0))
);


--
-- Name: assistant_ragindexrun_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.assistant_ragindexrun ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.assistant_ragindexrun_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assistant_ragsource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assistant_ragsource (
    id bigint NOT NULL,
    name character varying(200) NOT NULL,
    publisher character varying(200) NOT NULL,
    base_url character varying(200) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


--
-- Name: assistant_ragsource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.assistant_ragsource ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.assistant_ragsource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_permission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user (
    id integer NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL
);


--
-- Name: auth_user_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_groups (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    group_id integer NOT NULL
);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_user_groups ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_user_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_user ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_user_user_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_user_permissions (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_user_user_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_user_user_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: dim_period; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dim_period (
    period_key character varying(16) NOT NULL,
    reference_year integer NOT NULL,
    reference_month_number integer,
    granularity character varying(16) NOT NULL,
    CONSTRAINT ck_dim_period_granularity CHECK (((granularity)::text = ANY ((ARRAY['month'::character varying, 'year'::character varying])::text[])))
);


--
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    content_type_id integer,
    user_id integer NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_admin_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_admin_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_content_type ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


--
-- Name: fact_bdf_statinfo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fact_bdf_statinfo (
    reference_period text NOT NULL,
    reference_year integer NOT NULL,
    reference_month_number integer NOT NULL,
    departement_code text NOT NULL,
    indicator_key text NOT NULL,
    value real NOT NULL,
    source_file text,
    pipeline_version text
);


--
-- Name: fact_macro_override; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fact_macro_override (
    id integer NOT NULL,
    period_key text NOT NULL,
    reference_year integer NOT NULL,
    departement_code text NOT NULL,
    indicator_key text NOT NULL,
    indicator_code text NOT NULL,
    indicator_name text,
    indicator_group text,
    value real NOT NULL,
    source_note text,
    created_at text NOT NULL,
    updated_at text NOT NULL
);


--
-- Name: fact_macro_override_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fact_macro_override_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fact_macro_override_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fact_macro_override_id_seq OWNED BY public.fact_macro_override.id;


--
-- Name: fact_surendettement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fact_surendettement (
    reference_year integer NOT NULL,
    departement_code text NOT NULL,
    indicator_key text NOT NULL,
    value real NOT NULL,
    source_file text
);


--
-- Name: indicators_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.indicators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: indicators_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.indicators_id_seq OWNED BY public.indicators.id;


--
-- Name: observations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.observations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: observations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.observations_id_seq OWNED BY public.observations.id;


--
-- Name: pipeline_metadata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pipeline_metadata (
    database_version text NOT NULL,
    source_system text NOT NULL,
    source_path text NOT NULL,
    built_at text NOT NULL
);


--
-- Name: pipeline_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pipeline_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pipeline_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pipeline_runs_id_seq OWNED BY public.pipeline_runs.id;


--
-- Name: risk_score_details_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.risk_score_details_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risk_score_details_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.risk_score_details_id_seq OWNED BY public.risk_score_details.id;


--
-- Name: risk_score_indicator_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.risk_score_indicator_configs (
    id integer NOT NULL,
    risk_score_model_id integer NOT NULL,
    indicator_id integer,
    indicator_code character varying(128) NOT NULL,
    logical_code character varying(128) NOT NULL,
    weight numeric(12,8) NOT NULL,
    direction character varying(16) NOT NULL,
    normalization_method character varying(64) NOT NULL,
    fixed_min numeric(20,8),
    fixed_max numeric(20,8),
    expected_unit character varying(64),
    is_required boolean NOT NULL,
    is_active boolean NOT NULL,
    created_at character varying(32) NOT NULL,
    updated_at character varying(32) NOT NULL,
    CONSTRAINT ck_risk_score_indicator_direction CHECK (((direction)::text = ANY ((ARRAY['positive'::character varying, 'negative'::character varying])::text[]))),
    CONSTRAINT ck_risk_score_indicator_weight CHECK ((weight > (0)::numeric))
);


--
-- Name: risk_score_indicator_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.risk_score_indicator_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risk_score_indicator_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.risk_score_indicator_configs_id_seq OWNED BY public.risk_score_indicator_configs.id;


--
-- Name: risk_score_models_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.risk_score_models_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risk_score_models_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.risk_score_models_id_seq OWNED BY public.risk_score_models.id;


--
-- Name: risk_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.risk_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: risk_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.risk_scores_id_seq OWNED BY public.risk_scores.id;


--
-- Name: schema_deprecations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_deprecations (
    object_name text NOT NULL,
    object_type text NOT NULL,
    deprecated_since text NOT NULL,
    replacement text,
    reason text NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying(64) NOT NULL,
    description character varying(512) NOT NULL,
    applied_at character varying(32) NOT NULL
);


--
-- Name: source_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source_documents (
    id integer NOT NULL,
    source_name character varying(255) NOT NULL,
    publication_type character varying(255) NOT NULL,
    region_code character varying(16) NOT NULL,
    region_name character varying(255) NOT NULL,
    reference_period character varying(7) NOT NULL,
    publication_date character varying(32),
    updated_date character varying(32),
    page_url text NOT NULL,
    pdf_url text NOT NULL,
    pdf_filename character varying(512) NOT NULL,
    pdf_sha256 character varying(64) NOT NULL,
    pdf_size_bytes integer,
    storage_path text NOT NULL,
    http_etag character varying(255),
    http_last_modified character varying(255),
    downloaded_at character varying(32),
    extraction_status character varying(64) NOT NULL,
    extractor_version character varying(64) NOT NULL,
    created_at character varying(32) NOT NULL,
    updated_at character varying(32) NOT NULL
);


--
-- Name: source_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.source_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.source_documents_id_seq OWNED BY public.source_documents.id;


--
-- Name: surendettement_data; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.surendettement_data (
    id integer NOT NULL,
    year integer,
    region character varying(255),
    indicator character varying(255) NOT NULL,
    value double precision,
    source_file character varying(255) NOT NULL
);


--
-- Name: surendettement_data_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.surendettement_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: surendettement_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.surendettement_data_id_seq OWNED BY public.surendettement_data.id;


--
-- Name: v_bdf_total_deposits; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_bdf_total_deposits AS
 SELECT b.reference_period,
    b.reference_year,
    b.reference_month_number,
    b.departement_code,
    d.departement_name,
    d.region_name,
    b.value AS bdf_total_deposits_value
   FROM ((public.fact_bdf_statinfo b
     JOIN public.dim_indicator i ON ((i.indicator_key = b.indicator_key)))
     LEFT JOIN public.dim_department d ON ((d.departement_code = b.departement_code)))
  WHERE ((i.source_system = 'bdf_statinfo'::text) AND (i.indicator_code = 'total'::text));


--
-- Name: v_bdf_total_deposits_with_insee_macro; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_bdf_total_deposits_with_insee_macro AS
 SELECT b.reference_period AS bdf_reference_period,
    b.reference_year AS bdf_reference_year,
    b.reference_month_number AS bdf_reference_month_number,
    b.departement_code,
    b.departement_name,
    b.region_name,
    b.bdf_total_deposits_value,
    m.reference_year AS macro_reference_year,
    i.indicator_code AS macro_indicator_code,
    i.indicator_name AS macro_indicator_name,
    i.indicator_group AS macro_indicator_group,
    m.value AS macro_value
   FROM ((public.v_bdf_total_deposits b
     JOIN public.fact_insee_macro m ON (((m.departement_code = b.departement_code) AND (m.reference_year = ( SELECT max(fact_insee_macro.reference_year) AS max
           FROM public.fact_insee_macro
          WHERE (fact_insee_macro.reference_year <= (b.reference_year + 1)))))))
     JOIN public.dim_indicator i ON ((i.indicator_key = m.indicator_key)))
  WHERE (i.source_system = 'insee_macro'::text);


--
-- Name: v_surendettement_annual; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_surendettement_annual AS
 SELECT s.reference_year,
    s.departement_code,
    d.departement_name,
    d.region_name,
    sum(s.value) AS surendettement_value
   FROM (public.fact_surendettement s
     LEFT JOIN public.dim_department d ON ((d.departement_code = s.departement_code)))
  GROUP BY s.reference_year, s.departement_code, d.departement_name, d.region_name;


--
-- Name: v_surendettement_with_insee_macro; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_surendettement_with_insee_macro AS
 SELECT s.reference_year,
    s.departement_code,
    s.departement_name,
    s.region_name,
    s.surendettement_value,
    m.reference_year AS macro_reference_year,
    i.indicator_code AS macro_indicator_code,
    i.indicator_name AS macro_indicator_name,
    i.indicator_group AS macro_indicator_group,
    m.value AS macro_value
   FROM ((public.v_surendettement_annual s
     JOIN public.fact_insee_macro m ON (((m.departement_code = s.departement_code) AND (m.reference_year = ( SELECT max(fact_insee_macro.reference_year) AS max
           FROM public.fact_insee_macro
          WHERE (fact_insee_macro.reference_year <= (s.reference_year + 1)))))))
     JOIN public.dim_indicator i ON ((i.indicator_key = m.indicator_key)))
  WHERE (i.source_system = 'insee_macro'::text);


--
-- Name: fact_macro_override id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_macro_override ALTER COLUMN id SET DEFAULT nextval('public.fact_macro_override_id_seq'::regclass);


--
-- Name: indicators id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indicators ALTER COLUMN id SET DEFAULT nextval('public.indicators_id_seq'::regclass);


--
-- Name: observations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observations ALTER COLUMN id SET DEFAULT nextval('public.observations_id_seq'::regclass);


--
-- Name: pipeline_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_runs ALTER COLUMN id SET DEFAULT nextval('public.pipeline_runs_id_seq'::regclass);


--
-- Name: risk_score_details id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_details ALTER COLUMN id SET DEFAULT nextval('public.risk_score_details_id_seq'::regclass);


--
-- Name: risk_score_indicator_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_indicator_configs ALTER COLUMN id SET DEFAULT nextval('public.risk_score_indicator_configs_id_seq'::regclass);


--
-- Name: risk_score_models id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_models ALTER COLUMN id SET DEFAULT nextval('public.risk_score_models_id_seq'::regclass);


--
-- Name: risk_scores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_scores ALTER COLUMN id SET DEFAULT nextval('public.risk_scores_id_seq'::regclass);


--
-- Name: source_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_documents ALTER COLUMN id SET DEFAULT nextval('public.source_documents_id_seq'::regclass);


--
-- Name: surendettement_data id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.surendettement_data ALTER COLUMN id SET DEFAULT nextval('public.surendettement_data_id_seq'::regclass);


--
-- Name: corpus_chunks corpus_chunks_pkey; Type: CONSTRAINT; Schema: assistant; Owner: -
--

ALTER TABLE ONLY assistant.corpus_chunks
    ADD CONSTRAINT corpus_chunks_pkey PRIMARY KEY (chunk_id);


--
-- Name: corpus_chunks corpus_chunks_source_id_ordinal_source_sha256_key; Type: CONSTRAINT; Schema: assistant; Owner: -
--

ALTER TABLE ONLY assistant.corpus_chunks
    ADD CONSTRAINT corpus_chunks_source_id_ordinal_source_sha256_key UNIQUE (source_id, ordinal, source_sha256);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: assistant; Owner: -
--

ALTER TABLE ONLY assistant.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sql_executions sql_executions_pkey; Type: CONSTRAINT; Schema: assistant; Owner: -
--

ALTER TABLE ONLY assistant.sql_executions
    ADD CONSTRAINT sql_executions_pkey PRIMARY KEY (execution_id);


--
-- Name: assistant_conversation assistant_conversation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_conversation
    ADD CONSTRAINT assistant_conversation_pkey PRIMARY KEY (id);


--
-- Name: assistant_conversationmessage assistant_conversationmessage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_conversationmessage
    ADD CONSTRAINT assistant_conversationmessage_pkey PRIMARY KEY (id);


--
-- Name: assistant_ragchunk assistant_ragchunk_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragchunk
    ADD CONSTRAINT assistant_ragchunk_pkey PRIMARY KEY (id);


--
-- Name: assistant_ragdocument assistant_ragdocument_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragdocument
    ADD CONSTRAINT assistant_ragdocument_pkey PRIMARY KEY (id);


--
-- Name: assistant_ragdocument assistant_ragdocument_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragdocument
    ADD CONSTRAINT assistant_ragdocument_slug_key UNIQUE (slug);


--
-- Name: assistant_ragdocumentversion assistant_ragdocumentversion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragdocumentversion
    ADD CONSTRAINT assistant_ragdocumentversion_pkey PRIMARY KEY (id);


--
-- Name: assistant_ragindexrun assistant_ragindexrun_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragindexrun
    ADD CONSTRAINT assistant_ragindexrun_pkey PRIMARY KEY (id);


--
-- Name: assistant_ragsource assistant_ragsource_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragsource
    ADD CONSTRAINT assistant_ragsource_name_key UNIQUE (name);


--
-- Name: assistant_ragsource assistant_ragsource_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragsource
    ADD CONSTRAINT assistant_ragsource_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_user_id_group_id_94350c0c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_group_id_94350c0c_uniq UNIQUE (user_id, group_id);


--
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_permission_id_14a6b632_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_permission_id_14a6b632_uniq UNIQUE (user_id, permission_id);


--
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: dim_department dim_department_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_department
    ADD CONSTRAINT dim_department_pkey PRIMARY KEY (departement_code);


--
-- Name: dim_indicator dim_indicator_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_indicator
    ADD CONSTRAINT dim_indicator_pkey PRIMARY KEY (indicator_key);


--
-- Name: dim_period dim_period_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_period
    ADD CONSTRAINT dim_period_pkey PRIMARY KEY (period_key);


--
-- Name: dim_region dim_region_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_region
    ADD CONSTRAINT dim_region_pkey PRIMARY KEY (region_code);


--
-- Name: dim_region dim_region_region_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dim_region
    ADD CONSTRAINT dim_region_region_name_key UNIQUE (region_name);


--
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: fact_macro_override fact_macro_override_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_macro_override
    ADD CONSTRAINT fact_macro_override_pkey PRIMARY KEY (id);


--
-- Name: indicators indicators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indicators
    ADD CONSTRAINT indicators_pkey PRIMARY KEY (id);


--
-- Name: observations observations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observations
    ADD CONSTRAINT observations_pkey PRIMARY KEY (id);


--
-- Name: pipeline_runs pipeline_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pipeline_runs
    ADD CONSTRAINT pipeline_runs_pkey PRIMARY KEY (id);


--
-- Name: risk_score_details risk_score_details_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_details
    ADD CONSTRAINT risk_score_details_pkey PRIMARY KEY (id);


--
-- Name: risk_score_indicator_configs risk_score_indicator_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_indicator_configs
    ADD CONSTRAINT risk_score_indicator_configs_pkey PRIMARY KEY (id);


--
-- Name: risk_score_models risk_score_models_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_models
    ADD CONSTRAINT risk_score_models_pkey PRIMARY KEY (id);


--
-- Name: risk_scores risk_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_scores
    ADD CONSTRAINT risk_scores_pkey PRIMARY KEY (id);


--
-- Name: schema_deprecations schema_deprecations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_deprecations
    ADD CONSTRAINT schema_deprecations_pkey PRIMARY KEY (object_name);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: source_documents source_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_documents
    ADD CONSTRAINT source_documents_pkey PRIMARY KEY (id);


--
-- Name: surendettement_data surendettement_data_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.surendettement_data
    ADD CONSTRAINT surendettement_data_pkey PRIMARY KEY (id);


--
-- Name: indicators uq_indicators_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.indicators
    ADD CONSTRAINT uq_indicators_code UNIQUE (code);


--
-- Name: observations uq_observations_idempotence_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observations
    ADD CONSTRAINT uq_observations_idempotence_key UNIQUE (idempotence_key);


--
-- Name: assistant_ragchunk uq_rag_chunk_version_ordinal; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragchunk
    ADD CONSTRAINT uq_rag_chunk_version_ordinal UNIQUE (document_version_id, ordinal);


--
-- Name: assistant_ragdocumentversion uq_rag_document_version_sha; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragdocumentversion
    ADD CONSTRAINT uq_rag_document_version_sha UNIQUE (document_id, sha256);


--
-- Name: risk_score_details uq_risk_score_details_score_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_details
    ADD CONSTRAINT uq_risk_score_details_score_code UNIQUE (risk_score_id, indicator_code);


--
-- Name: risk_score_indicator_configs uq_risk_score_indicator_model_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_indicator_configs
    ADD CONSTRAINT uq_risk_score_indicator_model_code UNIQUE (risk_score_model_id, indicator_code);


--
-- Name: risk_score_models uq_risk_score_models_code_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_models
    ADD CONSTRAINT uq_risk_score_models_code_version UNIQUE (code, version);


--
-- Name: risk_scores uq_risk_scores_business_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_scores
    ADD CONSTRAINT uq_risk_scores_business_key UNIQUE (risk_score_model_id, geographic_level, geographic_code, reference_period);


--
-- Name: source_documents uq_source_documents_business_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_documents
    ADD CONSTRAINT uq_source_documents_business_version UNIQUE (publication_type, region_code, reference_period, pdf_sha256);


--
-- Name: source_documents uq_source_documents_pdf_sha256; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source_documents
    ADD CONSTRAINT uq_source_documents_pdf_sha256 UNIQUE (pdf_sha256);


--
-- Name: ix_assistant_chunks_search; Type: INDEX; Schema: assistant; Owner: -
--

CREATE INDEX ix_assistant_chunks_search ON assistant.corpus_chunks USING gin (search_vector);


--
-- Name: ix_assistant_chunks_source_active; Type: INDEX; Schema: assistant; Owner: -
--

CREATE INDEX ix_assistant_chunks_source_active ON assistant.corpus_chunks USING btree (source_id, is_active);


--
-- Name: ix_assistant_sql_executions_actor; Type: INDEX; Schema: assistant; Owner: -
--

CREATE INDEX ix_assistant_sql_executions_actor ON assistant.sql_executions USING btree (actor_id, created_at);


--
-- Name: ix_assistant_sql_executions_request; Type: INDEX; Schema: assistant; Owner: -
--

CREATE INDEX ix_assistant_sql_executions_request ON assistant.sql_executions USING btree (request_id, created_at);


--
-- Name: assistant_conversation_user_id_d68b3caa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX assistant_conversation_user_id_d68b3caa ON public.assistant_conversation USING btree (user_id);


--
-- Name: assistant_conversationmessage_conversation_id_e3ed1e9d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX assistant_conversationmessage_conversation_id_e3ed1e9d ON public.assistant_conversationmessage USING btree (conversation_id);


--
-- Name: assistant_ragchunk_document_version_id_fa53b364; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX assistant_ragchunk_document_version_id_fa53b364 ON public.assistant_ragchunk USING btree (document_version_id);


--
-- Name: assistant_ragdocument_slug_b1b2c563_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX assistant_ragdocument_slug_b1b2c563_like ON public.assistant_ragdocument USING btree (slug varchar_pattern_ops);


--
-- Name: assistant_ragdocument_source_id_7cb0f5f5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX assistant_ragdocument_source_id_7cb0f5f5 ON public.assistant_ragdocument USING btree (source_id);


--
-- Name: assistant_ragdocumentversion_document_id_1ab70475; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX assistant_ragdocumentversion_document_id_1ab70475 ON public.assistant_ragdocumentversion USING btree (document_id);


--
-- Name: assistant_ragsource_name_de4536d1_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX assistant_ragsource_name_de4536d1_like ON public.assistant_ragsource USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: auth_user_groups_group_id_97559544; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_groups_group_id_97559544 ON public.auth_user_groups USING btree (group_id);


--
-- Name: auth_user_groups_user_id_6a12ed8b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_groups_user_id_6a12ed8b ON public.auth_user_groups USING btree (user_id);


--
-- Name: auth_user_user_permissions_permission_id_1fbb5f2c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_user_permissions_permission_id_1fbb5f2c ON public.auth_user_user_permissions USING btree (permission_id);


--
-- Name: auth_user_user_permissions_user_id_a95ead1b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_user_permissions_user_id_a95ead1b ON public.auth_user_user_permissions USING btree (user_id);


--
-- Name: auth_user_username_6821ab7c_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_username_6821ab7c_like ON public.auth_user USING btree (username varchar_pattern_ops);


--
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: idx_bdf_department_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bdf_department_period ON public.fact_bdf_statinfo USING btree (departement_code, reference_period);


--
-- Name: idx_bdf_indicator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bdf_indicator ON public.fact_bdf_statinfo USING btree (indicator_key);


--
-- Name: idx_department_region_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_department_region_code ON public.dim_department USING btree (region_code);


--
-- Name: idx_insee_department_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_insee_department_year ON public.fact_insee_macro USING btree (departement_code, reference_year);


--
-- Name: idx_insee_indicator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_insee_indicator ON public.fact_insee_macro USING btree (indicator_key);


--
-- Name: idx_macro_override_lookup; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_macro_override_lookup ON public.fact_macro_override USING btree (period_key, departement_code, indicator_key);


--
-- Name: idx_surendettement_department_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_surendettement_department_year ON public.fact_surendettement USING btree (departement_code, reference_year);


--
-- Name: idx_surendettement_indicator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_surendettement_indicator ON public.fact_surendettement USING btree (indicator_key);


--
-- Name: ix_indicators_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_indicators_code ON public.indicators USING btree (code);


--
-- Name: ix_observations_code_level_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_code_level_period ON public.observations USING btree (indicator_code, geographic_level, reference_period);


--
-- Name: ix_observations_geo_period_indicator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_geo_period_indicator ON public.observations USING btree (geographic_level, reference_period, indicator_id, geographic_code);


--
-- Name: ix_observations_idempotence_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_idempotence_key ON public.observations USING btree (idempotence_key);


--
-- Name: ix_observations_indicator_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_indicator_code ON public.observations USING btree (indicator_code);


--
-- Name: ix_observations_indicator_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_indicator_id ON public.observations USING btree (indicator_id);


--
-- Name: ix_observations_period_level_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_period_level_code ON public.observations USING btree (reference_period, geographic_level, geographic_code);


--
-- Name: ix_observations_reference_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_reference_period ON public.observations USING btree (reference_period);


--
-- Name: ix_observations_region_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_region_code ON public.observations USING btree (region_code);


--
-- Name: ix_observations_source_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_observations_source_document_id ON public.observations USING btree (source_document_id);


--
-- Name: ix_pipeline_runs_name_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pipeline_runs_name_started ON public.pipeline_runs USING btree (pipeline_name, started_at);


--
-- Name: ix_pipeline_runs_pipeline_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pipeline_runs_pipeline_name ON public.pipeline_runs USING btree (pipeline_name);


--
-- Name: ix_pipeline_runs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pipeline_runs_status ON public.pipeline_runs USING btree (status);


--
-- Name: ix_rag_chunk_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rag_chunk_search ON public.assistant_ragchunk USING gin (search_vector);


--
-- Name: ix_risk_score_details_risk_score_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_score_details_risk_score_id ON public.risk_score_details USING btree (risk_score_id);


--
-- Name: ix_risk_score_indicator_configs_indicator_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_score_indicator_configs_indicator_id ON public.risk_score_indicator_configs USING btree (indicator_id);


--
-- Name: ix_risk_score_indicator_configs_risk_score_model_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_score_indicator_configs_risk_score_model_id ON public.risk_score_indicator_configs USING btree (risk_score_model_id);


--
-- Name: ix_risk_score_models_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_score_models_code ON public.risk_score_models USING btree (code);


--
-- Name: ix_risk_score_models_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_score_models_is_active ON public.risk_score_models USING btree (is_active);


--
-- Name: ix_risk_scores_geo_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_scores_geo_period ON public.risk_scores USING btree (geographic_level, geographic_code, reference_period);


--
-- Name: ix_risk_scores_model_level_period_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_scores_model_level_period_score ON public.risk_scores USING btree (risk_score_model_id, geographic_level, reference_period, score);


--
-- Name: ix_risk_scores_risk_score_model_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_risk_scores_risk_score_model_id ON public.risk_scores USING btree (risk_score_model_id);


--
-- Name: ix_source_documents_pdf_sha256; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_documents_pdf_sha256 ON public.source_documents USING btree (pdf_sha256);


--
-- Name: ix_source_documents_period_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_documents_period_status ON public.source_documents USING btree (reference_period, extraction_status);


--
-- Name: ix_source_documents_publication_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_documents_publication_type ON public.source_documents USING btree (publication_type);


--
-- Name: ix_source_documents_reference_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_documents_reference_period ON public.source_documents USING btree (reference_period);


--
-- Name: ix_source_documents_region_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_source_documents_region_code ON public.source_documents USING btree (region_code);


--
-- Name: ix_surendettement_data_region; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_surendettement_data_region ON public.surendettement_data USING btree (region);


--
-- Name: ix_surendettement_data_year; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_surendettement_data_year ON public.surendettement_data USING btree (year);


--
-- Name: uq_bdf_fact; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_bdf_fact ON public.fact_bdf_statinfo USING btree (reference_period, departement_code, indicator_key);


--
-- Name: uq_insee_fact; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_insee_fact ON public.fact_insee_macro USING btree (reference_year, departement_code, indicator_key);


--
-- Name: assistant_conversationmessage assistant_conversati_conversation_id_e3ed1e9d_fk_assistant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_conversationmessage
    ADD CONSTRAINT assistant_conversati_conversation_id_e3ed1e9d_fk_assistant FOREIGN KEY (conversation_id) REFERENCES public.assistant_conversation(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: assistant_conversation assistant_conversation_user_id_d68b3caa_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_conversation
    ADD CONSTRAINT assistant_conversation_user_id_d68b3caa_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: assistant_ragchunk assistant_ragchunk_document_version_id_fa53b364_fk_assistant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragchunk
    ADD CONSTRAINT assistant_ragchunk_document_version_id_fa53b364_fk_assistant FOREIGN KEY (document_version_id) REFERENCES public.assistant_ragdocumentversion(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: assistant_ragdocumentversion assistant_ragdocumen_document_id_1ab70475_fk_assistant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragdocumentversion
    ADD CONSTRAINT assistant_ragdocumen_document_id_1ab70475_fk_assistant FOREIGN KEY (document_id) REFERENCES public.assistant_ragdocument(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: assistant_ragdocument assistant_ragdocumen_source_id_7cb0f5f5_fk_assistant; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assistant_ragdocument
    ADD CONSTRAINT assistant_ragdocumen_source_id_7cb0f5f5_fk_assistant FOREIGN KEY (source_id) REFERENCES public.assistant_ragsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_group_id_97559544_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_group_id_97559544_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_user_id_6a12ed8b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_6a12ed8b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fact_bdf_statinfo fact_bdf_statinfo_departement_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_bdf_statinfo
    ADD CONSTRAINT fact_bdf_statinfo_departement_code_fkey FOREIGN KEY (departement_code) REFERENCES public.dim_department(departement_code);


--
-- Name: fact_bdf_statinfo fact_bdf_statinfo_indicator_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_bdf_statinfo
    ADD CONSTRAINT fact_bdf_statinfo_indicator_key_fkey FOREIGN KEY (indicator_key) REFERENCES public.dim_indicator(indicator_key);


--
-- Name: fact_insee_macro fact_insee_macro_departement_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_insee_macro
    ADD CONSTRAINT fact_insee_macro_departement_code_fkey FOREIGN KEY (departement_code) REFERENCES public.dim_department(departement_code);


--
-- Name: fact_insee_macro fact_insee_macro_indicator_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_insee_macro
    ADD CONSTRAINT fact_insee_macro_indicator_key_fkey FOREIGN KEY (indicator_key) REFERENCES public.dim_indicator(indicator_key);


--
-- Name: fact_macro_override fact_macro_override_departement_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_macro_override
    ADD CONSTRAINT fact_macro_override_departement_code_fkey FOREIGN KEY (departement_code) REFERENCES public.dim_department(departement_code);


--
-- Name: fact_macro_override fact_macro_override_indicator_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_macro_override
    ADD CONSTRAINT fact_macro_override_indicator_key_fkey FOREIGN KEY (indicator_key) REFERENCES public.dim_indicator(indicator_key);


--
-- Name: fact_macro_override fact_macro_override_period_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_macro_override
    ADD CONSTRAINT fact_macro_override_period_key_fkey FOREIGN KEY (period_key) REFERENCES public.dim_period(period_key);


--
-- Name: fact_surendettement fact_surendettement_departement_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_surendettement
    ADD CONSTRAINT fact_surendettement_departement_code_fkey FOREIGN KEY (departement_code) REFERENCES public.dim_department(departement_code);


--
-- Name: fact_surendettement fact_surendettement_indicator_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fact_surendettement
    ADD CONSTRAINT fact_surendettement_indicator_key_fkey FOREIGN KEY (indicator_key) REFERENCES public.dim_indicator(indicator_key);


--
-- Name: observations observations_indicator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observations
    ADD CONSTRAINT observations_indicator_id_fkey FOREIGN KEY (indicator_id) REFERENCES public.indicators(id);


--
-- Name: observations observations_source_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.observations
    ADD CONSTRAINT observations_source_document_id_fkey FOREIGN KEY (source_document_id) REFERENCES public.source_documents(id);


--
-- Name: risk_score_details risk_score_details_indicator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_details
    ADD CONSTRAINT risk_score_details_indicator_id_fkey FOREIGN KEY (indicator_id) REFERENCES public.indicators(id);


--
-- Name: risk_score_details risk_score_details_risk_score_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_details
    ADD CONSTRAINT risk_score_details_risk_score_id_fkey FOREIGN KEY (risk_score_id) REFERENCES public.risk_scores(id);


--
-- Name: risk_score_details risk_score_details_source_observation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_details
    ADD CONSTRAINT risk_score_details_source_observation_id_fkey FOREIGN KEY (source_observation_id) REFERENCES public.observations(id);


--
-- Name: risk_score_indicator_configs risk_score_indicator_configs_indicator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_indicator_configs
    ADD CONSTRAINT risk_score_indicator_configs_indicator_id_fkey FOREIGN KEY (indicator_id) REFERENCES public.indicators(id);


--
-- Name: risk_score_indicator_configs risk_score_indicator_configs_risk_score_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_score_indicator_configs
    ADD CONSTRAINT risk_score_indicator_configs_risk_score_model_id_fkey FOREIGN KEY (risk_score_model_id) REFERENCES public.risk_score_models(id);


--
-- Name: risk_scores risk_scores_risk_score_model_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.risk_scores
    ADD CONSTRAINT risk_scores_risk_score_model_id_fkey FOREIGN KEY (risk_score_model_id) REFERENCES public.risk_score_models(id);


--
-- PostgreSQL database dump complete
--

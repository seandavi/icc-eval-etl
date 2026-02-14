-- icc-data-views.sql
-- DuckDB views over the JSONL output files from the icc-eval-etl pipeline.
-- Reads JSONL from the output/ directory (relative to working directory).
--
-- Prerequisites:
--   1. Run the ETL pipeline first to populate output/:
--        uv run python main.py
--   2. DuckDB CLI installed (https://duckdb.org/docs/installation)
--
-- Usage:
--   Interactive session (views available at the prompt):
--     duckdb -init icc-data-views.sql
--
--   Run a query directly:
--     duckdb -init icc-data-views.sql -c "select * from projects limit 5;"
--
--   Pipe into a script:
--     duckdb < icc-data-views.sql
--
--   Load into a persistent database:
--     duckdb mydb.duckdb -c ".read icc-data-views.sql"
--
-- Views:
--   projects          - NIH Reporter grant records (one row per project-year)
--   publication_links - Core project num <-> PMID join table
--   publications      - Europe PMC publication metadata
--   icite             - iCite citation metrics for grant-associated publications
--   citation_links    - Cited PMID <-> citing PMID edge list
--   citing_icite      - iCite metrics for citing publications
--   github_repos      - GitHub repos tagged with project ID topics

-- ============================================================================
-- projects
-- NIH Reporter grant project records. One row per project-year (a project may
-- appear in multiple fiscal years with different award amounts). Core fields
-- are extracted; the full API response is available via the raw JSONL.
-- ============================================================================
create or replace view projects as
select
    appl_id,
    project_num,
    core_project_num,
    project_title,
    fiscal_year,
    award_amount,
    direct_cost_amt,
    indirect_cost_amt,
    activity_code,
    funding_mechanism,
    agency_code,
    is_active,
    is_new,
    contact_pi_name,
    organization->>'org_name'       as org_name,
    organization->>'org_city'       as org_city,
    organization->>'org_state'      as org_state,
    organization->>'org_country'    as org_country,
    project_start_date,
    project_end_date,
    budget_start,
    budget_end,
    award_notice_date,
    pref_terms,
    abstract_text
from read_json_auto('output/projects.jsonl');

-- ============================================================================
-- publication_links
-- Join table linking NIH core project numbers to PubMed IDs (PMIDs).
-- Sourced from NIH Reporter's publications search endpoint.
-- ============================================================================
create or replace view publication_links as
select
    coreproject  as core_project_num,
    pmid,
    applid       as appl_id
from read_json_auto('output/publication_links.jsonl');

-- ============================================================================
-- publications
-- Publication metadata from Europe PMC. One row per unique PMID.
-- Includes bibliographic info, open access status, and citation counts
-- as reported by Europe PMC (note: differs from iCite counts).
-- ============================================================================
create or replace view publications as
select
    pmid::int                       as pmid,
    doi,
    pmcid,
    title,
    authorString                    as author_string,
    pubYear::int                    as pub_year,
    journalInfo->'journal'->>'title'         as journal_title,
    journalInfo->'journal'->>'isoAbbreviation' as journal_abbrev,
    citedByCount::int               as cited_by_count,
    isOpenAccess                    as is_open_access,
    language,
    pubModel                        as pub_model,
    source,
    abstractText                    as abstract_text,
    firstPublicationDate            as first_publication_date
from read_json_auto('output/publications.jsonl');

-- ============================================================================
-- icite
-- iCite citation metrics for grant-associated publications. Includes NIH's
-- Relative Citation Ratio (RCR), expected/actual citations per year, and
-- NIH percentile. These are the publications directly linked to grants.
-- ============================================================================
create or replace view icite as
select
    pmid,
    title,
    doi,
    year,
    journal,
    citation_count,
    citations_per_year,
    relative_citation_ratio         as rcr,
    expected_citations_per_year,
    field_citation_rate,
    nih_percentile,
    is_research_article,
    is_clinical,
    provisional,
    cited_by,
    "references",
    len(cited_by)                   as cited_by_count,
    len("references")               as reference_count
from read_json_auto('output/icite.jsonl');

-- ============================================================================
-- citation_links
-- Edge list mapping grant-associated publications (cited_pmid) to the
-- publications that cite them (citing_pmid). Derived from iCite's cited_by
-- field. Use this to join icite and citing_icite.
-- ============================================================================
create or replace view citation_links as
select
    cited_pmid,
    citing_pmid
from read_json_auto('output/citation_links.jsonl');

-- ============================================================================
-- citing_icite
-- iCite citation metrics for publications that cite the grant-associated
-- papers. Same schema as icite, but covers the broader citation neighborhood
-- rather than the directly funded publications.
-- ============================================================================
create or replace view citing_icite as
select
    pmid,
    title,
    doi,
    year,
    journal,
    citation_count,
    citations_per_year,
    relative_citation_ratio         as rcr,
    expected_citations_per_year,
    field_citation_rate,
    nih_percentile,
    is_research_article,
    is_clinical,
    provisional,
    cited_by,
    "references",
    len(cited_by)                   as cited_by_count,
    len("references")               as reference_count
from read_json_auto('output/citing_icite.jsonl');

-- ============================================================================
-- github_repos
-- GitHub repositories tagged with core project IDs as topics. One row per
-- unique repo. core_project_ids lists which project IDs matched (a repo can
-- be tagged with multiple project topics).
-- ============================================================================
create or replace view github_repos as
select
    id                              as repo_id,
    name,
    full_name,
    html_url,
    description,
    topics,
    core_project_ids,
    language,
    stargazers_count                as stars,
    forks_count                     as forks,
    open_issues_count               as open_issues,
    owner->>'login'                 as owner_login,
    owner->>'type'                  as owner_type,
    license->>'name'                as license_name,
    created_at,
    updated_at,
    pushed_at,
    private                         as is_private,
    fork                            as is_fork,
    archived                        as is_archived
from read_json_auto('output/github_core.jsonl');

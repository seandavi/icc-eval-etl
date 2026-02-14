# icc-eval-etl

ETL pipeline for gathering NIH grant evaluation data. Given a set of NIH core project identifiers, the pipeline fetches grant records, associated publications, and citation metrics, outputting JSONL files.

## Data Flow

```
collection.yaml → NIH Reporter (projects + publication links) → extract PMIDs
                                                                      ↓
                                                         Europe PMC (pub metadata)
                                                         iCite (citation metrics)
                                                                      ↓
                                                         iCite cited_by → citing PMIDs
                                                         iCite (citing pub metrics)
                                                                      ↓
                                                              JSONL output files
```

## Setup

Requires Python 3.14, managed via [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```bash
uv run python main.py --config collection.yaml --output-dir output
```

Options:
- `-c`, `--config` — Path to collection YAML (default: `collection.yaml`)
- `-o`, `--output-dir` — Output directory for JSONL files (default: `output`)
- `-v`, `--verbose` — Enable debug logging

## Configuration

Grant collections are defined in `collection.yaml` with NIH core project identifiers:

```yaml
core_project_identifiers:
  u54od036472:
  ot2od030161:
```

## Output

Six JSONL files are written to the output directory:

| File | Source | Description |
|------|--------|-------------|
| `projects.jsonl` | NIH Reporter | Grant project records |
| `publication_links.jsonl` | NIH Reporter | Core project ↔ PMID associations |
| `publications.jsonl` | Europe PMC | Publication metadata |
| `icite.jsonl` | iCite | Citation metrics for grant-associated publications |
| `citation_links.jsonl` | iCite | Grant publication PMID ↔ citing PMID mappings |
| `citing_icite.jsonl` | iCite | Citation metrics for citing publications |

## Data Sources

- [NIH Reporter API](https://api.reporter.nih.gov/)
- [Europe PMC REST API](https://europepmc.org/RestfulWebService)
- [iCite API](https://icite.od.nih.gov/api)

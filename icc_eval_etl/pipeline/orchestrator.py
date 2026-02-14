import logging
from pathlib import Path

from icc_eval_etl.clients.europepmc import EuropePMCClient
from icc_eval_etl.clients.icite import ICiteClient
from icc_eval_etl.clients.nih_reporter import NIHReporterClient
from icc_eval_etl.models.config import CollectionConfig
from icc_eval_etl.pipeline.writers import JSONLWriter

logger = logging.getLogger(__name__)


async def run_pipeline(config: CollectionConfig, output_dir: Path) -> None:
    core_nums = [k.upper() for k in config.core_project_identifiers]
    logger.info("Starting ETL for %d core project(s): %s", len(core_nums), core_nums)

    writer = JSONLWriter(output_dir)
    nih = NIHReporterClient()
    epmc = EuropePMCClient()
    icite = ICiteClient()

    try:
        # Step 1: Fetch project records
        logger.info("Step 1/5: Fetching project records from NIH Reporter")
        projects = await nih.search_projects(core_nums)
        path = writer.write("projects.jsonl", projects)
        logger.info("Wrote %d project records to %s", len(projects), path)

        # Step 2: Fetch publication links
        logger.info("Step 2/5: Fetching publication links from NIH Reporter")
        pub_links = await nih.search_publications(core_nums)
        path = writer.write("publication_links.jsonl", pub_links)
        logger.info("Wrote %d publication link records to %s", len(pub_links), path)

        # Step 3: Extract unique PMIDs
        pmids = sorted({r.pmid for r in pub_links if r.pmid is not None})
        logger.info("Step 3/5: Extracted %d unique PMIDs", len(pmids))

        if not pmids:
            logger.warning("No PMIDs found, skipping publication and citation fetches")
            return

        # Step 4: Fetch publication metadata from Europe PMC
        logger.info("Step 4/5: Fetching publication metadata from Europe PMC")
        publications = await epmc.fetch_publications(pmids)
        path = writer.write("publications.jsonl", publications)
        logger.info("Wrote %d publication records to %s", len(publications), path)

        # Step 5: Fetch citation metrics from iCite
        logger.info("Step 5/5: Fetching citation metrics from iCite")
        icite_records = await icite.fetch_metrics(pmids)
        path = writer.write("icite.jsonl", icite_records)
        logger.info("Wrote %d iCite records to %s", len(icite_records), path)

        logger.info("ETL complete. Output directory: %s", output_dir)

    finally:
        await nih.close()
        await epmc.close()
        await icite.close()

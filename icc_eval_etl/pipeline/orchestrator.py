import logging
from pathlib import Path

from icc_eval_etl.clients.europepmc import EuropePMCClient
from icc_eval_etl.clients.github import GitHubClient
from icc_eval_etl.clients.icite import ICiteClient
from icc_eval_etl.clients.nih_reporter import NIHReporterClient
from icc_eval_etl.clients.openalex import OpenAlexClient
from icc_eval_etl.models.config import CollectionConfig
from icc_eval_etl.models.icite import CitationLink
from icc_eval_etl.pipeline.writers import JSONLWriter

logger = logging.getLogger(__name__)


async def run_pipeline(config: CollectionConfig, output_dir: Path) -> None:
    core_nums = [k.upper() for k in config.core_project_identifiers]
    logger.info("Starting ETL for %d core project(s): %s", len(core_nums), core_nums)

    writer = JSONLWriter(output_dir)
    nih = NIHReporterClient()
    epmc = EuropePMCClient()
    icite = ICiteClient()
    github = GitHubClient()
    openalex = OpenAlexClient()

    try:
        # Step 1: Fetch project records
        logger.info("Step 1/10: Fetching project records from NIH Reporter")
        projects = await nih.search_projects(core_nums)
        path = writer.write("projects.jsonl", projects)
        logger.info("Wrote %d project records to %s", len(projects), path)

        # Step 2: Fetch publication links
        logger.info("Step 2/10: Fetching publication links from NIH Reporter")
        pub_links = await nih.search_publications(core_nums)
        path = writer.write("publication_links.jsonl", pub_links)
        logger.info("Wrote %d publication link records to %s", len(pub_links), path)

        # Step 3: Extract unique PMIDs
        pmids = sorted({r.pmid for r in pub_links if r.pmid is not None})
        logger.info("Step 3/10: Extracted %d unique PMIDs", len(pmids))

        if pmids:
            # Step 4: Fetch publication metadata from Europe PMC
            logger.info("Step 4/10: Fetching publication metadata from Europe PMC")
            publications = await epmc.fetch_publications(pmids)
            path = writer.write("publications.jsonl", publications)
            logger.info("Wrote %d publication records to %s", len(publications), path)

            # Step 5: Fetch citation metrics from iCite
            logger.info("Step 5/10: Fetching citation metrics from iCite")
            icite_records = await icite.fetch_metrics(pmids)
            path = writer.write("icite.jsonl", icite_records)
            logger.info("Wrote %d iCite records to %s", len(icite_records), path)

            # Step 6: Build citation links and extract citing PMIDs
            pmid_set = set(pmids)
            citation_links: list[CitationLink] = []
            citing_pmids: set[int] = set()
            for rec in icite_records:
                if rec.pmid is None:
                    continue
                for citing_pmid in (rec.cited_by or []):
                    citation_links.append(
                        CitationLink(cited_pmid=rec.pmid, citing_pmid=citing_pmid)
                    )
                    citing_pmids.add(citing_pmid)
            # Exclude PMIDs we already have iCite data for
            new_citing_pmids = sorted(citing_pmids - pmid_set)
            path = writer.write("citation_links.jsonl", citation_links)
            logger.info(
                "Step 6/10: %d citation links, %d unique citing PMIDs (%d new)",
                len(citation_links), len(citing_pmids), len(new_citing_pmids),
            )

            # Step 7: Fetch iCite records for citing publications
            if new_citing_pmids:
                logger.info("Step 7/10: Fetching iCite records for %d citing publications", len(new_citing_pmids))
                citing_icite_records = await icite.fetch_metrics(new_citing_pmids)
                path = writer.write("citing_icite.jsonl", citing_icite_records)
                logger.info("Wrote %d citing iCite records to %s", len(citing_icite_records), path)
            else:
                logger.info("Step 7/10: No new citing PMIDs to fetch")

            # Step 8: Fetch OpenAlex works for grant-associated publications
            logger.info("Step 8/10: Fetching OpenAlex works for %d grant-associated PMIDs", len(pmids))
            openalex_works = await openalex.fetch_works(pmids)
            path = writer.write("openalex.jsonl", openalex_works)
            logger.info("Wrote %d OpenAlex work records to %s", len(openalex_works), path)

            # Step 9: Fetch OpenAlex works for citing publications
            if new_citing_pmids:
                logger.info("Step 9/10: Fetching OpenAlex works for %d citing PMIDs", len(new_citing_pmids))
                citing_openalex_works = await openalex.fetch_works(new_citing_pmids)
                path = writer.write("citing_openalex.jsonl", citing_openalex_works)
                logger.info("Wrote %d citing OpenAlex work records to %s", len(citing_openalex_works), path)
            else:
                logger.info("Step 9/10: No new citing PMIDs to fetch from OpenAlex")
        else:
            logger.warning("No PMIDs found, skipping publication and citation fetches (steps 4-9)")

        # Step 10: Fetch GitHub repos by topic
        logger.info("Step 10/10: Searching GitHub repos by project ID topics")
        github_repos = await github.fetch_repos(core_nums)
        path = writer.write("github_core.jsonl", github_repos)
        logger.info("Wrote %d GitHub repo records to %s", len(github_repos), path)

        logger.info("ETL complete. Output directory: %s", output_dir)

    finally:
        await nih.close()
        await epmc.close()
        await icite.close()
        await github.close()
        await openalex.close()

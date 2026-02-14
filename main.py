import asyncio
import logging
from pathlib import Path

import typer
from dotenv import load_dotenv

load_dotenv()

from icc_eval_etl.config import load_config
from icc_eval_etl.pipeline.orchestrator import run_pipeline

app = typer.Typer()


@app.command()
def main(
    config: Path = typer.Option("collection.yaml", "--config", "-c", help="Path to collection YAML"),
    output_dir: Path = typer.Option("output", "--output-dir", "-o", help="Output directory for JSONL files"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Fetch NIH grant evaluation data and write JSONL output."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    collection = load_config(config)
    asyncio.run(run_pipeline(collection, output_dir))


if __name__ == "__main__":
    app()

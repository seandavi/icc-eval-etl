from pathlib import Path

import yaml

from icc_eval_etl.models.config import CollectionConfig


def load_config(path: Path) -> CollectionConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return CollectionConfig.model_validate(data)

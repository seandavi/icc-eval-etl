from pydantic import BaseModel


class CollectionConfig(BaseModel):
    core_project_identifiers: dict[str, None]

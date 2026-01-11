import json
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class LegalExpertExtract(BaseModel):
    """A class representing raw legal expert data extracted from external sources.

    This class follows the structure of the legal_experts.json file and contains
    basic information about experts before enrichment.

    Args:
        id (str): Unique identifier for the legal expert.
        urls (List[str]): List of URLs with information about the legal expert.
    """

    id: str = Field(description="Unique identifier for the legal expert")
    urls: List[str] = Field(
        description="List of URLs with information about the legal expert"
    )

    @classmethod
    def from_json(cls, metadata_file: Path) -> list["LegalExpertExtract"]:
        with open(metadata_file, "r") as f:
            experts_data = json.load(f)

        return [cls(**expert) for expert in experts_data]


class LegalExpert(BaseModel):
    """A class representing a legal expert agent with memory capabilities.

    Args:
        id (str): Unique identifier for the legal expert.
        name (str): Name of the legal expert.
        expertise (str): Description of the expert's area of legal focus (e.g., Constitutional Law).
        style (str): Description of the expert's communication style.
    """

    id: str = Field(description="Unique identifier for the legal expert")
    name: str = Field(description="Name of the legal expert")
    expertise: str = Field(
        description="Description of the expert's area of legal focus"
    )
    style: str = Field(description="Description of the expert's communication style")

    def __str__(self) -> str:
        return f"LegalExpert(id={self.id}, name={self.name}, expertise={self.expertise}, style={self.style})"

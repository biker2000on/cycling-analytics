"""Pydantic schemas for CSV import functionality."""

from pydantic import BaseModel


class CsvRowError(BaseModel):
    """Represents an error that occurred while processing a CSV row."""

    row: int
    field: str | None = None
    message: str


class CsvImportResponse(BaseModel):
    """Response returned after CSV import attempt."""

    imported: int
    skipped: int
    errors: list[CsvRowError]
    activity_ids: list[int]

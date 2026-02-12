"""Pydantic schemas for activity route (GeoJSON) API endpoints."""

from typing import Any

from pydantic import BaseModel


class RouteGeoJSON(BaseModel):
    """GeoJSON Feature wrapping a LineString for an activity route."""

    type: str = "Feature"
    geometry: dict[str, Any]  # GeoJSON geometry object (LineString)
    properties: dict[str, Any]  # activity metadata

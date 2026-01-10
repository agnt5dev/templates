"""Data models for the weather agent."""

from pydantic import BaseModel
from typing import Optional


class WeatherData(BaseModel):
    """Weather information for a location."""

    location: str
    latitude: float
    longitude: float
    temperature_c: float
    temperature_f: float
    humidity: int
    wind_kph: float
    country: Optional[str] = None
    region: Optional[str] = None

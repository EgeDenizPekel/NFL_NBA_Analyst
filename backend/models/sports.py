from typing import Any
from pydantic import BaseModel


class PlayerStats(BaseModel):
    name: str
    team: str
    position: str
    season: str
    stats: dict[str, Any]


class TeamInfo(BaseModel):
    name: str
    abbreviation: str
    wins: int
    losses: int
    sport: str


class GamePreview(BaseModel):
    home_team: str
    away_team: str
    date: str
    status: str
    home_score: int | None = None
    away_score: int | None = None

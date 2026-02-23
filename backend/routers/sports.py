from fastapi import APIRouter

from services.nba_service import NBAService
from services.nfl_service import NFLService

router = APIRouter()
nba_service = NBAService()
nfl_service = NFLService()


@router.get("/api/sports/nba/scoreboard")
async def nba_scoreboard():
    data = await nba_service.get_scoreboard()
    return {"sport": "nba", "data": data}


@router.get("/api/sports/nba/standings")
async def nba_standings():
    data = await nba_service.get_standings()
    return {"sport": "nba", "data": data}


@router.get("/api/sports/nfl/scoreboard")
async def nfl_scoreboard():
    data = await nfl_service.get_scoreboard()
    return {"sport": "nfl", "data": data}


@router.get("/api/sports/nfl/standings")
async def nfl_standings():
    data = await nfl_service.get_standings()
    return {"sport": "nfl", "data": data}

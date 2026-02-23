from typing import Any

import httpx

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"


async def fetch_espn(sport: str, league: str, endpoint: str) -> dict[str, Any]:
    url = f"{ESPN_BASE}/{sport}/{league}/{endpoint}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

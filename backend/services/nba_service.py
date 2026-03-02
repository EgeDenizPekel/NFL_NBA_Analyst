import asyncio
import difflib
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from nba_api.stats.static import players as nba_players
from nba_api.stats.endpoints import playercareerstats, leagueleaders

from utils.cache import cache

BREF_BASE = "https://www.basketball-reference.com"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


async def _espn_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{ESPN_BASE}/{path}")
        r.raise_for_status()
        return r.json()


# ── Basketball-reference helpers ─────────────────────────────────────────────

def _bref_slugs(name: str) -> list[str]:
    """Return ordered list of bref URL slugs to try (suffixes 01–05)."""
    parts = name.lower().split()
    if len(parts) < 2:
        return []
    first, last = parts[0], parts[-1]
    base = (last[:5] + first[:2]).ljust(7, "a")
    return [f"/players/{last[0]}/{base}{n:02d}.html" for n in range(1, 6)]


def _parse_per_game(soup: BeautifulSoup) -> dict | None:
    """Extract the most recent season row from the per_game_stats table."""
    table = soup.find("table", {"id": "per_game_stats"})
    if not table:
        return None

    def td(row, stat: str) -> str:
        el = row.find(["td", "th"], {"data-stat": stat})
        return el.text.strip() if el else "N/A"

    for row in reversed(table.find("tbody").find_all("tr")):
        if not row.find("td", {"data-stat": "pts_per_g"}):
            continue
        pts = td(row, "pts_per_g")
        if not pts:
            continue
        return {
            "season":  td(row, "year_id"),
            "team":    td(row, "team_name_abbr"),
            "pos":     td(row, "pos"),
            "gp":      td(row, "games"),
            "mpg":     td(row, "mp_per_g"),
            "pts":     pts,
            "reb":     td(row, "trb_per_g"),
            "ast":     td(row, "ast_per_g"),
            "stl":     td(row, "stl_per_g"),
            "blk":     td(row, "blk_per_g"),
            "tov":     td(row, "tov_per_g"),
            "fg_pct":  td(row, "fg_pct"),
            "fg3_pct": td(row, "fg3_pct"),
            "ft_pct":  td(row, "ft_pct"),
        }
    return None


# ── nba_api fallback ─────────────────────────────────────────────────────────

def _nba_api_stats(player_id: int) -> dict | None:
    """Synchronous — must be called via asyncio.to_thread()."""
    try:
        career = playercareerstats.PlayerCareerStats(
            player_id=player_id,
            per_mode36="PerGame",
            timeout=15,
        )
        df = career.get_data_frames()[0]  # SeasonTotalsRegularSeason (PerGame)
        if df.empty:
            return None
        row = df.iloc[-1]
        gp = int(row.get("GP", 0))
        if gp == 0:
            return None
        return {
            "season":  str(row.get("SEASON_ID", "N/A")),
            "team":    str(row.get("TEAM_ABBREVIATION", "N/A")),
            "pos":     "N/A",  # not in career stats endpoint
            "gp":      str(gp),
            "mpg":     f"{row.get('MIN', 0):.1f}",
            "pts":     f"{row.get('PTS', 0):.1f}",
            "reb":     f"{row.get('REB', 0):.1f}",
            "ast":     f"{row.get('AST', 0):.1f}",
            "stl":     f"{row.get('STL', 0):.1f}",
            "blk":     f"{row.get('BLK', 0):.1f}",
            "tov":     f"{row.get('TOV', 0):.1f}",
            "fg_pct":  f"{row.get('FG_PCT', 0):.3f}",
            "fg3_pct": f"{row.get('FG3_PCT', 0):.3f}",
            "ft_pct":  f"{row.get('FT_PCT', 0):.3f}",
        }
    except Exception:
        return None


def _format_stats(canonical: str, stats: dict) -> str:
    return (
        f"PLAYER: {canonical} — {stats['team']} ({stats['pos']})\n"
        f"Season: {stats['season']}\n"
        f"Games: {stats['gp']} GP | {stats['mpg']} MPG\n"
        f"Points:   {stats['pts']} PPG\n"
        f"Rebounds: {stats['reb']} RPG\n"
        f"Assists:  {stats['ast']} APG\n"
        f"Steals:   {stats['stl']} SPG | Blocks: {stats['blk']} BPG\n"
        f"FG%: {stats['fg_pct']} | 3P%: {stats['fg3_pct']} | FT%: {stats['ft_pct']}\n"
        f"Turnovers: {stats['tov']} TPG"
    )


class NBAService:

    # ── Player name lookup ───────────────────────────────────────────────────

    async def _get_active_players(self) -> list[dict]:
        cached = cache.get("nba_active_players")
        if cached:
            return cached
        result = await asyncio.to_thread(nba_players.get_active_players)
        cache.set("nba_active_players", result, ttl=3600)
        return result

    async def find_player(self, name: str) -> dict | None:
        active = await self._get_active_players()
        full_names = [p["full_name"] for p in active]
        full_names_lower = [n.lower() for n in full_names]

        matches = difflib.get_close_matches(name.lower(), full_names_lower, n=1, cutoff=0.65)
        if matches:
            return active[full_names_lower.index(matches[0])]

        first_names_lower = [n.split()[0].lower() for n in full_names]
        matches = difflib.get_close_matches(name.lower(), first_names_lower, n=1, cutoff=0.85)
        if matches:
            return active[first_names_lower.index(matches[0])]

        return None

    # ── Player stats: bref primary, nba_api fallback ─────────────────────────

    async def get_player_season_stats(self, player_name: str) -> str:
        cache_key = f"nba_stats_{player_name.lower().replace(' ', '_')}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        player = await self.find_player(player_name)
        canonical = player["full_name"] if player else player_name

        # --- Path 1: basketball-reference scraping ---
        stats = None
        try:
            stats = await asyncio.wait_for(
                self._scrape_bref_stats(canonical),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            pass  # fall through to nba_api
        except Exception:
            pass

        # --- Path 2: nba_api fallback ---
        if stats is None and player:
            stats = await asyncio.to_thread(_nba_api_stats, player["id"])

        if stats is None:
            return f"No current season stats found for {canonical}."

        result = _format_stats(canonical, stats)
        cache.set(cache_key, result, ttl=1800)
        return result

    async def _scrape_bref_stats(self, name: str) -> dict | None:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # Try computed slugs 01–05 first (fast path)
            for path in _bref_slugs(name):
                r = await client.get(BREF_BASE + path, headers=HEADERS)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "lxml")
                stats = _parse_per_game(soup)
                if stats is not None:
                    return stats
                # Page exists but no per_game table — wrong player, try next suffix

            # Fall back to bref search
            r = await client.get(
                f"{BREF_BASE}/search/search.fcgi?search={quote_plus(name)}",
                headers=HEADERS,
            )
            inner = BeautifulSoup(r.text, "lxml")
            link = inner.select_one(".search-item-name a")
            if not link:
                return None
            r = await client.get(BREF_BASE + link["href"], headers=HEADERS)
            soup = BeautifulSoup(r.text, "lxml")
            return _parse_per_game(soup)

    # ── League leaders via nba_api ───────────────────────────────────────────

    async def get_league_leaders(self, category: str = "PTS") -> str:
        cache_key = f"nba_leaders_{category}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        category_map = {
            "PTS":  ("PTS",  "Points"),
            "REB":  ("REB",  "Rebounds"),
            "AST":  ("AST",  "Assists"),
            "STL":  ("STL",  "Steals"),
            "BLK":  ("BLK",  "Blocks"),
            "FG3M": ("FG3M", "3-Pointers Made"),
        }
        stat_col, label = category_map.get(category, ("PTS", "Points"))

        try:
            ll = await asyncio.to_thread(
                leagueleaders.LeagueLeaders,
                per_mode48="PerGame",
                stat_category_abbreviation=stat_col,
            )
            df = ll.get_data_frames()[0]
            if df.empty:
                return f"No NBA leaders data available for {label}."

            lines = [f"NBA LEAGUE LEADERS — {label}:"]
            for i, row in enumerate(df.head(10).itertuples(), 1):
                value = getattr(row, stat_col, "?")
                lines.append(f"{i}. {row.PLAYER} ({row.TEAM}) — {value:.1f}")

            result = "\n".join(lines)
            cache.set(cache_key, result, ttl=1800)
            return result

        except Exception as e:
            return f"Error fetching league leaders: {e}"

    # ── Scoreboard via ESPN ──────────────────────────────────────────────────

    async def get_scoreboard(self) -> str:
        cached = cache.get("nba_scoreboard")
        if cached:
            return cached

        try:
            data = await _espn_get("scoreboard")
            events = data.get("events", [])

            if not events:
                result = "No NBA games scheduled today."
            else:
                lines = [f"NBA GAMES TODAY ({len(events)} games):"]
                for event in events:
                    comp = event.get("competitions", [{}])[0]
                    competitors = comp.get("competitors", [])
                    status = event.get("status", {}).get("type", {}).get("description", "")
                    if len(competitors) >= 2:
                        away = competitors[1]
                        home = competitors[0]
                        away_name = away.get("team", {}).get("displayName", "?")
                        home_name = home.get("team", {}).get("displayName", "?")
                        if status == "Scheduled":
                            lines.append(f"  {away_name} @ {home_name} — Scheduled")
                        else:
                            lines.append(
                                f"  {away_name} {away.get('score', '')} "
                                f"@ {home_name} {home.get('score', '')} ({status})"
                            )
                result = "\n".join(lines)

            cache.set("nba_scoreboard", result, ttl=300)
            return result

        except Exception as e:
            return f"Error fetching NBA scoreboard: {e}"

    # ── Recent news via ESPN ─────────────────────────────────────────────────

    async def get_news(self) -> str:
        cached = cache.get("nba_news")
        if cached:
            return cached

        try:
            data = await _espn_get("news?limit=10")
            articles = data.get("articles", [])
            if not articles:
                return "No recent NBA news available."

            lines = ["RECENT NBA NEWS:"]
            for article in articles[:8]:
                headline = article.get("headline", "")
                description = article.get("description", "")
                if headline:
                    lines.append(f"- {headline}" + (f": {description}" if description else ""))

            result = "\n".join(lines)
            cache.set("nba_news", result, ttl=600)
            return result

        except Exception as e:
            return f"Error fetching NBA news: {e}"

    # ── Standings via ESPN (v2 endpoint) ────────────────────────────────────

    async def get_standings(self) -> str:
        cached = cache.get("nba_standings")
        if cached:
            return cached

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings"
                )
                r.raise_for_status()
                data = r.json()
            children = data.get("children", [])
            lines = ["NBA STANDINGS:"]

            for conference in children:
                conf_name = conference.get("name", "Conference")
                lines.append(f"\n{conf_name}:")
                entries = conference.get("standings", {}).get("entries", [])
                entries = sorted(
                    entries,
                    key=lambda e: int(next(
                        (s["value"] for s in e.get("stats", []) if s["name"] == "playoffSeed"),
                        999,
                    )),
                )
                for i, entry in enumerate(entries[:8], 1):
                    team_name = entry.get("team", {}).get("displayName", "Unknown")
                    stats = {s["name"]: s["displayValue"] for s in entry.get("stats", [])}
                    wins = stats.get("wins", "?")
                    losses = stats.get("losses", "?")
                    pct = stats.get("winPercent", "?")
                    gb = stats.get("gamesBehind", "0")
                    lines.append(f"  {i}. {team_name}: {wins}-{losses} ({pct}) GB: {gb}")

            result = "\n".join(lines)
            cache.set("nba_standings", result, ttl=3600)
            return result

        except Exception as e:
            return f"Error fetching NBA standings: {e}"

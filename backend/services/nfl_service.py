import asyncio
import difflib
from typing import Any

import httpx

from utils.cache import cache

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

# Current season — update each year
NFL_SEASON = 2024


async def _espn_get(path: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{ESPN_BASE}/{path}")
        r.raise_for_status()
        return r.json()


# ── nfl_data_py wrappers (synchronous — always call via asyncio.to_thread) ───

def _load_rosters() -> list[dict]:
    """Load current season roster as list of dicts. Synchronous."""
    import nfl_data_py as nfl
    df = nfl.import_seasonal_rosters([NFL_SEASON], columns=["player_id", "player_name", "position", "team"])
    df = df.dropna(subset=["player_name"])
    return df.to_dict("records")


def _load_seasonal_data() -> list[dict]:
    """Load current season aggregated stats. Synchronous."""
    import nfl_data_py as nfl
    df = nfl.import_seasonal_data([NFL_SEASON], s_type="REG")
    df = df.dropna(subset=["player_display_name"])
    return df.to_dict("records")


def _find_player_in_roster(name: str, roster: list[dict]) -> dict | None:
    """Fuzzy match player name against roster. Synchronous."""
    names = [r["player_name"] for r in roster]
    names_lower = [n.lower() for n in names]
    matches = difflib.get_close_matches(name.lower(), names_lower, n=1, cutoff=0.65)
    if matches:
        return roster[names_lower.index(matches[0])]
    return None


def _find_stats_row(display_name: str, seasonal: list[dict]) -> dict | None:
    """Find a player's seasonal stats row by display name."""
    display_names = [r.get("player_display_name", "") for r in seasonal]
    display_lower = [n.lower() for n in display_names]
    matches = difflib.get_close_matches(display_name.lower(), display_lower, n=1, cutoff=0.65)
    if matches:
        return seasonal[display_lower.index(matches[0])]
    return None


def _format_qb_stats(name: str, row: dict) -> str:
    gp = int(row.get("games", 0))
    cmp = row.get("completions", 0)
    att = row.get("attempts", 0)
    cmp_pct = f"{(cmp / att * 100):.1f}%" if att else "N/A"
    return (
        f"NFL PLAYER: {name} — {row.get('team', 'N/A')} (QB)\n"
        f"Season: {NFL_SEASON} | Games: {gp}\n"
        f"Passing: {int(row.get('passing_yards', 0))} yds | "
        f"{int(row.get('passing_tds', 0))} TD | {int(row.get('interceptions', 0))} INT\n"
        f"Completion%: {cmp_pct} ({int(cmp)}/{int(att)})\n"
        f"Rushing: {int(row.get('rushing_yards', 0))} yds | "
        f"{int(row.get('rushing_tds', 0))} TD"
    )


def _format_rb_stats(name: str, row: dict) -> str:
    gp = int(row.get("games", 0))
    return (
        f"NFL PLAYER: {name} — {row.get('team', 'N/A')} (RB)\n"
        f"Season: {NFL_SEASON} | Games: {gp}\n"
        f"Rushing: {int(row.get('rushing_yards', 0))} yds | "
        f"{int(row.get('rushing_tds', 0))} TD | {int(row.get('carries', 0))} carries\n"
        f"Receiving: {int(row.get('receptions', 0))} rec / {int(row.get('targets', 0))} tgt | "
        f"{int(row.get('receiving_yards', 0))} yds | {int(row.get('receiving_tds', 0))} TD"
    )


def _format_wr_te_stats(name: str, pos: str, row: dict) -> str:
    gp = int(row.get("games", 0))
    return (
        f"NFL PLAYER: {name} — {row.get('team', 'N/A')} ({pos})\n"
        f"Season: {NFL_SEASON} | Games: {gp}\n"
        f"Receiving: {int(row.get('receptions', 0))} rec / {int(row.get('targets', 0))} tgt | "
        f"{int(row.get('receiving_yards', 0))} yds | {int(row.get('receiving_tds', 0))} TD\n"
        f"Rushing: {int(row.get('rushing_yards', 0))} yds | "
        f"{int(row.get('rushing_tds', 0))} TD"
    )


def _format_stats_for_position(name: str, pos: str, row: dict) -> str:
    pos = (pos or "").upper()
    if pos == "QB":
        return _format_qb_stats(name, row)
    if pos == "RB":
        return _format_rb_stats(name, row)
    if pos in ("WR", "TE"):
        return _format_wr_te_stats(name, pos, row)
    # Generic — show whatever is available
    return (
        f"NFL PLAYER: {name} — {row.get('team', 'N/A')} ({pos})\n"
        f"Season: {NFL_SEASON} | Games: {int(row.get('games', 0))}\n"
        f"Passing Yds: {int(row.get('passing_yards', 0))} | "
        f"Rushing Yds: {int(row.get('rushing_yards', 0))} | "
        f"Receiving Yds: {int(row.get('receiving_yards', 0))}"
    )


def _get_leaders_sync(stat_col: str, label: str, n: int = 10) -> str:
    """Return top-N players for a stat column. Synchronous."""
    import nfl_data_py as nfl
    df = nfl.import_seasonal_data([NFL_SEASON], s_type="REG")
    if stat_col not in df.columns:
        return f"Stat '{stat_col}' not available."
    df = df.dropna(subset=["player_display_name", stat_col])
    df = df[df[stat_col] > 0].sort_values(stat_col, ascending=False).head(n)
    lines = [f"NFL LEADERS — {label} ({NFL_SEASON}):"]
    for i, (_, row) in enumerate(df.iterrows(), 1):
        name = row.get("player_display_name", "Unknown")
        team = row.get("team", "")
        pos = row.get("position", "")
        val = row[stat_col]
        lines.append(f"{i}. {name} ({team}/{pos}) — {int(val)}")
    return "\n".join(lines)


class NFLService:

    # ── Player lookup ────────────────────────────────────────────────────────

    async def _get_roster(self) -> list[dict]:
        cached = cache.get("nfl_roster")
        if cached:
            return cached
        roster = await asyncio.to_thread(_load_rosters)
        cache.set("nfl_roster", roster, ttl=3600)
        return roster

    async def _get_seasonal(self) -> list[dict]:
        cached = cache.get("nfl_seasonal")
        if cached:
            return cached
        seasonal = await asyncio.to_thread(_load_seasonal_data)
        cache.set("nfl_seasonal", seasonal, ttl=1800)
        return seasonal

    async def find_player(self, name: str) -> dict | None:
        roster = await self._get_roster()
        return await asyncio.to_thread(_find_player_in_roster, name, roster)

    # ── Player stats ─────────────────────────────────────────────────────────

    async def get_player_season_stats(self, player_name: str) -> str:
        cache_key = f"nfl_stats_{player_name.lower().replace(' ', '_')}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            roster_player = await self.find_player(player_name)
            canonical = roster_player["player_name"] if roster_player else player_name
            pos = roster_player["position"] if roster_player else ""

            seasonal = await self._get_seasonal()
            row = _find_stats_row(canonical, seasonal)
            if row is None:
                return f"No {NFL_SEASON} season stats found for {canonical}."

            result = _format_stats_for_position(canonical, pos, row)
            cache.set(cache_key, result, ttl=1800)
            return result

        except Exception as e:
            return f"Error fetching NFL stats for {player_name}: {e}"

    # ── League leaders ────────────────────────────────────────────────────────

    LEADER_STAT_MAP = {
        "passing_yards":   "Passing Yards",
        "passing_tds":     "Passing TDs",
        "rushing_yards":   "Rushing Yards",
        "rushing_tds":     "Rushing TDs",
        "receiving_yards": "Receiving Yards",
        "receiving_tds":   "Receiving TDs",
        "receptions":      "Receptions",
        "interceptions":   "Interceptions (thrown)",
        "sacks":           "Sacks",
    }

    async def get_league_leaders(self, stat_col: str = "passing_yards") -> str:
        cache_key = f"nfl_leaders_{stat_col}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        label = self.LEADER_STAT_MAP.get(stat_col, stat_col)
        try:
            result = await asyncio.to_thread(_get_leaders_sync, stat_col, label)
            cache.set(cache_key, result, ttl=1800)
            return result
        except Exception as e:
            return f"Error fetching NFL leaders: {e}"

    # ── Scoreboard via ESPN ───────────────────────────────────────────────────

    async def get_scoreboard(self) -> str:
        cached = cache.get("nfl_scoreboard")
        if cached:
            return cached

        try:
            data = await _espn_get("scoreboard")
            events = data.get("events", [])

            if not events:
                result = "No NFL games scheduled today."
            else:
                lines = [f"NFL GAMES TODAY ({len(events)} games):"]
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

            cache.set("nfl_scoreboard", result, ttl=300)
            return result

        except Exception as e:
            return f"Error fetching NFL scoreboard: {e}"

    # ── Standings via ESPN ────────────────────────────────────────────────────

    async def get_standings(self) -> str:
        cached = cache.get("nfl_standings")
        if cached:
            return cached

        try:
            data = await _espn_get("standings")
            children = data.get("children", [])
            lines = ["NFL STANDINGS:"]

            for conference in children:
                conf_name = conference.get("name", "Conference")
                lines.append(f"\n{conf_name}:")
                # NFL standings nest conference > division
                for division in conference.get("children", []):
                    div_name = division.get("name", "Division")
                    lines.append(f"  {div_name}:")
                    entries = division.get("standings", {}).get("entries", [])
                    for entry in entries:
                        team_name = entry.get("team", {}).get("displayName", "Unknown")
                        stats = {s["name"]: s["displayValue"] for s in entry.get("stats", [])}
                        wins = stats.get("wins", "?")
                        losses = stats.get("losses", "?")
                        pct = stats.get("winPercent", "?")
                        lines.append(f"    {team_name}: {wins}-{losses} ({pct})")

            result = "\n".join(lines)
            cache.set("nfl_standings", result, ttl=3600)
            return result

        except Exception as e:
            return f"Error fetching NFL standings: {e}"

    # ── News via ESPN ─────────────────────────────────────────────────────────

    async def get_news(self) -> str:
        cached = cache.get("nfl_news")
        if cached:
            return cached

        try:
            data = await _espn_get("news?limit=10")
            articles = data.get("articles", [])
            if not articles:
                return "No recent NFL news available."

            lines = ["RECENT NFL NEWS:"]
            for article in articles[:8]:
                headline = article.get("headline", "")
                description = article.get("description", "")
                if headline:
                    lines.append(f"- {headline}" + (f": {description}" if description else ""))

            result = "\n".join(lines)
            cache.set("nfl_news", result, ttl=600)
            return result

        except Exception as e:
            return f"Error fetching NFL news: {e}"

import asyncio
import difflib

from services.nba_service import NBAService
from services.nfl_service import NFLService

# ── Sport keywords ────────────────────────────────────────────────────────────

NBA_KEYWORDS = {
    "nba", "basketball",
    "lakers", "celtics", "warriors", "bulls", "heat", "nets", "knicks",
    "bucks", "sixers", "raptors", "cavaliers", "cavs", "pacers", "magic",
    "wizards", "hornets", "hawks", "pistons", "suns", "nuggets", "jazz",
    "thunder", "blazers", "kings", "clippers", "pelicans", "grizzlies",
    "mavericks", "mavs", "spurs", "rockets", "timberwolves", "wolves",
}

NFL_KEYWORDS = {
    "nfl", "football",
    "chiefs", "patriots", "cowboys", "eagles", "49ers", "niners", "packers",
    "bills", "ravens", "bengals", "browns", "steelers", "texans", "colts",
    "jaguars", "titans", "broncos", "raiders", "chargers", "seahawks",
    "rams", "cardinals", "falcons", "panthers", "saints", "buccaneers",
    "bears", "lions", "vikings", "commanders", "giants", "jets", "dolphins",
    "quarterback", "qb", "touchdown", "superbowl", "super bowl", "playoff",
}

# ── Intent keywords ───────────────────────────────────────────────────────────

COMPARISON_KEYWORDS = {"compare", "vs", "versus", "better than", "comparison", "between"}
SCOREBOARD_KEYWORDS = {"today", "tonight", "score", "scores", "scoreboard", "live", "playing today"}
STANDINGS_KEYWORDS  = {"standing", "standings", "record", "conference", "division", "playoff", "ranked"}
LEADERS_KEYWORDS    = {"leader", "leaders", "top scorer", "top scorers", "top shooter", "top shooters",
                       "best shooter", "best shooters", "who leads", "most points",
                       "most rebounds", "most assists", "most yards", "most touchdowns", "most tds",
                       "top qb", "top quarterback", "top receiver", "top rusher"}
STATS_KEYWORDS      = {"stats", "stat", "average", "averaging", "points", "rebounds", "assists",
                       "season", "playing", "performance", "numbers", "doing", "scoring",
                       "ppg", "rpg", "apg", "how is", "how has",
                       "yards", "touchdowns", "passing", "rushing", "receiving"}
NEWS_KEYWORDS       = {"champion", "championship", "title", "who won", "last champion", "won the",
                       "trade", "traded", "signing", "signed", "injury", "injured", "news",
                       "mvp", "award", "winner", "finals", "super bowl"}
PREDICTION_KEYWORDS = {"will win", "going to win", "predict", "prediction", "contender", "contenders",
                       "favorite", "favourites", "best team", "thoughts on", "who should"}

# ── NFL stat category detection ───────────────────────────────────────────────

# Ordered list — more specific compound phrases checked before generic words.
# Avoids "yards" matching passing when the user asks about receiving, etc.
NFL_STAT_PATTERNS: list[tuple[list[str], str]] = [
    # Compound / unambiguous phrases first
    (["receiving td", "receiving tds", "receiving touchdown"],            "receiving_tds"),
    (["rushing td", "rushing tds", "rushing touchdown"],                  "rushing_tds"),
    (["passing td", "passing tds", "touchdown pass", "touchdown passes"], "passing_tds"),
    (["passing yards", "passing yds"],                                    "passing_yards"),
    (["rushing yards", "rushing yds"],                                    "rushing_yards"),
    (["receiving yards", "receiving yds"],                                "receiving_yards"),
    (["receptions", "catches", "catch"],                                  "receptions"),
    # Generic single-word fallbacks (checked after compound phrases)
    (["receiver", "receiving", "wide receiver", "wr stats"],              "receiving_yards"),
    (["rusher", "rushing", "running back", "rb stats"],                   "rushing_yards"),
    (["quarterback", "passing", "qb stats", "passer"],                    "passing_yards"),
    (["sack", "sacks"],                                                   "sacks"),
    (["interception", "interceptions"],                                   "interceptions"),
]


class SportsContextService:
    def __init__(self) -> None:
        self.nba = NBAService()
        self.nfl = NFLService()

    async def build_context(self, message: str, sport_hint: str | None) -> str:
        msg = message.lower()
        sport = self._detect_sport(msg, sport_hint)

        # If no sport keyword found, infer from player names
        if sport is None:
            nba_players = await self._extract_nba_players(msg)
            if nba_players:
                sport = "nba"
            else:
                nfl_players = await self._extract_nfl_players(msg)
                if nfl_players:
                    sport = "nfl"

        if sport == "nba":
            try:
                return await self._nba_context(msg)
            except Exception:
                return ""

        if sport == "nfl":
            try:
                return await self._nfl_context(msg)
            except Exception:
                return ""

        return ""

    # ── Sport detection ───────────────────────────────────────────────────────

    def _detect_sport(self, message: str, hint: str | None) -> str | None:
        if hint in ("nba", "nfl"):
            return hint

        words = set(message.split())
        if words & NBA_KEYWORDS:
            return "nba"
        if words & NFL_KEYWORDS:
            return "nfl"

        # Multi-word team / phrase checks
        if "76ers" in message or "trail blazers" in message:
            return "nba"
        if "super bowl" in message or "49ers" in message:
            return "nfl"

        return None

    # ── Intent detection ──────────────────────────────────────────────────────

    def _detect_intent(self, message: str) -> str:
        if any(kw in message for kw in COMPARISON_KEYWORDS):
            return "comparison"
        # STANDINGS before SCOREBOARD: "standings today" should fetch standings,
        # not today's scoreboard. Standing keywords are specific enough that they
        # won't accidentally match pure scoreboard queries.
        if any(kw in message for kw in STANDINGS_KEYWORDS):
            return "standings"
        if any(kw in message for kw in SCOREBOARD_KEYWORDS):
            return "scoreboard"
        # PREDICTION before NEWS: prediction queries often contain news-adjacent words
        # ("title", "championship") but also "will win" / "going to win" which are
        # unambiguously future-oriented. NEWS check catches past-tense queries after.
        if any(kw in message for kw in PREDICTION_KEYWORDS):
            return "prediction"
        if any(kw in message for kw in NEWS_KEYWORDS):
            return "news"
        if any(kw in message for kw in LEADERS_KEYWORDS):
            return "leaders"
        return "player_stats"

    def _detect_nba_leaders_category(self, message: str) -> str:
        if any(w in message for w in ("rebound", "rebounds", "rebounding")):
            return "REB"
        if any(w in message for w in ("assist", "assists")):
            return "AST"
        if any(w in message for w in ("steal", "steals")):
            return "STL"
        if any(w in message for w in ("block", "blocks")):
            return "BLK"
        return "PTS"

    def _detect_nfl_leaders_stat(self, message: str) -> str:
        for keywords, stat_col in NFL_STAT_PATTERNS:
            if any(kw in message for kw in keywords):
                return stat_col
        return "passing_yards"

    # ── Player entity extraction ──────────────────────────────────────────────

    async def _extract_nba_players(self, message: str) -> list[str]:
        active = await self.nba._get_active_players()
        full_names = [p["full_name"] for p in active]
        names_lower = [n.lower() for n in full_names]

        words = message.split()
        found: list[str] = []

        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                if len(found) >= 2:
                    break
                phrase = " ".join(words[i : i + n])
                matches = difflib.get_close_matches(phrase, names_lower, n=1, cutoff=0.72)
                if matches:
                    idx = names_lower.index(matches[0])
                    canonical = full_names[idx]
                    if canonical not in found:
                        found.append(canonical)
            if len(found) >= 2:
                break

        return found

    async def _extract_nfl_players(self, message: str) -> list[str]:
        try:
            roster = await self.nfl._get_roster()
        except Exception:
            return []

        names = [r["player_name"] for r in roster]
        names_lower = [n.lower() for n in names]

        words = message.split()
        found: list[str] = []

        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                if len(found) >= 2:
                    break
                phrase = " ".join(words[i : i + n])
                matches = difflib.get_close_matches(phrase, names_lower, n=1, cutoff=0.72)
                if matches:
                    idx = names_lower.index(matches[0])
                    canonical = names[idx]
                    if canonical not in found:
                        found.append(canonical)
            if len(found) >= 2:
                break

        return found

    # ── NBA context builder ───────────────────────────────────────────────────

    async def _nba_context(self, message: str) -> str:
        intent = self._detect_intent(message)
        parts: list[str] = []

        if intent in ("player_stats", "comparison"):
            players = await self._extract_nba_players(message)
            if players:
                results = await asyncio.gather(
                    *[self.nba.get_player_season_stats(p) for p in players]
                )
                parts.extend(r for r in results if r)

        elif intent == "standings":
            text = await self.nba.get_standings()
            if text:
                parts.append(text)

        elif intent == "scoreboard":
            text = await self.nba.get_scoreboard()
            if text:
                parts.append(text)

        elif intent == "leaders":
            category = self._detect_nba_leaders_category(message)
            text = await self.nba.get_league_leaders(category)
            if text:
                parts.append(text)

        elif intent == "news":
            news, standings = await asyncio.gather(
                self.nba.get_news(),
                self.nba.get_standings(),
            )
            if news:
                parts.append(news)
            if standings:
                parts.append(standings)

        elif intent == "prediction":
            standings, leaders = await asyncio.gather(
                self.nba.get_standings(),
                self.nba.get_league_leaders("PTS"),
            )
            if standings:
                parts.append(standings)
            if leaders:
                parts.append(leaders)

        return "\n\n".join(parts)

    # ── NFL context builder ───────────────────────────────────────────────────

    async def _nfl_context(self, message: str) -> str:
        intent = self._detect_intent(message)
        parts: list[str] = []

        if intent in ("player_stats", "comparison"):
            players = await self._extract_nfl_players(message)
            if players:
                results = await asyncio.gather(
                    *[self.nfl.get_player_season_stats(p) for p in players]
                )
                parts.extend(r for r in results if r)

        elif intent == "standings":
            text = await self.nfl.get_standings()
            if text:
                parts.append(text)

        elif intent == "scoreboard":
            text = await self.nfl.get_scoreboard()
            if text:
                parts.append(text)

        elif intent == "leaders":
            stat_col = self._detect_nfl_leaders_stat(message)
            text = await self.nfl.get_league_leaders(stat_col)
            if text:
                parts.append(text)

        elif intent == "news":
            news, standings = await asyncio.gather(
                self.nfl.get_news(),
                self.nfl.get_standings(),
            )
            if news:
                parts.append(news)
            if standings:
                parts.append(standings)

        elif intent == "prediction":
            standings, leaders = await asyncio.gather(
                self.nfl.get_standings(),
                self.nfl.get_league_leaders("passing_yards"),
            )
            if standings:
                parts.append(standings)
            if leaders:
                parts.append(leaders)

        return "\n\n".join(parts)

"""
Unit tests for NBAService.

Fast tests mock all I/O. Integration tests (marked) hit real endpoints.
Run fast tests only:  pytest -m "not integration" tests/test_nba_service.py
Run all:              pytest tests/test_nba_service.py
"""
import textwrap

import pandas as pd
import pytest
from bs4 import BeautifulSoup
from unittest.mock import AsyncMock, MagicMock, patch

from services.nba_service import NBAService, _bref_slugs, _parse_per_game, _nba_api_stats
from utils.cache import TTLCache


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    """Each test gets a clean cache so prior results don't bleed through."""
    from utils import cache as cache_module
    fresh = TTLCache()
    monkeypatch.setattr(cache_module, "cache", fresh)
    # Also patch the reference inside nba_service
    import services.nba_service as nba_module
    monkeypatch.setattr(nba_module, "cache", fresh)
    return fresh


@pytest.fixture
def svc():
    return NBAService()


FAKE_PLAYERS = [
    {"id": 2544,  "full_name": "LeBron James",    "is_active": True},
    {"id": 201939,"full_name": "Stephen Curry",   "is_active": True},
    {"id": 1628369,"full_name": "Jayson Tatum",   "is_active": True},
    {"id": 203507, "full_name": "Giannis Antetokounmpo", "is_active": True},
]


# ── _bref_slugs ───────────────────────────────────────────────────────────────

class TestBrefSlugs:
    def test_lebron_james(self):
        slugs = _bref_slugs("LeBron James")
        assert slugs[0] == "/players/j/jamesle01.html"
        assert len(slugs) == 5

    def test_stephen_curry(self):
        slugs = _bref_slugs("Stephen Curry")
        assert slugs[0] == "/players/c/curryst01.html"

    def test_jayson_tatum(self):
        slugs = _bref_slugs("Jayson Tatum")
        assert slugs[0] == "/players/t/tatumja01.html"

    def test_giannis(self):
        slugs = _bref_slugs("Giannis Antetokounmpo")
        # last[:5] = "anteto", first[:2] = "gi" → "antetogi01"
        assert "/players/a/" in slugs[0]
        assert slugs[0].endswith("01.html")

    def test_slug_suffix_sequence(self):
        slugs = _bref_slugs("LeBron James")
        assert slugs[0].endswith("01.html")
        assert slugs[1].endswith("02.html")
        assert slugs[4].endswith("05.html")

    def test_single_name_returns_empty(self):
        assert _bref_slugs("Madonna") == []


# ── find_player ───────────────────────────────────────────────────────────────

class TestFindPlayer:
    async def test_exact_match(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_active_players", AsyncMock(return_value=FAKE_PLAYERS))
        result = await svc.find_player("LeBron James")
        assert result["id"] == 2544

    async def test_fuzzy_match(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_active_players", AsyncMock(return_value=FAKE_PLAYERS))
        result = await svc.find_player("lebron james")
        assert result is not None
        assert result["full_name"] == "LeBron James"

    async def test_close_spelling(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_active_players", AsyncMock(return_value=FAKE_PLAYERS))
        result = await svc.find_player("Steph Curry")
        # "steph curry" should fuzzy-match "stephen curry" or via first-name match
        assert result is not None

    async def test_no_match(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_active_players", AsyncMock(return_value=FAKE_PLAYERS))
        result = await svc.find_player("Xyzzy Nonexistent")
        assert result is None


# ── get_player_season_stats ───────────────────────────────────────────────────

FAKE_STATS = {
    "season": "2024-25", "team": "LAL", "pos": "SF",
    "gp": "52", "mpg": "35.0",
    "pts": "25.3", "reb": "7.1", "ast": "8.2",
    "stl": "1.2", "blk": "0.6", "tov": "3.4",
    "fg_pct": ".512", "fg3_pct": ".412", "ft_pct": ".751",
}


class TestGetPlayerSeasonStats:
    async def test_cache_hit_skips_network(self, svc, fresh_cache):
        fresh_cache.set("nba_stats_lebron_james", "CACHED RESULT", ttl=60)
        result = await svc.get_player_season_stats("LeBron James")
        assert result == "CACHED RESULT"

    async def test_bref_success_returns_formatted_string(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "find_player", AsyncMock(return_value=FAKE_PLAYERS[0]))
        monkeypatch.setattr(svc, "_scrape_bref_stats", AsyncMock(return_value=FAKE_STATS))

        result = await svc.get_player_season_stats("LeBron James")
        assert "LeBron James" in result
        assert "25.3 PPG" in result
        assert "7.1 RPG" in result
        assert "8.2 APG" in result

    async def test_bref_timeout_falls_back_to_nba_api(self, svc, monkeypatch):
        import asyncio
        monkeypatch.setattr(svc, "find_player", AsyncMock(return_value=FAKE_PLAYERS[0]))
        monkeypatch.setattr(svc, "_scrape_bref_stats", AsyncMock(side_effect=asyncio.TimeoutError))

        fake_api_stats = {**FAKE_STATS, "pos": "N/A", "source": "nba_api"}
        with patch("services.nba_service._nba_api_stats", return_value=fake_api_stats):
            result = await svc.get_player_season_stats("LeBron James")
        assert "LeBron James" in result

    async def test_bref_exception_falls_back_to_nba_api(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "find_player", AsyncMock(return_value=FAKE_PLAYERS[0]))
        monkeypatch.setattr(svc, "_scrape_bref_stats", AsyncMock(side_effect=Exception("network error")))

        with patch("services.nba_service._nba_api_stats", return_value=FAKE_STATS):
            result = await svc.get_player_season_stats("LeBron James")
        assert "LeBron James" in result

    async def test_both_sources_fail_returns_not_found_message(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "find_player", AsyncMock(return_value=FAKE_PLAYERS[0]))
        monkeypatch.setattr(svc, "_scrape_bref_stats", AsyncMock(return_value=None))
        with patch("services.nba_service._nba_api_stats", return_value=None):
            result = await svc.get_player_season_stats("LeBron James")
        assert "No current season stats" in result

    async def test_result_is_cached_after_fetch(self, svc, monkeypatch, fresh_cache):
        monkeypatch.setattr(svc, "find_player", AsyncMock(return_value=FAKE_PLAYERS[0]))
        monkeypatch.setattr(svc, "_scrape_bref_stats", AsyncMock(return_value=FAKE_STATS))

        await svc.get_player_season_stats("LeBron James")
        assert fresh_cache.get("nba_stats_lebron_james") is not None


# ── ESPN endpoints ────────────────────────────────────────────────────────────

class TestGetScoreboard:
    async def test_no_games(self, svc, monkeypatch):
        import services.nba_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value={"events": []}))
        result = await svc.get_scoreboard()
        assert "No NBA games" in result

    async def test_formats_scheduled_game(self, svc, monkeypatch):
        import services.nba_service as m
        fake_event = {
            "status": {"type": {"description": "Scheduled"}},
            "competitions": [{
                "competitors": [
                    {"team": {"displayName": "Boston Celtics"}, "score": ""},
                    {"team": {"displayName": "Los Angeles Lakers"}, "score": ""},
                ]
            }]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value={"events": [fake_event]}))
        result = await svc.get_scoreboard()
        assert "Boston Celtics" in result
        assert "Los Angeles Lakers" in result
        assert "Scheduled" in result

    async def test_formats_in_progress_game(self, svc, monkeypatch):
        import services.nba_service as m
        fake_event = {
            "status": {"type": {"description": "In Progress"}},
            "competitions": [{
                "competitors": [
                    {"team": {"displayName": "Boston Celtics"}, "score": "87"},
                    {"team": {"displayName": "Los Angeles Lakers"}, "score": "83"},
                ]
            }]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value={"events": [fake_event]}))
        result = await svc.get_scoreboard()
        assert "87" in result
        assert "83" in result

    async def test_espn_error_returns_error_string(self, svc, monkeypatch):
        import services.nba_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(side_effect=Exception("timeout")))
        result = await svc.get_scoreboard()
        assert "Error fetching" in result


class TestGetStandings:
    async def test_formats_conference_and_teams(self, svc, monkeypatch):
        import services.nba_service as m
        fake_data = {
            "children": [{
                "name": "Eastern Conference",
                "standings": {
                    "entries": [{
                        "team": {"displayName": "Boston Celtics"},
                        "stats": [
                            {"name": "wins", "displayValue": "52"},
                            {"name": "losses", "displayValue": "10"},
                            {"name": "winPercent", "displayValue": ".839"},
                            {"name": "gamesBehind", "displayValue": "0"},
                        ]
                    }]
                }
            }]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value=fake_data))
        result = await svc.get_standings()
        assert "Eastern Conference" in result
        assert "Boston Celtics" in result
        assert "52-10" in result

    async def test_espn_error_returns_error_string(self, svc, monkeypatch):
        import services.nba_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(side_effect=Exception("timeout")))
        result = await svc.get_standings()
        assert "Error fetching" in result


class TestGetLeagueLeaders:
    async def test_formats_top_scorers(self, svc, monkeypatch):
        import services.nba_service as m
        fake_data = {
            "categories": [{
                "name": "scoring",
                "leaders": [
                    {"athlete": {"displayName": "Shai Gilgeous-Alexander"}, "team": {"abbreviation": "OKC"}, "displayValue": "32.1"},
                    {"athlete": {"displayName": "Giannis Antetokounmpo"}, "team": {"abbreviation": "MIL"}, "displayValue": "29.8"},
                ]
            }]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value=fake_data))
        result = await svc.get_league_leaders("PTS")
        assert "Shai Gilgeous-Alexander" in result
        assert "32.1" in result

    async def test_category_not_found_uses_first(self, svc, monkeypatch):
        """If category name doesn't match, fall back to first category."""
        import services.nba_service as m
        fake_data = {
            "categories": [{
                "name": "someUnknownCategory",
                "leaders": [
                    {"athlete": {"displayName": "Player A"}, "team": {"abbreviation": "ABC"}, "displayValue": "10.0"},
                ]
            }]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value=fake_data))
        result = await svc.get_league_leaders("PTS")
        assert "Player A" in result

    async def test_empty_categories_returns_unavailable(self, svc, monkeypatch):
        import services.nba_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value={"categories": []}))
        result = await svc.get_league_leaders("PTS")
        assert "unavailable" in result.lower()

    async def test_espn_error_returns_error_string(self, svc, monkeypatch):
        import services.nba_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(side_effect=Exception("timeout")))
        result = await svc.get_league_leaders("PTS")
        assert "Error" in result


# ── _parse_per_game (bref HTML parser) ───────────────────────────────────────
# These tests exercise the actual BeautifulSoup parsing logic against minimal
# HTML fixtures that mirror the real basketball-reference table structure.
# They will catch bref data-stat renames or structural changes before production.

def _make_bref_html(*seasons: dict) -> BeautifulSoup:
    """
    Build a minimal bref per_game_stats table with one row per season dict.
    Keys match the data-stat attribute names used in _parse_per_game.
    Seasons should be ordered oldest → newest (function reverses to find latest).
    """
    rows = ""
    for s in seasons:
        cells = "".join(
            f'<td data-stat="{k}">{v}</td>' for k, v in s.items()
        )
        rows += f"<tr>{cells}</tr>"
    html = f'<table id="per_game_stats"><tbody>{rows}</tbody></table>'
    return BeautifulSoup(html, "lxml")


BREF_ROW_2425 = {
    "year_id": "2024-25", "team_name_abbr": "LAL", "pos": "SF",
    "games": "52", "mp_per_g": "35.0", "pts_per_g": "25.3",
    "trb_per_g": "7.1", "ast_per_g": "8.2", "stl_per_g": "1.2",
    "blk_per_g": "0.6", "tov_per_g": "3.4",
    "fg_pct": ".512", "fg3_pct": ".412", "ft_pct": ".751",
}

BREF_ROW_2324 = {**BREF_ROW_2425, "year_id": "2023-24", "pts_per_g": "24.0"}


class TestParsePerGame:
    def test_single_row_returns_correct_stats(self):
        soup = _make_bref_html(BREF_ROW_2425)
        result = _parse_per_game(soup)
        assert result is not None
        assert result["pts"]     == "25.3"
        assert result["reb"]     == "7.1"
        assert result["ast"]     == "8.2"
        assert result["season"]  == "2024-25"
        assert result["team"]    == "LAL"
        assert result["fg_pct"]  == ".512"
        assert result["fg3_pct"] == ".412"
        assert result["ft_pct"]  == ".751"

    def test_multiple_rows_returns_most_recent(self):
        """Rows are oldest→newest in HTML; function must return the newest."""
        soup = _make_bref_html(BREF_ROW_2324, BREF_ROW_2425)
        result = _parse_per_game(soup)
        assert result is not None
        assert result["season"] == "2024-25"
        assert result["pts"]    == "25.3"

    def test_missing_table_returns_none(self):
        soup = BeautifulSoup("<html><body>no table here</body></html>", "lxml")
        assert _parse_per_game(soup) is None

    def test_row_without_pts_cell_is_skipped(self):
        """Header/separator rows have no pts_per_g td — must be skipped."""
        header_row = {"year_id": "Season", "team_name_abbr": "Tm"}  # no pts_per_g
        soup = _make_bref_html(header_row, BREF_ROW_2425)
        result = _parse_per_game(soup)
        assert result is not None
        assert result["pts"] == "25.3"

    def test_missing_individual_stat_returns_na(self):
        """If a stat cell is absent, td() falls back to 'N/A'."""
        row_without_blk = {k: v for k, v in BREF_ROW_2425.items() if k != "blk_per_g"}
        soup = _make_bref_html(row_without_blk)
        result = _parse_per_game(soup)
        assert result is not None
        assert result["blk"] == "N/A"

    def test_empty_tbody_returns_none(self):
        soup = BeautifulSoup(
            '<table id="per_game_stats"><tbody></tbody></table>', "lxml"
        )
        assert _parse_per_game(soup) is None


# ── _nba_api_stats (nba_api DataFrame handling) ───────────────────────────────
# These tests exercise the actual DataFrame-reading logic in _nba_api_stats
# using fake DataFrames that mirror the real PlayerCareerStats(PerGame) schema.
# They will catch column renames in the nba_api package.

def _make_career_df(**overrides) -> pd.DataFrame:
    """Minimal PlayerCareerStats PerGame DataFrame row."""
    defaults = {
        "SEASON_ID": "2024-25",
        "TEAM_ABBREVIATION": "LAL",
        "GP": 52,
        "MIN": 35.0,
        "PTS": 25.3,
        "REB": 7.1,
        "AST": 8.2,
        "STL": 1.2,
        "BLK": 0.6,
        "TOV": 3.4,
        "FG_PCT": 0.512,
        "FG3_PCT": 0.412,
        "FT_PCT": 0.751,
    }
    defaults.update(overrides)
    return pd.DataFrame([defaults])


def _mock_career_stats(df: pd.DataFrame):
    """Return a mock PlayerCareerStats object whose get_data_frames()[0] == df."""
    mock = MagicMock()
    mock.get_data_frames.return_value = [df]
    return mock


class TestNbaApiStats:
    def test_returns_correct_values_from_dataframe(self):
        df = _make_career_df()
        with patch("services.nba_service.playercareerstats.PlayerCareerStats",
                   return_value=_mock_career_stats(df)):
            result = _nba_api_stats(2544)
        assert result is not None
        assert result["pts"]  == "25.3"
        assert result["reb"]  == "7.1"
        assert result["ast"]  == "8.2"
        assert result["team"] == "LAL"
        assert result["season"] == "2024-25"

    def test_uses_last_row_as_current_season(self):
        """nba_api returns one row per season; last row = most recent."""
        old = _make_career_df(SEASON_ID="2023-24", PTS=24.0)
        new = _make_career_df(SEASON_ID="2024-25", PTS=25.3)
        df = pd.concat([old, new], ignore_index=True)
        with patch("services.nba_service.playercareerstats.PlayerCareerStats",
                   return_value=_mock_career_stats(df)):
            result = _nba_api_stats(2544)
        assert result["season"] == "2024-25"
        assert result["pts"]    == "25.3"

    def test_zero_gp_returns_none(self):
        """A row with GP=0 means no games played — must return None."""
        df = _make_career_df(GP=0)
        with patch("services.nba_service.playercareerstats.PlayerCareerStats",
                   return_value=_mock_career_stats(df)):
            result = _nba_api_stats(2544)
        assert result is None

    def test_empty_dataframe_returns_none(self):
        empty_df = pd.DataFrame(columns=["SEASON_ID", "GP", "PTS"])
        with patch("services.nba_service.playercareerstats.PlayerCareerStats",
                   return_value=_mock_career_stats(empty_df)):
            result = _nba_api_stats(2544)
        assert result is None

    def test_api_exception_returns_none(self):
        with patch("services.nba_service.playercareerstats.PlayerCareerStats",
                   side_effect=Exception("NBA API timeout")):
            result = _nba_api_stats(2544)
        assert result is None

    def test_fg_pct_formatted_to_three_decimals(self):
        df = _make_career_df(FG_PCT=0.5123456)
        with patch("services.nba_service.playercareerstats.PlayerCareerStats",
                   return_value=_mock_career_stats(df)):
            result = _nba_api_stats(2544)
        assert result["fg_pct"] == "0.512"

    def test_pos_is_na_since_not_in_endpoint(self):
        """PlayerCareerStats doesn't include position — must be 'N/A'."""
        df = _make_career_df()
        with patch("services.nba_service.playercareerstats.PlayerCareerStats",
                   return_value=_mock_career_stats(df)):
            result = _nba_api_stats(2544)
        assert result["pos"] == "N/A"


# ── Integration tests (real network) ─────────────────────────────────────────

@pytest.mark.integration
class TestNBAIntegration:
    async def test_espn_scoreboard_reachable(self, svc):
        result = await svc.get_scoreboard()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_espn_standings_reachable(self, svc):
        result = await svc.get_standings()
        assert isinstance(result, str)
        assert "NBA STANDINGS" in result

    async def test_espn_leaders_reachable(self, svc):
        result = await svc.get_league_leaders("PTS")
        assert isinstance(result, str)

    async def test_player_stats_lebron(self, svc):
        result = await svc.get_player_season_stats("LeBron James")
        assert isinstance(result, str)
        assert "LeBron James" in result

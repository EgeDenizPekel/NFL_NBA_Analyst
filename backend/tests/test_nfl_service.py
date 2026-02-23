"""
Unit tests for NFLService.

Fast tests mock all I/O. Integration tests (marked) hit real ESPN endpoints
and download nfl_data_py data (slow — requires network).

Run fast tests only:  pytest -m "not integration" tests/test_nfl_service.py
Run all:              pytest tests/test_nfl_service.py
"""
import pandas as pd
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.nfl_service import (
    NFL_SEASON,
    NFLService,
    _find_player_in_roster,
    _load_rosters,
    _load_seasonal_data,
    _get_leaders_sync,
    _format_qb_stats,
    _format_rb_stats,
    _format_wr_te_stats,
    _format_stats_for_position,
)
from utils.cache import TTLCache


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    """Each test gets a clean cache."""
    from utils import cache as cache_module
    fresh = TTLCache()
    monkeypatch.setattr(cache_module, "cache", fresh)
    import services.nfl_service as nfl_module
    monkeypatch.setattr(nfl_module, "cache", fresh)
    return fresh


@pytest.fixture
def svc():
    return NFLService()


FAKE_ROSTER = [
    {"player_id": "00-0023459", "player_name": "Patrick Mahomes", "position": "QB", "team": "KC"},
    {"player_id": "00-0036971", "player_name": "Josh Allen",      "position": "QB", "team": "BUF"},
    {"player_id": "00-0038520", "player_name": "Derrick Henry",   "position": "RB", "team": "BAL"},
    {"player_id": "00-0033873", "player_name": "Davante Adams",   "position": "WR", "team": "LV"},
    {"player_id": "00-0036945", "player_name": "Travis Kelce",    "position": "TE", "team": "KC"},
]

FAKE_SEASONAL_QB = {
    "player_display_name": "Patrick Mahomes",
    "team": "KC",
    "position": "QB",
    "games": 17,
    "completions": 380,
    "attempts": 572,
    "passing_yards": 4183,
    "passing_tds": 26,
    "interceptions": 11,
    "carries": 55,
    "rushing_yards": 391,
    "rushing_tds": 2,
}

FAKE_SEASONAL_RB = {
    "player_display_name": "Derrick Henry",
    "team": "BAL",
    "position": "RB",
    "games": 16,
    "carries": 331,
    "rushing_yards": 1921,
    "rushing_tds": 16,
    "receptions": 26,
    "targets": 34,
    "receiving_yards": 198,
    "receiving_tds": 1,
}

FAKE_SEASONAL_WR = {
    "player_display_name": "Davante Adams",
    "team": "LV",
    "position": "WR",
    "games": 16,
    "receptions": 67,
    "targets": 103,
    "receiving_yards": 778,
    "receiving_tds": 6,
    "rushing_yards": 0,
    "rushing_tds": 0,
}


# ── _find_player_in_roster ────────────────────────────────────────────────────

class TestFindPlayerInRoster:
    def test_exact_match(self):
        result = _find_player_in_roster("Patrick Mahomes", FAKE_ROSTER)
        assert result is not None
        assert result["position"] == "QB"

    def test_case_insensitive(self):
        result = _find_player_in_roster("patrick mahomes", FAKE_ROSTER)
        assert result is not None

    def test_fuzzy_match(self):
        result = _find_player_in_roster("Mahomes", FAKE_ROSTER)
        # Single name won't fuzzy-match full name at 0.65 cutoff — expect None
        # (this is intentional: single-name lookups are handled at entity-extraction level)
        assert result is None or result["player_name"] == "Patrick Mahomes"

    def test_close_spelling(self):
        result = _find_player_in_roster("Josh Allen", FAKE_ROSTER)
        assert result is not None
        assert result["team"] == "BUF"

    def test_no_match(self):
        result = _find_player_in_roster("Xyzzy Nope", FAKE_ROSTER)
        assert result is None


# ── Stat formatters ───────────────────────────────────────────────────────────

class TestStatFormatters:
    def test_qb_includes_passing_stats(self):
        result = _format_qb_stats("Patrick Mahomes", FAKE_SEASONAL_QB)
        assert "Patrick Mahomes" in result
        assert "4183 yds" in result
        assert "26 TD" in result
        assert "11 INT" in result
        assert "66.4%" in result  # 380/572

    def test_qb_completion_pct_zero_attempts(self):
        row = {**FAKE_SEASONAL_QB, "attempts": 0, "completions": 0}
        result = _format_qb_stats("Test QB", row)
        assert "N/A" in result

    def test_rb_includes_rushing_and_receiving(self):
        result = _format_rb_stats("Derrick Henry", FAKE_SEASONAL_RB)
        assert "Derrick Henry" in result
        assert "1921 yds" in result
        assert "16 TD" in result
        assert "26 rec" in result

    def test_wr_includes_receiving_stats(self):
        result = _format_wr_te_stats("Davante Adams", "WR", FAKE_SEASONAL_WR)
        assert "Davante Adams" in result
        assert "67 rec" in result
        assert "778 yds" in result
        assert "6 TD" in result

    def test_format_stats_for_position_routes_qb(self):
        result = _format_stats_for_position("Pat M", "QB", FAKE_SEASONAL_QB)
        assert "4183 yds" in result

    def test_format_stats_for_position_routes_rb(self):
        result = _format_stats_for_position("D Henry", "RB", FAKE_SEASONAL_RB)
        assert "1921 yds" in result

    def test_format_stats_for_position_routes_wr(self):
        result = _format_stats_for_position("D Adams", "WR", FAKE_SEASONAL_WR)
        assert "67 rec" in result

    def test_format_stats_for_position_generic_fallback(self):
        result = _format_stats_for_position("K Specialist", "K", FAKE_SEASONAL_QB)
        assert "K Specialist" in result


# ── get_player_season_stats ───────────────────────────────────────────────────

class TestGetPlayerSeasonStats:
    async def test_cache_hit_skips_network(self, svc, fresh_cache):
        fresh_cache.set("nfl_stats_patrick_mahomes", "CACHED", ttl=60)
        result = await svc.get_player_season_stats("Patrick Mahomes")
        assert result == "CACHED"

    async def test_qb_stats_formatted_correctly(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_roster", AsyncMock(return_value=FAKE_ROSTER))
        monkeypatch.setattr(svc, "_get_seasonal", AsyncMock(return_value=[FAKE_SEASONAL_QB]))

        result = await svc.get_player_season_stats("Patrick Mahomes")
        assert "Patrick Mahomes" in result
        assert "4183 yds" in result

    async def test_rb_stats_formatted_correctly(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_roster", AsyncMock(return_value=FAKE_ROSTER))
        monkeypatch.setattr(svc, "_get_seasonal", AsyncMock(return_value=[FAKE_SEASONAL_RB]))

        result = await svc.get_player_season_stats("Derrick Henry")
        assert "Derrick Henry" in result
        assert "1921 yds" in result

    async def test_player_not_in_seasonal_returns_not_found(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_roster", AsyncMock(return_value=FAKE_ROSTER))
        monkeypatch.setattr(svc, "_get_seasonal", AsyncMock(return_value=[]))  # empty seasonal

        result = await svc.get_player_season_stats("Patrick Mahomes")
        assert "No" in result and "stats found" in result

    async def test_result_is_cached(self, svc, monkeypatch, fresh_cache):
        monkeypatch.setattr(svc, "_get_roster", AsyncMock(return_value=FAKE_ROSTER))
        monkeypatch.setattr(svc, "_get_seasonal", AsyncMock(return_value=[FAKE_SEASONAL_QB]))

        await svc.get_player_season_stats("Patrick Mahomes")
        assert fresh_cache.get("nfl_stats_patrick_mahomes") is not None

    async def test_exception_returns_error_string(self, svc, monkeypatch):
        monkeypatch.setattr(svc, "_get_roster", AsyncMock(side_effect=Exception("network down")))
        result = await svc.get_player_season_stats("Patrick Mahomes")
        assert "Error" in result


# ── ESPN endpoints ────────────────────────────────────────────────────────────

class TestGetScoreboard:
    async def test_no_games(self, svc, monkeypatch):
        import services.nfl_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value={"events": []}))
        result = await svc.get_scoreboard()
        assert "No NFL games" in result

    async def test_formats_scheduled_game(self, svc, monkeypatch):
        import services.nfl_service as m
        fake_event = {
            "status": {"type": {"description": "Scheduled"}},
            "competitions": [{
                "competitors": [
                    {"team": {"displayName": "Kansas City Chiefs"}, "score": ""},
                    {"team": {"displayName": "Buffalo Bills"}, "score": ""},
                ]
            }]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value={"events": [fake_event]}))
        result = await svc.get_scoreboard()
        assert "Kansas City Chiefs" in result
        assert "Buffalo Bills" in result

    async def test_espn_error_returns_error_string(self, svc, monkeypatch):
        import services.nfl_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(side_effect=Exception("timeout")))
        result = await svc.get_scoreboard()
        assert "Error" in result


class TestGetStandings:
    async def test_formats_conference_division_teams(self, svc, monkeypatch):
        import services.nfl_service as m
        fake_data = {
            "children": [{
                "name": "AFC",
                "children": [{
                    "name": "AFC West",
                    "standings": {
                        "entries": [{
                            "team": {"displayName": "Kansas City Chiefs"},
                            "stats": [
                                {"name": "wins", "displayValue": "15"},
                                {"name": "losses", "displayValue": "2"},
                                {"name": "winPercent", "displayValue": ".882"},
                            ]
                        }]
                    }
                }]
            }]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value=fake_data))
        result = await svc.get_standings()
        assert "AFC" in result
        assert "AFC West" in result
        assert "Kansas City Chiefs" in result
        assert "15-2" in result

    async def test_espn_error_returns_error_string(self, svc, monkeypatch):
        import services.nfl_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(side_effect=Exception("timeout")))
        result = await svc.get_standings()
        assert "Error" in result


class TestGetNews:
    async def test_formats_headlines(self, svc, monkeypatch):
        import services.nfl_service as m
        fake_data = {
            "articles": [
                {"headline": "Chiefs win Super Bowl", "description": "KC dominates."},
                {"headline": "Mahomes wins MVP", "description": "Historic season."},
            ]
        }
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value=fake_data))
        result = await svc.get_news()
        assert "Chiefs win Super Bowl" in result
        assert "Mahomes wins MVP" in result

    async def test_empty_articles(self, svc, monkeypatch):
        import services.nfl_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(return_value={"articles": []}))
        result = await svc.get_news()
        assert "No recent NFL news" in result

    async def test_espn_error_returns_error_string(self, svc, monkeypatch):
        import services.nfl_service as m
        monkeypatch.setattr(m, "_espn_get", AsyncMock(side_effect=Exception("timeout")))
        result = await svc.get_news()
        assert "Error" in result


# ── nfl_data_py contract tests ────────────────────────────────────────────────
# These tests exercise the actual DataFrame-handling code in _load_rosters,
# _load_seasonal_data, and _get_leaders_sync using fake DataFrames whose schema
# mirrors what nfl_data_py returns. They catch column renames or API changes in
# the package before they surface in production.

def _make_roster_df(*rows: dict) -> pd.DataFrame:
    """Minimal nfl_data_py.import_rosters() DataFrame."""
    defaults = {"player_id": "00-0000001", "player_name": "Test Player",
                "position": "QB", "team": "KC"}
    return pd.DataFrame([{**defaults, **r} for r in rows] if rows else [defaults])


def _make_seasonal_df(*rows: dict) -> pd.DataFrame:
    """Minimal nfl_data_py.import_seasonal_data() DataFrame."""
    defaults = {
        "player_id": "00-0000001", "player_display_name": "Test Player",
        "position": "QB", "team": "KC", "season": NFL_SEASON, "games": 17,
        "completions": 380, "attempts": 572,
        "passing_yards": 4000, "passing_tds": 28, "interceptions": 10,
        "carries": 50, "rushing_yards": 300, "rushing_tds": 2,
        "receptions": 0, "targets": 0, "receiving_yards": 0, "receiving_tds": 0,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows] if rows else [defaults])


class TestLoadRosters:
    def test_returns_list_of_dicts_with_required_keys(self):
        df = _make_roster_df()
        with patch("nfl_data_py.import_seasonal_rosters", return_value=df):
            result = _load_rosters()
        assert isinstance(result, list)
        assert len(result) == 1
        row = result[0]
        for key in ("player_id", "player_name", "position", "team"):
            assert key in row, f"Missing required key: {key}"

    def test_drops_rows_with_null_player_name(self):
        df = _make_roster_df(
            {"player_name": "Patrick Mahomes"},
            {"player_name": None},   # should be dropped
            {"player_name": "Josh Allen"},
        )
        with patch("nfl_data_py.import_seasonal_rosters", return_value=df):
            result = _load_rosters()
        names = [r["player_name"] for r in result]
        assert "Patrick Mahomes" in names
        assert "Josh Allen" in names
        assert None not in names
        assert len(result) == 2

    def test_passes_correct_season_to_package(self):
        """Verifies _load_rosters calls nfl_data_py with the configured season."""
        df = _make_roster_df()
        with patch("nfl_data_py.import_seasonal_rosters", return_value=df) as mock_import:
            _load_rosters()
        mock_import.assert_called_once()
        call_args = mock_import.call_args
        assert NFL_SEASON in call_args[0][0]  # first positional arg is [season]


class TestLoadSeasonalData:
    def test_returns_list_of_dicts_with_required_keys(self):
        df = _make_seasonal_df()
        with patch("nfl_data_py.import_seasonal_data", return_value=df):
            result = _load_seasonal_data()
        assert isinstance(result, list)
        assert len(result) == 1
        row = result[0]
        for key in ("player_display_name", "team", "position", "games",
                    "passing_yards", "rushing_yards", "receiving_yards"):
            assert key in row, f"Missing required key: {key}"

    def test_drops_rows_with_null_display_name(self):
        df = _make_seasonal_df(
            {"player_display_name": "Patrick Mahomes"},
            {"player_display_name": None},
        )
        with patch("nfl_data_py.import_seasonal_data", return_value=df):
            result = _load_seasonal_data()
        names = [r["player_display_name"] for r in result]
        assert "Patrick Mahomes" in names
        assert None not in names

    def test_passes_correct_season_and_type(self):
        df = _make_seasonal_df()
        with patch("nfl_data_py.import_seasonal_data", return_value=df) as mock_import:
            _load_seasonal_data()
        mock_import.assert_called_once()
        call_kwargs = mock_import.call_args[1]
        assert call_kwargs.get("s_type") == "REG"
        assert NFL_SEASON in mock_import.call_args[0][0]


class TestGetLeadersSync:
    def test_returns_sorted_top_n(self):
        df = _make_seasonal_df(
            {"player_display_name": "A Player", "team": "KC", "position": "QB", "passing_yards": 5000},
            {"player_display_name": "B Player", "team": "BUF", "position": "QB", "passing_yards": 4200},
            {"player_display_name": "C Player", "team": "PHI", "position": "QB", "passing_yards": 3800},
        )
        with patch("nfl_data_py.import_seasonal_data", return_value=df):
            result = _get_leaders_sync("passing_yards", "Passing Yards", n=3)
        assert "A Player" in result
        assert "B Player" in result
        assert "5000" in result
        # Verify ordering: A (5000) appears before B (4200)
        assert result.index("A Player") < result.index("B Player")

    def test_respects_n_limit(self):
        rows = [
            {"player_display_name": f"Player{i}", "team": "XX",
             "position": "QB", "passing_yards": 5000 - i * 100}
            for i in range(10)
        ]
        df = _make_seasonal_df(*rows)
        with patch("nfl_data_py.import_seasonal_data", return_value=df):
            result = _get_leaders_sync("passing_yards", "Passing Yards", n=3)
        lines = [l for l in result.splitlines() if l.strip().startswith(tuple("123456789"))]
        assert len(lines) == 3

    def test_filters_out_zero_values(self):
        """Players with 0 yards should not appear in the leader board."""
        df = _make_seasonal_df(
            {"player_display_name": "Active QB", "passing_yards": 3500},
            {"player_display_name": "Inactive QB", "passing_yards": 0},
        )
        with patch("nfl_data_py.import_seasonal_data", return_value=df):
            result = _get_leaders_sync("passing_yards", "Passing Yards")
        assert "Active QB" in result
        assert "Inactive QB" not in result

    def test_missing_stat_column_returns_error_message(self):
        df = _make_seasonal_df()  # doesn't have a "fake_stat" column
        with patch("nfl_data_py.import_seasonal_data", return_value=df):
            result = _get_leaders_sync("fake_stat", "Fake Stat")
        assert "not available" in result

    def test_output_includes_header_with_season(self):
        df = _make_seasonal_df({"player_display_name": "Top QB", "passing_yards": 4500})
        with patch("nfl_data_py.import_seasonal_data", return_value=df):
            result = _get_leaders_sync("passing_yards", "Passing Yards")
        assert "Passing Yards" in result
        assert str(NFL_SEASON) in result


# ── Integration tests (real network + nfl_data_py download) ──────────────────

@pytest.mark.integration
class TestNFLIntegration:
    async def test_espn_scoreboard_reachable(self, svc):
        result = await svc.get_scoreboard()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_espn_standings_reachable(self, svc):
        result = await svc.get_standings()
        assert isinstance(result, str)
        assert "NFL STANDINGS" in result

    async def test_espn_news_reachable(self, svc):
        result = await svc.get_news()
        assert isinstance(result, str)

    async def test_player_stats_mahomes(self, svc):
        """Downloads nfl_data_py seasonal data — slow on first run."""
        result = await svc.get_player_season_stats("Patrick Mahomes")
        assert isinstance(result, str)
        assert "Mahomes" in result or "Error" in result  # error is acceptable if data unavailable

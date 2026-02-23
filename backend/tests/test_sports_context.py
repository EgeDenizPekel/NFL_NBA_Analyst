"""
Unit tests for SportsContextService — pure logic tests (sport detection,
intent detection, leaders category). No network calls.
"""
import pytest

from services.sports_context import SportsContextService


@pytest.fixture
def svc():
    return SportsContextService()


# ── Sport detection ───────────────────────────────────────────────────────────

class TestDetectSport:
    def test_hint_nba(self, svc):
        assert svc._detect_sport("anything", "nba") == "nba"

    def test_hint_nfl(self, svc):
        assert svc._detect_sport("anything", "nfl") == "nfl"

    def test_hint_none_ignored(self, svc):
        # No hint — must fall through to keyword detection
        assert svc._detect_sport("lakers game tonight", None) == "nba"

    def test_nba_keyword_team(self, svc):
        assert svc._detect_sport("how are the celtics doing", None) == "nba"

    def test_nba_keyword_explicit(self, svc):
        assert svc._detect_sport("best nba players", None) == "nba"

    def test_nfl_keyword_team(self, svc):
        assert svc._detect_sport("chiefs vs eagles prediction", None) == "nfl"

    def test_nfl_keyword_explicit(self, svc):
        assert svc._detect_sport("who leads the nfl in passing", None) == "nfl"

    def test_76ers_multiword(self, svc):
        assert svc._detect_sport("76ers standings", None) == "nba"

    def test_super_bowl_multiword(self, svc):
        assert svc._detect_sport("who will win the super bowl", None) == "nfl"

    def test_no_keywords_returns_none(self, svc):
        assert svc._detect_sport("who is the best player ever", None) is None


# ── Intent detection ──────────────────────────────────────────────────────────

class TestDetectIntent:
    def test_comparison(self, svc):
        assert svc._detect_intent("compare lebron vs curry") == "comparison"

    def test_versus(self, svc):
        assert svc._detect_intent("lebron versus giannis stats") == "comparison"

    def test_scoreboard_today(self, svc):
        assert svc._detect_intent("games today") == "scoreboard"

    def test_scoreboard_score(self, svc):
        assert svc._detect_intent("what is the score") == "scoreboard"

    def test_standings(self, svc):
        assert svc._detect_intent("show me nba standings") == "standings"

    def test_standings_record(self, svc):
        assert svc._detect_intent("what is boston celtics record") == "standings"

    def test_news_championship(self, svc):
        assert svc._detect_intent("who won the championship") == "news"

    def test_news_trade(self, svc):
        assert svc._detect_intent("latest trade news") == "news"

    def test_prediction(self, svc):
        assert svc._detect_intent("who will win the title") == "prediction"

    def test_leaders(self, svc):
        assert svc._detect_intent("who leads in points") == "leaders"

    def test_default_player_stats(self, svc):
        assert svc._detect_intent("how is jayson tatum playing this season") == "player_stats"

    # Regression: "today" must not override an explicit standings keyword
    def test_standings_beats_scoreboard_today(self, svc):
        assert svc._detect_intent("nba standings today") == "standings"

    def test_nfl_standings_beats_scoreboard_today(self, svc):
        assert svc._detect_intent("nfl standings today") == "standings"

    # Regression: "top shooters" should map to leaders, not fall through to player_stats
    def test_top_shooters_leaders(self, svc):
        assert svc._detect_intent("who are the top shooters this season") == "leaders"

    def test_best_shooters_leaders(self, svc):
        assert svc._detect_intent("best shooters in the nba") == "leaders"

    # Scoreboard-only queries must still work after the standings/scoreboard swap
    def test_scoreboard_tonight(self, svc):
        assert svc._detect_intent("what games are on tonight") == "scoreboard"

    def test_scoreboard_live(self, svc):
        assert svc._detect_intent("live score updates") == "scoreboard"


# ── NBA leaders category detection ───────────────────────────────────────────

class TestNBALeadersCategory:
    def test_points_default(self, svc):
        assert svc._detect_nba_leaders_category("who scores the most") == "PTS"

    def test_rebounds(self, svc):
        assert svc._detect_nba_leaders_category("rebounding leaders") == "REB"

    def test_assists(self, svc):
        assert svc._detect_nba_leaders_category("most assists this season") == "AST"

    def test_steals(self, svc):
        assert svc._detect_nba_leaders_category("top steal leaders") == "STL"

    def test_blocks(self, svc):
        assert svc._detect_nba_leaders_category("who has the most blocks") == "BLK"


# ── NFL leaders stat detection ────────────────────────────────────────────────

class TestNFLLeadersStat:
    def test_passing_yards_default(self, svc):
        assert svc._detect_nfl_leaders_stat("who leads the nfl") == "passing_yards"

    def test_passing_yards_keyword(self, svc):
        assert svc._detect_nfl_leaders_stat("who has the most passing yards") == "passing_yards"

    def test_rushing_yards(self, svc):
        assert svc._detect_nfl_leaders_stat("top rushing leaders") == "rushing_yards"

    def test_receiving_yards(self, svc):
        assert svc._detect_nfl_leaders_stat("best receivers in yards") == "receiving_yards"

    def test_receptions(self, svc):
        assert svc._detect_nfl_leaders_stat("most receptions this season") == "receptions"

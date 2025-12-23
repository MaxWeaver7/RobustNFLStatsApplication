from __future__ import annotations


from src.web.queries_supabase import player_photo_url_from_name_team


def test_player_photo_url_handles_hyphens_and_punctuation() -> None:
    # These are all present in NFLAdvancedStats/data/db_playerids.csv with ESPN IDs.
    assert (
        player_photo_url_from_name_team(name="Jaxon Smith-Njigba", team="SEA")
        == "https://a.espncdn.com/i/headshots/nfl/players/full/4430878.png"
    )
    assert (
        player_photo_url_from_name_team(name="Amon-Ra St. Brown", team="DET")
        == "https://a.espncdn.com/i/headshots/nfl/players/full/4374302.png"
    )


def test_player_photo_url_returns_expected_for_examples() -> None:
    assert (
        player_photo_url_from_name_team(name="Kyle Pitts", team="ATL")
        == "https://a.espncdn.com/i/headshots/nfl/players/full/4360248.png"
    )
    assert (
        player_photo_url_from_name_team(name="Chigoziem Okonkwo", team="TEN")
        == "https://a.espncdn.com/i/headshots/nfl/players/full/4360635.png"
    )
    assert (
        player_photo_url_from_name_team(name="Marquise Brown", team="KCC")
        == "https://a.espncdn.com/i/headshots/nfl/players/full/4241372.png"
    )


def test_player_photo_url_unknown_returns_none() -> None:
    assert player_photo_url_from_name_team(name="Definitely Not A Real Player", team="XXX") is None


def test_player_photo_url_handles_suffixes() -> None:
    # Suffixes like Jr/Sr/III should not break mapping.
    assert player_photo_url_from_name_team(name="Anthony Richardson", team="IND") is not None
    assert player_photo_url_from_name_team(name="Joe Milton III", team="NE") is not None
    assert player_photo_url_from_name_team(name="James Cook III", team="BUF") is not None
    assert player_photo_url_from_name_team(name="Travis Etienne Jr.", team="JAX") is not None
    assert player_photo_url_from_name_team(name="Kenneth Walker III", team="SEA") is not None
    assert player_photo_url_from_name_team(name="Tyrone Tracy Jr.", team="NYG") is not None
    assert player_photo_url_from_name_team(name="Aaron Jones Sr.", team="MIN") is not None
    assert player_photo_url_from_name_team(name="Chris Rodriguez Jr.", team="WAS") is not None


def test_player_photo_url_handles_nicknames_and_short_names() -> None:
    # Nickname / short-name fallbacks (team-scoped last-name match)
    assert player_photo_url_from_name_team(name="Hollywood Brown", team="KC") is not None
    assert player_photo_url_from_name_team(name="Josh Palmer", team="LAC") is not None



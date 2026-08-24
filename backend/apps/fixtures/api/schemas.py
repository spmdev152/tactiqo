from datetime import datetime

from ninja import Schema


class LeagueResponse(Schema):
    """
    Public projection of a competition.

    Attributes
    ----------
    id : int
        Primary key of the competition, which is the identifier every other
        endpoint accepts. The provider identifier is deliberately absent.
    name : str
        Competition name.
    short_code : str
        Abbreviated competition label, an empty string when there is none.
    logo_url : str
        Absolute URL of the competition badge, an empty string when there is
        none.
    country_name : str
        Country the competition is organized in.
    country_flag_url : str
        Absolute URL of the country flag, an empty string when there is none.
    """

    id: int
    name: str
    short_code: str
    logo_url: str
    country_name: str
    country_flag_url: str


class TeamResponse(Schema):
    """
    Public projection of a club.

    Attributes
    ----------
    id : int
        Primary key of the club. The provider identifier is deliberately absent.
    name : str
        Club name.
    short_code : str
        Three-letter club abbreviation, an empty string when there is none.
    crest_url : str
        Absolute URL of the club crest, an empty string when there is none.
    """

    id: int
    name: str
    short_code: str
    crest_url: str


class FixtureResponse(Schema):
    """
    Public projection of a scheduled match.

    Attributes
    ----------
    id : int
        Primary key of the fixture. The provider identifier is deliberately
        absent.
    kickoff_at : datetime
        Instant the match starts, serialized as an ISO 8601 UTC timestamp.
    league : LeagueResponse
        Competition the match belongs to, embedded so a listing needs no second
        request to render a badge.
    home_team : TeamResponse
        Club playing at home.
    away_team : TeamResponse
        Club playing away.
    """

    id: int
    kickoff_at: datetime
    league: LeagueResponse
    home_team: TeamResponse
    away_team: TeamResponse

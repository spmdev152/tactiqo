from datetime import datetime

from ninja import Schema

from apps.fixtures.domain.enums import FixtureStatus


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
    Public projection of a match, played or still to be played.

    Attributes
    ----------
    id : int
        Primary key of the fixture. The provider identifier is deliberately
        absent.
    kickoff_at : datetime
        Instant the match starts, serialized as an ISO 8601 UTC timestamp.
    status : FixtureStatus
        Lifecycle stage of the match, serialized as the value of the member.
        The closed vocabulary is the platform's own: the provider's twenty-five
        states never reach this contract.
    home_goals : int or None
        Goals the home club has scored, ``null`` while the match has produced no
        score. A database constraint pairs it with ``away_goals``, so a reader
        never has to render one half of a score.
    away_goals : int or None
        Goals the away club has scored, ``null`` under the same condition.
    league : LeagueResponse
        Competition the match belongs to, embedded so a listing needs no second
        request to render a badge.
    home_team : TeamResponse
        Club playing at home.
    away_team : TeamResponse
        Club playing away.
    has_predictions : bool
        Whether any prediction is stored for the match, so the interface only
        offers a toggle on a row that has something to show. Prediction
        availability is fixture-dependent, and a day's listing would otherwise
        have to request every fixture's predictions in order to find out which
        of them are worth expanding. It is supplied by the ``has_predictions``
        annotation ``list_fixtures_on`` adds and by nothing else, and it
        deliberately carries no default: any further producer of this schema, a
        fixture-detail endpoint or an admin action among them, has to annotate
        it too, and a validation error is a better answer than quietly
        reporting ``false`` for a match that does have predictions.
    """

    id: int
    kickoff_at: datetime
    status: FixtureStatus
    home_goals: int | None
    away_goals: int | None
    league: LeagueResponse
    home_team: TeamResponse
    away_team: TeamResponse
    has_predictions: bool

from django.db import models


class FixtureStatus(models.TextChoices):
    """
    Lifecycle stage of a fixture, in the vocabulary the platform publishes.

    The provider distinguishes twenty-five states, most of which differ only in
    which interruption a match is currently under. This vocabulary keeps the
    five stages a reader of a listing acts on, so the Sportmonks boundary maps
    onto it and no provider code reaches the column, the API, or the interface.

    Attributes
    ----------
    SCHEDULED : str
        Match has not started, serialized as ``"scheduled"``. It is also what an
        unrecognized provider state is read as.
    LIVE : str
        Match is under way, including a half-time, extra-time, or penalty break
        within it, serialized as ``"live"``.
    FINISHED : str
        Match has been played to a result, serialized as ``"finished"``.
    POSTPONED : str
        Match was moved to a later date and keeps its identifier, serialized as
        ``"postponed"``.
    CANCELLED : str
        Match will not be played and yields no result, serialized as
        ``"cancelled"``.
    """

    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"

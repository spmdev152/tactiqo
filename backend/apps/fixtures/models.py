from typing import ClassVar

from django.db import models

from apps.fixtures.domain.enums import FixtureStatus


class League(models.Model):
    """
    Competition a fixture belongs to.

    Attributes
    ----------
    sportmonks_id : int
        Provider identifier, the natural key ingestion matches a row on. It is
        unique so a re-synchronization updates the row instead of duplicating
        it, and it never leaves the ingestion boundary: the public API exposes
        the primary key.
    name : str
        Competition name shown to a reader.
    short_code : str
        Abbreviated competition label, an empty string when the provider omits
        it.
    logo_url : str
        Absolute URL of the competition badge, an empty string when the provider
        omits it.
    country_name : str
        Country the competition is organized in.
    country_flag_url : str
        Absolute URL of the country flag, an empty string when the provider
        omits it.

    Methods
    -------
    __str__() -> str
        Return the competition name.
    """

    sportmonks_id = models.BigIntegerField(unique=True)

    name = models.CharField(max_length=255)
    short_code = models.CharField(max_length=16, blank=True)
    logo_url = models.URLField(max_length=512, blank=True)
    country_name = models.CharField(max_length=255, blank=True)
    country_flag_url = models.URLField(max_length=512, blank=True)

    class Meta:
        """
        Admin labels and default ordering of the league table.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, alphabetical by competition name, which is also
            the order the public league listing promises.
        """

        verbose_name = "league"
        verbose_name_plural = "leagues"
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self) -> str:
        """
        Return the competition name.

        Returns
        -------
        str
            Name of the competition.
        """

        return self.name


class Team(models.Model):
    """
    Club taking part in a fixture.

    Attributes
    ----------
    sportmonks_id : int
        Provider identifier, the natural key ingestion matches a row on. It is
        unique so a re-synchronization updates the row instead of duplicating
        it, and it never leaves the ingestion boundary: the public API exposes
        the primary key.
    name : str
        Club name shown to a reader.
    short_code : str
        Three-letter club abbreviation, an empty string when the provider omits
        it.
    crest_url : str
        Absolute URL of the club crest, an empty string when the provider omits
        it.

    Methods
    -------
    __str__() -> str
        Return the club name.
    """

    sportmonks_id = models.BigIntegerField(unique=True)

    name = models.CharField(max_length=255)
    short_code = models.CharField(max_length=16, blank=True)
    crest_url = models.URLField(max_length=512, blank=True)

    class Meta:
        """
        Admin labels and default ordering of the team table.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, alphabetical by club name.
        """

        verbose_name = "team"
        verbose_name_plural = "teams"
        ordering: ClassVar[list[str]] = ["name"]

    def __str__(self) -> str:
        """
        Return the club name.

        Returns
        -------
        str
            Name of the club.
        """

        return self.name


class Fixture(models.Model):
    """
    Scheduled match between two clubs in one competition.

    Attributes
    ----------
    sportmonks_id : int
        Provider identifier, the natural key ingestion matches a row on. A
        postponed match keeps its identifier and arrives with a later
        ``kickoff_at``, so the uniqueness is what makes the row move instead of
        the table gaining a duplicate.
    league : League
        Competition the match belongs to. Protected on delete because a league
        is reference data a synchronization may replace but must never silently
        take fixtures down with.
    home_team : Team
        Club playing at home.
    away_team : Team
        Club playing away.
    kickoff_at : datetime
        Instant the match starts, stored in UTC. Indexed on its own and
        together with the league, which are exactly the two filters the public
        fixture listing issues.
    status : str
        Lifecycle stage of the match in the platform's own vocabulary, one of
        ``FixtureStatus``. Deliberately unindexed although the admin change list
        filters on it: five distinct values over a season of a few thousand rows
        select too large a fraction of the table for an index to beat the
        sequential scan the planner would prefer anyway.
    home_goals : int or None
        Goals the home club has scored, ``None`` until the match produces a
        score. A check constraint pairs it with ``away_goals``.
    away_goals : int or None
        Goals the away club has scored, ``None`` until the match produces a
        score.
    synchronized_at : datetime
        Instant the last synchronization wrote this row, which is the freshness
        a reader of provider-sourced data needs.

    Methods
    -------
    __str__() -> str
        Return the two clubs and the kick-off instant.
    """

    sportmonks_id = models.BigIntegerField(unique=True)

    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="fixtures")

    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_fixtures")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_fixtures")

    kickoff_at = models.DateTimeField()

    status = models.CharField(
        max_length=16, choices=FixtureStatus.choices, default=FixtureStatus.SCHEDULED
    )

    home_goals = models.PositiveSmallIntegerField(null=True, blank=True)
    away_goals = models.PositiveSmallIntegerField(null=True, blank=True)

    synchronized_at = models.DateTimeField()

    class Meta:
        """
        Admin labels, ordering, read indexes, and invariants of the fixtures.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, earliest kick-off first, broken by primary key so
            two matches starting together list deterministically.
        indexes : list of Index
            Indexes serving the day filter and the day-within-a-league filter
            of the public fixture listing.
        constraints : list of BaseConstraint
            Invariant that a score is a pair, so no row can carry the goals of
            one club alone. It is enforced here rather than in the boundary that
            writes it or the template that reads it, because a half-written
            score is unrenderable and every future writer inherits the rule.
        """

        verbose_name = "fixture"
        verbose_name_plural = "fixtures"
        ordering: ClassVar[list[str]] = ["kickoff_at", "id"]

        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["kickoff_at"], name="fixture_kickoff_at_idx"),
            models.Index(fields=["league", "kickoff_at"], name="fixture_league_kickoff_idx"),
        ]

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(home_goals__isnull=True, away_goals__isnull=True)
                | models.Q(home_goals__isnull=False, away_goals__isnull=False),
                name="fixture_goals_pair_check",
            ),
        ]

    def __str__(self) -> str:
        """
        Return the two clubs and the kick-off instant.

        Returns
        -------
        str
            Home club, away club, and the kick-off instant in ISO 8601.
        """

        return f"{self.home_team.name} - {self.away_team.name} at {self.kickoff_at.isoformat()}"

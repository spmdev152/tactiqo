from typing import ClassVar

from django.db import models

from apps.statistics.domain.enums import MatchSide

SIDE_LENGTH = 8

POSSESSION_CEILING = 100


class MatchTeamStatistic(models.Model):
    """
    What one team recorded in one match it has already played.

    A match carries two rows, one per team, in one table. The alternative shape,
    one row per match holding a home and an away column family, was rejected on
    the read this table exists to serve: every question asked of it is one team's
    last few matches, and that team is the home side in some of them and the away
    side in the others. Keyed by team the filter is an equality against one
    index; keyed by match it becomes a disjunction wrapped around a conditional
    expression per metric, twenty-two of them, for twice the columns and no gain.
    Two rows also make the opposing figures free, because what a team conceded is
    the sibling row of the same match, so nothing is stored twice and the two
    halves of a match cannot drift apart.

    The columns are fixed rather than a metric name beside a value. The
    vocabulary is closed and chosen by product, every read is an average over a
    bounded set of rows, and a real column carries a type and a constraint. A new
    metric costs a migration, which makes it a decision somebody reviews instead
    of a row somebody inserts.

    Nothing about the result is stored. Goals, and therefore the win, draw, and
    loss shares, come from ``Fixture.home_goals`` and ``Fixture.away_goals``,
    which are already synchronized and already guarded as a pair. The provider
    omits its own goals statistic at nought, so a goalless side carries no row
    and a table sourcing goals from the statistics would read every goalless
    performance as missing data.

    Attributes
    ----------
    fixture : Fixture
        Match the record belongs to. Cascading on delete because a performance is
        meaningless without the match it happened in, and the fixture
        synchronization genuinely deletes a match the provider stops listing.
    team : Team
        Club the record belongs to. Protected on delete, matching the fixture's
        own stance: a club is reference data, and taking its history down
        silently is never the intended effect of replacing it.
    side : str
        Side the club occupied, one of ``MatchSide``. Stored rather than derived
        from the fixture at read time because it is the second half of the filter
        every venue-scoped read applies, and a join to recover it would undo the
        index the filter runs on.
    shots_total : int
        Shots the club took.
    shots_on_target : int
        Shots the club took that were on target.
    shots_inside_box : int
        Shots the club took from inside the penalty area.
    shots_blocked : int
        Shots the club blocked.
    big_chances_created : int
        Clear chances the club created.
    key_passes : int
        Passes by the club that led directly to a shot.
    corners : int
        Corners the club won.
    possession : int
        Share of the ball the club had, as a whole percentage. It is the one
        provider percentage stored as published, because it is already normalized
        to a single match, unlike a completion rate whose average over several
        matches is a ratio of sums.
    passes : int
        Passes the club attempted.
    successful_passes : int
        Passes the club completed. Stored beside the attempts rather than as the
        percentage the provider also publishes, because the accuracy over a
        sample is the completed passes of the sample over its attempts, and the
        mean of per-match percentages is a different and wrong number.
    crosses : int
        Crosses the club attempted.
    accurate_crosses : int
        Crosses the club completed, stored beside the attempts for the reason
        given for the passes.
    dribble_attempts : int
        Dribbles the club attempted.
    successful_dribbles : int
        Dribbles the club completed, stored beside the attempts for the reason
        given for the passes.
    saves : int
        Saves the club's goalkeeper made.
    tackles : int
        Tackles the club made.
    interceptions : int
        Interceptions the club made.
    duels_won : int
        Duels the club won.
    fouls : int
        Fouls the club conceded.
    yellow_cards : int
        Yellow cards the club received.
    red_cards : int
        Red cards the club received.
    offsides : int
        Times the club was called offside.
    synchronized_at : datetime
        Instant the last synchronization wrote this row. It is also the
        reconciliation marker: a run stamps every row it writes and then deletes
        the rows of the matches it read that still carry an earlier stamp, so a
        match the provider stops publishing statistics for leaves the table
        without the run having to enumerate what is missing.

    Methods
    -------
    __str__() -> str
        Return the club, the side it took, and the match.
    """

    fixture = models.ForeignKey(
        "fixtures.Fixture", on_delete=models.CASCADE, related_name="team_statistics"
    )

    team = models.ForeignKey(
        "fixtures.Team", on_delete=models.PROTECT, related_name="match_statistics"
    )

    side = models.CharField(max_length=SIDE_LENGTH, choices=MatchSide.choices)

    shots_total = models.PositiveSmallIntegerField()
    shots_on_target = models.PositiveSmallIntegerField()
    shots_inside_box = models.PositiveSmallIntegerField()
    shots_blocked = models.PositiveSmallIntegerField()
    big_chances_created = models.PositiveSmallIntegerField()
    key_passes = models.PositiveSmallIntegerField()
    corners = models.PositiveSmallIntegerField()

    possession = models.PositiveSmallIntegerField()

    passes = models.PositiveSmallIntegerField()
    successful_passes = models.PositiveSmallIntegerField()
    crosses = models.PositiveSmallIntegerField()
    accurate_crosses = models.PositiveSmallIntegerField()
    dribble_attempts = models.PositiveSmallIntegerField()
    successful_dribbles = models.PositiveSmallIntegerField()

    saves = models.PositiveSmallIntegerField()
    tackles = models.PositiveSmallIntegerField()
    interceptions = models.PositiveSmallIntegerField()
    duels_won = models.PositiveSmallIntegerField()

    fouls = models.PositiveSmallIntegerField()
    yellow_cards = models.PositiveSmallIntegerField()
    red_cards = models.PositiveSmallIntegerField()
    offsides = models.PositiveSmallIntegerField()

    synchronized_at = models.DateTimeField()

    class Meta:
        """
        Admin labels, ordering, read indexes, and invariants of the statistics.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, grouped by match then by side, so the two rows of a
            match always list home before away.
        indexes : list of Index
            One index on ``(team, side)``, which is the filter every form read
            applies once the fixtures of the window are known. The window itself
            is ordered by kick-off, which lives on the fixture and is indexed
            there.
        constraints : list of BaseConstraint
            Uniqueness of a club within a match, which is what makes the upsert
            idempotent; uniqueness of a side within a match, so no match can hold
            two home performances however a payload arrives; and the invariant
            that possession is a percentage. The bound is enforced here because a
            share outside it is unrenderable on a bar whose width is that share,
            and every future writer inherits the rule.
        """

        verbose_name = "match team statistic"
        verbose_name_plural = "match team statistics"
        ordering: ClassVar[list[str]] = ["fixture", "side"]

        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["team", "side"], name="match_statistic_team_side_idx"),
        ]

        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["fixture", "team"], name="match_statistic_team_unique"),
            models.UniqueConstraint(fields=["fixture", "side"], name="match_statistic_side_unique"),
            models.CheckConstraint(
                condition=models.Q(possession__lte=POSSESSION_CEILING),
                name="match_statistic_possession_range_check",
            ),
        ]

    def __str__(self) -> str:
        """
        Return the club, the side it took, and the match.

        Returns
        -------
        str
            Club name, the side it occupied, and the match it played.
        """

        return f"{self.team.name} {self.side} in {self.fixture}"

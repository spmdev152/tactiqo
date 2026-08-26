import logging

from django.contrib import admin
from django.http import HttpRequest

from apps.statistics.models import MatchTeamStatistic

logger = logging.getLogger(__name__)

STATISTIC_FIELDS = (
    "fixture",
    "team",
    "side",
    "shots_total",
    "shots_on_target",
    "shots_inside_box",
    "shots_blocked",
    "big_chances_created",
    "key_passes",
    "corners",
    "possession",
    "passes",
    "successful_passes",
    "crosses",
    "accurate_crosses",
    "dribble_attempts",
    "successful_dribbles",
    "saves",
    "tackles",
    "interceptions",
    "duels_won",
    "fouls",
    "yellow_cards",
    "red_cards",
    "offsides",
    "synchronized_at",
)


@admin.register(MatchTeamStatistic)
class MatchTeamStatisticAdmin(admin.ModelAdmin):
    """
    Admin surface of the per-team match statistics table.

    Every row is a measurement the synchronization task copied from the
    provider, so the whole change form is read-only and the add form is refused.
    A hand-edited figure would be undone by the next run, and a hand-added row
    would be deleted by it: the run stamps what it writes and removes the rows of
    the matches it read that carry an earlier stamp, so an invented row cannot
    survive a refresh of its match. It would also be worse than useless in the
    meantime, because a form sample is an average over these rows and a figure
    somebody typed would be indistinguishable in the panel from one the provider
    published.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list, kept to the match, the club, the side, and
        the handful of figures an operator checks a synchronization against
        rather than all twenty-two, which would be unreadable at this width.
    list_filter : tuple of str
        Filters offered beside the change list, by side and by the competition
        the match belongs to, which are the two ways an operator narrows a table
        holding two rows per finished match of five leagues.
    search_fields : tuple of str
        Fields the change list search box queries, reaching the club of the row
        and both clubs of the match through the fixture, so a performance can be
        looked up either by whose it is or by which match it belongs to.
    ordering : tuple of str
        Ordering of the change list, matching the model's own so the two rows of
        a match always list home before away in both.
    list_select_related : tuple of str
        Relations joined into the change list query. Naming the club, the
        fixture, and the fixture's own two clubs is what keeps a page of a
        hundred rows from costing four extra queries each.
    readonly_fields : tuple of str
        Every field: the task owns the whole row, not part of it.

    Methods
    -------
    has_add_permission(request) -> bool
        Refuse the creation of a statistic row through the admin.
    """

    list_display = ("fixture", "team", "side", "possession", "shots_total", "synchronized_at")

    list_filter = ("side", "fixture__league")

    search_fields = (
        "team__name",
        "fixture__home_team__name",
        "fixture__away_team__name",
    )
    ordering = ("fixture", "side")
    list_select_related = ("team", "fixture", "fixture__home_team", "fixture__away_team")
    readonly_fields = STATISTIC_FIELDS

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Refuse the creation of a statistic row through the admin.

        Parameters
        ----------
        request : HttpRequest
            Admin request the permission is evaluated for.

        Returns
        -------
        bool
            Always ``False``: the synchronization task writes every row.
        """

        logger.debug("Withheld the match statistic add form from %s", request.user)

        return False

import logging

from django.contrib import admin
from django.http import HttpRequest

from apps.predictions.models import FixturePrediction, LeagueMarketReliability

logger = logging.getLogger(__name__)


@admin.register(FixturePrediction)
class FixturePredictionAdmin(admin.ModelAdmin):
    """
    Admin surface of the fixture prediction table.

    Every row is a measurement the synchronization task copied from the
    provider, so the whole change form is read-only and the add form is refused.
    A hand-edited probability would be undone by the next run, and a hand-added
    one would be deleted by it: the run stamps what it writes and removes the
    rows of the fixtures it read that carry an earlier stamp, so an invented row
    cannot survive a refresh of its fixture.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    list_filter : tuple of str
        Filters offered beside the change list, by market and by the competition
        the match belongs to, which are the two ways an operator narrows a table
        holding fifty rows per fixture.
    search_fields : tuple of str
        Fields the change list search box queries, reaching both clubs through
        the fixture so a match can be looked up the way it is named.
    ordering : tuple of str
        Ordering of the change list, matching the model's own so a tie is broken
        the same way in both.
    list_select_related : tuple of str
        Relations joined into the change list query. Naming the fixture and its
        two clubs is what keeps a page of a hundred rows from costing three
        extra queries each.
    readonly_fields : tuple of str
        Every field: the task owns the whole row, not part of it.

    Methods
    -------
    has_add_permission(request) -> bool
        Refuse the creation of a prediction through the admin.
    """

    list_display = ("fixture", "market", "selection", "probability", "synchronized_at")

    list_filter = ("market", "fixture__league")

    search_fields = ("fixture__home_team__name", "fixture__away_team__name")
    ordering = ("fixture", "market", "id")
    list_select_related = ("fixture", "fixture__home_team", "fixture__away_team")
    readonly_fields = ("fixture", "market", "selection", "probability", "synchronized_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Refuse the creation of a prediction through the admin.

        Parameters
        ----------
        request : HttpRequest
            Admin request the permission is evaluated for.

        Returns
        -------
        bool
            Always ``False``: the synchronization task writes every row.
        """

        logger.debug("Withheld the prediction add form from %s", request.user)

        return False


@admin.register(LeagueMarketReliability)
class LeagueMarketReliabilityAdmin(admin.ModelAdmin):
    """
    Admin surface of the model reliability table.

    Read-only and closed to additions for the same reason the predictions are:
    the grade is the provider's own assessment of its model, and a value an
    operator chose would be indistinguishable from one the provider published
    while meaning the opposite of it.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    list_filter : tuple of str
        Filters offered beside the change list, by competition, market, and
        grade.
    ordering : tuple of str
        Ordering of the change list, matching the model's own.
    list_select_related : tuple of str
        Competition joined into the change list query, which the first column
        needs.
    readonly_fields : tuple of str
        Every field: the task owns the whole row.

    Methods
    -------
    has_add_permission(request) -> bool
        Refuse the creation of a reliability grade through the admin.
    """

    list_display = ("league", "market", "quality", "hit_ratio", "synchronized_at")

    list_filter = ("league", "market", "quality")

    ordering = ("league", "market")
    list_select_related = ("league",)
    readonly_fields = ("league", "market", "quality", "hit_ratio", "synchronized_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Refuse the creation of a reliability grade through the admin.

        Parameters
        ----------
        request : HttpRequest
            Admin request the permission is evaluated for.

        Returns
        -------
        bool
            Always ``False``: the synchronization task writes every row.
        """

        logger.debug("Withheld the reliability add form from %s", request.user)

        return False

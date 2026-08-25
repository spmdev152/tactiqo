import logging

from django.contrib import admin
from django.http import HttpRequest

from apps.fixtures.models import Fixture, League, Team

logger = logging.getLogger(__name__)


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    """
    Admin surface of the competition table.

    ``sportmonks_id`` is read-only because every row here is written by the
    synchronization task and that identifier is the natural key it matches a
    row on: an operator editing it would either detach the row from the
    provider, so the next run inserts a duplicate, or point it at another
    competition whose values the next run then overwrites.

    The add form follows from that. The task owns every row, and a hand-added
    one could carry no provider identity at all, since the column is not null
    and the form that would supply it is the one being refused.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    search_fields : tuple of str
        Fields the change list search box queries, which is also what the
        fixture admin's competition autocomplete searches.
    ordering : tuple of str
        Ordering of the change list.
    readonly_fields : tuple of str
        Fields the synchronization task owns, shown but not editable.

    Methods
    -------
    has_add_permission(request) -> bool
        Refuse the creation of a competition through the admin.
    """

    list_display = ("name", "short_code", "country_name", "sportmonks_id")
    search_fields = ("name", "country_name")
    ordering = ("name",)
    readonly_fields = ("sportmonks_id",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Refuse the creation of a competition through the admin.

        Parameters
        ----------
        request : HttpRequest
            Admin request the permission is evaluated for.

        Returns
        -------
        bool
            Always ``False``: the synchronization task writes every row.
        """

        logger.debug("Withheld the competition add form from %s", request.user)

        return False


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """
    Admin surface of the club table.

    ``sportmonks_id`` is read-only for the reason given on ``LeagueAdmin``: the
    synchronization task writes every row and matches it on that identifier, so
    editing it only makes the next run insert a duplicate or overwrite the
    wrong club. The add form is refused for the same reason, and because a club
    typed in by hand would have no provider identity to be matched on.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    search_fields : tuple of str
        Fields the change list search box queries, which is also what the
        fixture admin's two club autocompletes search.
    ordering : tuple of str
        Ordering of the change list.
    readonly_fields : tuple of str
        Fields the synchronization task owns, shown but not editable.

    Methods
    -------
    has_add_permission(request) -> bool
        Refuse the creation of a club through the admin.
    """

    list_display = ("name", "short_code", "sportmonks_id")
    search_fields = ("name", "short_code")
    ordering = ("name",)
    readonly_fields = ("sportmonks_id",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Refuse the creation of a club through the admin.

        Parameters
        ----------
        request : HttpRequest
            Admin request the permission is evaluated for.

        Returns
        -------
        bool
            Always ``False``: the synchronization task writes every row.
        """

        logger.debug("Withheld the club add form from %s", request.user)

        return False


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    """
    Admin surface of the fixture table.

    ``sportmonks_id`` and ``synchronized_at`` are read-only because the
    synchronization task owns both: the identifier is the natural key the run
    matches a row on, and the instant is the record of when that run happened,
    so an edited value is either undone by the next run or a lie about the
    freshness of provider-sourced data. Both columns are also not null and carry
    no default, which is why the add form is refused rather than made to accept
    them: making them editable would contradict the reason they are read-only,
    and a fixture invented in the admin would be deleted by the next run
    reconciling its window anyway.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    list_filter : tuple of str or tuple of str and type
        Filters offered beside the change list. The score is filtered on the
        emptiness of ``home_goals`` alone, which is exact rather than a
        shortcut: the table constraint makes the two goal columns null together,
        so one of them answers whether a row carries a result at all, and that
        is the question an operator reviewing a synchronization run asks.
    search_fields : tuple of str
        Fields the change list search box queries, reaching the two clubs and
        the competition through their relations so an operator can look a match
        up the way it is named.
    date_hierarchy : str
        Field the change list drill-down by year, month, and day walks.
    ordering : tuple of str
        Ordering of the change list, earliest kick-off first and broken by
        primary key, which is the model's own ordering. Naming the tiebreak is
        what keeps the two agreeing: fixture kick-offs are heavily tied, and a
        change list ordered on ``kickoff_at`` alone is not left non-deterministic
        but silently completed, because Django appends ``-pk`` to any ordering
        that no unique column settles. An operator would then read tied matches
        in the reverse of the order the model and the public listing put them in.
    list_select_related : tuple of str
        Relations joined into the change list query, which a day of around
        fifty rows displaying three related names each cannot do without: read
        lazily, the page would cost three extra queries per row. Naming the
        three keeps the join the columns need explicit and exact, rather than
        leaving it to the blanket ``select_related()`` Django falls back to
        while a related column happens to sit in ``list_display``.
    autocomplete_fields : tuple of str
        Relations edited through a search box rather than a select, which would
        otherwise load every competition and every club into the change form.
    readonly_fields : tuple of str
        Fields the synchronization task owns, shown but not editable.

    Methods
    -------
    has_add_permission(request) -> bool
        Refuse the creation of a fixture through the admin.
    """

    list_display = (
        "kickoff_at",
        "league",
        "home_team",
        "away_team",
        "status",
        "home_goals",
        "away_goals",
        "synchronized_at",
    )

    list_filter = ("league", "status", ("home_goals", admin.EmptyFieldListFilter), "kickoff_at")

    search_fields = ("home_team__name", "away_team__name", "league__name")
    date_hierarchy = "kickoff_at"
    ordering = ("kickoff_at", "id")
    list_select_related = ("league", "home_team", "away_team")
    autocomplete_fields = ("league", "home_team", "away_team")
    readonly_fields = ("sportmonks_id", "synchronized_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Refuse the creation of a fixture through the admin.

        Parameters
        ----------
        request : HttpRequest
            Admin request the permission is evaluated for.

        Returns
        -------
        bool
            Always ``False``: the synchronization task writes every row.
        """

        logger.debug("Withheld the fixture add form from %s", request.user)

        return False

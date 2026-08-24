from django.contrib import admin

from apps.fixtures.models import Fixture, League, Team


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    """
    Admin surface of the competition table.

    ``sportmonks_id`` is read-only because every row here is written by the
    synchronization task and that identifier is the natural key it matches a
    row on: an operator editing it would either detach the row from the
    provider, so the next run inserts a duplicate, or point it at another
    competition whose values the next run then overwrites.

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
    """

    list_display = ("name", "short_code", "country_name", "sportmonks_id")
    search_fields = ("name", "country_name")
    ordering = ("name",)
    readonly_fields = ("sportmonks_id",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """
    Admin surface of the club table.

    ``sportmonks_id`` is read-only for the reason given on ``LeagueAdmin``: the
    synchronization task writes every row and matches it on that identifier, so
    editing it only makes the next run insert a duplicate or overwrite the
    wrong club.

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
    """

    list_display = ("name", "short_code", "sportmonks_id")
    search_fields = ("name", "short_code")
    ordering = ("name",)
    readonly_fields = ("sportmonks_id",)


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    """
    Admin surface of the fixture table.

    ``sportmonks_id`` and ``synchronized_at`` are read-only because the
    synchronization task owns both: the identifier is the natural key the run
    matches a row on, and the instant is the record of when that run happened,
    so an edited value is either undone by the next run or a lie about the
    freshness of provider-sourced data.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    list_filter : tuple of str
        Filters offered beside the change list.
    search_fields : tuple of str
        Fields the change list search box queries, reaching the two clubs and
        the competition through their relations so an operator can look a match
        up the way it is named.
    date_hierarchy : str
        Field the change list drill-down by year, month, and day walks.
    ordering : tuple of str
        Ordering of the change list.
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
    """

    list_display = ("kickoff_at", "league", "home_team", "away_team", "synchronized_at")
    list_filter = ("league", "kickoff_at")
    search_fields = ("home_team__name", "away_team__name", "league__name")
    date_hierarchy = "kickoff_at"
    ordering = ("kickoff_at",)
    list_select_related = ("league", "home_team", "away_team")
    autocomplete_fields = ("league", "home_team", "away_team")
    readonly_fields = ("sportmonks_id", "synchronized_at")

from django.apps import AppConfig


class StatisticsConfig(AppConfig):
    """
    Application configuration of the statistics slice.

    The slice owns one table, the per-team record of what each side did in a
    match it has already played. It is the raw material of every backward-looking
    read the product makes: form over the last few matches, form at a venue, and
    form over a season are all the same rows under a different window, so they
    live in one place rather than in a table per window.

    Attributes
    ----------
    default_auto_field : str
        Field class Django uses for implicit primary keys of this application.
    name : str
        Dotted import path of the application package, whose last component
        gives the application the ``statistics`` label.
    verbose_name : str
        Human-readable application label shown in the Django admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.statistics"
    verbose_name = "Match statistics"

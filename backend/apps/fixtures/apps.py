from django.apps import AppConfig


class FixturesConfig(AppConfig):
    """
    Application configuration of the fixtures slice.

    The admin groups models by this label, and the slice owns competitions and
    clubs as well as matches, so naming the group after one of the three would
    file the other two under it. "Football catalogue" names what all three are:
    the reference entities every later slice hangs measurements off, which is
    also what keeps the group distinct from a future statistics, odds, or
    predictions group.

    Attributes
    ----------
    default_auto_field : str
        Field class Django uses for implicit primary keys of this application.
    name : str
        Dotted import path of the application package, whose last component
        gives the application the ``fixtures`` label.
    verbose_name : str
        Human-readable application label shown in the Django admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.fixtures"
    verbose_name = "Football catalogue"

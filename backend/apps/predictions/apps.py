from django.apps import AppConfig


class PredictionsConfig(AppConfig):
    """
    Application configuration of the predictions slice.

    The slice owns two tables that are measurements rather than reference data:
    the probabilities a fixture carries, and how the provider's model has
    performed on each market in each competition. Both are grouped under one
    admin label because a reader who doubts a probability goes straight to the
    grade beside it.

    Attributes
    ----------
    default_auto_field : str
        Field class Django uses for implicit primary keys of this application.
    name : str
        Dotted import path of the application package, whose last component
        gives the application the ``predictions`` label.
    verbose_name : str
        Human-readable application label shown in the Django admin.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.predictions"
    verbose_name = "Match predictions"

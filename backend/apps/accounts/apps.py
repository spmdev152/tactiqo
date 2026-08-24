import importlib

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Application configuration of the identity slice.

    Attributes
    ----------
    default_auto_field : str
        Field class Django uses for implicit primary keys of this application.
    name : str
        Dotted import path of the application package, whose last component
        gives the application the ``accounts`` label.
    verbose_name : str
        Human-readable application label shown in the Django admin.

    Methods
    -------
    ready() -> None
        Import the signal receivers of the slice once the registry is loaded.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        """
        Import the signal receivers of the slice once the registry is loaded.

        The receivers import the models, which cannot be imported while this
        module is, so the import happens here and by name rather than as a
        top-level statement whose only purpose is a side effect.
        """

        importlib.import_module("apps.accounts.signals")

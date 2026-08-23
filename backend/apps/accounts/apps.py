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
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"

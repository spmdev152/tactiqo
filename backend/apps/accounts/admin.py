import logging

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.accounts.application.services import revoke_sessions
from apps.accounts.models import AuthSession, User

logger = logging.getLogger(__name__)


class UserCreationForm(AdminUserCreationForm):
    """
    Admin form creating an account from an address and a password.

    Its own ``Meta`` binds the swapped user model, because the bundled form
    otherwise asks for a username column that does not exist here.
    """

    class Meta:
        """
        Model and field binding of the creation form.

        Attributes
        ----------
        model : type of User
            Swapped user model the form writes to.
        fields : tuple of str
            Editable fields, the login identifier only.
        """

        model = User
        fields = ("email",)


class UserUpdateForm(UserChangeForm):
    """
    Admin form editing an existing account.

    Its own ``Meta`` binds the swapped user model, because the bundled form
    otherwise asks for a username column that does not exist here.
    """

    class Meta:
        """
        Model and field binding of the change form.

        Attributes
        ----------
        model : type of User
            Swapped user model the form writes to.
        fields : tuple of str
            Editable fields, the login identifier only; the remaining fields
            come from the fieldsets declared on the model admin.
        """

        model = User
        fields = ("email",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin surface of the swapped user model.

    Every option the bundled ``UserAdmin`` defines in terms of ``username`` is
    overridden, because that column does not exist on this model.

    Attributes
    ----------
    form : type of UserUpdateForm
        Form used to edit an existing account.
    add_form : type of UserCreationForm
        Form used to create an account.
    fieldsets : tuple of (str or None, dict of str to Any)
        Field layout of the change view.
    add_fieldsets : tuple of (str or None, dict of str to Any)
        Field layout of the add view.
    list_display : tuple of str
        Columns of the change list.
    list_filter : tuple of str
        Filters offered beside the change list.
    search_fields : tuple of str
        Fields the change list search box queries.
    ordering : tuple of str
        Ordering of the change list.
    """

    form = UserUpdateForm
    add_form = UserCreationForm

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
    )

    list_display = ("email", "full_name", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser", "groups")
    search_fields = ("email", "full_name")
    ordering = ("email",)


@admin.register(AuthSession)
class AuthSessionAdmin(admin.ModelAdmin):
    """
    Admin surface of the bearer session table.

    The surface is inspect-and-revoke only. Every field is read-only and no
    session can be added, because ``resolve_session`` authenticates a request
    as ``session.user``: an operator able to repoint that foreign key, or to
    type a digest of a token they chose into an add form, would hold every
    account of the installation, superusers included, through the sole
    ``accounts.change_authsession`` permission. Revocation stays reachable
    through the action below, which goes through the application layer so an
    already revoked session keeps its first revocation instant.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    list_filter : tuple of str
        Filters offered beside the change list.
    search_fields : tuple of str
        Fields the change list search box queries.
    readonly_fields : tuple of str
        Every field of the record, none of them editable.
    actions : tuple of str
        Change list actions offered on a selection of sessions.

    Methods
    -------
    has_add_permission(request) -> bool
        Refuse the creation of a session through the admin.
    revoke_selected_sessions(request, queryset) -> None
        Revoke the selected sessions that are still current.
    """

    list_display = ("user", "created_at", "expires_at", "revoked_at")
    list_filter = ("expires_at", "revoked_at")
    search_fields = ("user__email",)
    readonly_fields = ("user", "token_digest", "created_at", "expires_at", "revoked_at")
    actions = ("revoke_selected_sessions",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Refuse the creation of a session through the admin.

        Parameters
        ----------
        request : HttpRequest
            Admin request the permission is evaluated for.

        Returns
        -------
        bool
            Always ``False``: a session is issued by signing in.
        """

        logger.debug("Withheld the session add form from %s", request.user)

        return False

    @admin.action(description="Revoke selected sessions")
    def revoke_selected_sessions(
        self, request: HttpRequest, queryset: QuerySet[AuthSession]
    ) -> None:
        """
        Revoke the selected sessions that are still current.

        Parameters
        ----------
        request : HttpRequest
            Admin request the outcome is reported on.
        queryset : QuerySet of AuthSession
            Sessions the operator selected in the change list.
        """

        revoked_count = revoke_sessions(queryset)

        self.message_user(request, f"Sessions revoked: {revoked_count}.", messages.SUCCESS)

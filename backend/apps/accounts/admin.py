from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from apps.accounts.models import AuthSession, User


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

    An operator can inspect and revoke a session but cannot forge one: the
    digest and the issue instant are read-only, so no request can be made to
    authenticate by typing a value into this form.

    Attributes
    ----------
    list_display : tuple of str
        Columns of the change list.
    list_filter : tuple of str
        Filters offered beside the change list.
    search_fields : tuple of str
        Fields the change list search box queries.
    readonly_fields : tuple of str
        Fields shown but not editable.
    autocomplete_fields : tuple of str
        Relations rendered as a search widget instead of a full dropdown.
    """

    list_display = ("user", "created_at", "expires_at", "revoked_at")
    list_filter = ("expires_at", "revoked_at")
    search_fields = ("user__email",)
    readonly_fields = ("token_digest", "created_at")
    autocomplete_fields = ("user",)

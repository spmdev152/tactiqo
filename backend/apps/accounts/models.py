from collections.abc import Iterable
from datetime import datetime
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models, transaction
from django.db.models.base import ModelBase
from django.utils import timezone


def normalize_email(email: str) -> str:
    """
    Return the canonical storage form of an email address.

    Both the local part and the domain are lowercased, which is stricter than
    ``BaseUserManager.normalize_email``. Combined with the unique constraint on
    ``User.email`` it makes two addresses differing only in case mutually
    exclusive, without the write cost of a second functional index.

    Parameters
    ----------
    email : str
        Address as submitted by a client or by an administrator.

    Returns
    -------
    str
        Stripped, fully lowercased address.
    """

    return email.strip().lower()


class UserManager(BaseUserManager["User"]):
    """
    Manager creating accounts identified by an email address.

    Methods
    -------
    create_user(email, password=None, **extra_fields) -> User
        Create and store an ordinary account.
    create_superuser(email, password=None, **extra_fields) -> User
        Create and store an account with every administrative flag set.
    """

    def create_user(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> "User":
        """
        Create and store an ordinary account.

        Parameters
        ----------
        email : str
            Login identifier, normalized before it reaches the database.
        password : str or None
            Raw password to hash, or ``None`` to leave the account without a
            usable password.
        **extra_fields : object
            Further model field values forwarded to the model constructor.

        Returns
        -------
        User
            Persisted account.

        Raises
        ------
        ValueError
            If the address is blank once normalized.
        """

        if not normalize_email(email):
            raise ValueError("An email address is required to create an account.")

        user = self.model(email=email, **extra_fields)

        if password is None:
            user.set_unusable_password()
        else:
            user.set_password(password)

        user.save(using=self._db)

        return user

    def create_superuser(
        self, email: str, password: str | None = None, **extra_fields: object
    ) -> "User":
        """
        Create and store an account with every administrative flag set.

        Parameters
        ----------
        email : str
            Login identifier, normalized before it reaches the database.
        password : str or None
            Raw password to hash, or ``None`` to leave the account without a
            usable password.
        **extra_fields : object
            Further model field values forwarded to the model constructor.

        Returns
        -------
        User
            Persisted account with staff and superuser rights.

        Raises
        ------
        ValueError
            If the caller contradicts the staff or superuser flag.
        """

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if not extra_fields["is_staff"]:
            raise ValueError("A superuser must have is_staff=True.")

        if not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Account able to sign in to the API, identified by a unique email address.

    Django's bundled user model requires a unique ``username`` and treats
    ``email`` as an optional, non-unique column. This project authenticates on
    the address alone, so the username column is dropped and the address
    carries the unique constraint.

    Attributes
    ----------
    email : str
        Unique, fully lowercased address acting as the login identifier.
    full_name : str
        Display name, empty when the account has not provided one.
    is_active : bool
        Whether the account may authenticate.
    is_staff : bool
        Whether the account may reach the Django admin.
    date_joined : datetime
        Instant the account was created.
    objects : UserManager
        Default manager creating accounts from an email address.
    USERNAME_FIELD : str
        Field Django authenticates against, the email address.
    EMAIL_FIELD : str
        Field Django sends account email to, the email address.
    REQUIRED_FIELDS : list of str
        Extra prompts of ``createsuperuser``, empty because the address and the
        password already cover every mandatory column.

    Methods
    -------
    save(force_insert=False, force_update=False, using=None, update_fields=None) -> None
        Normalize the address and write the row with its receivers.
    set_unusable_password() -> None
        Store a hash no password can match and record the credential as gone.
    has_new_password() -> bool
        Report whether the credential of the account was just replaced.
    """

    email = models.EmailField(unique=True, verbose_name="email address")
    full_name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    # django-stubs omits the private attribute `set_password` writes and `save`
    # clears, which `has_new_password` reads.
    _password: str | None

    _password_removed = False

    class Meta(AbstractBaseUser.Meta, PermissionsMixin.Meta):
        """
        Admin labels and default ordering of the account table.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, alphabetical on the login identifier.
        """

        verbose_name = "user"
        verbose_name_plural = "users"
        ordering: ClassVar[list[str]] = ["email"]

    def __str__(self) -> str:
        """
        Return the login identifier of the account.

        Returns
        -------
        str
            Email address of the account.
        """

        return self.email

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """
        Normalize the address and write the row with its receivers.

        The write is wrapped in a transaction because ``save_base`` sends
        ``post_save`` inside it, and a receiver of this model revokes the
        sessions of a replaced credential. Without the transaction the password
        column would commit before the revocation ran, so a failure in between
        would leave a rotated password whose old sessions still authenticate. Once
        the row is written, a credential destroyed by ``set_unusable_password`` is
        no longer pending, so the record of it is cleared the way
        ``AbstractBaseUser`` clears the raw password it kept.

        Parameters
        ----------
        force_insert : bool or tuple of ModelBase
            Forwarded to ``django.db.models.Model.save``.
        force_update : bool
            Forwarded to ``django.db.models.Model.save``.
        using : str or None
            Database alias forwarded to ``django.db.models.Model.save``.
        update_fields : iterable of str or None
            Columns to write, forwarded to ``django.db.models.Model.save``.
        """

        self.email = normalize_email(self.email)

        with transaction.atomic(using=using):
            super().save(
                force_insert=force_insert,
                force_update=force_update,
                using=using,
                update_fields=update_fields,
            )

        self._password_removed = False

    def set_unusable_password(self) -> None:
        """
        Store a hash no password can match and record the credential as gone.

        ``AbstractBaseUser.set_unusable_password`` writes that hash without
        touching the raw password, because Django does not count destroying a
        credential as changing it. Here it counts: the admin's own "Password-based
        authentication: Disabled" submit reaches this method, and the sessions
        issued under the credential it destroys must not outlive it.
        """

        super().set_unusable_password()

        self._password_removed = True

    def has_new_password(self) -> bool:
        """
        Report whether the credential of the account was just replaced.

        ``AbstractBaseUser.set_password`` keeps the raw password on the instance
        and clears it only once ``save`` has written the row, so the value is
        present exactly while a save is storing a credential the account did not
        have before. Django draws the same line itself: the setter that re-hashes
        a password verified against an outdated hasher clears the value before
        saving, because a hash upgrade is not a password change. Destroying the
        credential outright is tracked separately, since Django's own setter for
        it deliberately leaves no trace.

        Returns
        -------
        bool
            ``True`` between the replacement of the credential and the end of the
            save that stores it.
        """

        return self._password is not None or self._password_removed


class AuthSession(models.Model):
    """
    Server-side record backing an opaque bearer token.

    The name keeps the record distinct from ``django.contrib.sessions``, which
    stays installed for the admin. No ``last_used_at`` column exists on
    purpose: stamping it would turn every authenticated read into a write.

    Attributes
    ----------
    user : User
        Account the token authenticates.
    token_digest : str
        Hexadecimal SHA-256 of the token. A bare digest rather than a password
        hash because the token is 256 bits of ``secrets`` entropy, so a slow key
        derivation would buy no brute-force resistance while costing a
        derivation on every authenticated request.
    created_at : datetime
        Instant the token was issued.
    expires_at : datetime
        Instant from which the token stops authenticating. Indexed because the
        purge task selects rows by expiry alone.
    revoked_at : datetime or None
        Instant the token was revoked, ``None`` while it is still current.

    Methods
    -------
    is_usable(at) -> bool
        Report whether the session authenticates at a given instant.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_sessions"
    )

    token_digest = models.CharField(max_length=64, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """
        Admin labels and default ordering of the session table.

        Attributes
        ----------
        verbose_name : str
            Singular label shown in the Django admin.
        verbose_name_plural : str
            Plural label shown in the Django admin.
        ordering : list of str
            Default ordering, most recently issued session first.
        """

        verbose_name = "authentication session"
        verbose_name_plural = "authentication sessions"
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        """
        Return a label naming the account and the expiry of the session.

        Returns
        -------
        str
            Account address followed by the expiry instant.
        """

        return f"{self.user.email} until {self.expires_at.isoformat()}"

    def is_usable(self, at: datetime) -> bool:
        """
        Report whether the session authenticates at a given instant.

        Parameters
        ----------
        at : datetime
            Timezone-aware instant to evaluate the session against.

        Returns
        -------
        bool
            ``True`` when the session is neither revoked nor expired.
        """

        return self.revoked_at is None and self.expires_at > at

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from tests.conftest import UserFactory

MIXED_CASE_EMAIL = "  Ada.Lovelace@Example.COM  "
NORMALIZED_EMAIL = "ada.lovelace@example.com"


@pytest.mark.django_db
def test_saving_an_account_normalizes_its_email_address(user_password: str) -> None:
    """
    GIVEN an address padded with spaces and mixing upper and lower case
    WHEN the account is created
    THEN the stored address is stripped and fully lowercased
    """

    account = User.objects.create_user(email=MIXED_CASE_EMAIL, password=user_password)

    account.refresh_from_db()

    assert account.email == NORMALIZED_EMAIL


@pytest.mark.django_db
def test_two_accounts_cannot_share_an_address_differing_only_in_case(
    user_password: str,
) -> None:
    """
    GIVEN an existing account whose address is stored in lowercase
    WHEN a second account is created with the same address in upper case
    THEN the database rejects the write on the unique constraint
    """

    User.objects.create_user(email=NORMALIZED_EMAIL, password=user_password)

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(email=NORMALIZED_EMAIL.upper(), password=user_password)


@pytest.mark.django_db
def test_creating_an_account_without_an_address_is_rejected(user_password: str) -> None:
    """
    GIVEN an address made of whitespace only
    WHEN an account is created with it
    THEN the manager refuses before touching the database
    """

    with pytest.raises(ValueError, match="email address is required"):
        User.objects.create_user(email="   ", password=user_password)


@pytest.mark.django_db
def test_creating_a_superuser_sets_every_administrative_flag(user_password: str) -> None:
    """
    GIVEN no explicit permission flags
    WHEN a superuser is created
    THEN the account is active, staff, and superuser
    """

    account = User.objects.create_superuser(email=NORMALIZED_EMAIL, password=user_password)

    assert account.is_active
    assert account.is_staff
    assert account.is_superuser


@pytest.mark.django_db
@pytest.mark.parametrize("contradicted_flag", ["is_staff", "is_superuser"])
def test_creating_a_superuser_rejects_a_contradicted_flag(
    user_password: str, contradicted_flag: str
) -> None:
    """
    GIVEN a caller denying one of the two administrative flags
    WHEN a superuser is created
    THEN the manager refuses instead of storing a downgraded superuser
    """

    with pytest.raises(ValueError, match=f"must have {contradicted_flag}=True"):
        User.objects.create_superuser(
            email=NORMALIZED_EMAIL, password=user_password, **{contradicted_flag: False}
        )


@pytest.mark.django_db
def test_an_account_created_without_a_password_cannot_authenticate_with_one() -> None:
    """
    GIVEN an account created without a password
    WHEN its password is inspected
    THEN the stored hash is unusable
    """

    account = User.objects.create_user(email=NORMALIZED_EMAIL)

    assert not account.has_usable_password()


@pytest.mark.django_db
def test_an_account_renders_as_its_address(user: UserFactory) -> None:
    """
    GIVEN a persisted account
    WHEN it is rendered as text
    THEN the login identifier is returned
    """

    account = user(email=NORMALIZED_EMAIL)

    assert str(account) == NORMALIZED_EMAIL

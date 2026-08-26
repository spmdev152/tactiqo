import pytest
from django.contrib import admin
from django.http import HttpRequest
from django.test import RequestFactory

from apps.accounts.models import User
from apps.statistics.admin import STATISTIC_FIELDS, MatchTeamStatisticAdmin
from apps.statistics.models import MatchTeamStatistic
from tests.conftest import UserFactory


@pytest.fixture
def statistic_admin() -> MatchTeamStatisticAdmin:
    """
    Return the statistics admin surface bound to the default admin site.

    Returns
    -------
    MatchTeamStatisticAdmin
        Admin surface under test.
    """

    return MatchTeamStatisticAdmin(MatchTeamStatistic, admin.site)


@pytest.fixture
def operator(user: UserFactory) -> User:
    """
    Return a staff account standing in for an admin operator.

    Parameters
    ----------
    user : UserFactory
        Factory persisting accounts for the test.

    Returns
    -------
    User
        Account allowed into the admin.
    """

    account = user(email="operator@example.com")
    account.is_staff = True

    account.save(update_fields=["is_staff"])

    return account


@pytest.fixture
def admin_request(operator: User) -> HttpRequest:
    """
    Return an admin request carrying an operator.

    The surface offers no admin action, so the request needs no session and no
    message store: the add permission and the change form are the whole surface,
    and the only thing either of them reads off the request is the operator the
    refusal is logged against.

    Parameters
    ----------
    operator : User
        Staff account the request is attributed to.

    Returns
    -------
    HttpRequest
        Request the admin surface can be exercised with.
    """

    request = RequestFactory().get("/admin/statistics/")
    request.user = operator

    return request


@pytest.mark.django_db
def test_a_statistic_row_cannot_be_added_through_the_admin(
    statistic_admin: MatchTeamStatisticAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator inside the statistics admin
    WHEN the add permission is evaluated
    THEN it is refused, because the synchronization task writes every row
    """

    assert statistic_admin.has_add_permission(admin_request) is False


@pytest.mark.django_db
def test_every_statistic_field_is_read_only_in_the_admin(
    statistic_admin: MatchTeamStatisticAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator opening the change form of a statistic row
    WHEN the form is built
    THEN every field is read-only and the form exposes none of them
    """

    assert set(statistic_admin.get_readonly_fields(admin_request)) == set(STATISTIC_FIELDS)
    assert not statistic_admin.get_form(admin_request).base_fields


@pytest.mark.django_db
def test_the_read_only_surface_covers_every_field_the_model_declares(
    statistic_admin: MatchTeamStatisticAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN a model whose twenty-two metric columns are easy to fall behind by hand
    WHEN the read-only fields are compared with the editable fields of the model
    THEN they are the same set, so a new metric cannot become quietly editable
    """

    editable_fields = {
        field.name for field in MatchTeamStatistic._meta.concrete_fields if not field.primary_key
    }

    assert set(statistic_admin.get_readonly_fields(admin_request)) == editable_fields

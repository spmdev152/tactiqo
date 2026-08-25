import pytest
from django.contrib import admin
from django.http import HttpRequest
from django.test import RequestFactory

from apps.accounts.models import User
from apps.predictions.admin import FixturePredictionAdmin, LeagueMarketReliabilityAdmin
from apps.predictions.models import FixturePrediction, LeagueMarketReliability
from tests.conftest import UserFactory

PREDICTION_FIELDS = ("fixture", "market", "selection", "probability", "synchronized_at")

RELIABILITY_FIELDS = ("league", "market", "quality", "hit_ratio", "synchronized_at")


@pytest.fixture
def prediction_admin() -> FixturePredictionAdmin:
    """
    Return the prediction admin surface bound to the default admin site.

    Returns
    -------
    FixturePredictionAdmin
        Admin surface under test.
    """

    return FixturePredictionAdmin(FixturePrediction, admin.site)


@pytest.fixture
def reliability_admin() -> LeagueMarketReliabilityAdmin:
    """
    Return the reliability admin surface bound to the default admin site.

    Returns
    -------
    LeagueMarketReliabilityAdmin
        Admin surface under test.
    """

    return LeagueMarketReliabilityAdmin(LeagueMarketReliability, admin.site)


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

    Neither surface offers an admin action, so the request needs no session and
    no message store: the add permission and the change form are the whole
    surface, and the only thing either of them reads off the request is the
    operator the refusal is logged against.

    Parameters
    ----------
    operator : User
        Staff account the request is attributed to.

    Returns
    -------
    HttpRequest
        Request the admin surfaces can be exercised with.
    """

    request = RequestFactory().get("/admin/predictions/")
    request.user = operator

    return request


@pytest.mark.django_db
def test_a_prediction_cannot_be_added_through_the_admin(
    prediction_admin: FixturePredictionAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator inside the prediction admin
    WHEN the add permission is evaluated
    THEN it is refused, because the synchronization task writes every row
    """

    assert prediction_admin.has_add_permission(admin_request) is False


@pytest.mark.django_db
def test_every_prediction_field_is_read_only_in_the_admin(
    prediction_admin: FixturePredictionAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator opening the change form of a prediction
    WHEN the form is built
    THEN every field is read-only and the form exposes none of them
    """

    assert set(prediction_admin.get_readonly_fields(admin_request)) == set(PREDICTION_FIELDS)
    assert not prediction_admin.get_form(admin_request).base_fields


@pytest.mark.django_db
def test_a_reliability_grade_cannot_be_added_through_the_admin(
    reliability_admin: LeagueMarketReliabilityAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator inside the reliability admin
    WHEN the add permission is evaluated
    THEN it is refused, because the grade is the provider's assessment of itself
    """

    assert reliability_admin.has_add_permission(admin_request) is False


@pytest.mark.django_db
def test_every_reliability_field_is_read_only_in_the_admin(
    reliability_admin: LeagueMarketReliabilityAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN an operator opening the change form of a reliability grade
    WHEN the form is built
    THEN every field is read-only and the form exposes none of them
    """

    assert set(reliability_admin.get_readonly_fields(admin_request)) == set(RELIABILITY_FIELDS)
    assert not reliability_admin.get_form(admin_request).base_fields

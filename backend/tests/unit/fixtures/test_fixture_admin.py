from http import HTTPStatus

import pytest
from django.contrib import admin
from django.db import connection
from django.db.models import Model
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from pytest_django.fixtures import DjangoAssertNumQueries

from apps.accounts.models import User
from apps.fixtures.admin import FixtureAdmin
from apps.fixtures.domain.enums import FixtureStatus
from apps.fixtures.models import Fixture, League, Team
from tests.conftest import UserFactory
from tests.unit.fixtures.conftest import (
    BARCELONA,
    LA_LIGA,
    LIVERPOOL,
    NOTTINGHAM_FOREST,
    PREMIER_LEAGUE,
    SEVILLA,
    kickoff,
    provider_fixture,
    store_window,
)

ADMIN_INDEX_URL = "/admin/"
LEAGUE_CHANGE_LIST_URL = "/admin/fixtures/league/"
TEAM_CHANGE_LIST_URL = "/admin/fixtures/team/"
FIXTURE_CHANGE_LIST_URL = "/admin/fixtures/fixture/"
LEAGUE_ADD_URL = f"{LEAGUE_CHANGE_LIST_URL}add/"
TEAM_ADD_URL = f"{TEAM_CHANGE_LIST_URL}add/"
FIXTURE_ADD_URL = f"{FIXTURE_CHANGE_LIST_URL}add/"

FIRST_WINDOW = [
    provider_fixture(1, kickoff(11, 30)),
    provider_fixture(2, kickoff(14), league=LA_LIGA, home_team=BARCELONA, away_team=SEVILLA),
]

LATER_WINDOW = [
    provider_fixture(
        provider_id,
        kickoff(17, provider_id),
        league=LA_LIGA,
        home_team=SEVILLA,
        away_team=BARCELONA,
    )
    for provider_id in range(3, 13)
]

PLAYED_FIXTURE = provider_fixture(
    13,
    kickoff(20),
    league=LA_LIGA,
    home_team=BARCELONA,
    away_team=SEVILLA,
    status=FixtureStatus.FINISHED,
    home_goals=2,
    away_goals=0,
)


def change_list_rows(fixture_admin: FixtureAdmin, request: HttpRequest) -> list[str]:
    """
    Build the fixture change list and read every relation its columns display.

    Parameters
    ----------
    fixture_admin : FixtureAdmin
        Admin surface the change list is built from.
    request : HttpRequest
        Admin request the change list is built for.

    Returns
    -------
    list of str
        One entry per listed fixture, naming its competition and both clubs.
    """

    change_list = fixture_admin.get_changelist_instance(request)

    return [
        f"{fixture.league.name}: {fixture.home_team.name} - {fixture.away_team.name}"
        for fixture in change_list.result_list
    ]


@pytest.fixture
def fixture_admin() -> FixtureAdmin:
    """
    Return the fixture admin surface bound to the default admin site.

    Returns
    -------
    FixtureAdmin
        Admin surface under test.
    """

    return FixtureAdmin(Fixture, admin.site)


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
        Account allowed into the admin and holding every permission.
    """

    account = user(email="operator@example.com")

    account.is_staff = True
    account.is_superuser = True

    account.save(update_fields=["is_staff", "is_superuser"])

    return account


@pytest.fixture
def admin_request(operator: User) -> HttpRequest:
    """
    Return an unfiltered change list request carrying an operator.

    Parameters
    ----------
    operator : User
        Staff account the request is attributed to.

    Returns
    -------
    HttpRequest
        Request the admin surface can be exercised with.
    """

    request = RequestFactory().get(FIXTURE_CHANGE_LIST_URL)

    request.user = operator

    return request


@pytest.fixture
def operator_client(operator: User) -> Client:
    """
    Return a client signed in to the admin as an operator.

    Parameters
    ----------
    operator : User
        Staff account the client authenticates as.

    Returns
    -------
    Client
        Client whose requests reach the admin.
    """

    client = Client()

    client.force_login(operator)

    return client


def test_every_fixture_model_is_registered_in_the_admin() -> None:
    """
    GIVEN the fixtures application loaded together with its admin module
    WHEN the default admin site registry is inspected
    THEN the competition, the club, and the fixture are all registered
    """

    assert admin.site.is_registered(League)
    assert admin.site.is_registered(Team)
    assert admin.site.is_registered(Fixture)


@pytest.mark.django_db
def test_the_admin_index_lists_the_three_fixture_change_lists(operator_client: Client) -> None:
    """
    GIVEN an operator signed in to the admin
    WHEN the admin index is rendered
    THEN it links to the competition, the club, and the fixture change lists
    """

    index = operator_client.get(ADMIN_INDEX_URL)

    assert index.status_code == HTTPStatus.OK
    assert LEAGUE_CHANGE_LIST_URL in index.text
    assert TEAM_CHANGE_LIST_URL in index.text
    assert FIXTURE_CHANGE_LIST_URL in index.text


@pytest.mark.django_db
def test_the_fixture_change_list_renders_a_stored_fixture(operator_client: Client) -> None:
    """
    GIVEN a stored fixture and an operator signed in to the admin
    WHEN the fixture change list is rendered
    THEN the page comes back carrying the row, its competition, and both clubs
    """

    store_window([provider_fixture(1, kickoff(11, 30))])

    stored = Fixture.objects.get(sportmonks_id=1)

    change_list = operator_client.get(FIXTURE_CHANGE_LIST_URL)

    assert change_list.status_code == HTTPStatus.OK
    assert f"{FIXTURE_CHANGE_LIST_URL}{stored.pk}/change/" in change_list.text
    assert PREMIER_LEAGUE.name in change_list.text
    assert LIVERPOOL.name in change_list.text
    assert NOTTINGHAM_FOREST.name in change_list.text


@pytest.mark.django_db
def test_the_fixture_change_list_narrows_to_the_fixtures_carrying_a_result(
    operator_client: Client,
) -> None:
    """
    GIVEN one stored fixture played to a result beside one still scheduled
    WHEN the change list is filtered on the finished stage and on a score
    THEN only the played fixture is listed by either filter
    """

    store_window([provider_fixture(1, kickoff(11, 30)), PLAYED_FIXTURE])

    scheduled = Fixture.objects.get(sportmonks_id=1)
    played = Fixture.objects.get(sportmonks_id=PLAYED_FIXTURE.provider_id)

    by_status = operator_client.get(f"{FIXTURE_CHANGE_LIST_URL}?status__exact=finished")
    with_a_score = operator_client.get(f"{FIXTURE_CHANGE_LIST_URL}?home_goals__isempty=0")

    for change_list in (by_status, with_a_score):
        assert change_list.status_code == HTTPStatus.OK
        assert f"{FIXTURE_CHANGE_LIST_URL}{played.pk}/change/" in change_list.text
        assert f"{FIXTURE_CHANGE_LIST_URL}{scheduled.pk}/change/" not in change_list.text


@pytest.mark.django_db
def test_the_fixture_change_list_costs_the_same_queries_whatever_the_row_count(
    fixture_admin: FixtureAdmin,
    admin_request: HttpRequest,
    django_assert_num_queries: DjangoAssertNumQueries,
) -> None:
    """
    GIVEN a change list read once over two fixtures and once over twelve
    WHEN both reads name the competition and both clubs of every listed row
    THEN the second costs exactly what the first did, so no query is per row
    """

    store_window(FIRST_WINDOW)

    with CaptureQueriesContext(connection) as first_read:
        change_list_rows(fixture_admin, admin_request)

    store_window(FIRST_WINDOW + LATER_WINDOW)

    with django_assert_num_queries(len(first_read)):
        rows = change_list_rows(fixture_admin, admin_request)

    assert len(rows) == len(FIRST_WINDOW) + len(LATER_WINDOW)


@pytest.mark.django_db
def test_the_fixture_change_list_orders_the_way_the_model_does(
    fixture_admin: FixtureAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN the fixture change list built for an operator
    WHEN the ordering it resolves is read
    THEN it is the model's own, not the descending key Django completes a tie with
    """

    change_list = fixture_admin.get_changelist_instance(admin_request)

    resolved = change_list.get_ordering(admin_request, Fixture.objects.all())

    assert resolved == ["kickoff_at", "id"]
    assert resolved == list(Fixture._meta.ordering or [])


@pytest.mark.django_db
def test_the_provider_identifier_is_read_only_on_the_fixture_change_form(
    fixture_admin: FixtureAdmin, admin_request: HttpRequest
) -> None:
    """
    GIVEN a stored fixture an operator opens the change form of
    WHEN the form is built
    THEN the fields the synchronization owns are read-only and absent from it
    """

    store_window([provider_fixture(1, kickoff(11, 30))])

    stored = Fixture.objects.get(sportmonks_id=1)

    read_only = set(fixture_admin.get_readonly_fields(admin_request, stored))
    editable = fixture_admin.get_form(admin_request, stored, change=True).base_fields

    assert {"sportmonks_id", "synchronized_at"} <= read_only
    assert "sportmonks_id" not in editable
    assert "synchronized_at" not in editable


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("add_url", "model"),
    [
        (LEAGUE_ADD_URL, League),
        (TEAM_ADD_URL, Team),
        (FIXTURE_ADD_URL, Fixture),
    ],
)
def test_the_admin_refuses_to_add_a_row_the_synchronization_owns(
    operator_client: Client, add_url: str, model: type[Model]
) -> None:
    """
    GIVEN an operator holding every permission on a synchronized table
    WHEN its add form is opened and then submitted
    THEN both are refused and no row appears, rather than the write failing
    """

    opened = operator_client.get(add_url)
    submitted = operator_client.post(add_url, {})

    assert opened.status_code == HTTPStatus.FORBIDDEN
    assert submitted.status_code == HTTPStatus.FORBIDDEN
    assert model.objects.exists() is False

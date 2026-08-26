from django.conf import settings
from ninja import NinjaAPI

from apps.accounts.api.router import router as auth_router
from apps.fixtures.api.router import fixtures_router, leagues_router
from apps.predictions.api.router import predictions_router
from apps.statistics.api.router import statistics_router
from config.health import router as health_router

api = NinjaAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Football intelligence contracts for fixtures, statistics, odds, and predictions.",
)

api.add_router("/", health_router)
api.add_router("/auth", auth_router)
api.add_router("/leagues", leagues_router)
api.add_router("/fixtures", fixtures_router)
api.add_router("/fixtures", predictions_router)
api.add_router("/fixtures", statistics_router)

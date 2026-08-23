from django.conf import settings
from ninja import NinjaAPI

from config.health import router as health_router

api = NinjaAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Football intelligence contracts for fixtures, statistics, odds, and predictions.",
)

api.add_router("/", health_router)

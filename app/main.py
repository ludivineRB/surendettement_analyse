from app.core.config import settings
from app.views.analytics_api import analytics_api
from app.views.risk_scores_api import risk_scores_api


from fastapi import FastAPI


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
app.include_router(analytics_api)
app.include_router(risk_scores_api)


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/data/health",
    }

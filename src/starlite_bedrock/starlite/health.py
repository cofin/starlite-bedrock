from sqlalchemy import text
from starlite import get

from starlite_bedrock.config import AppSettings, api_settings, app_settings
from starlite_bedrock.starlite import db


@get(path=api_settings.HEALTH_PATH, cache=False, tags=["Misc"])
async def health_check() -> AppSettings:
    """Check database available and returns app config info."""
    assert (await db.AsyncScopedSession().execute(text("SELECT 1"))).scalar_one() == 1
    return app_settings

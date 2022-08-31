from starlite_bedrock.cli import console
from starlite_bedrock.config import SentrySettings, app_settings


def configure() -> None:
    """
    Callback to configure sentry on app startup.

    See [SentrySettings][starlite_bedrock.config.SentrySettings].
    """
    sentry_settings = SentrySettings()
    try:
        import sentry_sdk  # pylint: disable=[import-outside-toplevel]
        from sentry_sdk.integrations.sqlalchemy import (  # pylint: disable=[import-outside-toplevel]
            SqlalchemyIntegration,
        )
    except ImportError:
        console.print("[bold red]Could not find Sentry libraries")

    sentry_sdk.init(
        dsn=sentry_settings.DSN,
        environment=app_settings.ENVIRONMENT,
        release=app_settings.BUILD_NUMBER,
        integrations=[SqlalchemyIntegration()],
        traces_sample_rate=sentry_settings.TRACES_SAMPLE_RATE,
    )

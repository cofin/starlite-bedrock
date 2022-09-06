from pydantic_openapi_schema.v3_1_0 import Contact
from starlite import OpenAPIConfig

from starlite_bedrock.config import app_settings, openapi_settings

config = OpenAPIConfig(
    title=openapi_settings.TITLE or app_settings.NAME,
    version=openapi_settings.VERSION,
    contact=Contact(
        name=openapi_settings.CONTACT_NAME, email=openapi_settings.CONTACT_EMAIL
    ),
    use_handler_docstrings=True,
    root_schema_site="elements",
)
"""
OpenAPI config for app, see [OpenAPISettings][starlite_bedrock.config.OpenAPISettings]

Defaults to 'elements' for the documentation.
 It has an interactive 3.1 compliant web app and Swagger does not yet support 3.1
"""

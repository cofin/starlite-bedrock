from starlite import OpenAPIConfig, Starlite

from starlite_bedrock.starlite import get

openapi_config = OpenAPIConfig(
    title="example",
    version="0.0.1",
    use_handler_docstrings=True,
    root_schema_site="elements",
)
"""
OpenAPI config for app, see [OpenAPISettings][starlite_bedrock.config.OpenAPISettings]

Defaults to 'elements' for the documentation.
    It has an interactive 3.1 compliant web app and Swagger does not yet support 3.1
"""


@get("/example")
def example_handler() -> dict:
    return {"hello": "world"}


app = Starlite(route_handlers=[example_handler])

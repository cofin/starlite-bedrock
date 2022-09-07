# flake8: noqa
"""
# starlite-foundation

An opinionated starlite api configuration library.
"""
from starlite_bedrock import (
    cli,
    client,
    config,
    db,
    db_types,
    endpoint_decorator,
    orm,
    repository,
    schema,
    starlite,
)

__all__ = [
    "cli",
    "client",
    "config",
    "db",
    "db_types",
    "endpoint_decorator",
    "orm",
    "repository",
    "schema",
    "starlite",
]


def main() -> None:
    cli.app()


if __name__ == "__main__":
    main()

from opdba.cli.commands.admin import cli as config_cli
from opdba.cli.commands.collect import cli as collect_cli
from opdba.cli.commands.run import cli as run_cli
from opdba.cli.commands.upload import cli as upload_cli

__all__ = [
    "config_cli",
    "run_cli",
    "collect_cli",
    "upload_cli",
]

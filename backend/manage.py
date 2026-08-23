import os
import sys
from pathlib import Path

from django.core.management import execute_from_command_line

from config.settings.environment import load_environment_file

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS_MODULE = "config.settings.local"


def main() -> None:
    """
    Run the Django management command given on the command line.

    Unlike the container entrypoints, which receive their configuration injected
    by Docker Compose, this script is run straight from a developer workstation.
    The repository dotenv file is therefore loaded before the settings module is
    resolved, so that ``DJANGO_SETTINGS_MODULE`` can be declared in ``.env``.
    """

    load_environment_file(REPOSITORY_ROOT / ".env")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", DEFAULT_SETTINGS_MODULE)

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

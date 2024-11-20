import os

from app.lib.util import strtobool
from populate import populate

from app import create_app

app = create_app(
    os.getenv("CONFIG", "config.Production"),
)

populate_on_startup = strtobool(os.getenv("POPULATE_ON_STARTUP", "True"))
if populate_on_startup:
    populate()

import os
from pathlib import Path

MASTER_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"
PLAYER_URL = "https://fantasy.premierleague.com/api/element-summary/{id}/"

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5
MAX_DELAY = 60
BACKOFF_BASE = 1
TIMEOUT = 10
CONCURRENCY = 10
USER_AGENT = "fpl-data-pipeline/0.1 (+https://github.com/yutsz1203/fpl-data-pipeline)"

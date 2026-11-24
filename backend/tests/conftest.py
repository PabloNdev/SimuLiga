import os

# Keep the test suite deterministic and offline: real API credentials in the
# developer's .env must not leak into unit tests or burn the daily quota.
os.environ["API_FOOTBALL_KEY"] = ""
os.environ["CLUBELO_ENABLED"] = "false"
os.environ["DATA_SOURCE"] = "demo"
os.environ["CHAMPIONS_API_FOOTBALL_KEY"] = ""
os.environ["CHAMPIONS_CLUBELO_ENABLED"] = "false"
os.environ["CHAMPIONS_DATA_SOURCE"] = "demo"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.champions.config import get_champions_settings  # noqa: E402

get_champions_settings.cache_clear()

import app.data.league as league  # noqa: E402
import app.champions.data.snapshot as champions_snapshot  # noqa: E402

league._SNAPSHOT = None
champions_snapshot._SNAPSHOT = None

"""Keep direct repository scripts on the publication timezone (Asia/Tokyo).

GitHub-hosted runners use UTC by default. Python automatically imports sitecustomize
from the script directory, so date.today() in direct publishing scripts resolves to JST
without changing system-wide runner settings.
"""
from __future__ import annotations

import os
import time

os.environ.setdefault("TZ", "Asia/Tokyo")
if hasattr(time, "tzset"):
    time.tzset()

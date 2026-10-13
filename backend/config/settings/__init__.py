"""Settings entry point.

DJANGO_SETTINGS_MODULE is always ``config.settings``; DJANGO_ENV picks the module.
An unset or unknown DJANGO_ENV resolves to production, so a misconfigured host
fails closed (DEBUG off, strict validation) instead of open.
"""

import os

_ENV = os.environ.get("DJANGO_ENV", "production").strip().lower()

if _ENV == "development":
    from .development import *  # noqa: F403
elif _ENV == "test":
    from .test import *  # noqa: F403
else:
    from .production import *  # noqa: F403

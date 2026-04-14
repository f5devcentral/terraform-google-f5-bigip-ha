"""Utilities for example test cases."""

import re

DEFAULT_BACKEND_SERVICE_SELF_LINK_PATTERN = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/regions/([a-z][a-z-]+[0-9])/backendServices/([a-z](?:[a-z0-9-]{0,61}[a-z0-9])?)$",
)
DEFAULT_TARGET_POOL_SELF_LINK_PATTERN = re.compile(
    r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])/regions/([a-z][a-z-]+[0-9])/targetPools/([a-z](?:[a-z0-9-]{0,61}[a-z0-9])?)$",
)

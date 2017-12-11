INCOMING_TOKEN = "XXXXXXX"
OUTGOING_TOKEN = "XXXXXXX"
TIMEOUT_SECONDS = 2 * 60
EXPIRE_SECONDS = 60 * 60

try:
    from .conf_private import *  # noqa
except ImportError:
    pass

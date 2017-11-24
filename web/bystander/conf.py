INCOMING_TOKEN = "XXXXXXX"
OUTGOING_TOKEN = "XXXXXXX"
EXPIRE_SECONDS = 60 * 60

try:
    from .conf_private import *  # noqa
except ImportError:
    pass

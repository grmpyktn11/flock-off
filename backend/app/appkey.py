"""The shared secret the app sends, and what it is worth.

This is not authentication and should not be mistaken for it. The key is
compiled into every APK, so anyone willing to unzip one has it, and no
amount of care here changes that.

What it buys is the difference between an endpoint that answers anything
and an endpoint that answers a client which knows one fact. Most abuse of
an open API proxy comes from scanners that find a URL, get a 200, and move
in. A 401 sends them elsewhere. The rate limit handles anyone who does not
leave, and the Google daily quota handles the case where both of those
fail.

Unset means open, matching how the rest of app.config treats missing
configuration: a fresh checkout runs with no setup, and locking the
service down is a deliberate act rather than an accident.
"""

import secrets

from fastapi import Header, HTTPException

from app import config


def require_app_key(x_app_key: str = Header(default="")) -> None:
    if not config.APP_KEY:
        return
    # compare_digest rather than == so the comparison takes the same time
    # whether the first character is wrong or the last. The attack it
    # forecloses is remote and slow, and the call is free.
    if not secrets.compare_digest(x_app_key, config.APP_KEY):
        raise HTTPException(status_code=401, detail="Unrecognised client.")

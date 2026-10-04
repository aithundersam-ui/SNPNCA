"""Rate limiting and lockout for repeated failed logins.

Failures are counted per email and per IP in the shared database cache. Once
either counter reaches LOGIN_MAX_FAILURES, further attempts are refused until
the lockout window expires, even with the right password.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache


def _key(kind, value):
    digest = hashlib.sha256((value or "").lower().encode()).hexdigest()[:32]
    return f"login-fail:{kind}:{digest}"


def is_locked(email, ip):
    limit = settings.LOGIN_MAX_FAILURES
    # The IP limit is looser so one shared office address can't lock everyone out.
    return cache.get(_key("email", email), 0) >= limit or cache.get(_key("ip", ip), 0) >= limit * 4


def record_failure(email, ip):
    for kind, value in (("email", email), ("ip", ip)):
        key = _key(kind, value)
        if cache.add(key, 1, settings.LOGIN_LOCKOUT_SECONDS):
            continue
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)


def clear(email):
    cache.delete(_key("email", email))


def hit_rate_limit(bucket, limit, window_seconds):
    """Generic fixed-window limiter. Returns True when the caller is over the limit."""
    key = f"rl:{hashlib.sha256(bucket.encode()).hexdigest()[:40]}"
    if cache.add(key, 1, window_seconds):
        return False
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window_seconds)
        return False
    return count > limit

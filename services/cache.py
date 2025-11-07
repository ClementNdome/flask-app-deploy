import time
import threading

_cache = {}
_lock = threading.Lock()


def cache_response(key: str, ttl: int, value_func):
    """Simple cache helper: returns cached value for key if not expired, else calls value_func to compute and cache it."""
    now = time.time()
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] > now:
            return entry[1]
    # compute outside lock
    val = value_func()
    with _lock:
        _cache[key] = (now + ttl, val)
    return val


def clear_cache():
    with _lock:
        _cache.clear()


def make_cache_decorator(ttl: int = 30):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # build a simple key from function name and args/kwargs
            key = func.__name__ + '|' + str(args) + '|' + str(kwargs)
            return cache_response(key, ttl, lambda: func(*args, **kwargs))
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

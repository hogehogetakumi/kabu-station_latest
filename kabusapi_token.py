import urllib.request
import json
import pprint
import time
from const import api_key, base_url

# Cached token and expiry timestamp (epoch seconds)
_token_cache: str | None = None
_token_expiry: float = 0.0
# Default token TTL in seconds (adjust as needed)
DEFAULT_TOKEN_TTL = 300.0


def _request_token() -> dict:
    """Perform the HTTP request to obtain a fresh token and return parsed JSON."""
    obj = {'APIPassword': api_key}
    json_data = json.dumps(obj).encode('utf8')
    url = f'{base_url.rstrip("/")}/token'
    req = urllib.request.Request(url, json_data, method='POST')
    req.add_header('Content-Type', 'application/json')

    with urllib.request.urlopen(req) as res:
        raw = res.read()
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return {'raw': raw}


def get_token(ttl: float = DEFAULT_TOKEN_TTL) -> str:
    """
    Return a valid API token. Uses an in-process cache with expiry (ttl seconds).
    If a cached token exists and hasn't expired, return it. Otherwise request a new token.

    Args:
        ttl: time-to-live in seconds for the cached token.

    Returns:
        token string

    Raises:
        RuntimeError if token cannot be obtained and no valid cached token exists.
    """
    global _token_cache, _token_expiry
    now = time.time()
    # return cached token if still valid
    if _token_cache and now < _token_expiry:
        return _token_cache

    # need to request a new token
    try:
        content = _request_token()
        # expecting {'Token': '...'} in response
        token = content.get('Token') if isinstance(content, dict) else None
        if token:
            _token_cache = token
            _token_expiry = now + float(ttl)
            return token
        else:
            # unexpected response
            raise RuntimeError({'http_error': False, 'body': content})
    except urllib.error.HTTPError as e:
        try:
            err_raw = e.read()
            err = json.loads(err_raw.decode('utf-8')) if isinstance(err_raw, (bytes, bytearray)) else json.loads(err_raw)
        except Exception:
            err = {'error': str(e)}
        # If previously cached token exists, return it with a warning
        if _token_cache:
            print('Warning: token endpoint returned HTTPError; using cached token')
            return _token_cache
        raise RuntimeError({'http_error': True, 'status': e.code, 'body': err}) from e
    except Exception as e:
        # fallback: if cached token exists, use it
        if _token_cache:
            print('Warning: failed to refresh token; using cached token')
            return _token_cache
        raise RuntimeError(f'Failed to obtain token: {e}') from e


if __name__ == '__main__':
    # quick smoke test
    try:
        t = get_token()
        print('Token:', t)
    except Exception as e:
        print('Failed to get token:', e)

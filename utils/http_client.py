import requests

from utils.logger import log

# Prefix so outbound network traffic is easy to spot/filter in the console.
_TAG = "[HTTP]"

# Query params whose values must never be logged.
_SENSITIVE_PARAMS = {"refresh_token", "code", "client_secret", "access_token", "api_key"}

# Cap logged bodies so a huge response can't flood the console.
_MAX_BODY_LOG = 800


def request(method: str, url: str, **kwargs) -> requests.Response:
    """``requests.request`` wrapper that logs the call and, on any HTTP error,
    the full response body — so failures aren't a black box.

    Drop-in for ``requests.request``: same signature/return, pass ``timeout``,
    ``params``, ``json`` etc. as usual. Network-level failures (timeout, DNS)
    are logged and re-raised. The ``Response`` is returned untouched, so callers
    still check status / parse JSON / call ``raise_for_status`` themselves.
    """
    method = method.upper()
    safe_params = _redact(kwargs.get("params"))
    log.debug(f"{_TAG} → {method} {url} params={safe_params}")

    try:
        resp = requests.request(method, url, **kwargs)
    except requests.RequestException as e:
        log.error(f"{_TAG} ✗ {method} {url} — network error: {e}")
        raise

    if resp.ok:
        log.debug(f"{_TAG} ← {resp.status_code} {method} {url}")
    else:
        log.error(f"{_TAG} ← {resp.status_code} {method} {url} — body: {_body(resp)}")
    return resp


def get(url: str, **kwargs) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)


def put(url: str, **kwargs) -> requests.Response:
    return request("PUT", url, **kwargs)


def delete(url: str, **kwargs) -> requests.Response:
    return request("DELETE", url, **kwargs)


def patch(url: str, **kwargs) -> requests.Response:
    return request("PATCH", url, **kwargs)


def _redact(params):
    if not isinstance(params, dict):
        return params
    return {k: ("***" if k in _SENSITIVE_PARAMS else v) for k, v in params.items()}


def _body(resp: requests.Response) -> str:
    text = (resp.text or "").strip()
    if not text:
        return "<empty>"
    return text[:_MAX_BODY_LOG] + ("…" if len(text) > _MAX_BODY_LOG else "")

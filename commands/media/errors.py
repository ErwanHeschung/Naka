import requests


def friendly_http_error(e: requests.HTTPError) -> str:
    """Turn a media-service HTTP error into a short, speakable message.

    Surfaces the service's own ``error.reason``/``error.message`` (Spotify
    returns these in the body) instead of guessing, so a 403 says *why* —
    e.g. the app is still in Development Mode and the account isn't allow-listed.
    """
    resp   = e.response
    status = resp.status_code if resp is not None else "?"

    reason  = ""
    message = ""
    if resp is not None:
        try:
            err = resp.json().get("error", {})
            if isinstance(err, dict):
                reason  = (err.get("reason")  or "").strip()
                message = (err.get("message") or "").strip()
        except Exception:
            pass

    if status == 401:
        return "Media auth failed — check your credentials in .env."

    if status == 403:
        if reason == "PREMIUM_REQUIRED":
            return "Playback control needs a Spotify Premium account."
        if "restriction violated" in message.lower():
            return (
                "The device refused the command. Open Spotify and start playing "
                "a track on the target device once, then try again."
            )
        detail = message or reason
        if detail:
            return (
                f"The media service refused the request (403): {detail}. "
                "If your app is in Development Mode, add your Spotify account "
                "under Users in the developer dashboard."
            )
        return (
            "The media service refused the request (403). If your app is in "
            "Development Mode, add your Spotify account under Users in the "
            "developer dashboard."
        )

    if status == 404:
        return "No active device found. Open the media app on any device first."

    detail = message or reason
    return f"Media API error {status}: {detail}" if detail else f"Media API error {status}: {e}"

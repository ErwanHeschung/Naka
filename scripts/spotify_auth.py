"""
One-time setup script — generates your Spotify refresh token.

Usage:
    uv run python scripts/spotify_auth.py

Prerequisites:
    1. Go to https://developer.spotify.com/dashboard
    2. Create an app (any name)
    3. In app settings, add this Redirect URI:  http://127.0.0.1:8888/spotify/callback
    4. Copy the Client ID and Client Secret

The script opens your browser, asks you to log in, then prints the three
variables to paste into your .env file.
"""

import http.server
import secrets
import threading
import urllib.parse
import webbrowser

import requests

REDIRECT_URI = "http://127.0.0.1:8888/spotify/callback"
SCOPES       = "user-modify-playback-state user-read-playback-state"

# ------------------------------------------------------------------
# Credentials
# ------------------------------------------------------------------
client_id     = input("Spotify Client ID:").strip()
client_secret = input("Spotify Client Secret: ").strip()

# ------------------------------------------------------------------
# Step 1 — open browser for user consent
# ------------------------------------------------------------------

# Cryptographically random state prevents CSRF on the local callback:
# without it, any process on the machine could race to POST a forged code.
_state = secrets.token_urlsafe(32)

auth_url = (
    "https://accounts.spotify.com/authorize"
    f"?client_id={client_id}"
    "&response_type=code"
    f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
    f"&scope={urllib.parse.quote(SCOPES)}"
    f"&state={_state}"
)

_code: list[str] = [] 
_done = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed        = urllib.parse.urlparse(self.path)
        if parsed.path != "/spotify/callback":
            self.send_response(404)
            self.end_headers()
            return

        params        = urllib.parse.parse_qs(parsed.query)
        code          = params.get("code",  [None])[0]
        error         = params.get("error", [None])[0]
        received_state = params.get("state", [None])[0]

        # Reject the callback if the state doesn't match what we sent —
        # this blocks any local process that races to deliver a forged code.
        if received_state != _state:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("Invalid state — possible CSRF attempt. Aborting.")
            _done.set()
            return

        if error:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Auth denied: {error}".encode())
        else:
            _code.append(code)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Auth complete - you can close this tab.")
        _done.set()

    def log_message(self, *_args) -> None:
        pass   # silence request logs


server = http.server.HTTPServer(("127.0.0.1", 8888), _CallbackHandler)
threading.Thread(target=server.handle_request, daemon=True).start()

print("\nOpening Spotify in your browser...")
webbrowser.open(auth_url)
_done.wait(timeout=120)

if not _code:
    print("\n❌ Auth failed or timed out.")
    raise SystemExit(1)

# ------------------------------------------------------------------
# Step 2 — exchange auth code for tokens
# ------------------------------------------------------------------
resp = requests.post(
    "https://accounts.spotify.com/api/token",
    data={
        "grant_type":   "authorization_code",
        "code":         _code[0],
        "redirect_uri": REDIRECT_URI,
    },
    auth=(client_id, client_secret),
    timeout=10,
)
resp.raise_for_status()
tokens = resp.json()

print("\n✅  Add these lines to your .env file:\n")
print(f"SPOTIFY_CLIENT_ID={client_id}")
print(f"SPOTIFY_CLIENT_SECRET={client_secret}")
print(f"SPOTIFY_REFRESH_TOKEN={tokens['refresh_token']}")

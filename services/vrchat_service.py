"""Shared VRChat API service.

Authenticates once per session (cookies persisted to config), then polls
the user / world / instance every 30s into an in-memory cache. Tokens read
from the cache so OSC cycles never hit the API directly.

WARNING: VRChat's API is unofficial and using it from third-party tools
technically violates VRChat's Terms of Service. Account ban risk is real.
The login dialog presents this warning to the user before sign-in.
"""

from __future__ import annotations

import atexit
import base64
import http.cookiejar
import json
import logging
import threading
import time
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

API_BASE = "https://api.vrchat.cloud/api/1"
USER_AGENT = "OpenChatbox/0.0.4 https://github.com/ZorudaRinku/OpenChatbox"
POLL_INTERVAL = 30.0
COOKIE_DOMAIN = "api.vrchat.cloud"

VRC_HINT = "<b>VRChat API is unofficial</b> - use could violate VRChat ToS and risks account bans. <b>Use at your own risk!</b>"


class VRChatAuthError(Exception):
    """Authentication failed."""


class TwoFactorRequired(Exception):
    """Login accepted credentials but needs a 2FA code next."""

    def __init__(self, methods: list[str]):
        super().__init__("Two-factor authentication required")
        self.methods = methods


def _parse_iso8601(value: str) -> float | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def _make_cookie(name: str, value: str) -> http.cookiejar.Cookie:
    return http.cookiejar.Cookie(
        version=0, name=name, value=value,
        port=None, port_specified=False,
        domain=COOKIE_DOMAIN, domain_specified=True, domain_initial_dot=False,
        path="/", path_specified=True,
        secure=True, expires=None, discard=False,
        comment=None, comment_url=None, rest={}, rfc2109=False,
    )


class VRChatService:
    def __init__(self):
        self._lock = threading.RLock()
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar)
        )
        self._user: dict[str, Any] | None = None
        self._user_id: str = ""
        self._world: dict[str, Any] | None = None
        self._instance: dict[str, Any] | None = None
        self._group: dict[str, Any] | None = None
        self._world_cache: dict[str, dict[str, Any]] = {}
        self._group_cache: dict[str, dict[str, Any]] = {}
        self._last_login_epoch: float | None = None
        self._worlds_seen: set[str] = set()
        self._prev_world_id: str = ""
        self._world_entered_at: float | None = None
        self._notifications_count: int = 0
        self._status: str = "Not signed in"
        self._poll_thread: threading.Thread | None = None
        self._poll_wakeup = threading.Event()
        self._stop_event = threading.Event()

    # --- Networking ---

    def _request(self, method: str, path: str, *,
                 data: dict | None = None,
                 basic_auth: tuple[str, str] | None = None,
                 timeout: float = 10.0) -> Any:
        url = f"{API_BASE}{path}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        if basic_auth is not None:
            user, pw = basic_auth
            user_q = urllib.parse.quote(user, safe="")
            pw_q = urllib.parse.quote(pw, safe="")
            token = base64.b64encode(f"{user_q}:{pw_q}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with self._opener.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode(errors="replace"))
                err = payload.get("error", {})
                if isinstance(err, dict):
                    message = err.get("message") or str(payload)
                else:
                    message = str(err) or str(payload)
            except Exception:
                message = exc.reason or "HTTP error"
            exc.vrc_message = message  # type: ignore[attr-defined]
            exc.vrc_status = exc.code  # type: ignore[attr-defined]
            raise

    # --- Cookie persistence ---

    def restore_cookies(self, auth: str, two_factor: str = ""):
        """Inject persisted auth cookies. Caller verifies via verify_session()."""
        with self._lock:
            self._cookie_jar.clear()
            if auth:
                self._cookie_jar.set_cookie(_make_cookie("auth", auth))
            if two_factor:
                self._cookie_jar.set_cookie(_make_cookie("twoFactorAuth", two_factor))

    def export_cookies(self) -> dict[str, str]:
        out: dict[str, str] = {}
        with self._lock:
            for c in self._cookie_jar:
                if c.name in ("auth", "twoFactorAuth"):
                    out[c.name] = c.value or ""
        return out

    # --- Authentication ---

    def verify_session(self) -> bool:
        """Try GET /auth/user with current cookies. True if authed."""
        try:
            result = self._request("GET", "/auth/user")
        except urllib.error.HTTPError as exc:
            self._set_status(f"Not signed in ({getattr(exc, 'vrc_status', '?')})")
            return False
        except Exception as exc:
            logger.warning("VRChat session verify failed: %s", exc)
            self._set_status("Offline")
            return False
        if "requiresTwoFactorAuth" in result:
            self._set_status("Session needs 2FA - please sign in again")
            return False
        with self._lock:
            self._user = result
            self._user_id = result.get("id", "")
        self._set_status(f"Signed in as {result.get('displayName', 'unknown')}")
        return True

    def login(self, username: str, password: str):
        """Step 1 of login. Raises TwoFactorRequired or VRChatAuthError."""
        with self._lock:
            self._cookie_jar.clear()
        try:
            result = self._request("GET", "/auth/user", basic_auth=(username, password))
        except urllib.error.HTTPError as exc:
            raise VRChatAuthError(getattr(exc, "vrc_message", "Login failed")) from exc
        if "requiresTwoFactorAuth" in result:
            raise TwoFactorRequired(result["requiresTwoFactorAuth"] or [])
        with self._lock:
            self._user = result
            self._user_id = result.get("id", "")
        self._set_status(f"Signed in as {result.get('displayName', 'unknown')}")

    def verify_2fa(self, code: str, method: str = "totp"):
        """Step 2 of login. method: 'totp', 'emailotp', or 'otp' (recovery)."""
        path = f"/auth/twofactorauth/{method}/verify"
        try:
            result = self._request("POST", path, data={"code": code})
        except urllib.error.HTTPError as exc:
            raise VRChatAuthError(getattr(exc, "vrc_message", "2FA failed")) from exc
        if not result.get("verified"):
            raise VRChatAuthError("Invalid 2FA code")
        user = self._request("GET", "/auth/user")
        with self._lock:
            self._user = user
            self._user_id = user.get("id", "")
        self._set_status(f"Signed in as {user.get('displayName', 'unknown')}")

    def logout(self):
        try:
            self._request("PUT", "/logout")
        except Exception:
            pass
        with self._lock:
            self._cookie_jar.clear()
            self._user = None
            self._user_id = ""
            self._world = None
            self._instance = None
            self._group = None
            self._last_login_epoch = None
            self._worlds_seen = set()
            self._prev_world_id = ""
            self._world_entered_at = None
            self._notifications_count = 0
        self._set_status("Not signed in")

    def is_authenticated(self) -> bool:
        with self._lock:
            return self._user is not None

    # --- State accessors ---

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    def _set_status(self, value: str):
        with self._lock:
            self._status = value

    def get_user(self) -> dict | None:
        with self._lock:
            return self._user.copy() if self._user else None

    def get_world(self) -> dict | None:
        with self._lock:
            return self._world.copy() if self._world else None

    def get_instance(self) -> dict | None:
        with self._lock:
            return self._instance.copy() if self._instance else None

    def get_group(self) -> dict | None:
        with self._lock:
            return self._group.copy() if self._group else None

    def get_last_login_epoch(self) -> float | None:
        """Wall-clock epoch seconds of the user's last VRChat login."""
        with self._lock:
            return self._last_login_epoch

    def get_world_entered_at(self) -> float | None:
        """time.monotonic() value when the current world was entered."""
        with self._lock:
            return self._world_entered_at

    def get_friends_in_instance_count(self) -> int:
        """Friends present in the user's current instance (instance.users[*].isFriend)."""
        with self._lock:
            instance = self._instance or {}
        users = instance.get("users") or []
        return sum(1 for u in users
                   if isinstance(u, dict) and u.get("isFriend"))

    def get_worlds_hopped_count(self) -> int:
        """Distinct worlds visited since this OpenChatbox session signed in."""
        with self._lock:
            return len(self._worlds_seen)

    def get_notifications_count(self) -> int:
        with self._lock:
            return self._notifications_count

    # --- Polling ---

    def start_polling(self):
        if self._poll_thread and self._poll_thread.is_alive():
            return
        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="VRChat-poll"
        )
        self._poll_thread.start()

    def stop_polling(self):
        self._stop_event.set()
        self._poll_wakeup.set()

    def request_refresh(self):
        self._poll_wakeup.set()

    def _poll_loop(self):
        while not self._stop_event.is_set():
            if self.is_authenticated():
                try:
                    self._poll_once()
                except Exception:
                    logger.exception("VRChat poll failed")
            self._poll_wakeup.wait(POLL_INTERVAL)
            self._poll_wakeup.clear()

    def _poll_once(self):
        # /auth/user returns own session
        # /users/{me_id} returns the cross-session aggregated view
        try:
            auth_user = self._request("GET", "/auth/user")
        except urllib.error.HTTPError as exc:
            if getattr(exc, "vrc_status", 0) == 401:
                with self._lock:
                    self._user = None
                self._set_status("Session expired - please sign in again")
            raise

        user_id = self._user_id or auth_user.get("id", "")
        if not self._user_id and user_id:
            with self._lock:
                self._user_id = user_id

        live_user: dict[str, Any] | None = None
        if user_id:
            try:
                live_user = self._request("GET", f"/users/{user_id}")
            except urllib.error.HTTPError as exc:
                logger.warning("VRChat /users/%s failed: %s", user_id,
                               getattr(exc, "vrc_message", exc))

        merged = dict(auth_user)
        if live_user:
            for key in ("state", "status", "statusDescription", "location",
                        "worldId", "instanceId", "travelingToInstance",
                        "travelingToWorld", "travelingToLocation",
                        "lastPlatform", "platform",
                        "last_login", "lastLogin"):
                if key in live_user:
                    merged[key] = live_user[key]

        with self._lock:
            self._user = merged

        last_login_raw = merged.get("last_login") or merged.get("lastLogin") or ""
        last_login_epoch = _parse_iso8601(last_login_raw) if last_login_raw else None
        world_id = (merged.get("worldId") or "").strip()
        with self._lock:
            self._last_login_epoch = last_login_epoch
            if world_id != self._prev_world_id:
                if world_id:
                    self._worlds_seen.add(world_id)
                    self._world_entered_at = time.monotonic()
                else:
                    self._world_entered_at = None
                self._prev_world_id = world_id

        try:
            notifs = self._request("GET", "/auth/user/notifications?n=100")
            if isinstance(notifs, list):
                count = sum(1 for n in notifs if not n.get("seen", True))
                with self._lock:
                    self._notifications_count = count
        except urllib.error.HTTPError as exc:
            logger.debug("VRChat notifications fetch failed: %s",
                         getattr(exc, "vrc_message", exc))

        location = (merged.get("location") or "").strip()
        if location and ":" in location and not location.startswith(("offline", "private", "traveling")):
            world_id = location.split(":", 1)[0]
            world = self._world_cache.get(world_id)
            if world is None:
                try:
                    world = self._request("GET", f"/worlds/{world_id}")
                    self._world_cache[world_id] = world
                except urllib.error.HTTPError:
                    world = None
            try:
                instance = self._request("GET", f"/instances/{location}")
            except urllib.error.HTTPError:
                instance = None

            group = None
            if instance:
                owner = (instance.get("ownerId") or "").strip()
                if owner.startswith("grp_"):
                    group = self._group_cache.get(owner)
                    if group is None:
                        try:
                            group = self._request("GET", f"/groups/{owner}")
                            self._group_cache[owner] = group
                        except urllib.error.HTTPError:
                            group = None

            with self._lock:
                self._world = world
                self._instance = instance
                self._group = group
        else:
            with self._lock:
                self._world = None
                self._instance = None
                self._group = None


# --- Singleton ---

_lock = threading.Lock()
_service: VRChatService | None = None


def get_service() -> VRChatService:
    global _service
    with _lock:
        if _service is None:
            _service = VRChatService()
        return _service


def persist_cookies(svc: VRChatService, config: dict):
    """Copy current auth cookies into config['vrchat'] and save to disk."""
    from config import save_config
    cookies = svc.export_cookies()
    config.setdefault("vrchat", {})
    config["vrchat"]["auth_cookie"] = cookies.get("auth", "")
    config["vrchat"]["two_factor_cookie"] = cookies.get("twoFactorAuth", "")
    save_config(config)


def bootstrap_from_config(config: dict):
    """Restore persisted cookies, verify the session, and start polling.

    Non-blocking: verification runs on a daemon thread so app startup is
    never delayed by VRChat API latency.
    """
    vrc = config.get("vrchat") or {}
    auth = vrc.get("auth_cookie") or ""
    two_factor = vrc.get("two_factor_cookie") or ""
    if not auth:
        return
    svc = get_service()
    svc.restore_cookies(auth, two_factor)

    def _init():
        try:
            svc.verify_session()
        finally:
            svc.start_polling()

    threading.Thread(target=_init, daemon=True, name="VRChat-init").start()


def shutdown():
    global _service
    with _lock:
        svc = _service
        _service = None
    if svc is not None:
        svc.stop_polling()


atexit.register(shutdown)

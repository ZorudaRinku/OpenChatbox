import tomllib
from unittest.mock import patch

import pytest

from services import vrchat_service


class _FakeService:
    def __init__(self, cookies):
        self._cookies = cookies

    def export_cookies(self):
        return dict(self._cookies)


def test_persist_cookies_writes_config_section(tmp_path):
    config_file = tmp_path / "config.toml"
    config = {"osc": {"ip": "127.0.0.1", "port": 9000}, "chats": []}
    svc = _FakeService({"auth": "AUTH123", "twoFactorAuth": "2FA456"})

    with patch("config.CONFIG_PATH", config_file):
        vrchat_service.persist_cookies(svc, config)

    with open(config_file, "rb") as f:
        loaded = tomllib.load(f)

    assert loaded["vrchat"]["auth_cookie"] == "AUTH123"
    assert loaded["vrchat"]["two_factor_cookie"] == "2FA456"
    assert config["vrchat"]["auth_cookie"] == "AUTH123"


def test_persist_cookies_handles_missing_two_factor(tmp_path):
    config_file = tmp_path / "config.toml"
    config = {}
    svc = _FakeService({"auth": "ONLY"})

    with patch("config.CONFIG_PATH", config_file):
        vrchat_service.persist_cookies(svc, config)

    assert config["vrchat"]["auth_cookie"] == "ONLY"
    assert config["vrchat"]["two_factor_cookie"] == ""


def test_persist_cookies_clears_section_on_logout(tmp_path):
    config_file = tmp_path / "config.toml"
    config = {"vrchat": {"auth_cookie": "OLD", "two_factor_cookie": "OLD2FA"}}
    svc = _FakeService({})

    with patch("config.CONFIG_PATH", config_file):
        vrchat_service.persist_cookies(svc, config)

    assert config["vrchat"]["auth_cookie"] == ""
    assert config["vrchat"]["two_factor_cookie"] == ""


@pytest.mark.parametrize("instance,expected", [
    ({"n_users": 4, "capacity": 16}, "4/16"),
    ({"n_users": 16, "capacity": 16}, "16/16"),
    ({"n_users": 16, "capacity": 16, "queueSize": 0}, "16/16"),
    ({"n_users": 16, "capacity": 16, "queueSize": 12}, "16/16 (12)"),
    ({"n_users": 20, "capacity": 16, "queueSize": 5}, "20/16 (5)"),
    ({"n_users": 4, "capacity": 16, "queueSize": 12}, "4/16"),
])
def test_instance_users_queue_display(monkeypatch, instance, expected):
    from services.tokens import VrcInstanceUsersToken
    from services.text_processor import init_fields

    token = VrcInstanceUsersToken()
    init_fields(token)
    monkeypatch.setattr(token._svc, "get_instance", lambda: instance)
    assert token.resolve() == expected


@pytest.mark.parametrize("authed,count,expected", [
    (False, 0, ""),
    (True, 0, ""),
    (True, 3, "3 unread"),
    (True, 1, "1 unread"),
])
def test_notifications_zero_uses_fallback(monkeypatch, authed, count, expected):
    from services.tokens import VrcNotificationsToken
    from services.text_processor import init_fields

    token = VrcNotificationsToken()
    init_fields(token)
    monkeypatch.setattr(token._svc, "is_authenticated", lambda: authed)
    monkeypatch.setattr(token._svc, "get_notifications_count", lambda: count)
    assert token.resolve() == expected


@pytest.mark.parametrize("token_cls_name", [
    "VrcStatusToken", "VrcStatusMessageToken", "VrcPronounsToken",
    "VrcFriendsOnlineToken", "VrcFriendsTotalToken",
    "VrcFriendsInInstanceToken", "VrcWorldToken", "VrcTimeInWorldToken",
    "VrcInstanceUsersToken", "VrcInstanceGroupToken", "VrcRegionToken",
    "VrcSessionLengthToken", "VrcWorldsHoppedToken", "VrcNotificationsToken",
])
def test_vrc_token_resolves_to_fallback_when_unauthenticated(token_cls_name):
    from services import tokens
    from services.text_processor import init_fields

    cls = getattr(tokens, token_cls_name)
    token = cls()
    init_fields(token)
    result = token.resolve()
    assert isinstance(result, str)
    assert result == token.fields.get("fallback", "")

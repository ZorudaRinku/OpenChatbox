import json
from unittest.mock import patch, MagicMock
from services.tokens.window_token import (
    X11Backend,
    HyprlandBackend,
    SwayBackend,
    KdotoolBackend,
    GnomeBackend,
    FallbackBackend,
    WindowToken,
    _detect_backend,
)
from services.text_processor import init_fields


def _mock_run(stdout="", returncode=0):
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    return result


class TestX11Backend:
    @patch("subprocess.run")
    def test_returns_title(self, mock_run):
        mock_run.return_value = _mock_run("Firefox\n")
        assert X11Backend().get_title() == "Firefox"

    @patch("subprocess.run")
    def test_returns_unknown_on_failure(self, mock_run):
        mock_run.return_value = _mock_run("", returncode=1)
        assert X11Backend().get_title() == "Unknown"

    @patch("subprocess.run")
    def test_returns_unknown_on_empty(self, mock_run):
        mock_run.return_value = _mock_run("")
        assert X11Backend().get_title() == "Unknown"


class TestHyprlandBackend:
    @patch("subprocess.run")
    def test_returns_title(self, mock_run):
        data = json.dumps({"title": "Alacritty"})
        mock_run.return_value = _mock_run(data)
        assert HyprlandBackend().get_title() == "Alacritty"

    @patch("subprocess.run")
    def test_returns_unknown_on_failure(self, mock_run):
        mock_run.return_value = _mock_run("", returncode=1)
        assert HyprlandBackend().get_title() == "Unknown"

    @patch("subprocess.run")
    def test_returns_unknown_when_no_title(self, mock_run):
        data = json.dumps({"title": ""})
        mock_run.return_value = _mock_run(data)
        assert HyprlandBackend().get_title() == "Unknown"


class TestSwayBackend:
    def _sway_tree(self, focused_name="kitty"):
        return {
            "name": "root",
            "focused": False,
            "nodes": [
                {
                    "name": "output",
                    "focused": False,
                    "nodes": [
                        {"name": focused_name, "focused": True, "nodes": []},
                    ],
                    "floating_nodes": [],
                }
            ],
            "floating_nodes": [],
        }

    @patch("subprocess.run")
    def test_returns_focused_title(self, mock_run):
        mock_run.return_value = _mock_run(json.dumps(self._sway_tree("VLC")))
        assert SwayBackend().get_title() == "VLC"

    @patch("subprocess.run")
    def test_returns_unknown_on_failure(self, mock_run):
        mock_run.return_value = _mock_run("", returncode=1)
        assert SwayBackend().get_title() == "Unknown"

    @patch("subprocess.run")
    def test_returns_unknown_when_nothing_focused(self, mock_run):
        tree = {"name": "root", "focused": False, "nodes": [], "floating_nodes": []}
        mock_run.return_value = _mock_run(json.dumps(tree))
        assert SwayBackend().get_title() == "Unknown"

    def test_find_focused_in_floating(self):
        tree = {
            "name": "root",
            "focused": False,
            "nodes": [],
            "floating_nodes": [
                {"name": "floating-win", "focused": True, "nodes": [], "floating_nodes": []},
            ],
        }
        assert SwayBackend()._find_focused(tree) == "floating-win"


class TestKdotoolBackend:
    @patch("subprocess.run")
    def test_returns_title(self, mock_run):
        mock_run.return_value = _mock_run("Dolphin\n")
        assert KdotoolBackend().get_title() == "Dolphin"

    @patch("subprocess.run")
    def test_returns_unknown_on_failure(self, mock_run):
        mock_run.return_value = _mock_run("", returncode=1)
        assert KdotoolBackend().get_title() == "Unknown"


class TestGnomeBackend:
    @patch("subprocess.run")
    def test_returns_title(self, mock_run):
        output = (
            'method return time=123 sender=:1.1\n'
            '   boolean true\n'
            '   string "Files"\n'
        )
        mock_run.return_value = _mock_run(output)
        assert GnomeBackend().get_title() == "Files"

    @patch("subprocess.run")
    def test_returns_unknown_on_failure(self, mock_run):
        mock_run.return_value = _mock_run("", returncode=1)
        assert GnomeBackend().get_title() == "Unknown"

    @patch("subprocess.run")
    def test_returns_unknown_on_empty_title(self, mock_run):
        output = (
            'method return time=123 sender=:1.1\n'
            '   boolean true\n'
            '   string ""\n'
        )
        mock_run.return_value = _mock_run(output)
        assert GnomeBackend().get_title() == "Unknown"


class TestFallbackBackend:
    def test_always_unknown(self):
        assert FallbackBackend().get_title() == "Unknown"


class TestDetectBackend:
    @patch("services.tokens.window_token.IS_WINDOWS", True)
    @patch("services.tokens.window_token.WinBackend")
    def test_windows(self, mock_cls):
        backend = _detect_backend()
        mock_cls.assert_called_once()

    @patch("services.tokens.window_token.IS_WINDOWS", False)
    @patch("services.tokens.window_token.session_type", return_value="x11")
    @patch("services.tokens.window_token.has_cmd", return_value=True)
    def test_x11_with_xdotool(self, *_):
        assert isinstance(_detect_backend(), X11Backend)

    @patch("services.tokens.window_token.IS_WINDOWS", False)
    @patch("services.tokens.window_token.session_type", return_value="x11")
    @patch("services.tokens.window_token.has_cmd", return_value=False)
    def test_x11_without_xdotool(self, *_):
        assert isinstance(_detect_backend(), FallbackBackend)

    @patch("services.tokens.window_token.IS_WINDOWS", False)
    @patch("services.tokens.window_token.session_type", return_value="wayland")
    @patch("services.tokens.window_token.desktop_env", return_value="hyprland")
    def test_wayland_hyprland(self, *_):
        assert isinstance(_detect_backend(), HyprlandBackend)

    @patch("services.tokens.window_token.IS_WINDOWS", False)
    @patch("services.tokens.window_token.session_type", return_value="wayland")
    @patch("services.tokens.window_token.desktop_env", return_value="sway")
    def test_wayland_sway(self, *_):
        assert isinstance(_detect_backend(), SwayBackend)

    @patch("services.tokens.window_token.IS_WINDOWS", False)
    @patch("services.tokens.window_token.session_type", return_value="wayland")
    @patch("services.tokens.window_token.desktop_env", return_value="gnome")
    def test_wayland_gnome(self, *_):
        assert isinstance(_detect_backend(), GnomeBackend)

    @patch("services.tokens.window_token.IS_WINDOWS", False)
    @patch("services.tokens.window_token.session_type", return_value="wayland")
    @patch("services.tokens.window_token.desktop_env", return_value="kde")
    @patch("services.tokens.window_token.has_cmd", return_value=True)
    def test_wayland_kde_with_kdotool(self, *_):
        assert isinstance(_detect_backend(), KdotoolBackend)

    @patch("services.tokens.window_token.IS_WINDOWS", False)
    @patch("services.tokens.window_token.session_type", return_value="wayland")
    @patch("services.tokens.window_token.desktop_env", return_value="kde")
    @patch("services.tokens.window_token.has_cmd", return_value=False)
    def test_wayland_kde_without_kdotool(self, *_):
        assert isinstance(_detect_backend(), FallbackBackend)


class TestWindowToken:
    def test_resolve_delegates_to_backend(self):
        token = WindowToken.__new__(WindowToken)
        init_fields(token)
        mock_backend = MagicMock()
        mock_backend.get_title.return_value = "Test Window"
        token._backend = mock_backend
        assert token.resolve() == "Test Window"

    def test_resolve_falls_back_on_exception(self):
        token = WindowToken.__new__(WindowToken)
        init_fields(token)
        mock_backend = MagicMock()
        mock_backend.get_title.side_effect = RuntimeError("fail")
        token._backend = mock_backend
        assert token.resolve() == "Unknown"

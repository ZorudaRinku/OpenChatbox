from unittest.mock import patch
from services.osc import OSCClient


class TestOSCClient:
    @patch("services.osc.SimpleUDPClient")
    def test_constructor(self, mock_udp_cls):
        OSCClient("10.0.0.1", 8000)
        mock_udp_cls.assert_called_once_with("10.0.0.1", 8000)

    @patch("services.osc.SimpleUDPClient")
    def test_default_ip_port(self, mock_udp_cls):
        OSCClient()
        mock_udp_cls.assert_called_once_with("127.0.0.1", 9000)

    @patch("services.osc.SimpleUDPClient")
    def test_send_message(self, mock_udp_cls):
        OSCClient().send_message("hello")
        mock_udp_cls.return_value.send_message.assert_called_once_with(
            "/chatbox/input", ["hello", True]
        )

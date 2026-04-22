import logging
from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger(__name__)


class OSCClient:
    def __init__(self, ip: str = "127.0.0.1", port: int = 9000):
        self.client = SimpleUDPClient(ip, port)

    def send_message(self, message: str, send_immediately: bool = True):
        self.client.send_message("/chatbox/input", [message, send_immediately])
        logger.info("\n" + message)

    def set_typing(self, is_typing: bool):
        self.client.send_message("/chatbox/typing", is_typing)
        logger.debug("typing=%s", is_typing)

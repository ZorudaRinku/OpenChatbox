import logging
from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger(__name__)


class OSCClient:
    def __init__(self, ip: str = "127.0.0.1", port: int = 9000):
        self.client = SimpleUDPClient(ip, port)

    def send_message(self, message: str):
        self.client.send_message("/chatbox/input", [message, True])
        logger.info("\n" + message)

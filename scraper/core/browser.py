import random
from scrapling.fetchers import StealthySession

class BrowserManager:
    """
    Manages Playwright sessions with integrated stealth.
    """
    def __init__(self):
        self.user_agents = [
            "IndeedApp/1.0 (Android; 10; SM-G973F)",
            "IndeedApp/1.1 (iPhone; iOS 14.4; Scale/3.00)",
            "IndeedApp/1.2 (Linux; Android 11; Pixel 5)"
        ]

    def get_session(self, headless: bool = True):
        """
        Creates and returns a new StealthySession.
        """
        # Scrapling's StealthySession can take headless parameter
        session = StealthySession(headless=headless)
        return session

    def get_random_mobile_ua(self):
        return random.choice(self.user_agents)

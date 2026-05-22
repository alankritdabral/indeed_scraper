import os
from scrapling.fetchers import StealthySession

class IndeedSessionManager:
    """
    Handles logging in and saving the browser state using a persistent directory.
    """
    def __init__(self, session_dir="indeed_session"):
        self.session_dir = session_dir
        self.base_url = "https://www.indeed.com"

    def login_and_save(self):
        """
        Opens a headed browser with a persistent profile for manual login.
        """
        print(f"🚀 Starting Stealthy Session with profile: {self.session_dir}...")
        
        # Ensure the session directory exists
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)

        # Use StealthySession with a persistent user data directory
        session = StealthySession(headless=False, user_data_dir=self.session_dir)
        session.start()
        
        page = session.context.new_page()
        page.goto(f"{self.base_url}/auth", wait_until="networkidle")
        
        print("\n--- ACTION REQUIRED ---")
        print("1. Please log in to your Indeed account manually in the browser window.")
        print("2. Once you are fully logged in and see your dashboard/home page,")
        print("   simply close the browser window or return here and press Enter.")
        
        input("\nPress Enter once you have logged in successfully...")
        
        print(f"✅ Session data maintained in '{self.session_dir}' directory.")
        session.close()

if __name__ == "__main__":
    manager = IndeedSessionManager()
    manager.login_and_save()

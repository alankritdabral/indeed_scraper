from scraper.platforms.indeed import IndeedScraper

class ScraperFactory:
    """
    Handles the creation of platform-specific scrapers.
    """
    @staticmethod
    def get_scraper(platform: str, domain: str = "com", headless: bool = True):
        if platform.lower() == "indeed":
            return IndeedScraper(domain=domain, headless=headless)
        # Add other platforms like linkedin here as needed
        else:
            raise ValueError(f"Platform '{platform}' is not supported.")

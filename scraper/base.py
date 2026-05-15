from abc import ABC, abstractmethod

class BasePlatform(ABC):
    @abstractmethod
    def scrape(self, query: str, location: str, pages: int = 1):
        """
        Main entry point for scraping jobs from a specific platform.
        """
        pass

    @abstractmethod
    def get_job_details(self, job_id: str):
        """
        Extract detailed information for a specific job.
        """
        pass

    @abstractmethod
    def save_results(self, filename: str):
        """
        Save the scraped results to a file.
        """
        pass

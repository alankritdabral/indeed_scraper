"""
Post search scraper for LinkedIn.

Searches for posts on LinkedIn based on keywords and filters.
"""
import logging
from typing import List, Optional
from urllib.parse import urlencode
from playwright.async_api import Page

from ..models.post import Post
from ..callbacks import ProgressCallback, SilentCallback
from .base import BaseScraper
from .company_posts import CompanyPostsScraper

logger = logging.getLogger(__name__)


class PostSearchScraper(CompanyPostsScraper):
    """
    Scraper for LinkedIn post search results.
    
    Filters for time:
    - past-24h: "past-24h"
    - past-week: "past-week"
    - past-month: "past-month"
    """
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize post search scraper.
        
        Args:
            page: Playwright page object
            callback: Optional progress callback
        """
        super().__init__(page, callback or SilentCallback())
    
    async def search(
        self,
        keywords: str,
        time_filter: Optional[str] = None,
        limit: int = 0
    ) -> List[Post]:
        """
        Search for posts on LinkedIn.
        
        Args:
            keywords: Search keywords
            time_filter: Time filter ('past-24h', 'past-week', 'past-month')
            limit: Maximum number of posts to return
            
        Returns:
            List of Post objects
        """
        logger.info(f"Starting post search: keywords='{keywords}', time_filter='{time_filter}'")
        
        search_url = self._build_search_url(keywords, time_filter)
        await self.callback.on_start("PostSearch", search_url)
        
        await self.navigate_and_wait(search_url)
        await self.callback.on_progress("Navigated to search results", 20)
        
        await self.check_rate_limit()
        
        # Initial wait for posts to load
        await self._wait_for_posts_to_load()
        await self.callback.on_progress("Initial posts loaded", 40)
        
        # Scrape with infinite scroll logic
        posts = await self._scrape_posts(limit)
        
        await self.callback.on_progress(f"Scraped {len(posts)} posts", 100)
        await self.callback.on_complete("PostSearch", posts)
        
        logger.info(f"Successfully scraped {len(posts)} posts")
        return posts
    
    def _build_search_url(self, keywords: str, time_filter: Optional[str] = None, sort_by: str = "date") -> str:
        """Build LinkedIn search URL for posts."""
        base_url = "https://www.linkedin.com/search/results/content/"
        
        params = {
            "keywords": keywords,
            "origin": "FACETED_SEARCH",
            "sortBy": f'"{sort_by}"' # "date" for Latest, "relevance" for Top
        }
        
        if time_filter:
            date_posted_map = {
                "past-24h": "past-24h",
                "past-week": "past-week",
                "past-month": "past-month"
            }
            if time_filter in date_posted_map:
                params["datePosted"] = f'"{date_posted_map[time_filter]}"'
        
        return f"{base_url}?{urlencode(params)}"

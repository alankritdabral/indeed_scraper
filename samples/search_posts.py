"""
Example: Search for posts with time filters
"""
import asyncio
from linkedin_scraper.scrapers.post_search import PostSearchScraper
from linkedin_scraper.core.browser import BrowserManager


async def main():
    keywords = "Artificial Intelligence"
    time_filter = "past-24h" # Options: past-24h, past-week, past-month
    
    async with BrowserManager(headless=False, slow_mo=100) as browser:
        await browser.load_session("linkedin_session.json")
        print("✓ Session loaded")
        
        scraper = PostSearchScraper(browser.page)
        
        print(f"🔍 Searching for posts: '{keywords}' ({time_filter})")
        posts = await scraper.search(keywords, time_filter=time_filter, limit=5)
        
        print("\n" + "="*60)
        print(f"Found {len(posts)} posts")
        print("="*60)
        
        for i, post in enumerate(posts, 1):
            print(f"\n[{i}] Posted: {post.posted_date}")
            print(f"URL: {post.linkedin_url}")
            print(f"Text: {post.text[:150]}...")
            print(f"Stats: {post.reactions_count} reactions, {post.comments_count} comments")
            print("-" * 40)
    
    print("\n✓ Done!")


if __name__ == "__main__":
    asyncio.run(main())

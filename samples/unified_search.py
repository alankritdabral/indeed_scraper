"""
Unified Post Search, Extraction, and Summarization Tool.
This script performs a search for posts in the last 24 hours, extracts content/metadata,
summarizes the text, and exports the results to a structured format.
"""
import asyncio
import json
import os
from datetime import datetime
from typing import List
from linkedin_scraper.scrapers.post_search import PostSearchScraper
from linkedin_scraper.core.browser import BrowserManager
from linkedin_scraper.models.post import Post

def generate_summary(text: str) -> str:
    """
    Generates a one-line summary of the post text.
    In a production environment, this could be replaced with an LLM call.
    """
    if not text:
        return "No content available."
    
    # Simple logic: get first sentence and clean it
    lines = text.strip().split('\n')
    first_meaningful_line = ""
    for line in lines:
        if len(line.strip()) > 20:
            first_meaningful_line = line.strip()
            break
    
    if not first_meaningful_line:
        first_meaningful_line = text[:100]
    
    # Split by common sentence endings
    for char in ['. ', '! ', '? ']:
        if char in first_meaningful_line:
            first_meaningful_line = first_meaningful_line.split(char)[0] + char.strip()
            break
            
    # Cap length
    if len(first_meaningful_line) > 120:
        first_meaningful_line = first_meaningful_line[:117] + "..."
        
    return first_meaningful_line

async def run_extraction(keywords: str, limit: int = 10):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"linkedin_posts_{timestamp}.json"
    report_filename = f"linkedin_report_{timestamp}.md"
    
    # Initialize empty JSON file
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump([], f)

    async with BrowserManager(headless=False, slow_mo=100) as browser:
        await browser.load_session("linkedin_session.json")
        print("✓ Session loaded")
        
        scraper = PostSearchScraper(browser.page)
        print(f"🔍 Searching for '{keywords}' in the last 24 hours...")
        
        # We'll use a local callback-like pattern or just check scraper state
        posts_count = 0
        
        def save_real_time(post_obj):
            summary = generate_summary(post_obj.text)
            post_data = {
                "username": post_obj.author_name,
                "profile_link": post_obj.author_url,
                "post_summary": summary,
                "full_post": post_obj.text,
                "post_url": post_obj.linkedin_url,
                "external_links": post_obj.external_links,
                "posted_at": post_obj.posted_date,
                "stats": {
                    "reactions": post_obj.reactions_count,
                    "comments": post_obj.comments_count,
                    "reposts": post_obj.reposts_count
                }
            }
            
            try:
                with open(output_filename, 'r+', encoding='utf-8') as f:
                    data = json.load(f)
                    data.append(post_data)
                    f.seek(0)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.truncate()
            except Exception as e:
                print(f"⚠️ Error saving real-time: {e}")

        # Inject real-time save callback into scraper
        scraper.on_post_extracted = save_real_time
        
        print(f"🚀 Extraction started. Saving to {output_filename} in real-time...")
        posts = await scraper.search(keywords, time_filter="past-24h", limit=limit)
        
        results = []
        # Re-read final results for the Markdown report
        with open(output_filename, 'r', encoding='utf-8') as f:
            results = json.load(f)
            
        # Save Markdown Report
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(f"# LinkedIn Post Search Report: {keywords}\n")
            f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"**Total Posts Scraped:** {len(results)}\n\n")
            
            for i, p in enumerate(results, 1):
                f.write(f"## {i}. {p['username']}\n")
                f.write(f"- **Profile:** {p['profile_link']}\n")
                f.write(f"- **Summary:** {p['post_summary']}\n")
                f.write(f"- **Links:** {', '.join(p['external_links']) if p['external_links'] else 'None'}\n")
                f.write(f"- **Stats:** {p['stats']['reactions']} likes, {p['stats']['comments']} comments\n\n")
                f.write(f"### Content\n{p['full_post']}\n\n")
                f.write("---\n\n")
                
    print(f"\n✅ Scraping complete!")
    print(f"📊 Final JSON data: {output_filename}")
    print(f"📝 Markdown report: {report_filename}")

if __name__ == "__main__":
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "Artificial Intelligence"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    print(f"🚀 Starting Unified Search for: '{query}' (Limit: {'None' if limit <= 0 else limit})")
    asyncio.run(run_extraction(query, limit))

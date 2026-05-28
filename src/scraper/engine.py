import json
import time
import random
import argparse
import os
import sqlite3
from scrapling.fetchers import StealthySession

from src.manager import JobDatabase

class IndeedScraper:
    """
    Indeed Scraper Engine: Supports both Headed and Headless modes.
    Uses Playwright (StealthySession) to bypass blocks and extract job data.
    """
    def __init__(self, domain="com", headless=True, session=None):
        self.domain = domain.strip('.')
        self.base_url = f"https://www.indeed.{self.domain}"
        self.headless = headless
        
        # Initialize or reuse the stealthy browser session
        if session:
            self.session = session
            self._session_owned = False
        else:
            self.session = StealthySession(headless=self.headless)
            self.session.start()
            self._session_owned = True
        
        # Standard mobile-app headers for the list view
        self.search_headers = {
            "X-Requested-With": "com.indeed.android.jobsearch",
            "X-Indeed-App-Version": "165.0",
            "X-Indeed-Client-Type": "android"
        }
        self.jobs_data = []

    def _get_job_details(self, job_info):
        """Extracts full job details using the desktop view."""
        jk = job_info['jk']
        url = f"{self.base_url}/viewjob?jk={jk}"
        
        try:
            page = self.session.context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(2, 4))
            
            # Broad selectors for descriptions
            desc_selectors = [
                '#jobDescriptionText', 
                '.jobsearch-JobComponent-description', 
                '.jobsearch-jobDescriptionText',
                '[data-testid="jobsearch-JobComponent-description"]',
                '.jobsearch-ViewJobLayout-jobDisplay',
                '#vjs-content'
            ]
            for sel in desc_selectors:
                el = page.locator(sel).first
                if el.count() > 0:
                    txt = el.inner_text().strip()
                    if txt and len(txt) > 20:
                        job_info["description"] = txt
                        break
            
            # Extract Apply URL (with fallback)
            apply_url = f"{self.base_url}/applystart?jk={jk}"
            is_easy_apply = False
            
            # Check for "Indeed Apply" button identifiers
            easy_apply_selectors = [
                'button#indeedApplyButton', 
                '.jobsearch-IndeedApplyButton',
                '#indeedApplyButtonContainer'
            ]
            for sel in easy_apply_selectors:
                if page.locator(sel).first.count() > 0:
                    is_easy_apply = True
                    break

            # Extract Apply URL
            apply_selectors = [
                'a#applyButtonLink', 'button[data-href]', 'a.icl-Button--primary', 
                '.jobsearch-CallToApplyPrimaryButton', 'a[href*="applystart"]'
            ]
            for sel in apply_selectors:
                el = page.locator(sel).first
                if el.count() > 0:
                    href = el.get_attribute('href') or el.get_attribute('data-href')
                    if href:
                        apply_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        # Only mark as easy apply if it's an indeed.com/applystart URL
                        if 'indeed.com/applystart' in apply_url or 'indeed.com/apply' in apply_url:
                            is_easy_apply = True
                        else:
                            is_easy_apply = False # Overwrite if it's an external link
                        break
            
            job_info["apply_url"] = apply_url
            job_info["is_easy_apply"] = is_easy_apply
            page.close()
        except:
            pass
        return job_info

    def scrape(self, query, location, limit=10, days=None, use_db=False, easy_apply_only=False):
        mode_str = "Headless" if self.headless else "Headed"
        filter_str = " (Easy Apply only)" if easy_apply_only else ""
        print(f"🚀 Reliable {mode_str} Scraping{filter_str}: '{query}' in '{location}'")
        
        db = None
        existing_jks = set()
        if use_db:
            db = JobDatabase()
            with sqlite3.connect(db.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT jk FROM jobs")
                existing_jks = {row[0] for row in cursor.fetchall()}
            print(f"🗄️ Database integration enabled. Found {len(existing_jks)} existing jobs in DB.")

        page_num = 0
        total_scraped = 0
        main_page = self.session.context.new_page()
        main_page.set_extra_http_headers(self.search_headers)

        while True:
            start = page_num * 10
            date_filter = f"&fromage={days}" if days else ""
            # Reverting to the mobile-app view URL which is often more consistent for Easy Apply tags
            url = f"{self.base_url}/m/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start}&isapp=1&vjs=3{date_filter}"
            
            print(f"\n[Page {page_num+1}] Fetching search results...")
            try:
                main_page.goto(url, wait_until="networkidle")
                
                try:
                    main_page.wait_for_selector('.job_seen_beacon, div[data-jk]', timeout=15000)
                except:
                    print("🏁 No more jobs found or blocked.")
                    break

                job_cards = main_page.locator('.job_seen_beacon, div[data-jk]').all()
                
                batch = []
                for card in job_cards:
                    if limit and total_scraped >= limit: break
                    jk = card.get_attribute('data-jk') or card.locator('a[data-jk]').get_attribute('data-jk')
                    
                    if not jk or jk in existing_jks:
                        continue

                    # Check for "Easily apply" label using multiple methods
                    is_easy = False
                    
                    # 1. Check inner text (very reliable on mobile view)
                    card_text = card.inner_text()
                    if "Easily apply" in card_text or "Easily Apply" in card_text:
                        is_easy = True
                    
                    # 2. Check for specific icons or containers
                    if not is_easy:
                        easy_indicators = [
                            ".iaIcon", 
                            "span:has-text('Easily apply')",
                            ".jobCardShelfContainer",
                            ".ia-EasilyApply",
                            ".jobCardShelfItem"
                        ]
                        for indicator in easy_indicators:
                            try:
                                if card.locator(indicator).first.count() > 0:
                                    is_easy = True
                                    break
                            except: continue

                    if easy_apply_only and not is_easy:
                        continue

                    try:
                        title_el = card.locator('.jobTitle').first
                        title = title_el.inner_text().strip()
                        
                        company_el = card.locator('[data-testid="company-name"], .companyName').first
                        company = company_el.inner_text().strip()
                        
                        location_el = card.locator('[data-testid="text-location"], .companyLocation, .location').first
                        loc = location_el.inner_text().strip() if location_el.count() > 0 else "N/A"
                    except:
                        continue
                    
                    batch.append({
                        "jk": jk, "title": title, "company": company, "location": loc, 
                        "url": f"{self.base_url}/viewjob?jk={jk}", "description": "N/A",
                        "is_easy_apply": is_easy
                    })
                    total_scraped += 1

                if batch:
                    print(f"  📦 Processing {len(batch)} new jobs...")
                    for i, job in enumerate(batch):
                        updated_job = self._get_job_details(job)
                        self.jobs_data.append(updated_job)
                        if db: 
                            db.add_job(updated_job)
                            existing_jks.add(updated_job['jk'])
                        status = "✅" if updated_job['is_easy_apply'] else "❌"
                        print(f"  {status} [{i+1}/{len(batch)}] Extracted: {updated_job['title']} @ {updated_job['company']}")

                if limit and total_scraped >= limit: break
                page_num += 1
                time.sleep(random.uniform(2, 5))
            except Exception as e:
                print(f"❌ Error on page {page_num+1}: {e}")
                break

        if self._session_owned:
            self.session.close()

    def save_data(self, filename="jobs_extracted.json"):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.jobs_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indeed Scraper Engine")
    parser.add_argument("-q", "--query", default="Python Developer", help="Search query")
    parser.add_argument("-l", "--location", default="Remote", help="Location")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Max jobs")
    parser.add_argument("--days", type=int, default=None, help="Filter by date posted")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser window")
    parser.add_argument("--db", action="store_true", help="Save to SQLite database")
    
    args = parser.parse_args()
    scraper = IndeedScraper(headless=not args.headed)
    try:
        scraper.scrape(args.query, args.location, limit=args.limit, days=args.days, use_db=args.db)
        scraper.save_data()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        print(f"\n✅ Done.")

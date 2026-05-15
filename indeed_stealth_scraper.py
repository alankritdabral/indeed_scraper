import json
import time
import random
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrapling import Fetcher
from urllib.parse import urlparse

class IndeedStealthScraper:
    """
    Indeed Stealth Scraper: Optimized for high-volume, high-speed headless scraping.
    Uses Mobile App Bypass for unlimited pagination and ThreadPool for fast detail extraction.
    """
    def __init__(self, domain="com", max_workers=5, proxy=None):
        self.domain = domain.strip('.')
        self.base_url = f"https://www.indeed.{self.domain}"
        self.max_workers = max_workers
        self.proxy = proxy
        
        print(f"🤖 Initializing FAST STEALTH Mode (Workers: {max_workers}, Proxy: {'Yes' if proxy else 'No'})...")
        # Using Fetcher for maximum stealth/bypass via curl_cffi
        self.engine = Fetcher()
        if self.proxy:
            # Configure engine to use the provided proxy
            self.engine.configure(proxy=self.proxy)
        
        # Proven Mobile App Headers
        self.headers = {
            "User-Agent": "IndeedApp/1.0 (Android; 10; SM-G973F)",
            "X-Requested-With": "com.indeed.android.jobsearch",
            "X-Indeed-App-Version": "165.0",
            "X-Indeed-Client-Type": "android",
            "X-Indeed-App-Package": "com.indeed.android.jobsearch",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        }
        self.jobs_data = []

    def _establish_session(self):
        """Initial visit to mobile home to get cookies and handle regional redirects."""
        print(f"--- Establishing session for indeed.{self.domain} ---")
        try:
            response = self.engine.get(f"{self.base_url}/m/", headers=self.headers)
            if "indeed" in response.url:
                parsed = urlparse(response.url)
                self.base_url = f"{parsed.scheme}://{parsed.netloc}"
                print(f"📍 Target Region: {self.base_url}")
            time.sleep(2)
        except Exception as e:
            print(f"Warning: Session setup error: {e}")

    def get_job_details(self, jk):
        """Fetches job details (description and apply URL) using the mobile view endpoint."""
        url = f"{self.base_url}/m/viewjob?jk={jk}"
        # Standard Indeed apply redirect is a reliable fallback
        apply_fallback = f"{self.base_url}/applystart?jk={jk}&from=vj"
        details = {"description": "N/A", "apply_url": apply_fallback}
        try:
            time.sleep(random.uniform(1, 3))
            response = self.engine.get(url, headers=self.headers)
            
            # Extract description - trying multiple selectors
            desc_selectors = [
                '#jobDescriptionText',
                '.jobsearch-JobComponent-description',
                '.jobsearch-jobDescriptionText',
                '[data-testid="jobsearch-JobComponent-description"]',
                'div.jobsearch-JobComponent-description',
                '#vjs-content'
            ]
            
            for sel in desc_selectors:
                desc_els = response.css(sel)
                if desc_els:
                    text = desc_els.first.get_all_text().strip()
                    if text:
                        details["description"] = text
                        break
            
            # Extract Apply URL (Redirects to company site or Indeed apply)
            apply_link = response.css('a#applyButtonLink::attr(href)').get() or \
                         response.css('button[data-href]::attr(data-href)').get() or \
                         response.css('a[href*="apply"]::attr(href)').get() or \
                         response.css('a.icl-Button--primary::attr(href)').get()
            
            if apply_link:
                # Ensure it's an absolute URL
                if apply_link.startswith('/'):
                    details["apply_url"] = f"{self.base_url}{apply_link}"
                else:
                    details["apply_url"] = apply_link
            
            # If it's still just the JK viewjob link, use applystart
            if "viewjob?jk=" in details["apply_url"] and "applystart" not in details["apply_url"]:
                details["apply_url"] = apply_fallback

            return details
        except Exception as e:
            print(f"      ⚠️ Detail Fetch Error ({jk}): {e}")
            return details

    def scrape(self, query, location, limit=None, days=None):
        self._establish_session()
        
        print(f"\n🚀 Stealth Scraping started: '{query}' in '{location}'")
        if days:
            print(f"📅 Filtering by last {days} days")
        
        page = 0
        total_scraped = 0
        
        while True:
            start = page * 10
            # fromage parameter handles the "Date Posted" filter (e.g., fromage=1 for last 24h)
            date_filter = f"&fromage={days}" if days else ""
            url = f"{self.base_url}/m/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start}&isapp=1&vjs=3{date_filter}"
            
            print(f"\n[Page {page+1}] Fetching list: {url}")
            
            if page > 0:
                self.headers["Referer"] = f"{self.base_url}/m/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start-10}&isapp=1&vjs=3"
            else:
                self.headers["Referer"] = f"{self.base_url}/m/"

            try:
                response = self.engine.get(url, headers=self.headers)
                
                if "signin" in response.url.lower() or "auth" in response.url.lower():
                    print("❌ Login wall detected. Pagination blocked.")
                    break

                jobs = response.css('div[data-jk]') or response.css('.job_seen_beacon')
                
                if not jobs:
                    print("No more jobs found. Finishing.")
                    break

                print(f"Found {len(jobs)} jobs. Fetching details concurrently...")

                current_batch = []
                for job_el in jobs:
                    if limit and total_scraped >= limit:
                        break

                    jk = job_el.attrib.get('data-jk') or job_el.css('a::attr(data-jk)').get()
                    if not jk: continue

                    title = job_el.css('.jobTitle::text').get() or \
                            job_el.css('h2.jobTitle span::text').get() or \
                            job_el.css('a[data-jk]::text').get()
                            
                    company = job_el.css('.companyName::text').get() or \
                              job_el.css('[data-testid="company-name"]::text').get() or \
                              job_el.css('.company::text').get()
                    
                    loc = job_el.css('[data-testid="text-location"]::text').get() or \
                          job_el.css('.location::text').get()

                    date_posted = job_el.css('.date::text').get() or \
                                  job_el.css('.myJobsState::text').get() or \
                                  job_el.css('[class*="date"]::text').get()

                    job_info = {
                        "title": title.strip() if title else "N/A",
                        "company": company.strip() if company else "N/A",
                        "location": loc.strip() if loc else "N/A",
                        "jk": jk,
                        "posted_date": date_posted.strip() if date_posted else "N/A",
                        "url": f"{self.base_url}/viewjob?jk={jk}"
                    }
                    current_batch.append(job_info)
                    total_scraped += 1

                # Concurrent extraction of details
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_job = {executor.submit(self.get_job_details, job['jk']): job for job in current_batch}
                    for future in as_completed(future_to_job):
                        job = future_to_job[future]
                        try:
                            res = future.result()
                            job["description"] = res["description"]
                            job["apply_url"] = res["apply_url"]
                            
                            status = "✅" if job["description"] != "N/A" else "⚠️ (No Desc)"
                            print(f"  {status} Extracted: {job['title']} @ {job['company']}")
                        except Exception as e:
                            job["description"] = "N/A"
                            job["apply_url"] = job["url"]
                            print(f"  ❌ Failed: {job['title']} - {e}")
                        
                        self.jobs_data.append(job)

                
                self.save_data()
                
                if limit and total_scraped >= limit:
                    print(f"\n✅ Reached target limit of {limit} jobs.")
                    return

                page += 1
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                print(f"Error on page {page+1}: {e}")
                break

    def save_data(self, filename="jobs_stealth.json"):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.jobs_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indeed Stealth Scraper - High Speed Headless Mobile Bypass")
    parser.add_argument("-q", "--query", default="Python Developer", help="Job search query")
    parser.add_argument("-l", "--location", default="Remote", help="Job location")
    parser.add_argument("-d", "--domain", default="com", help="Indeed domain")
    parser.add_argument("-n", "--limit", type=int, default=None, help="Max jobs to scrape")
    parser.add_argument("-w", "--workers", type=int, default=5, help="Number of concurrent workers (default: 5)")
    parser.add_argument("--days", type=int, default=None, help="Filter by date posted (e.g., 1 for last 24 hours, 7 for last week)")
    
    args = parser.parse_args()

    scraper = IndeedStealthScraper(domain=args.domain, max_workers=args.workers)
    try:
        scraper.scrape(args.query, args.location, limit=args.limit, days=args.days)
    except KeyboardInterrupt:
        print("\nScraping interrupted.")
    finally:
        print(f"\n✅ Done! Total jobs scraped: {len(scraper.jobs_data)}")
        print(f"Results saved to jobs_stealth.json")

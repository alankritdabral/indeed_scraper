import json
import time
import os
import random
from typing import List, Dict
from scraper.base import BasePlatform
from scraper.core.browser import BrowserManager

class IndeedScraper(BasePlatform):
    def __init__(self, domain: str = "com", headless: bool = False):
        self.domain = domain.strip('.')
        self.base_url = f"https://www.indeed.{self.domain}/m/jobs"
        self.viewjob_url = f"https://www.indeed.{self.domain}/viewjob"
        self.m_viewjob_url = f"https://www.indeed.{self.domain}/m/viewjob"
        
        self.browser_manager = BrowserManager()
        self.session = self.browser_manager.get_session(headless=headless)
        self.session.start()
        
        # Using a more robust and consistent mobile UA (Indeed App)
        self.user_agent = "IndeedApp/1.0 (Android; 10; SM-G973F)"
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "X-Requested-With": "com.indeed.android.jobsearch"
        }
        self.jobs_data = []

    def _handle_resilience(self, response):
        """
        Resilience Loop: Pauses for manual CAPTCHA solving when Turnstile is detected.
        """
        content = response.text.lower()
        if "cf-challenge" in content or "turnstile" in content:
            print("!!! CAPTCHA/Turnstile Detected !!!")
            print("Please solve the CAPTCHA in the browser window if it opened, or check your IP.")
            input("Press Enter once you have resolved the challenge...")
            return True
        return False

    def get_job_details(self, jk: str):
        """
        Extracts structured data directly from the viewjob page using stealthy headers.
        """
        url = f"{self.viewjob_url}?jk={jk}"
        print(f"  --> Fetching details for {jk}...")
        try:
            # Use cleaner headers for the detailed view to avoid detection
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Referer": self.base_url
            }
            response = self.session.fetch(url, headers=headers, solve_cloudflare=True)
            self._handle_resilience(response)

            # Try to extract JSON-LD first (most structured)
            json_ld_selectors = response.css('script[type="application/ld+json"]::text')
            json_ld = json_ld_selectors.getall()
            
            if json_ld:
                for ld_text in json_ld:
                    try:
                        data = json.loads(ld_text)
                        # Handle both single objects and lists
                        ld_items = data if isinstance(data, list) else [data]
                        for item in ld_items:
                            if item.get('@type') == 'JobPosting':
                                return {
                                    "description": item.get("description", "N/A"),
                                    "raw_json_ld": item
                                }
                    except json.JSONDecodeError:
                        continue

            # Fallback to verified CSS selectors
            desc_els = response.css('#jobDescriptionText')
            if desc_els:
                return {"description": desc_els.first.get_all_text().strip()}
            
            alt_selectors = ['.jobsearch-JobComponent-description', '.jobsearch-jobDescriptionText']
            for sel in alt_selectors:
                el = response.css(sel)
                if el:
                    return {"description": el.first.get_all_text().strip()}
            
            return {"description": "N/A"}

        except Exception as e:
            print(f"Error getting details for {jk}: {e}")
            return None

    def scrape(self, query: str, location: str, pages: int = 1, limit: int = None):
        # Mobile app parameters to bypass login wall
        common_params = "from=mobRdr&utm_source=%2Fm%2F&utm_medium=redir&utm_campaign=dt"
        
        jobs_count = 0
        for p in range(pages):
            start = p * 10
            # Strictly use the /m/jobs endpoint as recommended for mobile bypass
            url = f"https://www.indeed.{self.domain}/m/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start}&{common_params}"
            print(f"\nScraping Page {p+1}: {url}")
            
            # Additional delay between pages to mimic human browsing
            if p > 0:
                time.sleep(random.uniform(5, 12))
            
            try:
                # Rotate Referer
                self.headers["Referer"] = random.choice([
                    "https://www.google.com/",
                    "https://www.bing.com/",
                    f"https://www.indeed.{self.domain}/"
                ])
                
                response = self.session.fetch(url, headers=self.headers, solve_cloudflare=True)
                self._handle_resilience(response)

                if "signin" in response.url.lower() or "auth" in response.url.lower():
                    print("Warning: Hit login wall. Attempting deep session rotation...")
                    self.session.close()
                    time.sleep(2)
                    self.session = self.browser_manager.get_session(headless=True)
                    self.session.start()
                    # Try a different UA for the new session
                    self.user_agent = self.browser_manager.get_random_mobile_ua()
                    self.headers["User-Agent"] = self.user_agent
                    response = self.session.fetch(url, headers=self.headers, solve_cloudflare=True)
                    
                    if "signin" in response.url.lower() or "auth" in response.url.lower():
                        print(f"Failed to bypass login wall on page {p+1}. Skipping page.")
                        continue

                jobs = response.css('.job_seen_beacon')
                if not jobs:
                    jobs = response.css('div[data-jk]') 
                
                print(f"Found {len(jobs)} jobs on page {p+1}")
                
                if len(jobs) == 0:
                    break

                for job_el in jobs:
                    if limit and jobs_count >= limit:
                        print(f"Reached limit of {limit} jobs. Stopping.")
                        return

                    title = job_el.css('h2.jobTitle span::text').get() or job_el.css('.jobTitle::text').get()
                    company = job_el.css('[data-testid="company-name"]::text').get() or job_el.css('.companyName::text').get()
                    location_text = job_el.css('[data-testid="text-location"]::text').get() or job_el.css('.location::text').get()
                    jk = job_el.attrib.get('data-jk') or job_el.css('a::attr(data-jk)').get()
                    
                    if not jk:
                        continue

                    job_info = {
                        "title": title.strip() if title else "N/A",
                        "company": company.strip() if company else "N/A",
                        "location": location_text.strip() if location_text else "N/A",
                        "jk": jk,
                        "link": f"{self.viewjob_url}?jk={jk}",
                        "description": "N/A"
                    }
                    
                    details = self.get_job_details(jk)
                    if details:
                        job_info["description"] = details.get("description", "N/A")
                        if "raw_json_ld" in details:
                            job_info["json_ld"] = details["raw_json_ld"]
                    
                    self.jobs_data.append(job_info)
                    jobs_count += 1
                    self.save_results("jobs.json")
                    
                    # Random delay between jobs
                    time.sleep(random.uniform(2, 5))

            except Exception as e:
                print(f"Error on page {p+1}: {e}")
                break

    def save_results(self, filename: str):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.jobs_data, f, indent=4, ensure_ascii=False)

    def convert_to_md(self, json_file="jobs.json", md_file="jobs.md"):
        if not os.path.exists(json_file):
            return
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write("# Indeed Job Search Results\n\n")
            for job in data:
                f.write(f"## {job.get('title', 'N/A')}\n")
                f.write(f"- **Company:** {job.get('company', 'N/A')}\n")
                f.write(f"- **Location:** {job.get('location', 'N/A')}\n")
                f.write(f"- **Link:** {job.get('link', 'N/A')}\n\n")
                f.write(f"### Description\n{job.get('description', 'N/A')}\n\n")
                f.write("---\n\n")

    def close(self):
        if hasattr(self.session, 'close'):
            self.session.close()

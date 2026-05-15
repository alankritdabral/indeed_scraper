import json
import time
import random
import argparse
import os
from scrapling.fetchers import StealthySession

class IndeedHeadedAppScraper:
    """
    Indeed Headed App Scraper: Uses mobile app view in a headed browser.
    This bypasses login walls by mimicking the mobile app behavior.
    """
    def __init__(self, domain="com", headed=True):
        self.domain = domain.strip('.')
        self.base_url = f"https://www.indeed.{self.domain}"
        self.headed = headed
        
        # Mobile app headers
        self.ua = "IndeedApp/1.0 (Android; 10; SM-G973F)"
        self.headers = {
            "X-Requested-With": "com.indeed.android.jobsearch",
            "X-Indeed-App-Version": "165.0",
            "X-Indeed-Client-Type": "android"
        }
        
        print(f"🖥️  Initializing {'HEADED' if self.headed else 'HEADLESS'} Mobile App Session...")
        self.session = StealthySession(
            headless=not self.headed,
            useragent=self.ua,
            extra_headers=self.headers
        )
        self.session.start()
        
        self.jobs_data = []

    def scrape(self, query, location, limit=None, days=None):
        filename = "jobs_headed_app.json"
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    self.jobs_data = json.load(f)
                    print(f"📂 Resuming from {len(self.jobs_data)} existing jobs...")
            except:
                self.jobs_data = []

        date_filter = f"&fromage={days}" if days else ""

        total_scraped = len(self.jobs_data)
        page_num = total_scraped // 10

        # Using the /m/jobs mobile endpoint with app parameters
        start_val = page_num * 10
        search_url = f"{self.base_url}/m/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start_val}&isapp=1&vjs=3{date_filter}"

        print(f"\n🚀 Navigating to Mobile App View: {search_url}")

        try:
            self.page = self.session.context.new_page()
            self.page.goto(search_url, wait_until="networkidle")

            # Handle potential initial popups
            time.sleep(5)
            self._dismiss_popups()

            jobs_since_restart = 0

            while True:
                # Periodic browser restart to prevent memory issues
                if jobs_since_restart >= 50:
                    print("\n🔄 Periodic browser restart to maintain stability...")
                    self.session.close()
                    time.sleep(5)
                    self.session.start()
                    self.page = self.session.context.new_page()
                    # Re-navigate to the correct page
                    start_next = page_num * 10
                    current_url = f"{self.base_url}/m/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start_next}&isapp=1&vjs=3{date_filter}"
                    self.page.goto(current_url, wait_until="networkidle")
                    self._dismiss_popups()
                    jobs_since_restart = 0

                # Wait for jobs to load
                try:
                    self.page.wait_for_selector('.job_seen_beacon, div[data-jk]', timeout=15000)
                except:
                    print("No jobs found or timeout. Finishing.")
                    break
                    
                job_cards = self.page.locator('.job_seen_beacon, div[data-jk]')
                count = job_cards.count()
                
                if count == 0:
                    break
                
                print(f"Found {count} jobs on Page {page_num + 1}")
                
                # We'll collect JKs first because navigating away might invalidate locators
                job_infos = []
                for i in range(count):
                    card = job_cards.nth(i)
                    jk = card.get_attribute('data-jk') or card.locator('a[data-jk]').get_attribute('data-jk')
                    if jk:
                        # Extract basic info from the list view
                        title_el = card.locator('.jobTitle').first
                        title = title_el.inner_text().strip() if title_el.count() > 0 else "N/A"
                        
                        company_el = card.locator('[data-testid="company-name"], .companyName').first
                        company = company_el.inner_text().strip() if company_el.count() > 0 else "N/A"
                        
                        job_infos.append({"jk": jk, "title": title, "company": company})

                for job in job_infos:
                    if limit and total_scraped >= limit:
                        print(f"✅ Reached limit of {limit} jobs.")
                        return

                    jk = job["jk"]
                    print(f"  [{total_scraped + 1}] Fetching details: {job['title']} @ {job['company']}")
                    
                    # Open job details in a new page/tab
                    try:
                        details = self._get_job_details(jk)
                        
                        job_entry = {
                            **job,
                            "description": details["description"],
                            "apply_url": details["apply_url"],
                            "url": f"{self.base_url}/viewjob?jk={jk}"
                        }
                        
                        self.jobs_data.append(job_entry)
                        total_scraped += 1
                        jobs_since_restart += 1
                        self.save_data()
                    except Exception as e:
                        print(f"    ⚠️ Error extracting job {jk}: {e}")
                    
                    # Mimic human browsing
                    time.sleep(random.uniform(1.0, 2.5))

                # Check for "Next" page
                next_button = self.page.locator('a:has-text("Next"), a[aria-label="Next"]').last
                if next_button.count() > 0 and next_button.is_visible():
                    print("\n⏭️ Moving to next page...")
                    next_button.click()
                    time.sleep(random.uniform(3, 6))
                    self._dismiss_popups()
                    page_num += 1
                else:
                    # Try alternate pagination
                    start_next = (page_num + 1) * 10
                    next_url = f"{self.base_url}/m/jobs?q={query.replace(' ', '+')}&l={location.replace(' ', '+')}&start={start_next}&isapp=1&vjs=3{date_filter}"
                    print(f"\n⏭️ Navigating to next page manually: {next_url}")
                    try:
                        self.page.goto(next_url, wait_until="networkidle")
                        time.sleep(3)
                        self._dismiss_popups()
                        page_num += 1
                    except:
                        print("Failed to navigate to next page. Finishing.")
                        break

                    
        except Exception as e:
            print(f"❌ Critical error: {e}")
        finally:
            self.close()

    def _get_job_details(self, jk):
        """Extracts details from the job page with multiple fallbacks."""
        # We'll try a few variations of the URL
        urls = [
            f"{self.base_url}/viewjob?jk={jk}",
            f"{self.base_url}/m/viewjob?jk={jk}",
            f"{self.base_url}/job/{jk}"
        ]

        res = {"description": "N/A", "apply_url": f"{self.base_url}/applystart?jk={jk}&from=vj"}

        detail_page = self.session.context.new_page()
        try:
            # Try URLs until one works
            for detail_url in urls:
                print(f"    Trying detail: {detail_url}")
                try:
                    detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(3, 5))

                    # 1. Try JSON-LD first (most reliable if present)
                    json_ld_elements = detail_page.locator('script[type="application/ld+json"]').all()
                    for ld in json_ld_elements:
                        try:
                            data = json.loads(ld.inner_text())
                            if isinstance(data, list):
                                data = data[0]
                            if data.get('@type') == 'JobPosting' or 'description' in data:
                                desc = data.get('description', '')
                                if desc and len(desc) > 50:
                                    res["description"] = desc
                                    print("      ✅ Found in JSON-LD")
                                    break
                        except: continue

                    if res["description"] != "N/A": break

                    # 2. Try CSS Selectors
                    desc_selectors = [
                        '#jobDescriptionText',
                        '.jobsearch-JobComponent-description',
                        '.jobsearch-jobDescriptionText',
                        '[data-testid="jobsearch-JobComponent-description"]',
                        '.job-description',
                        'div[role="main"]',
                        '#vjs-content',
                        '.vjs-desc',
                        '#desc-content'
                    ]

                    for sel in desc_selectors:
                        el = detail_page.locator(sel).first
                        if el.count() > 0:
                            txt = el.inner_text().strip()
                            if txt and len(txt) > 50:
                                res["description"] = txt
                                print(f"      ✅ Found with selector: {sel}")
                                break

                    if res["description"] != "N/A": break

                    # 3. Try iframes
                    for frame in detail_page.frames:
                        for sel in desc_selectors:
                            el = frame.locator(sel).first
                            if el.count() > 0:
                                txt = el.inner_text().strip()
                                if txt and len(txt) > 50:
                                    res["description"] = txt
                                    print(f"      ✅ Found in iframe with {sel}")
                                    break
                        if res["description"] != "N/A": break

                    if res["description"] != "N/A": break
                except Exception as e:
                    print(f"      ⚠️ Failed URL {detail_url}: {e}")
                    continue

            # Extract Apply URL (from the last successful page)
            apply_selectors = [
                'a#applyButtonLink',
                'button[data-href]',
                'a.icl-Button--primary',
                'a[href*="apply"]',
                '[data-testid="jobsearch-ViewJobButtons-container"] a',
                '#apply-button'
            ]

            for sel in apply_selectors:
                try:
                    apply_el = detail_page.locator(sel).first
                    if apply_el.count() > 0:
                        href = apply_el.get_attribute('href') or apply_el.get_attribute('data-href')
                        if href:
                            if href.startswith('http'):
                                res["apply_url"] = href
                            else:
                                res["apply_url"] = f"{self.base_url}{href}"
                            break
                except: continue

        except Exception as e:
            print(f"    ⚠️ Error fetching details for {jk}: {e}")
        finally:
            detail_page.close()

        return res

    def _dismiss_popups(self):
        """Dismisses common mobile view popups."""
        try:
            popups = [
                'button[aria-label="Close"]',
                '.icl-CloseButton',
                '[data-testid="app-download-promo-bottom-sheet"] button',
                '#sm-close-button',
                '.vjs-close-button'
            ]
            for sel in popups:
                el = self.page.locator(sel).first
                if el.count() > 0 and el.is_visible():
                    el.click()
                    time.sleep(0.5)
        except:
            pass

    def save_data(self, filename="jobs_headed_app.json"):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(self.jobs_data, f, indent=4, ensure_ascii=False)

    def close(self):
        if hasattr(self.session, 'close'):
            self.session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indeed Headed App Scraper - Mobile View Bypass")
    parser.add_argument("-q", "--query", default="Python Developer", help="Job search query")
    parser.add_argument("-l", "--location", default="Remote", help="Job location")
    parser.add_argument("-d", "--domain", default="com", help="Indeed domain")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Max jobs to scrape")
    parser.add_argument("--days", type=int, default=None, help="Filter by date posted")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    
    args = parser.parse_args()
    scraper = IndeedHeadedAppScraper(domain=args.domain, headed=not args.headless)
    try:
        scraper.scrape(args.query, args.location, limit=args.limit, days=args.days)
    except KeyboardInterrupt:
        print("\nScraping interrupted.")
    finally:
        print(f"\n✅ Total jobs scraped: {len(scraper.jobs_data)}")
        print(f"Results saved to jobs_headed_app.json")

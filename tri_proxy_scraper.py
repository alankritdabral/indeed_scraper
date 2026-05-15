import os
import time
import random
import datetime
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from scrapling import Fetcher

# Load .env for MONGO_URI
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "indeed_scraper"

class TriProxyIndeedScraper:
    def __init__(self, query, location, domain, p_search, p_read1, p_read2, days=7):
        self.query = query
        self.location = location
        self.domain = domain
        self.days = days
        self.base_url = f"https://www.indeed.{domain}"
        
        # 1. Initialize DB
        if not MONGO_URI:
            raise ValueError("MONGO_URI not found in environment or .env file.")
            
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.jobs = self.db["jobs"]
        # Ensure index exists
        self.jobs.create_index("jk", unique=True)

        # 2. Initialize Engines with dedicated proxies and stable impersonation
        print(f"🔄 Initializing Engines with dedicated proxies...")
        
        # We use 'chrome124' impersonation which is very stable for Indeed
        fetcher_kwargs = {"impersonate": "chrome124"}

        self.search_engine = Fetcher(**fetcher_kwargs)
        if p_search: 
            self.search_engine.configure(proxy=p_search)
            print(f"  📡 Searcher Proxy: {p_search}")
        
        self.reader_1 = Fetcher(**fetcher_kwargs)
        if p_read1: 
            self.reader_1.configure(proxy=p_read1)
            print(f"  📖 Reader 1 Proxy: {p_read1}")
        
        self.reader_2 = Fetcher(**fetcher_kwargs)
        if p_read2: 
            self.reader_2.configure(proxy=p_read2)
            print(f"  📖 Reader 2 Proxy: {p_read2}")
        
        self.readers = [self.reader_1, self.reader_2]
        self.headers = {
            "User-Agent": "IndeedApp/1.0 (Android; 10; SM-G973F)",
            "X-Requested-With": "com.indeed.android.jobsearch",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def warmup(self):
        """Establishing session cookies for all three proxies."""
        print("🔥 Warming up sessions...")
        for i, engine in enumerate([self.search_engine, self.reader_1, self.reader_2]):
            try:
                # Visit mobile home to establish session
                engine.get(f"{self.base_url}/m/", headers=self.headers)
                print(f"  ✅ Engine {i+1} Session Established.")
            except Exception as e:
                print(f"  ⚠️ Engine {i+1} Warmup Failed: {e}")
        time.sleep(2)

    def get_detailed_job(self, job_basic, reader_engine):
        """Reader Proxy visits the job detail page."""
        jk = job_basic['jk']
        url = f"{self.base_url}/m/viewjob?jk={jk}"
        job_basic["description"] = "N/A"
        job_basic["apply_url"] = f"{self.base_url}/applystart?jk={jk}"
        job_basic["salary"] = None
        
        try:
            # Human-like delay before hitting detail page
            time.sleep(random.uniform(2, 5))
            response = reader_engine.get(url, headers=self.headers)
            
            # Extract Description
            for sel in ['#jobDescriptionText', '.jobsearch-JobComponent-description', '.jobsearch-jobDescriptionText']:
                desc = response.css(sel)
                if desc:
                    job_basic["description"] = desc.first.get_all_text().strip()
                    break
            
            # Extract Salary
            salary = response.css('.jobsearch-JobMetadataHeader-item::text').get() or \
                     response.css('.icl-u-xs-mr--1::text').get()
            if salary: job_basic["salary"] = salary.strip()
            
            # Extract Apply URL (Redirects to company site)
            apply = response.css('a#applyButtonLink::attr(href)').get() or \
                    response.css('button[data-href]::attr(data-href)').get()
            if apply:
                job_basic["apply_url"] = apply if apply.startswith('http') else f"{self.base_url}{apply}"
            
            return job_basic
        except Exception as e:
            print(f"      ⚠️ Reader Error ({jk}): {e}")
            return job_basic

    def run(self, once=False):
        self.warmup()
        while True:
            print(f"\n🚀 Starting search for '{self.query}' in '{self.location}'...")
            page = 0
            while True:
                # ... same logic ...

                # fromage=X filters for jobs posted within the last X days
                url = f"{self.base_url}/m/jobs?q={self.query.replace(' ', '+')}&l={self.location.replace(' ', '+')}&start={start}&isapp=1&fromage={self.days}"
                
                try:
                    # Proxy A (Searcher) fetches the list
                    response = self.search_engine.get(url, headers=self.headers)
                    job_els = response.css('div[data-jk]') or response.css('.job_seen_beacon')
                    
                    if not job_els:
                        print("   🏁 No more results found.")
                        break

                    # 1. Extract basic data from the list
                    found_jobs = []
                    for el in job_els:
                        jk = el.attrib.get('data-jk') or el.css('a::attr(data-jk)').get()
                        if not jk: continue
                        
                        found_jobs.append({
                            "jk": jk,
                            "platform": "Indeed",
                            "title": (el.css('.jobTitle::text').get() or el.css('h2.jobTitle span::text').get() or "N/A").strip(),
                            "company": (el.css('.companyName::text').get() or el.css('[data-testid="company-name"]::text').get() or "N/A").strip(),
                            "location": (el.css('[data-testid="text-location"]::text').get() or "N/A").strip(),
                            "date_posted": (el.css('.date::text').get() or "N/A").strip(),
                            "url": f"{self.base_url}/viewjob?jk={jk}",
                            "scraped_at": datetime.datetime.now(datetime.UTC),
                            "last_seen_at": datetime.datetime.now(datetime.UTC),
                            "metadata": {"query": self.query, "location": self.location}
                        })

                    # 2. PRE-FETCH DEDUPLICATION (Database Check)
                    # We only want to send NEW jobs to the Reader proxies (B & C)
                    all_jks = [j['jk'] for j in found_jobs]
                    existing_jobs = list(self.jobs.find({"jk": {"$in": all_jks}}, {"jk": 1}))
                    existing_jks = {j['jk'] for j in existing_jobs}

                    new_jobs = [j for j in found_jobs if j['jk'] not in existing_jks]
                    
                    # Update 'last_seen' for existing jobs so we know they are still active
                    if existing_jks:
                        self.jobs.update_many(
                            {"jk": {"$in": list(existing_jks)}}, 
                            {"$set": {"last_seen_at": datetime.datetime.now(datetime.UTC)}}
                        )
                        print(f"   [Page {page+1}] {len(existing_jks)} jobs already in DB. Updated 'last_seen' timestamps.")

                    if not new_jobs:
                        print(f"   [Page {page+1}] No NEW jobs to scrape on this page.")
                    else:
                        print(f"   [Page {page+1}] Found {len(new_jobs)} NEW jobs. Distributing to Reader Proxies...")
                        
                        # 3. CONCURRENT EXTRACTION (Using Proxy B and Proxy C)
                        with ThreadPoolExecutor(max_workers=2) as executor:
                            futures = []
                            for i, job in enumerate(new_jobs):
                                # Alternate between Reader 1 (Proxy B) and Reader 2 (Proxy C)
                                engine = self.readers[i % 2]
                                futures.append(executor.submit(self.get_detailed_job, job, engine))
                            
                            final_jobs = [f.result() for f in as_completed(futures)]
                            
                            # 4. Save fully detailed new jobs to Atlas
                            ops = []
                            for j in final_jobs:
                                ops.append(UpdateOne(
                                    {"jk": j["jk"]}, 
                                    {
                                        "$set": j, 
                                        "$setOnInsert": {"first_seen_at": datetime.datetime.now(datetime.UTC)}
                                    }, 
                                    upsert=True
                                ))
                            self.jobs.bulk_write(ops, ordered=False)
                            print(f"   ✅ Saved {len(final_jobs)} new detailed jobs to Atlas.")

                    page += 1
                    # Stealth delay between pages for Proxy A
                    time.sleep(random.uniform(6, 12))
                    
                except Exception as e:
                    print(f"   ❌ Searcher Error on page {page+1}: {e}")
                    break

            if once:
                print(f"\n✅ Search complete (Once-mode). Exiting.")
                break

            print(f"\n😴 Search finished for '{self.query}'. Restarting in 1 hour to find new postings...")
            time.sleep(3600)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tri-Proxy Dedicated Role Scraper")
    parser.add_argument("--query", required=True, help="Job search query")
    parser.add_argument("--location", default="India", help="Search location")
    parser.add_argument("--domain", default="in", help="Indeed domain (e.g., 'in' for India)")
    parser.add_argument("--p-search", help="Proxy for the Searcher (Proxy A)")
    parser.add_argument("--p-read-1", help="Proxy for Reader 1 (Proxy B)")
    parser.add_argument("--p-read-2", help="Proxy for Reader 2 (Proxy C)")
    parser.add_argument("--days", type=int, default=7, help="Filter by date posted (e.g. 7 for last week)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    
    args = parser.parse_args()

    # Fallback to Environment Variables if CLI args are missing
    p_search = args.p_search or os.getenv("PROXY_SEARCH")
    p_read_1 = args.p_read_1 or os.getenv("PROXY_READ_1")
    p_read_2 = args.p_read_2 or os.getenv("PROXY_READ_2")

    # Verify MONGO_URI
    if not MONGO_URI:
        print("❌ Error: MONGO_URI not found. Please set it in your .env file.")
        exit(1)

    scraper = TriProxyIndeedScraper(
        query=args.query, 
        location=args.location, 
        domain=args.domain, 
        p_search=p_search, 
        p_read1=p_read_1, 
        p_read2=p_read_2,
        days=args.days
    )
    
    try:
        scraper.run(once=args.once)
    except KeyboardInterrupt:
        print("\n👋 Scraper stopped by user.")

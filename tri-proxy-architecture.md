# Tri-Proxy Dedicated Role Scraping Architecture

## Objective
Build a standalone, CLI-driven Indeed scraper that utilizes a three-proxy system to maximize stealth, speed, and efficiency. The architecture decouples list-fetching from detail-fetching and implements aggressive pre-fetch database checks to minimize unnecessary scraping.

## Architecture & Roles

1.  **Searcher Engine (Proxy A):**
    *   **Role:** Exclusively responsible for navigating search results (pagination).
    *   **Action:** Fetches the job listing pages (e.g., `/m/jobs?q=...&start=0`) and extracts the basic metadata and the `jk` (Job Key) for each listing.
    *   **Stealth Benefit:** This IP mimics a user browsing through pages without ever clicking into a specific job.

2.  **Reader Engines (Proxies B & C):**
    *   **Role:** Exclusively responsible for fetching job details (description, salary, apply URL).
    *   **Action:** Concurrently visits the specific job pages (e.g., `/m/viewjob?jk=...`) based on the `jk` keys provided by the Searcher.
    *   **Stealth Benefit:** These IPs mimic direct traffic to job postings, keeping their request volume much lower than the Searcher.

## Execution Flow

1.  **Initialization:** The script starts and initializes three separate `scrapling.Fetcher` instances, applying Proxy A to the Searcher and Proxies B & C to the Readers.
2.  **Pagination Fetch:** The Searcher (Proxy A) requests a page of results (e.g., 25 jobs).
3.  **Pre-Fetch Deduplication (Crucial Optimization):**
    *   The script extracts the `jk` keys from the 25 jobs.
    *   It queries MongoDB: `db.jobs.find({"jk": {"$in": [list_of_jks]}})`
    *   **If a job exists:** Its `last_seen_at` timestamp is updated in the database. It is **dropped** from the processing queue.
    *   **If a job is new:** It remains in the queue.
4.  **Concurrent Detail Fetching:**
    *   The remaining *new* jobs (e.g., 5 out of 25) are distributed between Reader 1 (Proxy B) and Reader 2 (Proxy C).
    *   The Readers concurrently fetch the full descriptions and salaries for these new jobs.
5.  **Save to Database:** The fully detailed new jobs are saved to MongoDB using an atomic `upsert`.
6.  **Loop:** The Searcher moves to the next page, and the process repeats.
7.  **Continuous Operation:** Once all pages for a query are exhausted, the script sleeps for a configured duration (e.g., 60 minutes) and restarts from Page 1.

## CLI Usage

The script (`tri_proxy_scraper.py`) will be executed directly on the servers, passing all configuration via command-line arguments:

```bash
python tri_proxy_scraper.py \
  --query "web development" \
  --location "India" \
  --domain "in" \
  --proxy-search "http://user:pass@proxy-a.com" \
  --proxy-read-1 "http://user:pass@proxy-b.com" \
  --proxy-read-2 "http://user:pass@proxy-c.com"
```

## Benefits
*   **Anti-Ban:** Distributes the request footprint across specialized IPs.
*   **Cost-Efficient:** The pre-fetch database check guarantees that expensive proxy bandwidth is only used on genuinely new job postings.
*   **Scalable:** Multiple instances can be launched manually on different servers for different queries without needing a central task queue.
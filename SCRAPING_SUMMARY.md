# Indeed Scraper: Login Wall & Pagination Bypass Summary

This document summarizes the technical strategies and findings from the session regarding bypassing Indeed's anti-bot measures.

## 1. The Challenge
Indeed implements a "Login Wall" that typically appears when a user attempts to navigate beyond the first page of search results (Page 2+). Additionally, Cloudflare protects the site from automated access, often resulting in `403 Forbidden` errors.

## 2. The Strategy: Mobile App Bypass
The primary breakthrough in this session was the **Indeed Mobile App Spoofing** strategy.

### Technical Details:
- **Endpoint:** Instead of the standard `/jobs` URL, we target the mobile-specific `/m/jobs` endpoint.
- **User-Agent Spoofing:** We impersonate the official Indeed Android App by using the User-Agent: `IndeedApp/1.0 (Android; 10; SM-G973F)`.
- **Specialized Headers:** We send headers that the mobile app uses, such as:
    - `X-Requested-With: com.indeed.android.jobsearch`
    - `X-Indeed-App-Version: 165.0`
    - `isapp=1` (URL parameter)

By perfectly mimicking the mobile app, Indeed's servers serve the "Mobile View," which allows for **unlimited pagination** without requiring a login.

## 3. Implementation with Scrapling
We utilized the [Scrapling](https://github.com/D4Vinci/Scrapling) library for its advanced stealth capabilities.

### Fetcher vs. StealthySession:
- **Fetcher (Stealth Mode):** Uses raw HTTP requests via `curl_cffi` to mimic browser TLS fingerprints. This is the **most successful** method because it avoids JavaScript-based fingerprinting.
- **StealthySession (Headed Mode):** Uses a real browser (Playwright). While it can solve CAPTCHAs, it is more easily detected by Indeed's advanced bot-detection algorithms.

## 4. The "Headed Mode" Limitation
**Why Headed Mode still hits the Login Wall:**
Despite using the same mobile headers, Indeed's security system (including Cloudflare and internal fingerprinting) can detect properties of an automated browser (like `navigator.webdriver` or hardware inconsistencies). 

When Indeed detects a **browser** trying to act like a **mobile app**, it flags the session as "suspicious" and forces a redirect to `secure.indeed.com/auth`. This is why:
1. **Stealth Mode (Fetcher)** works for unlimited pagination (it doesn't have a browser fingerprint).
2. **Headed Mode** often fails on Page 2 (its browser fingerprint contradicts its app headers).

## 5. Final Tool: `indeed_pro_scraper.py`
The final script is a robust, single-file solution that supports:
- **Exhaustive Scraping:** Scrapes all available jobs if no limit is set.
- **Hybrid Engine:** Defaults to the ultra-stealthy `Fetcher` but allows `--headed` for visible debugging.
- **Regional Support:** Automatically detects redirects to regional domains like `in.indeed.com`.
- **Auto-Save:** Saves data to `jobs_exhaustive.json` in real-time.

### Usage:
- **Recommended (Stealth):** `python3 indeed_pro_scraper.py -q "Python" -l "Remote" -n 50`
- **Visible Browser:** `python3 indeed_pro_scraper.py -q "Python" -l "Remote" --headed`

## 6. Job Description Extraction
One of the core requirements was to "Click and Copy" the job description.

### Technical Implementation:
- **API Pattern:** We discovered that Scrapling's selector objects require the `.first.get_all_text()` method to accurately capture the full content of `#jobDescriptionText`.
- **Header Switching:** For the detailed `viewjob` page, we use a standard Desktop User-Agent. This is because Indeed's security system is more lenient when a "Browser" visits a "Job Page" than when it visits the "Search Results" page.
- **Iframe Handling:** In desktop-headed mode, Indeed often wraps the description in an iframe (`#vjs-container-iframe`). The `indeed_click_scraper.py` includes specialized logic to switch into these frames for extraction.

---
*Created by Gemini CLI - May 14, 2026*

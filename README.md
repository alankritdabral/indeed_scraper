# Indeed Job Scraper Suite

A powerful, multi-engine scraping solution designed to bypass Indeed's anti-bot protections, login walls, and pagination limits.

## 🚀 Four Scraping Strategies

### 1. Headed App Scraper (`indeed_headed_app_scraper.py`)
**Optimized for: Bypassing login walls while maintaining visibility.**
- **How it works:** Combines the "App View" bypass with a visible browser.
- **Why use it:** Use this if Indeed blocks your headless scrapers with a login wall. It uses mobile app parameters to stay unrestricted.

### 2. Stealth Scraper (`indeed_stealth_scraper.py`)
**Optimized for: High-volume, high-speed background scraping.**
- **How it works:** Mimics the Indeed Android App (Mobile App Bypass) in a headless environment.
- **Speed:** Supports concurrent workers for detail extraction.

### 3. Tri-Proxy Scraper (`tri_proxy_scraper.py`)
**Optimized for: Maximum stealth and distributed load.**
- **How it works:** Uses a three-proxy architecture. Proxy A handles pagination (Searcher), while Proxies B & C handle job detail extraction (Readers).
- **Benefit:** Decouples search from reading to minimize IP footprint and avoid bans.

### 4. Distributed Scraper (`indeed_distributed_scraper.py`)
**Optimized for: Extreme scale and high-volume data collection.**
- **How it works:** Spawns multiple parallel "Sessions", each with its own identity and cookies.
- **Parallel Pagination:** Scrapes multiple pages (e.g., 1, 5, 10) simultaneously.

### 5. Click-Based Scraper (`indeed_click_scraper.py`)
**Optimized for: Desktop view mimicry.**
- **How it works:** Mimics a desktop user by clicking job cards on the split-view layout.

---

## 🛠️ Installation

1. **Clone and Install:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   scrapling install
   ```

---

## 💻 Usage

### Tri-Proxy Scraper (Maximum Stealth)
```bash
python3 tri_proxy_scraper.py \
  --query "Software Engineer" \
  --location "Remote" \
  --domain "in" \
  --p-search "http://user:pass@proxy-a.com" \
  --p-read-1 "http://user:pass@proxy-b.com" \
  --p-read-2 "http://user:pass@proxy-c.com"
```

### Headed App Scraper (Best for Bypassing Login Walls)
```bash
# Scrape 20 jobs using the mobile app view in a visible browser
python3 indeed_headed_app_scraper.py -q "Software Engineer" -l "Remote" -n 20
```

### Distributed Scraper (Maximum Performance)
```bash
# Scrape 20 pages using 4 parallel sessions (5 pages per session)
python3 indeed_distributed_scraper.py -q "Software Engineer" -p 20 -s 4
```

### Stealth Scraper (High Speed Headless)
```bash
# Scrape 100 jobs using 10 parallel workers
python3 indeed_stealth_scraper.py -q "Python Developer" -n 100 -w 10
```

---

## 📊 Data Extracted
Both scrapers provide structured JSON data including:
- **`title`**, **`company`**, **`location`**, **`posted_date`**, **`description`**, **`apply_url`**, **`url`**, **`jk`**.

---

## 📂 Project Structure
- `indeed_headed_app_scraper.py`: Hybrid tool using mobile app view in a headed browser (Best for login bypass).
- `indeed_distributed_scraper.py`: Power tool for multi-session, proxy-enabled scraping.
- `indeed_stealth_scraper.py`: Background tool for standard high-volume scraping.
- `indeed_click_scraper.py`: Interactive tool for desktop-view extraction.
- `SCRAPING_SUMMARY.md`: Technical documentation on bypass strategies.

## ⚠️ Disclaimer
This tool is for educational purposes only. Always respect Indeed's `robots.txt` and Terms of Service.

---
*Maintained by Gemini CLI - May 2026*

# 🚀 Indeed Job Automation Suite

A professional, modular, and high-performance automation suite for Indeed. This project provides a unified interface for scraping job listings, managing a persistent job database, and automating "Easy Apply" applications using advanced stealth browser techniques.

---

## 📁 Project Architecture

The project is organized into a clean `src/` directory to maximize code reuse and maintainability:

```text
.
├── main.py              # 🎛️ Unified CLI Entry Point
├── src/
│   ├── scraper/         
│   │   └── engine.py    # 🕸️ Consolidated Scraper (Headed & Headless)
│   ├── manager.py       # 🗄️ SQLite Database Manager
│   ├── login.py         # 🔑 Session & Authentication Manager
│   ├── applier.py       # ⚡ Auto-Application Automation
│   └── __init__.py
├── jobs_manager.db      # 📊 Persistent SQLite Database
└── indeed_session/      # 🍪 Persistent Browser Profile (Cookies/State)
```

---

## 🛠️ Installation & Setup

### 1. Clone and Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Manual Login (Highly Recommended)
Before running the scraper or applier, log in once manually to save your session. This helps bypass login walls and bot detection.
```bash
python main.py login
```

---

## 📖 CLI Reference & Parameters

The suite is controlled via `main.py` using three primary commands: `login`, `scrape`, and `apply`.

### 1. `scrape` Command
Extracts job listings from Indeed and stores them in the database.

| Parameter | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--query` | `-q` | `"Python Developer"` | The job title or keywords to search for. |
| `--location` | `-l` | `"Remote"` | The geographic location or "Remote". |
| `--limit` | `-n` | `10` | Maximum number of jobs to extract in this session. |
| `--days` | | `None` | Filter for jobs posted within the last X days (e.g., `--days 7`). |
| `--headed` | | `False` | Run with a visible browser window (Headless by default). |
| `--db` | | `True` | Save extracted jobs to the SQLite database. |

**Example:**
```bash
# Scrape 20 "Data Scientist" jobs from the last 7 days in Headless mode
python main.py scrape -q "Data Scientist" -l "United States" -n 20 --days 7
```

### 2. `apply` Command
Automates the application process for jobs marked as "Easy Apply" in your database.

| Parameter | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--limit` | `-n` | `5` | Maximum number of applications to attempt. |
| `--headed` | | `False` | Run with a visible window (Recommended for monitoring automation). |

**Example:**
```bash
# Attempt to apply to 10 jobs using a visible browser
python main.py apply --limit 10 --headed
```

### 3. `login` Command
Opens a persistent browser session for you to log in to Indeed. This session is reused by all other commands.

---

## 💡 Advanced Configuration

### Customizing Application Answers
You can pre-configure your default answers for common application questions (experience, salary, etc.) by editing the `AutoApplier` class in `src/applier.py`:

```python
# src/applier.py
self.answers = {
    "experience": "5",
    "authorized": True,
    "sponsorship": False,
    "education": "Bachelor's Degree",
    "salary": "100000",
}
```

---

## 📊 Database Schema
The suite uses a `jobs_manager.db` SQLite database to track every job and prevent duplicate applications.
- **Statuses:** `Pending`, `Applied`, `Skipped`.
- **Easy Apply Tracking:** Automatically identifies and prioritizes Indeed Easy Apply listings.

---

## ✅ Validation Status
The current version has been verified with:
- [x] Multi-page pagination (scraped 20+ jobs across multiple pages).
- [x] Database conflict resolution (skips duplicates automatically).
- [x] Parameter validation (headed/headless, limit, days filter).
- [x] Modular import integrity.

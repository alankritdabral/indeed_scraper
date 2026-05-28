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
| `--easy-apply`| | `False` | Only scrape jobs that have the "Easily apply" label. |

**Example:**
```bash
# Scrape 20 "Data Scientist" jobs with "Easy Apply" filter in Headed mode
python main.py scrape -q "Data Scientist" -l "United States" -n 20 --easy-apply --headed
```

### 2. `apply` Command
Automates the application process for jobs marked as "Easy Apply" in your database.

| Parameter | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--limit` | `-n` | `5` | Maximum number of applications to attempt. |
| `--headed` | | `False` | Run with a visible window (Required for CAPTCHA solving). |

**Example:**
```bash
# Attempt to apply to 10 jobs using a visible browser
python main.py apply --limit 10 --headed
```

### 3. `continuous` Command
Loops scraping and applying phases indefinitely.

| Parameter | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--query` | `-q` | `"Python Developer"` | Search keywords for the scraping phase. |
| `--location` | `-l` | `"Remote"` | Location for the scraping phase. |
| `--limit` | `-n` | `10` | Batch size for each scrape/apply cycle. |
| `--headed` | | `False` | Run with a visible window (Satisfies "don't close browser" rule). |
| `--easy-apply`| | `False` | Filter for "Easy Apply" jobs during the scraping phase. |

**Example:**
```bash
# Run indefinitely with session persistence and visible browser
python main.py continuous -q "Python Developer" -l "India" --easy-apply --headed
```

### 4. `login` Command

Opens a persistent browser session for you to log in to Indeed. This session is reused by all other commands.

---

## 🤖 Advanced Automation Features

### 1. Manual CAPTCHA Handling
The suite includes a smart pause mechanism for CAPTCHAs. If an Indeed "Easy Apply" form triggers a bot challenge:
- The terminal will display: `🚨 ACTION REQUIRED: Please solve the CAPTCHA in the browser window.`
- The script **pauses** all automation.
- You solve the CAPTCHA manually in the headed browser.
- Press **ENTER** in the terminal to resume automation.

### 2. Session & Tab Persistence
To satisfy the "don't close the browser" rule:
- **Shared Session:** In `continuous` mode, the same browser session is shared between scraping and applying.
- **Persistent Tabs:** During the application phase, the script opens a new tab for every job and **keeps them open** after submission for your final review.
- **Headless Compatibility:** All features except manual CAPTCHA solving work in headless mode.

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
- [x] **Session Persistence:** Browser stays open across scraping/applying in continuous mode.
- [x] **Tab Management:** Opens and keeps tabs for each job application.
- [x] **Manual CAPTCHA:** Successfully pauses and resumes for bot challenges.
- [x] **Easy Apply Filter:** Scraper accurately filters for "Easily apply" jobs.
- [x] **Pagination:** Multi-page scraping and duplicate conflict resolution.
- [x] **Headless/Headed:** Seamless transition between modes.

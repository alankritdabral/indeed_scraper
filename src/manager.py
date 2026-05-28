import sqlite3
from datetime import datetime

class JobDatabase:
    def __init__(self, db_path="jobs_manager.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    jk TEXT PRIMARY KEY,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    description TEXT,
                    apply_url TEXT,
                    source_url TEXT,
                    is_easy_apply INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'Pending',
                    scraped_date TEXT,
                    applied_date TEXT,
                    notes TEXT
                )
            ''')
            conn.commit()

    def add_job(self, job_dict):
        """Adds or updates a job in the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO jobs (jk, title, company, location, description, apply_url, source_url, is_easy_apply, scraped_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(jk) DO UPDATE SET
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    description=excluded.description,
                    apply_url=excluded.apply_url,
                    is_easy_apply=excluded.is_easy_apply
            ''', (
                job_dict.get('jk'),
                job_dict.get('title'),
                job_dict.get('company'),
                job_dict.get('location'),
                job_dict.get('description'),
                job_dict.get('apply_url'),
                job_dict.get('url'),
                1 if job_dict.get('is_easy_apply') else 0,
                datetime.now().isoformat()
            ))
            conn.commit()

    def get_pending_jobs(self, easy_apply_only=False):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if easy_apply_only:
                cursor.execute("SELECT * FROM jobs WHERE status = 'Pending' AND is_easy_apply = 1 ORDER BY scraped_date DESC")
            else:
                cursor.execute("SELECT * FROM jobs WHERE status = 'Pending' ORDER BY scraped_date DESC")
            return [dict(row) for row in cursor.fetchall()]

    def update_job_status(self, jk, status='Applied', notes=""):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs 
                SET status = ?, applied_date = ?, notes = ?
                WHERE jk = ?
            ''', (status, datetime.now().isoformat(), notes, jk))
            conn.commit()

    def mark_as_applied(self, jk, notes=""):
        self.update_job_status(jk, status='Applied', notes=notes)

if __name__ == "__main__":
    db = JobDatabase()
    print("✅ Job database initialized.")
    pending = db.get_pending_jobs()
    print(f"📊 Current pending jobs: {len(pending)}")

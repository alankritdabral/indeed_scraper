import time
import random
import re
import os
import json
from scrapling.fetchers import StealthySession

from src.manager import JobDatabase

class AutoApplier:
    """
    AutoApplier: A template script to automate the application process.
    """
    def __init__(self, headless=False):
        self.db = JobDatabase()
        self.headless = headless
        # USER CONFIGURATION: Default answers for common questions
        self.answers = {
            "experience": "5",
            "authorized": True,
            "sponsorship": False,
            "education": "Bachelor's Degree",
            "salary": "100000",
            "notice_period": "Immediate",
            "default_text": "5"
        }

    def _answer_questions(self, page):
        """Attempts to find and answer common questions on the current page."""
        try:
            # 1. Handle Numeric / Text Inputs
            inputs = page.locator("input[type='text'], input[type='number'], textarea").all()
            for input_el in inputs:
                try:
                    if not input_el.is_visible() or input_el.input_value():
                        continue
                    
                    label_text = ""
                    id_attr = input_el.get_attribute("id")
                    if id_attr:
                        label = page.locator(f"label[for='{id_attr}']")
                        if label.count() > 0:
                            label_text = label.inner_text().lower()
                    
                    if not label_text:
                        label_text = input_el.evaluate("el => el.parentElement.innerText").lower()

                    if "experience" in label_text or "years" in label_text:
                        print(f"  📝 Answering numeric: '{label_text.strip()[:30]}...' -> {self.answers['experience']}")
                        input_el.fill(self.answers["experience"])
                    elif "salary" in label_text or "expectation" in label_text:
                        input_el.fill(self.answers["salary"])
                    elif "notice" in label_text:
                        input_el.fill(self.answers["notice_period"])
                    elif input_el.get_attribute("type") == "number":
                        input_el.fill(self.answers["default_text"])
                except: continue

            # 2. Handle Radio Buttons (Yes/No)
            radio_groups = page.locator("fieldset").all()
            for group in radio_groups:
                try:
                    legend = group.locator("legend").first
                    if legend.count() > 0:
                        text = legend.inner_text().lower()
                        target_answer = None
                        if "authorized" in text or "permit" in text:
                            target_answer = "Yes" if self.answers["authorized"] else "No"
                        elif "sponsorship" in text or "visa" in text:
                            target_answer = "No" if not self.answers["sponsorship"] else "Yes"
                        elif "background check" in text:
                            target_answer = "Yes"
                        elif "education" in text or "degree" in text or "graduated" in text:
                            target_answer = "Yes"

                        if target_answer:
                            option = group.locator(f"label:has-text('{target_answer}')")
                            if option.count() > 0:
                                print(f"  🔘 Selecting radio: '{text.strip()[:30]}...' -> {target_answer}")
                                option.click()
                except: continue

            # 3. Handle Select Dropdowns
            selects = page.locator("select").all()
            for sel in selects:
                try:
                    if sel.input_value() and sel.input_value() != "0":
                        continue
                    sel.select_option(index=1)
                except: continue

        except Exception as e:
            print(f"  ⚠️ Error answering questions: {e}")

    def run(self, limit=10):
        jobs = self.db.get_pending_jobs(easy_apply_only=True)
        if not jobs:
            print("📭 No verified Easy Apply jobs found in database.")
            return

        print(f"🚀 Starting automation for {len(jobs[:limit])} verified Easy Apply jobs...")
        
        session_dir = "indeed_session"
        self.session = StealthySession(headless=self.headless, user_data_dir=session_dir)
        self.session.start()
        
        count = 0
        for job in jobs:
            if count >= limit: break
            
            apply_url = job.get('apply_url')
            print(f"\n⚡ Processing: {job['title']} at {job['company']}")
            
            try:
                page = self.session.context.new_page()
                page.set_default_timeout(60000)
                page.goto(apply_url, wait_until="domcontentloaded")
                
                if "indeed.com" not in page.url:
                    print(f"  ⏭️ Redirected to external site ({page.url.split('/')[2]}). Skipping.")
                    page.close()
                    continue

                print("  ✅ Proceeding with automated application...")
                success = self._fill_indeed_apply(page)
                if success:
                    self.db.mark_as_applied(job['jk'], notes="Automated application submitted.")
                    print(f"  🎉 SUCCESS: Applied for {job['jk']}")
                else:
                    print(f"  ⚠️ STUCK: Form requires manual input.")

                time.sleep(random.uniform(1, 2))
                page.close()
                count += 1
                
            except Exception as e:
                print(f"  ❌ Screening Error: {e}")
                try: page.close()
                except: pass

        self.session.close()

    def _fill_indeed_apply(self, page):
        max_steps = 15
        for step in range(max_steps):
            try:
                self._answer_questions(page)
                time.sleep(1)

                submit_button = page.get_by_role("button", name=re.compile("submit your application", re.IGNORECASE))
                if submit_button.is_visible():
                    print("🚀 Clicking final 'Submit Application' button...")
                    submit_button.click()
                    time.sleep(5)
                    return True

                review_button = page.get_by_role("button", name=re.compile("review your application", re.IGNORECASE))
                if review_button.is_visible():
                    print("🧐 Clicking 'Review' button...")
                    review_button.click()
                    time.sleep(2)
                    continue

                continue_button = page.get_by_role("button", name=re.compile("continue|next", re.IGNORECASE)).first
                if continue_button.is_visible():
                    print(f"➡️ Step {step+1}: Clicking 'Continue'...")
                    continue_button.click()
                    time.sleep(2)
                    continue
                
                if "post-apply" in page.url or page.locator("text=Application submitted").count() > 0:
                    print("🎉 Application appears to be submitted successfully!")
                    return True

                print("🛑 Stuck? No 'Continue' button found. It might be asking for specific info/questions.")
                return False

            except Exception as e:
                print(f"⚠️ Error during step {step}: {e}")
                return False
        
        return False

if __name__ == "__main__":
    applier = AutoApplier(headless=False) 
    applier.run(limit=5)

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
    def __init__(self, headless=False, session=None):
        self.db = JobDatabase()
        self.headless = headless                                                        
        if session:
            self.session = session
            self._session_owned = False
        else:                                                                                                                                                                   
            self.session = None
            self._session_owned = True

        # USER CONFIGURATION: Default answers for common questions
        self.answers = {
            "experience": "10",
            "authorized": True,
            "sponsorship": False,
            "education": "Bachelor's Degree",
            "salary": "120000",
            "notice_period": "Immediate",
            "default_text": "10"
        }

    def _check_for_captcha(self, target):
        """Checks if a captcha or 'I am not a robot' challenge is present."""
        captcha_indicators = [
            "iframe[src*='captcha']",
            "iframe[src*='hcaptcha']",
            "iframe[src*='recaptcha']",
            "div.g-recaptcha",
            "#captcha-container",
            "text=Verify you are human",
            "text=hCaptcha",
        ]
        for selector in captcha_indicators:
            try:
                if target.locator(selector).first.is_visible():
                    return True
            except: continue
        return False

    def _get_progress(self, target):
        """Attempts to extract the current progress percentage."""
        try:
            progress_bar = target.locator("div[role='progressbar']").first
            if progress_bar.count() > 0:
                val = progress_bar.get_attribute("aria-valuenow")
                if val:
                    return int(val)
        except: pass
        return 0

    def _human_scroll(self, page, element):
        """Scrolls to an element using the mouse wheel instead of JavaScript jumps."""
        try:
            # Get target's position
            box = element.bounding_box()
            if not box:
                return
            
            # Current viewport scroll position is harder to get without JS, 
            # but we can scroll in chunks until the element is in a good spot
            max_scrolls = 10
            for _ in range(max_scrolls):
                box = element.bounding_box()
                if not box: break
                
                # If element is within a comfortable middle range of the viewport
                viewport_height = page.viewport_size['height']
                if 100 < box['y'] < viewport_height - 200:
                    break
                
                # Calculate scroll amount with some momentum
                scroll_amount = (box['y'] - 200) 
                # Break it into chunks to simulate wheel turns
                chunks = random.randint(3, 6)
                for _ in range(chunks):
                    step = (scroll_amount / chunks) + random.uniform(-10, 10)
                    page.mouse.wheel(0, step)
                    time.sleep(random.uniform(0.05, 0.15))
                
                time.sleep(random.uniform(0.2, 0.4))
        except:
            element.scroll_into_view_if_needed()

    def _human_type(self, target, element, text):
        """Types text like a human using physical keyboard events."""
        try:
            # 1. Scroll and Click to focus
            page = self.session.context.pages[-1] if hasattr(self, 'session') else None
            if page:
                self._human_scroll(page, element)
            
            self._human_click(target, element)
            time.sleep(random.uniform(0.2, 0.5))

            # 2. Clear field using physical keys (Ctrl+A -> Backspace)
            # This is much more stealthy than .fill("")
            modifier = "Control" # Standard for Linux/Windows in Playwright
            page.keyboard.down(modifier)
            page.keyboard.press("a")
            page.keyboard.up(modifier)
            time.sleep(random.uniform(0.1, 0.2))
            page.keyboard.press("Backspace")
            time.sleep(random.uniform(0.2, 0.4))

            # 3. Type sequentially
            print(f"    ⌨️ Physical Typing: '{text}'...")
            for char in text:
                page.keyboard.type(char, delay=random.randint(40, 120))
                # Occasional tiny pause between words
                if char == ' ':
                    time.sleep(random.uniform(0.1, 0.2))
            
            time.sleep(random.uniform(0.3, 0.6))
        except Exception as e:
            print(f"  ⚠️ Physical type failed: {e}")
            try: element.fill(text)
            except: pass

    def _human_click(self, target, element):
        """Moves mouse to element and clicks it using physical events."""
        try:
            # We need the page for the mouse
            page = None
            if hasattr(target, 'mouse'): # It's a Page
                page = target
            elif hasattr(self, 'session') and self.session and self.session.context.pages:
                page = self.session.context.pages[-1]

            if page:
                # Ensure it's in view first
                # self._human_scroll(page, element) # Avoid recursion if called from type
                
                box = element.bounding_box()
                if box:
                    # Target point with jitter
                    target_x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
                    target_y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
                    
                    # Move mouse in steps to simulate curve (simplified)
                    page.mouse.move(target_x, target_y, steps=random.randint(10, 20))
                    time.sleep(random.uniform(0.1, 0.2))
                    page.mouse.click(target_x, target_y, delay=random.randint(50, 150))
                    return

            # Fallback
            element.click(delay=random.randint(50, 150))
        except Exception as e:
            print(f"  ⚠️ Human click failed: {e}")
            try: element.click(force=True)
            except: pass

    def _answer_questions(self, target):
        """Attempts to find and answer common questions on the current page/frame."""
        try:
            # 1. Handle Numeric / Text Inputs
            inputs = target.locator("input[type='text'], input[type='number'], textarea").all()
            for input_el in inputs:
                try:
                    if not input_el.is_visible() or input_el.input_value():
                        continue
                    
                    label_text = ""
                    id_attr = input_el.get_attribute("id")
                    if id_attr:
                        label = target.locator(f"label[for='{id_attr}']")
                        if label.count() > 0:
                            label_text = label.inner_text().lower()
                    
                    if not label_text:
                        label_text = input_el.evaluate("el => el.parentElement.innerText").lower()

                    answer = None
                    if any(x in label_text for x in ["experience", "years", "how long"]):
                        answer = self.answers["experience"]
                    elif "salary" in label_text or "expectation" in label_text:
                        answer = self.answers["salary"]
                    elif "notice" in label_text:
                        answer = self.answers["notice_period"]
                    elif any(x in label_text for x in ["visa", "sponsorship", "authorized", "permit", "legal"]):
                        answer = "Yes"
                    elif "job title" in label_text or "position" in label_text:
                        answer = "Python Developer"
                    elif "company" in label_text or "employer" in label_text:
                        answer = "Freelance"
                    elif input_el.get_attribute("type") == "number":
                        answer = self.answers["default_text"]

                    if answer:
                        print(f"  📝 Answering numeric/text: '{label_text.strip()[:30]}...' -> {answer}")
                        self._human_type(target, input_el, answer)
                        time.sleep(random.uniform(0.5, 1.5))
                except: continue

            # 2. Handle Radio Buttons (Yes/No)
            radios = target.locator("input[type='radio']").all()
            handled_names = set()
            for radio in radios:
                try:
                    name = radio.get_attribute("name")
                    if not name or name in handled_names:
                        continue
                    
                    # Find the question container
                    container = target.locator(f"div:has(> input[name='{name}']), fieldset:has(input[name='{name}'])").first
                    if container.count() == 0:
                        container = radio.evaluate_handle("el => el.parentElement.parentElement")
                    
                    options_elements = target.locator(f"div:has(> input[name='{name}']), label:has(input[name='{name}'])").all()
                    
                    # If it's a Yes/No question, always select Yes
                    found_yes = False
                    for opt in options_elements:
                        opt_text = opt.inner_text().lower()
                        if "yes" == opt_text.strip() or "yes" in opt_text:
                            print(f"  🔘 Selecting radio: 'Yes' (Yes/No group detected)")
                            self._human_click(target, opt)
                            handled_names.add(name)
                            found_yes = True
                            time.sleep(random.uniform(0.3, 0.8))
                            break
                    if found_yes: continue

                    # Fallback for other radio groups (not explicitly Yes/No)
                    text = container.evaluate("el => el.innerText").lower()
                    if len(text) < 10:
                        id_attr = container.get_attribute("id")
                        if id_attr:
                            label = target.locator(f"label[for*='{id_attr.split(':')[0]}']").first
                            if label.count() > 0:
                                text = label.inner_text().lower()

                    target_answer = None
                    if any(x in text for x in ["authorized", "permit", "legal", "background check", "drug", "education", "degree", "graduated", "high school"]):
                        target_answer = "Yes"
                    elif any(x in text for x in ["sponsorship", "visa", "future"]):
                        target_answer = "Yes" # Overriding for user rule

                    if target_answer:
                        for opt in options_elements:
                            if target_answer.lower() in opt.inner_text().lower():
                                print(f"  🔘 Selecting radio: '{text.strip()[:30]}...' -> {target_answer}")
                                self._human_click(target, opt)
                                handled_names.add(name)
                                time.sleep(random.uniform(0.3, 0.8))
                                break
                except: continue

            # 3. Handle Select Dropdowns
            selects = target.locator("select").all()
            for sel in selects:
                try:
                    if sel.input_value() and sel.input_value() != "0" and sel.input_value() != "":
                        continue
                    
                    label_text = ""
                    id_attr = sel.get_attribute("id")
                    if id_attr:
                        label = target.locator(f"label[for='{id_attr}']")
                        if label.count() > 0:
                            label_text = label.inner_text().lower()
                    if not label_text:
                        label_text = sel.evaluate("el => el.parentElement.innerText").lower()

                    time.sleep(random.uniform(0.5, 1.0))
                    if any(x in label_text for x in ["authorized", "permit", "legal"]):
                        try: sel.select_option(label="Yes")
                        except: sel.select_option(index=1)
                    elif any(x in label_text for x in ["sponsorship", "visa", "future"]):
                        try: sel.select_option(label="No")
                        except: sel.select_option(index=1)
                    else:
                        sel.select_option(index=1)
                    
                    sel.dispatch_event("change")
                    time.sleep(random.uniform(0.2, 0.5))
                except: continue

        except Exception as e:
            print(f"  ⚠️ Error answering questions: {e}")

    def _handle_captcha(self, target, job_jk):
        """Pauses execution and waits for the user to solve the captcha."""
        print(f"\n  🤖 CAPTCHA DETECTED for {job_jk}!")
        if self.headless:
            print("  ⚠️ You are running in HEADLESS mode. You cannot solve the captcha manually.")
            print("  ⚠️ Please run with '--headed' to solve captchas.")
            return False
        
        print("  🚨 ACTION REQUIRED: Please solve the CAPTCHA in the browser window.")
        print("  ⏳ The script is PAUSED. Once you have solved the captcha and reached the next step (or submitted),")
        print("  ⏳ press ENTER in this terminal to resume automation.")
        input("  [Press ENTER to resume after solving]")
        print("  ▶️ Resuming...")
        return True

    def run(self, limit=10):
        jobs = self.db.get_pending_jobs(easy_apply_only=True)
        if not jobs:
            print("📭 No verified Easy Apply jobs found in database.")
            return

        print(f"🚀 Starting automation for {len(jobs[:limit])} verified Easy Apply jobs...")
        
        session_dir = "indeed_session"
        if not hasattr(self, 'session') or self.session is None:
            self.session = StealthySession(headless=self.headless, user_data_dir=session_dir)
            self.session.start()
        
        count = 0
        for job in jobs:
            if count >= limit: break
            
            apply_url = job.get('apply_url')
            print(f"\n⚡ Processing: {job['title']} at {job['company']}")
            
            try:
                # Open a new tab for each job as requested
                page = self.session.context.new_page()
                page.set_default_timeout(60000)
                page.goto(apply_url, wait_until="domcontentloaded")
                
                if "indeed.com" not in page.url:
                    print(f"  ⏭️ Redirected to external site ({page.url.split('/')[2]}). Skipping.")
                    self.db.update_job_status(job['jk'], status='Skipped', notes=f"Redirected to {page.url.split('/')[2]}")
                    # We can close this page since we didn't apply
                    page.close()
                    continue

                print("  ✅ Proceeding with automated application...")
                result, current_page = self._fill_indeed_apply(page, job['jk'])
                
                if result == "SUCCESS":
                    self.db.mark_as_applied(job['jk'], notes="Automated application submitted.")
                    print(f"  🎉 SUCCESS: Applied for {job['jk']}")
                    count += 1
                elif result == "SKIP":
                    self.db.update_job_status(job['jk'], status='Skipped', notes="Skipped due to high completion captcha.")
                    print(f"  ⏭️ SKIPPED: {job['jk']}")
                    current_page.close() # Close if we skipped
                elif result == "STUCK":
                    self.db.update_job_status(job['jk'], status='Manual', notes="Stuck during automated filling. Review stuck_pages/.")
                    print(f"  ⚠️ STUCK: {job['jk']}")
                else:
                    self.db.update_job_status(job['jk'], status='Error', notes=f"Error: {result}")
                    print(f"  ❌ ERROR: {job['jk']}")

                time.sleep(random.uniform(2, 5))
                # Note: We DON'T close the current_page here to keep it open as requested
                
            except Exception as e:
                print(f"  ❌ Application Loop Error: {e}")

        # In standard 'run', we still close the session at the end.
        # But for continuous mode, we might want to keep it.
        # If the user is running a single batch, closing is fine.
        if self._session_owned:
            self.session.close()

    def _save_stuck_state(self, target_obj, job_jk, step):
        """Saves page HTML, screenshot, and a summary of form elements for manual analysis."""
        os.makedirs("stuck_pages", exist_ok=True)
        timestamp = int(time.time())
        filename_base = f"stuck_pages/{job_jk}_step{step}_{timestamp}"
        
        # Determine the actual page object if target_obj is a frame
        page = target_obj if hasattr(target_obj, 'screenshot') else target_obj._page if hasattr(target_obj, '_page') else None
        
        try:
            content = target_obj.evaluate("() => document.documentElement.outerHTML") if hasattr(target_obj, 'evaluate') else ""
            with open(f"{filename_base}.html", "w", encoding="utf-8") as f:
                f.write(content)
        except: pass

        if page:
            try:
                page.screenshot(path=f"{filename_base}.png", timeout=5000, animations="disabled")
            except: pass
        
        try:
            errors = target_obj.locator(".icl-TextInput-error, .ia-ScreenerQuestions-error, [role='alert'], .ia-ErrorBanner").all()
            err_msgs = [e.inner_text().strip() for e in errors if e.is_visible()]
            summary = {"errors": err_msgs, "elements": []}
            inputs = target_obj.locator("input, select, textarea, fieldset").all()
            for i, el in enumerate(inputs):
                try:
                    if not el.is_visible(): continue
                    summary["elements"].append({
                        "index": i,
                        "tag": el.evaluate("el => el.tagName").lower(),
                        "type": el.get_attribute("type") or "N/A",
                        "name": el.get_attribute("name") or "N/A",
                        "id": el.get_attribute("id") or "N/A",
                        "label": el.evaluate("el => el.parentElement.innerText").strip().split('\n')[0]
                    })
                except: continue
            with open(f"{filename_base}_summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=4)
            print(f"  📸 Stuck state saved: {filename_base}.png/html/json")
        except: pass

    def _fill_indeed_apply(self, page, job_jk):
        max_steps = 25
        last_url = ""
        last_content_hash = 0
        target = page # Default target
        
        for step in range(max_steps):
            try:
                if "challenge-platform" in page.content():
                    print("  🛡️ Cloudflare challenge detected. Waiting...")
                    time.sleep(5)

                # Check for "Already applied" indicators
                already_applied_indicators = [
                    "text=You have already applied",
                    "text=Applied on",
                    ".jobsearch-JobComponent-description--applied",
                    "text=Application submitted",
                    "text=You've already applied",
                    "button:has-text('Applied')",
                    "button[disabled]:has-text('Applied')"
                ]
                for selector in already_applied_indicators:
                    try:
                        if page.locator(selector).first.is_visible():
                            print(f"  ✅ Already applied to this job (found '{selector}'). Marking as SUCCESS.")
                            return "SUCCESS", page
                    except: continue

                # Check for "Resume Mismatch" or other interventions
                intervention_indicators = [
                    "text=Resume Mismatch",
                    "text=Missing info",
                    "text=Help us improve your application",
                    "text=mismatch",
                    "text=missing info"
                ]
                for selector in intervention_indicators:
                    try:
                        if page.locator(selector).first.count() > 0:
                            print(f"  ⚠️ Intervention detected: '{selector}'. Attempting to bypass...")
                            bypass_selectors = [
                                "button:has-text('Continue')", 
                                "button:has-text('Next')", 
                                "button:has-text('Acknowledge')",
                                "button:has-text('with Indeed Resume')",
                                "button:has-text('with my resume')"
                            ]
                            for b_sel in bypass_selectors:
                                btn = page.locator(b_sel).first
                                if btn.count() > 0 and btn.is_visible():
                                    print(f"  🖱️ Clicking bypass button: '{btn.inner_text().strip()}'")
                                    btn.click(force=True)
                                    time.sleep(3)
                                    break
                    except: continue

                if "/viewjob" in page.url or "/job/" in page.url:
                    apply_button = page.locator("#indeedApplyButton, .jobsearch-IndeedApplyButton button").first
                    if apply_button.count() > 0 and apply_button.is_visible():
                        print("  🖱️ On job page. Clicking 'Apply with Indeed' button...")
                        try:
                            # Move mouse to button first
                            self._human_click(page, apply_button)
                            with page.context.expect_page(timeout=5000) as popup_info:
                                # The click is already done by _human_click, but we might need to click again if it didn't trigger popup
                                # Actually, _human_click already clicks. Let's wrap it.
                                pass
                            page = popup_info.value
                            page.wait_for_load_state()
                            print(f"  🆕 Popup opened: {page.url}")
                        except:
                            print("  ℹ️ No popup detected. Continuing on main page...")
                            time.sleep(3)
                        continue
                
                apply_iframe = page.frame_locator('iframe[title="Job application"], iframe[src*="indeed.com/apply"]')
                if apply_iframe.locator("button").count() > 0:
                    print("  🖼️ Detected application form in iframe.")
                    target = apply_iframe
                else:
                    target = page

                # Check for loading spinners
                spinner_selectors = [
                    "svg title:has-text('loading')", 
                    ".ia-Spinner", 
                    "svg title:has-text('Saving')",
                    "svg title:has-text('continuing')",
                    "[data-testid*='spinner']"
                ]
                found_spinner = False
                for sel in spinner_selectors:
                    try:
                        if target.locator(sel).count() > 0:
                            found_spinner = True
                            break
                    except: continue
                
                if found_spinner:
                    print("  ⏳ Page is loading (spinner detected). Waiting...")
                    time.sleep(5)
                    # Don't increment step if we are just waiting for loading
                    if step > 0: step -= 1
                    continue

                if self._check_for_captcha(target):
                    progress = self._get_progress(target)
                    print(f"  🤖 Captcha detected! (Progress: {progress}%)")
                    if self._handle_captcha(target, job_jk):
                        # After handling, we continue the loop to check the state again
                        continue
                    else:
                        if progress >= 90:
                            print("  ⏭️ High completion with captcha but couldn't handle. Skipping job.")
                            return "SKIP", page
                        else:
                            print("  🛑 Captcha block but couldn't handle. Manual intervention needed.")
                            return "STUCK", page

                current_url = page.url
                # Focus on a larger part of content for hash
                content_for_hash = page.content() if not hasattr(target, 'evaluate') else target.evaluate("() => document.body.innerText")
                current_content_hash = hash(content_for_hash)
                
                if current_url == last_url and current_content_hash == last_content_hash:
                    if step > 5:
                        print(f"  ⚠️ Content hasn't changed. Bail at step {step+1}.")
                        self._save_stuck_state(target, job_jk, step+1)
                        return "STUCK", page
                
                last_url = current_url
                last_content_hash = current_content_hash

                self._answer_questions(target)
                time.sleep(random.uniform(1.0, 2.0))

                progression_button = None
                submit_selectors = ["button:has-text('Submit')", "button[type='submit']", "text=Submit your application"]
                for sel in submit_selectors:
                    btn = target.locator(sel).first
                    if btn.count() > 0 and btn.is_visible():
                        progression_button = btn
                        print(f"🚀 Found Submit button: '{btn.inner_text().strip()}'")
                        break
                
                if not progression_button:
                    review_selectors = ["button:has-text('Review')", "text=Review your application"]
                    for sel in review_selectors:
                        btn = target.locator(sel).first
                        if btn.count() > 0 and btn.is_visible():
                            progression_button = btn
                            print(f"🧐 Found Review button: '{btn.inner_text().strip()}'")
                            break

                if not progression_button:
                    continue_selectors = [
                        "button:has-text('Continue')", "button:has-text('Next')", 
                        "button:has-text('Save and continue')", ".ia-continue-button",
                        "button[data-testid='continue-button']", "button:has-text('Apply')",
                        "button:has-text('Submit')"
                    ]
                    for sel in continue_selectors:
                        btn = target.locator(sel).first
                        if btn.count() > 0 and btn.is_visible():
                            progression_button = btn
                            print(f"➡️ Step {step+1}: Found '{btn.inner_text().strip()}' button.")
                            break

                if progression_button:
                    # Add a "review" delay if this is a high-stakes button
                    button_text = progression_button.inner_text().lower()
                    if any(x in button_text for x in ["submit", "review"]):
                        delay = random.uniform(3.0, 8.0)
                        print(f"  🧐 Simulating review of application... ({delay:.1f}s)")
                        time.sleep(delay)
                    
                    try:
                        self._human_click(target, progression_button)
                    except:
                        print(f"  🖱️ Human click failed, retrying with standard click...")
                        progression_button.click(timeout=10000)
                    
                    time.sleep(random.uniform(4, 6))
                    if "post-apply" in page.url or target.locator("text=Application submitted").count() > 0 or target.locator("text=Turn on recommended jobs").count() > 0:
                        return "SUCCESS", page
                    continue
                
                if "post-apply" in page.url or target.locator("text=Application submitted").count() > 0 or target.locator("text=Turn on recommended jobs").count() > 0:
                    print("🎉 Application appears to be submitted successfully!")
                    return "SUCCESS", page

                print(f"🛑 Stuck? No progression button found at step {step+1}.")
                self._save_stuck_state(target, job_jk, step+1)
                return "STUCK", page

            except Exception as e:
                if "expect_page" in str(e): pass
                else:
                    print(f"⚠️ Error during step {step+1}: {e}")
                    self._save_stuck_state(page, job_jk, step+1)
                    return "ERROR", page
        
        return "STUCK", page

if __name__ == "__main__":
    applier = AutoApplier(headless=False) 
    applier.run(limit=5)

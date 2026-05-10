import logging
import re
import random
import asyncio
from typing import List, Optional
from playwright.async_api import Page

from ..models.post import Post
from ..callbacks import ProgressCallback, SilentCallback
from ..core import human_scroll, human_click, random_mouse_move
from .base import BaseScraper

logger = logging.getLogger(__name__)


class CompanyPostsScraper(BaseScraper):
    
    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        super().__init__(page, callback or SilentCallback())
        self.on_post_extracted = None
        self._stats = {
            "liked": 0,
            "profile_visits": 0,
            "total_extracted": 0
        }
    
    async def scrape(self, company_url: str, limit: int = 10) -> List[Post]:
        logger.info(f"Starting company posts scraping: {company_url}")
        await self.callback.on_start("company_posts", company_url)
        
        posts_url = self._build_posts_url(company_url)
        await self.navigate_and_wait(posts_url)
        await self.callback.on_progress("Navigated to posts page", 10)
        
        await self.check_rate_limit()
        
        await self._wait_for_posts_to_load()
        await self.callback.on_progress("Posts loaded", 20)
        
        posts = await self._scrape_posts(limit)
        await self.callback.on_progress(f"Scraped {len(posts)} posts", 100)
        await self.callback.on_complete("company_posts", posts)
        
        logger.info(f"Successfully scraped {len(posts)} posts")
        return posts
    
    def _build_posts_url(self, company_url: str) -> str:
        company_url = company_url.rstrip('/')
        if '/posts' not in company_url:
            return f"{company_url}/posts/"
        return company_url
    
    async def _wait_for_posts_to_load(self, timeout: int = 30000) -> None:
        try:
            # Wait for any post container or search result container
            await self.page.wait_for_selector('[role="listitem"], .feed-shared-update-v2, .reusable-search__result-container, .update-components-actor__name', timeout=timeout)
        except Exception as e:
            logger.debug(f"Selector wait timeout: {e}")
        
        await self.page.wait_for_timeout(random.randint(2000, 5000))
        
        for attempt in range(5):
            # More robust check for posts in the DOM
            has_posts = await self.page.evaluate('''() => {
                const selectors = ['[role="listitem"]', '.feed-shared-update-v2', '.reusable-search__result-container', '[data-urn*="activity"]', '.update-components-actor__name'];
                return selectors.some(s => document.querySelector(s));
            }''')
            
            if has_posts:
                logger.debug(f"Posts found after attempt {attempt + 1}")
                return
            
            await self._trigger_lazy_load()
            await self.page.wait_for_timeout(random.randint(1500, 3000))
        
        logger.warning("Posts may not have loaded fully")
    
    async def _trigger_lazy_load(self) -> None:
        # Use human_scroll for more natural behavior
        await human_scroll(self.page, total_distance=800)
        # Occasionally scroll back up slightly to trigger some event listeners
        if random.random() > 0.5:
            await human_scroll(self.page, total_distance=-random.uniform(200, 400))
        await self.page.wait_for_timeout(random.randint(1000, 2000))
    
    async def _scrape_posts(self, limit: int) -> List[Post]:
        posts: List[Post] = []
        scroll_count = 0
        
        # If limit is 0 or less, we treat it as "no limit"
        is_infinite = limit <= 0
        max_scrolls = 3000 if is_infinite else (limit // 2) + 20
        effective_limit = float('inf') if is_infinite else limit
        
        last_height = 0
        no_growth_count = 0
        
        # Tracking scroll position to detect resets
        last_scroll_y = 0
        
        while len(posts) < effective_limit and scroll_count < max_scrolls:
            new_posts = await self._extract_posts_from_page()
            
            added_any = False
            for post in new_posts:
                if not any((p.urn == post.urn if post.urn and p.urn else False) or 
                          (p.text[:100] == post.text[:100] and p.author_name == post.author_name) 
                          for p in posts):
                    posts.append(post)
                    added_any = True
                    self._stats["total_extracted"] += 1
                    
                    # Print progress
                    print(f"✨ [{self._stats['total_extracted']}] {post.author_name}")
                    
                    if self.on_post_extracted:
                        self.on_post_extracted(post)

                    # --- Stealth Interactions ---
                    # Surgical Like (5% chance)
                    if random.random() < 0.05:
                        await self._perform_random_like(post)
                    
                    # Behavioral Diversion (2% chance) - mimic "getting distracted"
                    if random.random() < 0.02:
                        await self._perform_behavioral_diversion()

                    # Safety Break: 2 minutes every 50 posts
                    if self._stats["total_extracted"] % 50 == 0:
                        print(f"\n🛡️  [SAFETY BREAK] 50 posts reached. Pausing for 2 minutes to mimic human rest...")
                        for i in range(120, 0, -1):
                            print(f"   ⏳ Resuming in {i}s...   ", end='\r')
                            await asyncio.sleep(1)
                        print("\n✅ Resuming...\n")

                    if not is_infinite and len(posts) >= limit:
                        break
            
            if is_infinite or len(posts) < limit:
                # Get current state before scroll
                current_scroll_y = await self.page.evaluate('window.scrollY')
                current_height = await self.page.evaluate('document.documentElement.scrollHeight')
                
                # RESET DETECTION (More robust)
                # If we were far down and now we are at the top
                if current_scroll_y < 500 and last_scroll_y > 2000:
                    print(f"⚠️  [DETECTED RESET] Page jumped from {last_scroll_y}px to {current_scroll_y}px. Recovering...")
                    no_growth_count = 0
                    # Aggressive jump back
                    await self.page.evaluate(f'window.scrollTo(0, {last_scroll_y + 1000})')
                    await self.page.wait_for_timeout(2000)
                    last_scroll_y = await self.page.evaluate('window.scrollY')
                    continue

                await self._scroll_for_more_posts()
                scroll_count += 1
                await self.page.wait_for_timeout(random.randint(1500, 3000))
                
                # Update tracking
                new_scroll_y = await self.page.evaluate('window.scrollY')
                new_height = await self.page.evaluate('document.documentElement.scrollHeight')
                
                if new_height <= last_height and not added_any:
                    no_growth_count += 1
                else:
                    no_growth_count = 0
                    last_height = new_height
                
                last_scroll_y = new_scroll_y
                
                # Stop only if we are truly stuck (30 attempts ~ 1.5 mins of no progress)
                if no_growth_count >= 30:
                    logger.debug("No growth for 30 attempts, stopping.")
                    break
        
        return posts if is_infinite else posts[:limit]
    
    async def _perform_random_like(self, post: Post) -> None:
        """Attempt to like a post using physical mouse movement."""
        try:
            # First, find the post element and ensure it's somewhat in view
            # We use URN or text snippet to locate it
            selector = f'[data-urn="{post.urn}"]' if post.urn else f'div:has-text("{post.text[:30]}")'
            post_locator = self.page.locator(selector).first
            
            if await post_locator.count() == 0:
                return

            # Check if like button exists and isn't already liked
            like_btn_selector = f'{selector} button[aria-label*="Like"]'
            like_btn = self.page.locator(like_btn_selector).first
            
            if await like_btn.count() > 0:
                is_liked = await like_btn.get_attribute('aria-pressed') == 'true'
                if not is_liked:
                    # Scroll it into view smoothly first
                    await post_locator.scroll_into_view_if_needed()
                    await self.page.wait_for_timeout(random.randint(500, 1500))
                    
                    # Physical click
                    await human_click(self.page, like_btn_selector)
                    logger.info(f"❤️ Stealth Like: Physically liked post by {post.author_name}")
                    self._stats["liked"] += 1
        except Exception as e:
            logger.debug(f"Failed to perform stealth like: {e}")

    async def _perform_behavioral_diversion(self) -> None:
        """Simulate a human getting distracted: random mouse moves, or checking home feed."""
        try:
            choice = random.random()
            if choice < 0.7:
                # 70% chance: just move mouse randomly
                logger.info("👤 Stealth: Simulating idle mouse movement...")
                await random_mouse_move(self.page)
            else:
                # 30% chance: "Check" home feed briefly in a new tab
                logger.info("👤 Stealth: Simulating distraction (checking home feed)...")
                new_page = await self.page.context.new_page()
                await new_page.goto('https://www.linkedin.com/feed/', wait_until="domcontentloaded")
                await human_scroll(new_page, total_distance=random.uniform(300, 600))
                await asyncio.sleep(random.uniform(5, 12))
                await new_page.close()
                
            await self.page.wait_for_timeout(random.randint(1000, 3000))
        except Exception as e:
            logger.debug(f"Behavioral diversion failed: {e}")

    async def _perform_random_profile_visit(self, profile_url: str) -> None:
        """Visit a profile in a background tab to preserve search results state."""
        new_page = None
        try:
            logger.info(f"👤 Stealth: Visiting profile in background: {profile_url}")
            
            # Create a new page (tab) in the same browser context
            new_page = await self.page.context.new_page()
            
            # Navigate to profile in the NEW tab
            await new_page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            
            # Small random scroll in the background tab
            await human_scroll(new_page, total_distance=random.uniform(200, 500))
            await new_page.wait_for_timeout(random.randint(3000, 6000))
            
            # Close the background tab
            await new_page.close()
            
            # Ensure main page is still healthy
            await self.page.wait_for_timeout(random.randint(500, 1500))
            
        except Exception as e:
            logger.debug(f"Failed to perform random profile visit in background: {e}")
            if new_page:
                try:
                    await new_page.close()
                except:
                    pass

    async def _extract_posts_from_page(self) -> List[Post]:
        return await self._extract_posts_via_js()
    
    async def _extract_posts_via_js(self) -> List[Post]:
        # Only click "see more" buttons that are actually visible near current scroll
        await self.page.evaluate('''() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            buttons.forEach(btn => {
                const text = btn.innerText.toLowerCase();
                const isExpandBtn = btn.getAttribute('data-testid') === 'expandable-text-button' || 
                                   btn.classList.contains('feed-shared-inline-show-more-text__button') ||
                                   (text.includes('more') && text.length < 15);
                
                if (isExpandBtn) {
                    const rect = btn.getBoundingClientRect();
                    const isVisible = (
                        rect.top >= -500 &&
                        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) + 500
                    );
                    if (isVisible) btn.click();
                }
            });
        }''')
        await self.page.wait_for_timeout(random.randint(800, 1500))

        posts_data = await self.page.evaluate('''() => {
            const posts = [];
            
            const postSelectors = [
                '[role="listitem"]',
                '.feed-shared-update-v2',
                '.reusable-search__result-container',
                'div[componentkey*="SEARCH"]',
                '[data-urn*="activity"]'
            ];
            
            let postElements = [];
            for (const sel of postSelectors) {
                const els = Array.from(document.querySelectorAll(sel));
                if (els.length > postElements.length) {
                    postElements = els;
                }
            }
            
            const seenContents = new Set();
            
            for (const el of postElements) {
                // Try to get URN
                let urn = el.getAttribute('data-urn') || '';
                if (!urn) {
                    const urnEl = el.querySelector('[data-urn*="activity"], [data-chameleon-result-urn*="activity"]');
                    if (urnEl) {
                        urn = urnEl.getAttribute('data-urn') || urnEl.getAttribute('data-chameleon-result-urn');
                    }
                }
                
                if (!urn) {
                    const match = el.innerHTML.match(/urn:li:activity:(\\d+)/);
                    if (match) urn = match[0];
                }
                
                // Get text content - extremely permissive
                let text = '';
                const textSelectors = [
                    '.feed-shared-update-v2__description',
                    '.update-components-text',
                    '.feed-shared-text',
                    '.break-words.whitespace-pre-wrap',
                    '[data-testid="expandable-text-box"]',
                    '.feed-shared-update-v2__commentary',
                    '.update-components-actor__sub-description', // Sometimes text is next to this
                    '.reusable-search__result-container' // The container itself
                ];
                
                for (const sel of textSelectors) {
                    const textEl = el.querySelector(sel);
                    if (textEl) {
                        const t = textEl.innerText?.trim() || '';
                        if (t.length > text.length) text = t;
                    }
                }
                
                // If still no text, try all paragraphs
                if (!text || text.length < 10) {
                    text = Array.from(el.querySelectorAll('p, span'))
                        .map(n => n.innerText)
                        .filter(t => t && t.length > 20)
                        .join('\\n');
                }
                
                if (!text || text.length < 10) continue;
                
                // Clean up text
                text = text.replace(/\\n\\n+/g, '\\n').trim();
                
                // Deduplicate by content snippet
                const contentSnippet = text.substring(0, 80);
                if (seenContents.has(contentSnippet)) continue;
                seenContents.add(contentSnippet);
                
                // Time
                const timeEl = el.querySelector('[class*="actor__sub-description"], [class*="update-components-actor__sub-description"], .update-components-actor__sub-description');
                const timeText = timeEl ? timeEl.innerText.split('•')[0].trim() : '';
                
                // Author
                let authorName = 'Unknown';
                const links = Array.from(el.querySelectorAll('a[href*="/in/"]'));
                for (const link of links) {
                    const ariaLabel = link.getAttribute('aria-label');
                    if (ariaLabel) {
                        authorName = ariaLabel.split('•')[0].split('view')[0].split("'s profile")[0].trim();
                    } else {
                        authorName = link.innerText.split('\\n')[0].trim();
                    }
                    if (authorName && authorName !== 'Unknown' && authorName.length > 2 && !authorName.includes('profile picture')) break;
                }
                
                // Fallback for author name
                if (authorName === 'Unknown' || authorName === '') {
                    const actorEl = el.querySelector('.update-components-actor__name, .feed-shared-actor__name, [class*="actor__name"]');
                    if (actorEl) authorName = actorEl.innerText.split('\\n')[0].trim();
                }

                const authorLinkEl = el.querySelector('a[href*="/in/"]');
                let authorUrl = authorLinkEl ? authorLinkEl.href : '';
                if (authorUrl && authorUrl.includes('?')) authorUrl = authorUrl.split('?')[0];

                // Stats
                const getStat = (query) => {
                    const nodes = Array.from(el.querySelectorAll('span, button, a'));
                    for (const node of nodes) {
                        const t = node.innerText.toLowerCase();
                        if (t.includes(query)) return node.innerText;
                    }
                    return '';
                };

                posts.push({
                    urn: urn,
                    text: text,
                    timeText: timeText,
                    authorName: authorName,
                    authorUrl: authorUrl,
                    reactions: getStat('reaction') || getStat('like') || '',
                    comments: getStat('comment') || '',
                    reposts: getStat('repost') || '',
                    images: Array.from(el.querySelectorAll('img[src*="media"]')).map(img => img.src)
                });
            }
            return posts;
        }''')
        
        result: List[Post] = []
        for data in posts_data:
            activity_id = data['urn'].replace('urn:li:activity:', '') if 'activity' in data['urn'] else data['urn']
            if not activity_id:
                import hashlib
                activity_id = hashlib.md5(data['text'][:100].encode()).hexdigest()
                linkedin_url = f"https://www.linkedin.com/search/results/content/?keywords={activity_id}"
            else:
                linkedin_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                
            post = Post(
                linkedin_url=linkedin_url,
                urn=data['urn'] if 'activity' in data['urn'] else None,
                text=data['text'],
                posted_date=self._extract_time_from_text(data.get('timeText', '')),
                reactions_count=self._parse_count(data.get('reactions', '')),
                comments_count=self._parse_count(data.get('comments', '')),
                reposts_count=self._parse_count(data.get('reposts', '')),
                image_urls=data.get('images', []),
                author_name=data.get('authorName'),
                author_url=data.get('authorUrl')
            )
            result.append(post)
        
        return result
    
    def _extract_time_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None
        match = re.search(r'(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        parts = text.split('•')
        if parts:
            return parts[0].strip()
        return None
    
    async def _parse_post_element(self, element) -> Optional[Post]:
        try:
            urn = await element.get_attribute('data-urn')
            if not urn or 'activity' not in urn:
                return None
            
            activity_id = urn.replace('urn:li:activity:', '')
            linkedin_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
            
            text = await self._get_post_text(element)
            posted_date = await self._get_posted_date(element)
            reactions_count = await self._get_reactions_count(element)
            comments_count = await self._get_comments_count(element)
            reposts_count = await self._get_reposts_count(element)
            image_urls = await self._get_image_urls(element)
            
            return Post(
                linkedin_url=linkedin_url,
                urn=urn,
                text=text,
                posted_date=posted_date,
                reactions_count=reactions_count,
                comments_count=comments_count,
                reposts_count=reposts_count,
                image_urls=image_urls
            )
        except Exception as e:
            logger.debug(f"Error parsing post: {e}")
            return None
    
    async def _get_post_text(self, element) -> Optional[str]:
        try:
            text_container = element.locator('.feed-shared-update-v2__description, .break-words')
            if await text_container.count() > 0:
                text = await text_container.first.inner_text()
                return text.strip() if text else None
        except:
            pass
        return None
    
    async def _get_posted_date(self, element) -> Optional[str]:
        try:
            time_elem = element.locator('[class*="actor__sub-description"], [class*="update-components-actor__sub-description"]')
            if await time_elem.count() > 0:
                text = await time_elem.first.inner_text()
                match = re.search(r'(\d+[hdwmy]|\d+\s*(?:hour|day|week|month|year)s?\s*ago)', text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                if text:
                    clean_text = text.split('•')[0].strip()
                    return clean_text if clean_text else None
        except:
            pass
        return None
    
    async def _get_reactions_count(self, element) -> Optional[int]:
        try:
            reactions_elem = element.locator('[class*="social-details-social-counts__reactions"], button[aria-label*="reaction"]')
            if await reactions_elem.count() > 0:
                text = await reactions_elem.first.inner_text()
                return self._parse_count(text)
        except:
            pass
        return None
    
    async def _get_comments_count(self, element) -> Optional[int]:
        try:
            comments_elem = element.locator('button[aria-label*="comment"]')
            if await comments_elem.count() > 0:
                text = await comments_elem.first.inner_text()
                return self._parse_count(text)
        except:
            pass
        return None
    
    async def _get_reposts_count(self, element) -> Optional[int]:
        try:
            reposts_elem = element.locator('button[aria-label*="repost"]')
            if await reposts_elem.count() > 0:
                text = await reposts_elem.first.inner_text()
                return self._parse_count(text)
        except:
            pass
        return None
    
    async def _get_image_urls(self, element) -> List[str]:
        urls: List[str] = []
        try:
            images = await element.locator('img[src*="media"]').all()
            for img in images:
                src = await img.get_attribute('src')
                if src and 'profile' not in src and 'logo' not in src:
                    urls.append(src)
        except:
            pass
        return urls
    
    def _parse_count(self, text: str) -> Optional[int]:
        if not text:
            return None
        try:
            numbers = re.findall(r'[\d,]+', text.replace(',', ''))
            if numbers:
                return int(numbers[0])
        except:
            pass
        return None
    
    async def _scroll_for_more_posts(self) -> None:
        try:
            # AVOID MOUSE MOVEMENT - it might trigger UI resets
            # 1. Page Down
            await self.page.keyboard.press('PageDown')
            await self.page.wait_for_timeout(random.randint(500, 1000))
            
            # 2. Human-like wheel scroll (distance only)
            await human_scroll(self.page, total_distance=random.uniform(1200, 2500))
            
            # 3. Aggressive "Show more results" check
            show_more_selectors = [
                'button:has-text("Show more results")',
                'button:has-text("See more results")',
                '.scaffold-layout__infinite-scroll-load-button',
                'button[aria-label="Show more results"]'
            ]
            
            for selector in show_more_selectors:
                try:
                    btn = self.page.locator(selector).first
                    if await btn.is_visible(timeout=500):
                        print("👉 Clicking 'Show more results' button...")
                        await btn.scroll_into_view_if_needed()
                        await self.page.wait_for_timeout(500)
                        await btn.click()
                        await self.page.wait_for_timeout(2000)
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error scrolling: {e}")
            await self.page.keyboard.press('PageDown')

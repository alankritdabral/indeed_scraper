"""Utility functions for scraping operations."""

import asyncio
import functools
import logging
import random
import math
from typing import Any, Callable, Optional, TypeVar, cast
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .exceptions import RateLimitError, ElementNotFoundError, NetworkError

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_async(
    max_attempts: int = 3,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for async functions to add retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff: Backoff multiplier for exponential backoff
        exceptions: Tuple of exceptions to catch and retry
    
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff ** attempt
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}"
                        )
            raise last_exception
        return wrapper
    return decorator


async def detect_rate_limit(page: Page) -> None:
    """
    Detect if LinkedIn has rate limited the session.
    
    Args:
        page: Playwright page object
        
    Raises:
        RateLimitError: If rate limiting is detected
    """
    # Check for common rate limit indicators
    
    # Check URL for security challenges
    current_url = page.url
    if 'linkedin.com/checkpoint' in current_url or 'authwall' in current_url:
        raise RateLimitError(
            "LinkedIn security checkpoint detected. "
            "You may need to verify your identity or wait before continuing.",
            suggested_wait_time=3600  # 1 hour
        )
    
    # Check for CAPTCHA
    try:
        captcha = await page.locator('iframe[title*="captcha" i], iframe[src*="captcha" i]').count()
        if captcha > 0:
            raise RateLimitError(
                "CAPTCHA challenge detected. Manual intervention required.",
                suggested_wait_time=3600
            )
    except Exception:
        pass
    
    # Check for rate limit messages
    try:
        body_text = await page.locator('body').text_content(timeout=1000)
        if body_text:
            body_lower = body_text.lower()
            if any(phrase in body_lower for phrase in [
                'too many requests',
                'rate limit',
                'slow down',
                'try again later'
            ]):
                raise RateLimitError(
                    "Rate limit message detected on page.",
                    suggested_wait_time=1800  # 30 minutes
                )
    except PlaywrightTimeoutError:
        pass


async def wait_for_element_smart(
    page: Page,
    selector: str,
    timeout: float = 5000,
    state: str = "visible",
    error_context: Optional[str] = None
) -> None:
    """
    Wait for an element with better error messages.
    
    Args:
        page: Playwright page object
        selector: CSS selector or text selector
        timeout: Timeout in milliseconds
        state: Element state to wait for (visible, attached, hidden, detached)
        error_context: Additional context for error message
        
    Raises:
        ElementNotFoundError: If element is not found with helpful context
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout, state=state)
    except PlaywrightTimeoutError:
        context = f" when {error_context}" if error_context else ""
        suggestions = _get_selector_suggestions(selector)
        
        raise ElementNotFoundError(
            f"Could not find element with selector '{selector}'{context}. "
            f"This may indicate:\n"
            f"  • The page structure has changed\n"
            f"  • The profile has restricted visibility\n"
            f"  • The content doesn't exist on this page\n"
            f"  • Network slowness (try increasing timeout)\n"
            f"{suggestions}"
        )


def _get_selector_suggestions(selector: str) -> str:
    """Get helpful suggestions based on selector type."""
    if '#' in selector:
        return "Tip: ID selectors may be dynamic. Consider using data attributes or text content."
    elif 'pv-' in selector or 'artdeco' in selector:
        return "Tip: LinkedIn class names change frequently. This selector may need updating."
    return ""


async def extract_text_safe(
    page: Page,
    selector: str,
    default: str = "",
    timeout: float = 2000
) -> str:
    """
    Safely extract text from an element, returning default if not found.
    
    Args:
        page: Playwright page object
        selector: CSS selector
        default: Default value if element not found
        timeout: Timeout in milliseconds
        
    Returns:
        Extracted text or default value
    """
    try:
        element = page.locator(selector).first
        text = await element.text_content(timeout=timeout)
        return text.strip() if text else default
    except PlaywrightTimeoutError:
        logger.debug(f"Element not found: {selector}, returning default: {default}")
        return default
    except Exception as e:
        logger.debug(f"Error extracting text from {selector}: {e}")
        return default


async def scroll_to_bottom(page: Page, pause_time: float = 1.0, max_scrolls: int = 10) -> None:
    """
    Scroll to the bottom of the page smoothly with pauses.
    
    Args:
        page: Playwright page object
        pause_time: Time to pause between scrolls (seconds)
        max_scrolls: Maximum number of scroll attempts
    """
    for i in range(max_scrolls):
        # Get current scroll position
        previous_height = await page.evaluate('document.body.scrollHeight')
        
        # Scroll down
        await human_scroll(page)
        await asyncio.sleep(pause_time * random.uniform(0.8, 1.2))
        
        # Check if we've reached the bottom
        new_height = await page.evaluate('document.body.scrollHeight')
        if new_height == previous_height:
            logger.debug(f"Reached bottom after {i + 1} scrolls")
            break


async def scroll_to_half(page: Page) -> None:
    """Scroll to middle of page."""
    height = await page.evaluate('document.body.scrollHeight')
    await human_scroll(page, total_distance=height / 2)


async def human_type(page: Page, selector: str, text: str, delay_range: tuple = (50, 200)) -> None:
    """
    Type text with realistic human-like cadence, including variable delays
    and occasional pauses.
    
    Args:
        page: Playwright page object
        selector: Input element selector
        text: Text to type
        delay_range: (min, max) delay between keystrokes in ms
    """
    await page.focus(selector)
    
    for char in text:
        # Normal typing delay
        delay = random.uniform(delay_range[0], delay_range[1]) / 1000
        await asyncio.sleep(delay)
        
        # Occasional longer pause (thinking or repositioning hands)
        if random.random() < 0.1:
            await asyncio.sleep(random.uniform(0.2, 0.8))
            
        await page.type(selector, char, delay=0)  # Use 0 since we handle delay
        
    # Final pause after typing
    await asyncio.sleep(random.uniform(0.3, 1.0))


async def human_click(page: Page, selector: str, timeout: float = 5000) -> None:
    """
    Perform a human-like click by moving the mouse to the element first
    with a natural curve, then clicking.
    
    Args:
        page: Playwright page object
        selector: Element selector to click
        timeout: Wait timeout
    """
    element = page.locator(selector).first
    await element.wait_for(state="visible", timeout=timeout)
    
    # Get element boundaries
    box = await element.bounding_box()
    if not box:
        # Fallback to direct click if bounding box fails
        await element.click()
        return

    # Target a random point within the element (avoid dead center)
    target_x = box['x'] + (box['width'] * random.uniform(0.2, 0.8))
    target_y = box['y'] + (box['height'] * random.uniform(0.2, 0.8))
    
    # Get current mouse position from state or default
    state = getattr(page, '_human_scroll_state', {'last_mouse_pos': {'x': 0, 'y': 0}})
    start_x = state.get('last_mouse_pos', {}).get('x', 0)
    start_y = state.get('last_mouse_pos', {}).get('y', 0)
    
    # Move mouse in a curve to the target
    steps = random.randint(5, 15)
    for i in range(steps + 1):
        # Quadratic Bezier curve or simple linear interpolation with jitter
        t = i / steps
        # Add some "human" sway
        sway = math.sin(t * math.pi) * random.uniform(-20, 20)
        
        curr_x = start_x + (target_x - start_x) * t + (sway if i < steps else 0)
        curr_y = start_y + (target_y - start_y) * t + (sway if i < steps else 0)
        
        await page.mouse.move(curr_x, curr_y)
        await asyncio.sleep(random.uniform(0.01, 0.03))
    
    # Short pause before clicking
    await asyncio.sleep(random.uniform(0.1, 0.3))
    
    # Perform the click
    await page.mouse.click(target_x, target_y)
    
    # Update state
    if hasattr(page, '_human_scroll_state'):
        getattr(page, '_human_scroll_state')['last_mouse_pos'] = {'x': target_x, 'y': target_y}

    await asyncio.sleep(random.uniform(0.2, 0.5))


async def random_mouse_move(page: Page) -> None:
    """Simulate idle human mouse movement."""
    viewport = page.viewport_size or {'width': 1280, 'height': 720}
    
    steps = random.randint(10, 30)
    for _ in range(steps):
        target_x = random.uniform(100, viewport['width'] - 100)
        target_y = random.uniform(100, viewport['height'] - 100)
        
        await page.mouse.move(target_x, target_y, steps=random.randint(5, 15))
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        if random.random() < 0.2:
            break


async def human_scroll(
    page: Page, 
    total_distance: Optional[float] = None,
    scrolls_before_break: Optional[int] = None
) -> None:
    """
    Perform human-like scrolling with variable movement, timing, and random breaks.
    Uses non-linear acceleration/deceleration.
    
    Args:
        page: Playwright page object
        total_distance: Total distance to scroll. If None, scrolls a random amount.
        scrolls_before_break: Number of scrolls before taking a longer break.
    """
    # Initialize state on the page object if not present
    if not hasattr(page, '_human_scroll_state'):
        setattr(page, '_human_scroll_state', {
            'count': 0,
            'target_break': scrolls_before_break or random.randint(5, 15),
            'last_mouse_pos': {'x': random.randint(100, 1000), 'y': random.randint(100, 600)}
        })
    
    state = getattr(page, '_human_scroll_state')
    
    # Random distance if not specified
    if total_distance is None:
        total_distance = random.uniform(300, 800)
    
    # Variable number of steps for the scroll
    steps = random.randint(15, 45)
    
    logger.debug(f"Human scroll: target {total_distance:.2f}px in {steps} steps")
    
    # Use a basic easing function (sine ease-in-out) to simulate physical movement
    accumulated_scroll = 0
    for i in range(steps):
        # Progress from 0.0 to 1.0
        t = i / steps
        # Sine ease-in-out multiplier for the step size
        # This makes it start slow, speed up in middle, then slow down
        multiplier = (math.sin((t * math.pi) - (math.pi / 2)) + 1) / 2
        
        # Calculate current target scroll based on easing
        # But add some jitter to the speed
        current_target = total_distance * multiplier
        step_delta = (current_target - accumulated_scroll) * random.uniform(0.8, 1.2)
        accumulated_scroll += step_delta
        
        # Simulate human hand jitter/zigzag
        curr_x = state['last_mouse_pos']['x']
        curr_y = state['last_mouse_pos']['y']
        
        jitter_x = random.uniform(-2, 2)
        jitter_y = random.uniform(-1, 1)
        
        new_x = curr_x + jitter_x
        new_y = curr_y + jitter_y
        
        # Constrain to viewport
        viewport = page.viewport_size or {'width': 1280, 'height': 720}
        new_x = max(50, min(viewport['width'] - 50, new_x))
        new_y = max(50, min(viewport['height'] - 50, new_y))
        
        try:
            await page.mouse.move(new_x, new_y)
            state['last_mouse_pos'] = {'x': new_x, 'y': new_y}
        except:
            pass
            
        # Perform the scroll
        await page.mouse.wheel(0, step_delta)
        
        # Variable timing between "flicks"
        await asyncio.sleep(random.uniform(0.01, 0.05))
        
        # Occasional pause (re-adjusting grip)
        if i > 0 and i % 15 == 0:
            await asyncio.sleep(random.uniform(0.2, 0.6))

    # Update scroll counter
    state['count'] += 1
    
    # Random long break to simulate reading
    if state['count'] >= state['target_break']:
        # 1% chance of a VERY long break (going for coffee)
        if random.random() < 0.01:
            break_time = random.uniform(300, 600)
            logger.warning(f"🛡️ Long break: Human-like 'coffee break' for {break_time/60:.1f} minutes...")
        else:
            break_time = random.uniform(5.0, 15.0)
            
        await asyncio.sleep(break_time)
        
        # Reset state for next cycle
        state['count'] = 0
        state['target_break'] = scrolls_before_break or random.randint(5, 15)



async def click_see_more_buttons(page: Page, max_attempts: int = 10) -> int:
    """
    Click all 'Show more' / 'See more' buttons on the page.
    
    Args:
        page: Playwright page object
        max_attempts: Maximum number of buttons to click
        
    Returns:
        Number of buttons clicked
    """
    clicked = 0
    for _ in range(max_attempts):
        try:
            # Look for common "see more" button patterns
            see_more = page.locator('button:has-text("See more"), button:has-text("Show more"), button:has-text("show all")').first
            
            if await see_more.is_visible(timeout=1000):
                await see_more.click()
                await asyncio.sleep(0.5)  # Wait for content to load
                clicked += 1
            else:
                break
        except:
            break
    
    if clicked > 0:
        logger.debug(f"Clicked {clicked} 'see more' buttons")
    
    return clicked


async def handle_modal_close(page: Page) -> bool:
    """
    Close any popup modals that might be blocking content.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if a modal was closed, False otherwise
    """
    try:
        # Look for common close button patterns
        close_button = page.locator(
            'button[aria-label="Dismiss"], '
            'button[aria-label="Close"], '
            'button.artdeco-modal__dismiss'
        ).first
        
        if await close_button.is_visible(timeout=1000):
            await close_button.click()
            await asyncio.sleep(0.5)
            logger.debug("Closed modal")
            return True
    except:
        pass
    
    return False


async def is_page_loaded(page: Page) -> bool:
    """
    Check if page has finished loading.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if page is loaded
    """
    try:
        state = await page.evaluate('document.readyState')
        return state == 'complete'
    except:
        return False

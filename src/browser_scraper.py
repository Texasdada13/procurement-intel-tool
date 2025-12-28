"""
Browser-based scraping for JavaScript-rendered procurement sites.
Uses Playwright for headless browser automation.

Install with: pip install playwright && playwright install chromium
"""

import os
import sys
import logging
import asyncio
from typing import List, Dict, Optional, Callable
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# Check if Playwright is available
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")


class BrowserScraper:
    """
    Browser-based scraper for JavaScript-rendered sites.
    Uses Playwright with Chromium for headless browsing.
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Initialize the browser scraper.

        Args:
            headless: Run browser in headless mode (no UI)
            timeout: Default timeout for page operations in ms
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright is not installed. Run: pip install playwright && playwright install chromium")

        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_page(self) -> Page:
        """Create a new page with standard settings."""
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        page.set_default_timeout(self.timeout)
        return page

    async def fetch_page_content(self, url: str, wait_for: str = None) -> str:
        """
        Fetch page content after JavaScript rendering.

        Args:
            url: URL to fetch
            wait_for: Optional selector to wait for before returning content

        Returns:
            Rendered HTML content
        """
        page = await self.get_page()
        try:
            await page.goto(url, wait_until='networkidle')

            if wait_for:
                await page.wait_for_selector(wait_for, timeout=self.timeout)

            content = await page.content()
            return content
        finally:
            await page.close()

    async def scrape_demandstar(self, search_terms: List[str] = None) -> List[Dict]:
        """
        Scrape RFPs from DemandStar (requires JavaScript).

        Args:
            search_terms: List of keywords to search for

        Returns:
            List of RFP dictionaries
        """
        rfps = []
        page = await self.get_page()

        try:
            # Go to DemandStar bid search
            await page.goto('https://www.demandstar.com/app/bids', wait_until='networkidle')

            # Wait for the bid list to load
            await page.wait_for_selector('[data-testid="bid-list"]', timeout=15000)

            # Apply Florida filter if available
            try:
                state_filter = page.locator('text=Florida')
                if await state_filter.count() > 0:
                    await state_filter.first.click()
                    await page.wait_for_load_state('networkidle')
            except Exception:
                pass

            # Get bid items
            bid_items = page.locator('[data-testid="bid-item"], .bid-list-item, .opportunity-card')
            count = await bid_items.count()

            for i in range(min(count, 50)):  # Limit to 50 items
                try:
                    item = bid_items.nth(i)

                    title_el = item.locator('h2, h3, .bid-title, .opportunity-title').first
                    title = await title_el.text_content() if await title_el.count() > 0 else None

                    agency_el = item.locator('.agency, .organization, .buyer-name').first
                    agency = await agency_el.text_content() if await agency_el.count() > 0 else None

                    date_el = item.locator('.due-date, .close-date, [data-testid="due-date"]').first
                    due_date = await date_el.text_content() if await date_el.count() > 0 else None

                    link_el = item.locator('a').first
                    url = await link_el.get_attribute('href') if await link_el.count() > 0 else None

                    if title:
                        rfps.append({
                            'title': title.strip(),
                            'agency': agency.strip() if agency else None,
                            'due_date': due_date.strip() if due_date else None,
                            'source_url': f"https://www.demandstar.com{url}" if url and not url.startswith('http') else url,
                            'source_portal': 'demandstar'
                        })
                except Exception as e:
                    logger.debug(f"Error extracting bid item {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping DemandStar: {e}")
        finally:
            await page.close()

        return rfps

    async def scrape_bonfire(self, portal_url: str) -> List[Dict]:
        """
        Scrape RFPs from Bonfire procurement portal.

        Args:
            portal_url: Base URL of the Bonfire portal (e.g., 'https://agency.bonfirehub.com')

        Returns:
            List of RFP dictionaries
        """
        rfps = []
        page = await self.get_page()

        try:
            await page.goto(f"{portal_url}/opportunities", wait_until='networkidle')

            # Wait for opportunities to load
            await page.wait_for_selector('.opportunity-card, .opportunity-list-item', timeout=15000)

            # Get opportunity items
            items = page.locator('.opportunity-card, .opportunity-list-item')
            count = await items.count()

            for i in range(min(count, 50)):
                try:
                    item = items.nth(i)

                    title_el = item.locator('.opportunity-title, h2, h3').first
                    title = await title_el.text_content() if await title_el.count() > 0 else None

                    date_el = item.locator('.close-date, .due-date').first
                    due_date = await date_el.text_content() if await date_el.count() > 0 else None

                    link_el = item.locator('a').first
                    url = await link_el.get_attribute('href') if await link_el.count() > 0 else None

                    if title:
                        rfps.append({
                            'title': title.strip(),
                            'due_date': due_date.strip() if due_date else None,
                            'source_url': url if url and url.startswith('http') else f"{portal_url}{url}",
                            'source_portal': 'bonfire'
                        })
                except Exception as e:
                    logger.debug(f"Error extracting opportunity {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping Bonfire portal: {e}")
        finally:
            await page.close()

        return rfps

    async def scrape_ionwave(self, portal_url: str) -> List[Dict]:
        """
        Scrape RFPs from IonWave eProcurement portal (many FL counties use this).

        Args:
            portal_url: Base URL of the IonWave portal

        Returns:
            List of RFP dictionaries
        """
        rfps = []
        page = await self.get_page()

        try:
            # IonWave typically has a bid board
            await page.goto(f"{portal_url}/BidBoard", wait_until='networkidle')

            # Wait for bid table
            await page.wait_for_selector('table, .bid-list, .solicitation-list', timeout=15000)

            # Get table rows
            rows = page.locator('table tbody tr, .bid-item, .solicitation-item')
            count = await rows.count()

            for i in range(min(count, 50)):
                try:
                    row = rows.nth(i)

                    cells = row.locator('td')
                    if await cells.count() >= 3:
                        title = await cells.nth(0).text_content()
                        due_date = await cells.nth(2).text_content() if await cells.count() > 2 else None

                        link_el = row.locator('a').first
                        url = await link_el.get_attribute('href') if await link_el.count() > 0 else None

                        if title:
                            rfps.append({
                                'title': title.strip(),
                                'due_date': due_date.strip() if due_date else None,
                                'source_url': url,
                                'source_portal': 'ionwave'
                            })
                except Exception as e:
                    logger.debug(f"Error extracting row {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping IonWave portal: {e}")
        finally:
            await page.close()

        return rfps

    async def scrape_generic_table(self, url: str, config: Dict) -> List[Dict]:
        """
        Generic table scraper with configurable selectors.

        Args:
            url: URL to scrape
            config: Configuration dict with selectors:
                - wait_selector: Element to wait for
                - row_selector: Selector for table rows
                - title_selector: Selector for title within row
                - date_selector: Selector for due date within row
                - link_selector: Selector for link within row

        Returns:
            List of RFP dictionaries
        """
        rfps = []
        page = await self.get_page()

        try:
            await page.goto(url, wait_until='networkidle')

            if config.get('wait_selector'):
                await page.wait_for_selector(config['wait_selector'], timeout=15000)

            rows = page.locator(config.get('row_selector', 'table tbody tr'))
            count = await rows.count()

            for i in range(min(count, 100)):
                try:
                    row = rows.nth(i)

                    title_el = row.locator(config.get('title_selector', 'td:first-child')).first
                    title = await title_el.text_content() if await title_el.count() > 0 else None

                    date_el = row.locator(config.get('date_selector', 'td:nth-child(3)')).first
                    due_date = await date_el.text_content() if await date_el.count() > 0 else None

                    link_el = row.locator(config.get('link_selector', 'a')).first
                    link_url = await link_el.get_attribute('href') if await link_el.count() > 0 else None

                    if title and title.strip():
                        rfps.append({
                            'title': title.strip(),
                            'due_date': due_date.strip() if due_date else None,
                            'source_url': link_url,
                            'source_portal': config.get('portal_name', 'generic')
                        })
                except Exception as e:
                    logger.debug(f"Error extracting row {i}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
        finally:
            await page.close()

        return rfps


async def run_browser_discovery(sites: List[Dict] = None) -> Dict:
    """
    Run browser-based discovery on configured sites.

    Args:
        sites: List of site configurations. Each should have:
            - url: Site URL
            - type: 'demandstar', 'bonfire', 'ionwave', or 'generic'
            - config: Additional config for generic scraper

    Returns:
        Discovery statistics
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not installed. Skipping browser-based discovery.")
        return {'error': 'Playwright not installed', 'found': 0}

    # Default Florida sites that require JavaScript
    default_sites = [
        {'type': 'demandstar', 'url': 'https://www.demandstar.com'},
    ]

    sites = sites or default_sites
    all_rfps = []

    async with BrowserScraper(headless=True) as scraper:
        for site in sites:
            try:
                site_type = site.get('type', 'generic')

                if site_type == 'demandstar':
                    rfps = await scraper.scrape_demandstar()
                elif site_type == 'bonfire':
                    rfps = await scraper.scrape_bonfire(site['url'])
                elif site_type == 'ionwave':
                    rfps = await scraper.scrape_ionwave(site['url'])
                else:
                    rfps = await scraper.scrape_generic_table(site['url'], site.get('config', {}))

                all_rfps.extend(rfps)
                logger.info(f"Found {len(rfps)} RFPs from {site.get('url', site_type)}")

            except Exception as e:
                logger.error(f"Error processing site {site}: {e}")
                continue

    return {
        'found': len(all_rfps),
        'rfps': all_rfps
    }


def sync_browser_discovery(sites: List[Dict] = None) -> Dict:
    """Synchronous wrapper for browser discovery."""
    return asyncio.run(run_browser_discovery(sites))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("Testing browser-based scraping...")
    print(f"Playwright available: {PLAYWRIGHT_AVAILABLE}")

    if PLAYWRIGHT_AVAILABLE:
        results = sync_browser_discovery()
        print(f"\nFound {results['found']} RFPs")
        for rfp in results.get('rfps', [])[:5]:
            print(f"  - {rfp['title'][:60]}...")
    else:
        print("\nInstall Playwright with: pip install playwright && playwright install chromium")

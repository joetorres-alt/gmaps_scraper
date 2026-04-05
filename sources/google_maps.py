"""Google Maps lead scraper."""
import asyncio
import re
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from models import Lead

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
SKIP_DOMAINS = {
    "example.com", "test.com", "domain.com", "email.com", "yourdomain.com",
    "sentry.io", "wixpress.com", "squarespace.com", "wordpress.com",
    "shopify.com", "amazonaws.com", "googletagmanager.com",
}


def _find_emails(html: str) -> list[str]:
    found = EMAIL_RE.findall(html)
    seen, clean = set(), []
    for e in found:
        e = e.lower()
        if e.split("@")[1] not in SKIP_DOMAINS and e not in seen:
            clean.append(e)
            seen.add(e)
    return clean


async def _harvest_email(page: Page, url: str) -> str:
    try:
        await page.goto(url, timeout=12_000, wait_until="domcontentloaded")
        emails = _find_emails(await page.content())
        if emails:
            return emails[0]
        for link_text in ["contact", "about"]:
            try:
                link = page.locator(f'a:has-text("{link_text}")')
                if await link.count() > 0:
                    href = await link.first.get_attribute("href") or ""
                    dest = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                    await page.goto(dest, timeout=10_000, wait_until="domcontentloaded")
                    emails = _find_emails(await page.content())
                    if emails:
                        return emails[0]
            except Exception:
                continue
    except Exception:
        pass
    return ""


class GoogleMapsScraper:
    def __init__(self, headless: bool = True, delay_ms: int = 1_500):
        self.headless = headless
        self.delay_ms = delay_ms

    async def scrape(self, keyword: str, location: str, max_results: int = 50) -> list[Lead]:
        query = f"{keyword} in {location}"
        leads: list[Lead] = []

        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(headless=self.headless)
            context: BrowserContext = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            maps_page: Page = await context.new_page()
            web_page: Page = await context.new_page()

            try:
                urls = await self._collect_urls(maps_page, query, max_results)
                print(f"  [Google Maps] Found {len(urls)} listings")

                for idx, url in enumerate(urls, 1):
                    lead = await self._scrape_listing(maps_page, web_page, url)
                    if lead.name:
                        lead.source = "google_maps"
                        leads.append(lead)
                        print(f"    [{idx}/{len(urls)}] {lead.name[:50]}")
                    await asyncio.sleep(self.delay_ms / 1_000)
            finally:
                await browser.close()

        return leads

    async def _collect_urls(self, page: Page, query: str, max_results: int) -> list[str]:
        await page.goto(
            f"https://www.google.com/maps/search/{query.replace(' ', '+')}",
            timeout=20_000,
        )
        await page.wait_for_timeout(3_000)

        for btn_text in ["Accept all", "Accept", "I agree"]:
            try:
                btn = page.locator(f'button:has-text("{btn_text}")')
                if await btn.is_visible(timeout=2_000):
                    await btn.click()
                    await page.wait_for_timeout(1_000)
                    break
            except Exception:
                pass

        urls, seen, stall = [], set(), 0
        feed = page.locator('div[role="feed"]')

        for _ in range(30):
            for anchor in await page.locator('a[href*="/maps/place/"]').all():
                href = await anchor.get_attribute("href")
                if href and href not in seen:
                    seen.add(href)
                    urls.append(href)
            if len(urls) >= max_results:
                break
            if await page.locator('span:has-text("reached the end")').count() > 0:
                break
            prev = len(urls)
            await feed.evaluate("el => el.scrollBy(0, 800)")
            await page.wait_for_timeout(1_800)
            if len(urls) == prev:
                stall += 1
                if stall >= 3:
                    break
            else:
                stall = 0

        return urls[:max_results]

    async def _scrape_listing(self, maps_page: Page, web_page: Page, url: str) -> Lead:
        lead = Lead()
        try:
            await maps_page.goto(url, timeout=15_000, wait_until="domcontentloaded")
            await maps_page.wait_for_timeout(2_000)

            for sel in ["h1.DUwDvf", "h1[data-attrid='title']", "h1"]:
                try:
                    el = maps_page.locator(sel).first
                    if await el.count() > 0:
                        lead.name = (await el.inner_text(timeout=4_000)).strip()
                        if lead.name:
                            break
                except Exception:
                    pass

            try:
                addr = maps_page.locator('button[data-item-id="address"]')
                if await addr.count() > 0:
                    lead.address = (await addr.inner_text(timeout=3_000)).strip()
            except Exception:
                pass

            try:
                phone_el = maps_page.locator('[data-item-id^="phone:tel:"]')
                if await phone_el.count() > 0:
                    lead.phone = (await phone_el.inner_text(timeout=3_000)).strip()
            except Exception:
                pass

            try:
                site_el = maps_page.locator('a[data-item-id="authority"]')
                if await site_el.count() > 0:
                    lead.website = (await site_el.get_attribute("href") or "").strip()
            except Exception:
                pass

            try:
                rating_el = maps_page.locator('div.F7nice span[aria-hidden="true"]').first
                if await rating_el.count() > 0:
                    txt = (await rating_el.inner_text()).strip()
                    lead.rating = float(txt) if txt else 0.0
            except Exception:
                pass

            try:
                reviews_el = maps_page.locator('div.F7nice span[aria-label*="review"]').first
                if await reviews_el.count() > 0:
                    txt = (await reviews_el.get_attribute("aria-label") or "").replace(",", "")
                    nums = re.findall(r"\d+", txt)
                    lead.review_count = int(nums[0]) if nums else 0
            except Exception:
                pass

            if lead.website:
                lead.email = await _harvest_email(web_page, lead.website)

        except Exception as exc:
            print(f"      ⚠ {exc}")

        return lead

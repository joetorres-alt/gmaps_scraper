"""Yelp lead scraper."""
import asyncio
import re
from playwright.async_api import async_playwright, Page
from models import Lead


class YelpScraper:
    def __init__(self, headless: bool = True, delay_ms: int = 1_500):
        self.headless = headless
        self.delay_ms = delay_ms

    async def scrape(self, keyword: str, location: str, max_results: int = 50) -> list[Lead]:
        leads: list[Lead] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            page: Page = await context.new_page()

            try:
                biz_urls = await self._collect_urls(page, keyword, location, max_results)
                print(f"  [Yelp] Found {len(biz_urls)} listings")

                for idx, url in enumerate(biz_urls, 1):
                    lead = await self._scrape_listing(page, url)
                    if lead.name:
                        lead.source = "yelp"
                        leads.append(lead)
                        print(f"    [{idx}/{len(biz_urls)}] {lead.name[:50]}")
                    await asyncio.sleep(self.delay_ms / 1_000)
            finally:
                await browser.close()

        return leads

    async def _collect_urls(self, page: Page, keyword: str, location: str, max_results: int) -> list[str]:
        urls, seen = [], set()
        start = 0

        while len(urls) < max_results:
            search_url = (
                f"https://www.yelp.com/search"
                f"?find_desc={keyword.replace(' ', '+')}"
                f"&find_loc={location.replace(' ', '+')}"
                f"&start={start}"
            )
            try:
                await page.goto(search_url, timeout=20_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2_500)
            except Exception:
                break

            anchors = await page.locator('a[href*="/biz/"]').all()
            new_found = 0
            for anchor in anchors:
                href = await anchor.get_attribute("href") or ""
                # only business pages, not search filters
                if "/biz/" in href and "?" not in href and href not in seen:
                    full = href if href.startswith("http") else "https://www.yelp.com" + href
                    seen.add(href)
                    urls.append(full)
                    new_found += 1

            if new_found == 0:
                break
            start += 10

        return urls[:max_results]

    async def _scrape_listing(self, page: Page, url: str) -> Lead:
        lead = Lead()
        try:
            await page.goto(url, timeout=15_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2_000)

            # Name
            try:
                h1 = page.locator("h1").first
                if await h1.count() > 0:
                    lead.name = (await h1.inner_text(timeout=4_000)).strip()
            except Exception:
                pass

            # Category
            try:
                cat = page.locator('span.css-11bijt4').first
                if await cat.count() > 0:
                    lead.category = (await cat.inner_text()).strip()
            except Exception:
                pass

            # Address
            try:
                addr_el = page.locator('address p').first
                if await addr_el.count() > 0:
                    lead.address = (await addr_el.inner_text()).strip().replace("\n", ", ")
            except Exception:
                pass

            # Phone
            try:
                phone_el = page.locator('p:has-text("(")').first
                if await phone_el.count() > 0:
                    txt = (await phone_el.inner_text()).strip()
                    if re.match(r"\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}", txt):
                        lead.phone = txt
            except Exception:
                pass

            # Website
            try:
                website_link = page.locator('a[href*="biz_redir"]').first
                if await website_link.count() > 0:
                    lead.website = (await website_link.get_attribute("href") or "").strip()
            except Exception:
                pass

            # Rating
            try:
                rating_el = page.locator('div[aria-label*="star rating"]').first
                if await rating_el.count() > 0:
                    aria = await rating_el.get_attribute("aria-label") or ""
                    nums = re.findall(r"[\d.]+", aria)
                    lead.rating = float(nums[0]) if nums else 0.0
            except Exception:
                pass

            # Review count
            try:
                rev_el = page.locator('a[href*="#reviews"] span').first
                if await rev_el.count() > 0:
                    txt = (await rev_el.inner_text()).replace(",", "").strip()
                    nums = re.findall(r"\d+", txt)
                    lead.review_count = int(nums[0]) if nums else 0
            except Exception:
                pass

        except Exception as exc:
            print(f"      ⚠ Yelp listing error: {exc}")

        return lead

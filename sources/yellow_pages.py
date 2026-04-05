"""Yellow Pages lead scraper."""
import asyncio
import re
from playwright.async_api import async_playwright, Page
from models import Lead


class YellowPagesScraper:
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
                print(f"  [Yellow Pages] Found {len(biz_urls)} listings")

                for idx, url in enumerate(biz_urls, 1):
                    lead = await self._scrape_listing(page, url)
                    if lead.name:
                        lead.source = "yellow_pages"
                        leads.append(lead)
                        print(f"    [{idx}/{len(biz_urls)}] {lead.name[:50]}")
                    await asyncio.sleep(self.delay_ms / 1_000)
            finally:
                await browser.close()

        return leads

    async def _collect_urls(self, page: Page, keyword: str, location: str, max_results: int) -> list[str]:
        urls, seen = [], set()
        pg = 1

        while len(urls) < max_results:
            search_url = (
                f"https://www.yellowpages.com/search"
                f"?search_terms={keyword.replace(' ', '+')}"
                f"&geo_location_terms={location.replace(' ', '+')}"
                f"&page={pg}"
            )
            try:
                await page.goto(search_url, timeout=20_000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2_500)
            except Exception:
                break

            anchors = await page.locator('a.business-name').all()
            new_found = 0
            for anchor in anchors:
                href = await anchor.get_attribute("href") or ""
                if href and href not in seen:
                    full = "https://www.yellowpages.com" + href if not href.startswith("http") else href
                    seen.add(href)
                    urls.append(full)
                    new_found += 1

            if new_found == 0:
                break
            pg += 1

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
                cat_el = page.locator('.categories a').first
                if await cat_el.count() > 0:
                    lead.category = (await cat_el.inner_text()).strip()
            except Exception:
                pass

            # Address
            try:
                street = page.locator('.street-address').first
                city_el = page.locator('.locality').first
                parts = []
                if await street.count() > 0:
                    parts.append((await street.inner_text()).strip())
                if await city_el.count() > 0:
                    parts.append((await city_el.inner_text()).strip())
                lead.address = ", ".join(parts)
            except Exception:
                pass

            # Phone
            try:
                phone_el = page.locator('.phone').first
                if await phone_el.count() > 0:
                    lead.phone = (await phone_el.inner_text()).strip()
            except Exception:
                pass

            # Website
            try:
                web_el = page.locator('a.website-link, a[data-analytics="website"]').first
                if await web_el.count() > 0:
                    lead.website = (await web_el.get_attribute("href") or "").strip()
            except Exception:
                pass

            # Rating
            try:
                rating_el = page.locator('.ratings .score').first
                if await rating_el.count() > 0:
                    txt = (await rating_el.inner_text()).strip()
                    lead.rating = float(txt) if txt else 0.0
            except Exception:
                pass

        except Exception as exc:
            print(f"      ⚠ YP listing error: {exc}")

        return lead

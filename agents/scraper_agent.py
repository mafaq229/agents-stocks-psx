import asyncio
from playwright.async_api import async_playwright
import json
import os
import re
from typing import Dict, Any, List

class PSXScraper:
    BASE_URL = "https://dps.psx.com.pk/company/"

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scrape_company(self, symbol: str) -> Dict[str, Any]:
        """
        Scrapes data for a specific company symbol from PSX.
        """
        url = f"{self.BASE_URL}{symbol}"
        print(f"Scraping {url}...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page(viewport={"width": 1280, "height": 800})
            
            try:
                response = await page.goto(url, timeout=60000)
                if response.status != 200:
                    return {"error": f"Failed to load page. Status: {response.status}"}

                await page.wait_for_selector(".quote__close", timeout=10000)

                # 1. Quote Data
                quote_data = {}
                try:
                    quote_data = await self._scrape_quote(page)
                except Exception as e:
                    print(f"Error scraping quote: {e}")
                
                # 2. Chart Data
                chart_svg = ""
                try:
                    chart_svg = await self._scrape_chart(page)
                except Exception as e:
                    print(f"Error scraping chart: {e}")
                
                # 3. Profile & Equity
                profile_data, equity_data = {}, {}
                try:
                    profile_data = await self._scrape_profile(page)
                    equity_data = await self._scrape_equity(page)
                except Exception as e:
                    print(f"Error scraping profile/equity: {e}")

                # 4. Financials (Annual & Quarterly)
                financials = {}
                try:
                    # Annual
                    # Try to target the Annual panel explicitly if possible, or fallback to default
                    financials["annual"] = await self._scrape_table(page, "div.tabs__panel[data-name='Annual'] table")
                    if not financials["annual"]:
                        # Fallback for default view
                        financials["annual"] = await self._scrape_table(page, "#financials table")
                except Exception as e:
                    print(f"Error scraping annual financials: {e}")

                # Quarterly
                try:
                    # Click toggle
                    toggle = page.locator("div.tabs__list__item[data-name='Quarterly']")
                    if await toggle.count() > 0:
                        await toggle.click(force=True)
                        await page.wait_for_timeout(1000)
                        
                        # Target the Quarterly Panel specifically!
                        financials["quarterly"] = await self._scrape_table(page, "div.tabs__panel[data-name='Quarterly'] table")
                    else:
                        print("Quarterly toggle not found")
                except Exception as e:
                    print(f"Could not scrape quarterly financials: {e}")

                # 5. Ratios
                ratios_data = []
                try:
                    ratio_tab = page.locator("a[href='#ratios'], a[data-link='#ratios']")
                    if await ratio_tab.count() > 0:
                        await ratio_tab.first.click(force=True)
                        await page.wait_for_timeout(1000)
                    ratios_data = await self._scrape_table(page, "#ratios table") 
                except Exception as e:
                    print(f"Error scraping ratios: {e}")

                # 6. Announcements (Sub-tabs)
                announcements = {}
                try:
                    ann_tab = page.locator("a[href='#announcements'], a[data-link='#announcements']")
                    if await ann_tab.count() > 0:
                        await ann_tab.first.click(force=True)
                        await page.wait_for_timeout(1000)

                    for tab in ["Financial Results", "Board Meetings", "Others"]:
                        try:
                            sub_tab = page.locator(f"div.tabs__list__item[data-name='{tab}']")
                            if await sub_tab.count() > 0:
                                await sub_tab.click(force=True)
                                await page.wait_for_timeout(1000)
                                
                                # Target the specific panel for this tab
                                items = await self._scrape_announcement_table(page, selector=f"div.tabs__panel[data-name='{tab}'] table")
                                announcements[tab.lower().replace(" ", "_")] = items
                            else:
                                print(f"Sub-tab {tab} not found")
                        except Exception as e:
                            print(f"Skip announcement tab {tab}: {e}")
                except Exception as e:
                    print(f"Error scraping announcements section: {e}")

                # 7. Financial Reports
                reports_data = []
                try:
                    rep_tab = page.locator("a[href='#reports'], a[data-link='#reports']")
                    if await rep_tab.count() > 0:
                        await rep_tab.first.click(force=True)
                        await page.wait_for_timeout(1000)
                    
                    reports_data = await self._scrape_documents_table(page)
                except Exception as e:
                    print(f"Error scraping reports: {e}")

                return {
                    "symbol": symbol,
                    "quote": quote_data,
                    "profile": profile_data,
                    "equity": equity_data,
                    "financials": financials,
                    "ratios": ratios_data,
                    "announcements": announcements,
                    "financial_reports": reports_data,
                    "chart_svg": chart_svg[:100] + "..." if chart_svg else None
                }
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"error": str(e)}
            finally:
                await browser.close()

    async def _scrape_quote(self, page) -> Dict[str, str]:
        try:
            price_el = await page.wait_for_selector(".quote__close", timeout=5000)
            price = await price_el.inner_text() if price_el else "N/A"
            change_el = await page.query_selector(".quote__change")
            change = await change_el.inner_text() if change_el else "N/A"
            volume = "N/A"
            try:
                vol_el = page.locator(".stats_item").filter(has_text=re.compile("Volume", re.IGNORECASE)).locator(".stats_value")
                if await vol_el.count() > 0:
                    volume = await vol_el.first.inner_text()
            except:
                pass
            return {"price": price.strip(), "change": change.strip().replace("\n", " "), "volume": volume.strip()}
        except Exception as e:
            return {}

    async def _scrape_chart(self, page) -> str:
        try:
            chart_div = await page.wait_for_selector("#companyDailyChart", timeout=3000)
            svg = await chart_div.query_selector("svg")
            return await svg.evaluate("el => el.outerHTML") if svg else ""
        except:
            return ""

    async def _scrape_table(self, page, selector) -> List[Dict[str, str]]:
        data = []
        try:
            # If selector is explicit path, use it directly
            if "table" not in selector and ".tbl" not in selector and "[" not in selector:
                selector += " table"
            
            rows = await page.locator(f"{selector} tr").all()
            if not rows and "#" in selector and " " not in selector:
                 rows = await page.locator(f"{selector} table tr").all()

            if not rows: return []

            headers = []
            header_cells = await rows[0].locator("th, td").all()
            headers = [await cell.inner_text() for cell in header_cells]
            if headers and headers[0].strip() == "":
                headers[0] = "Metric"

            for i in range(1, len(rows)):
                cells = await rows[i].locator("td").all()
                row_vals = [await cell.inner_text() for cell in cells]
                if len(row_vals) == len(headers):
                    data.append(dict(zip(headers, row_vals)))
        except Exception as e:
            pass
        return data

    async def _scrape_announcement_table(self, page, selector=None) -> List[Dict[str, str]]:
        data = []
        try:
            target_selector = selector
            if not target_selector or target_selector == ".announcements__table":
                target_selector = ".company_announcements table"
            
            rows = await page.locator(f"{target_selector} tr").all()
            
            for i in range(1, len(rows)):
                cells = await rows[i].locator("td").all()
                if len(cells) >= 2:
                    date = await cells[0].inner_text()
                    title = await cells[1].inner_text()
                    
                    link = None
                    row_links = await rows[i].locator("a").all()
                    for lnk in reversed(row_links):
                        href = await lnk.get_attribute("href")
                        if href and (".pdf" in href or "DownloadPDF" in href):
                            link = href
                            break
                    if not link and row_links:
                        link = await row_links[-1].get_attribute("href")

                    if link and not link.startswith("http"):
                        link = "https://dps.psx.com.pk" + link
                    
                    data.append({"date": date.strip(), "title": title.strip(), "url": link})
        except Exception as e:
            print(f"Error scraping ann table: {e}")
        return data

    async def _scrape_documents_table(self, page) -> List[Dict[str, str]]:
        return await self._scrape_announcement_table(page, selector="#reports table")

    async def _scrape_profile(self, page) -> Dict[str, str]:
        try:
            desc = await page.locator("#profile p").first.inner_text()
            return {"description": desc.strip()}
        except:
            return {}

    async def _scrape_equity(self, page) -> Dict[str, str]:
        data = {}
        try:
            values = await page.locator("#equity .stats_value").all_inner_texts()
            if len(values) >= 2:
                data["Market Cap"] = values[0].strip()
                data["Shares"] = values[1].strip()
        except:
            pass
        return data

if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "LSECL"
    scraper = PSXScraper(headless=True)
    result = asyncio.run(scraper.scrape_company(symbol))
    print(json.dumps(result, indent=2))

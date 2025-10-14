import aiohttp
import asyncio
import tldextract
import urllib.robotparser
import json
from bs4 import BeautifulSoup
from readability import Document
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import Tuple

class WebsiteCrawler:
    def __init__(self, start_url: str, max_pages: int = 30, crawler_delay: float = 0.5):
        self.start_url = start_url
        self.max_pages = max_pages
        self.crawler_delay = crawler_delay

        self.visited_urls = set()
        self.to_visit = asyncio.Queue()
        # use newer attribute name to avoid deprecation warning:
        self.domain = tldextract.extract(start_url).top_domain_under_public_suffix
        self.results = {}  # url -> {"html": ..., "text": ...}

        # inflight = number of URLs currently being processed by workers
        self._inflight = 0
        self._inflight_lock = asyncio.Lock()

        self.data_dir = Path("data/pages")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.set_url(robots_url)
            rp.read()
            return rp.can_fetch("*", url)
        except Exception:
            return True

    async def fetch(self, session: aiohttp.ClientSession, url: str) -> Tuple[str, str]:
        """
        Fetch the URL and return (html, clean_text).
        If anything fails or it's not HTML, returns ("", "").
        """
        try:
            async with session.get(url, timeout=15, headers={"User-Agent": "RAGCrawler/1.0"}) as resp:
                if resp.status != 200 or 'text/html' not in resp.headers.get('Content-Type', ''):
                    return "", ""
                html = await resp.text()
                # Use readability to extract main content
                doc = Document(html)
                content_html = doc.summary()
                soup = BeautifulSoup(content_html, 'html.parser')
                text = soup.get_text(separator='\n', strip=True)
                return html, text
        except Exception as e:
            # log minimally and return empty
            print(f"⚠️ fetch error for {url}: {e}")
            return "", ""

    def extract_links(self, base_url: str, html: str):
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].split('#')[0]
            if not href:
                continue
            full_url = urljoin(base_url, href)
            try:
                ext = tldextract.extract(full_url).top_domain_under_public_suffix
            except Exception:
                continue
            if ext == self.domain:
                links.add(full_url)
        return links

    async def _increment_inflight(self):
        async with self._inflight_lock:
            self._inflight += 1

    async def _decrement_inflight(self):
        async with self._inflight_lock:
            if self._inflight > 0:
                self._inflight -= 1

    async def worker(self, session: aiohttp.ClientSession, worker_id: int):
        """
        Worker consumes URLs from the queue. None is used as sentinel to stop.
        """
        while True:
            url = await self.to_visit.get()
            # sentinel => shutdown
            if url is None:
                print(f"🛑 Worker-{worker_id}: received shutdown sentinel.")
                break

            # If we've already reached max_pages before processing this URL, skip it.
            if len(self.visited_urls) >= self.max_pages:
                print(f"🛑 Worker-{worker_id}: max pages reached, skipping {url}")
                # do not re-enqueue; just continue to pick up sentinel later
                continue

            # mark as inflight
            await self._increment_inflight()
            try:
                if url in self.visited_urls:
                    print(f"🔁 Worker-{worker_id}: already visited {url}")
                    continue

                # check robots
                allowed = await self.can_fetch(url)
                if not allowed:
                    print(f"🚫 Worker-{worker_id}: disallowed by robots.txt -> {url}")
                    continue

                print(f"🔍 Worker-{worker_id}: Crawling {url}")
                html, text = await self.fetch(session, url)
                if text:
                    # store both HTML and text for citation & snippet later
                    self.results[url] = {"html": html, "text": text}
                    self.visited_urls.add(url)
                    print(f"✅ Worker-{worker_id}: stored {url} ({len(self.visited_urls)}/{self.max_pages})")
                else:
                    # Even if no text, mark visited to avoid reprocessing
                    self.visited_urls.add(url)
                    print(f"⚠️ Worker-{worker_id}: no text extracted for {url} (still counted as visited)")

                # enqueue discovered links, but keep total budget in mind
                if html and len(self.visited_urls) < self.max_pages:
                    for link in self.extract_links(url, html):
                        # quick budget check: visited + queue size < max_pages
                        if link not in self.visited_urls and (len(self.visited_urls) + self.to_visit.qsize()) < self.max_pages:
                            await self.to_visit.put(link)
            except Exception as e:
                print(f"⚠️ Worker-{worker_id}: unexpected error for {url}: {e}")
            finally:
                await self._decrement_inflight()
                # polite delay between requests
                await asyncio.sleep(self.crawler_delay)

        print(f"🛑 Worker-{worker_id} exiting.")

    async def crawl(self, n_workers: int = 3):
        # seed the queue
        await self.to_visit.put(self.start_url)

        async with aiohttp.ClientSession() as session:
            tasks = [asyncio.create_task(self.worker(session, i + 1)) for i in range(n_workers)]

            # controller loop: monitor visited count, queue, and inflight to decide when to stop
            try:
                while True:
                    await asyncio.sleep(0.5)  # polling interval

                    visited = len(self.visited_urls)
                    qsize = self.to_visit.qsize()
                    async with self._inflight_lock:
                        inflight = self._inflight

                    print(f"ℹ️ status: visited={visited}, queue={qsize}, inflight={inflight}")

                    # stop if reached page budget
                    if visited >= self.max_pages:
                        print("ℹ️ controller: reached max_pages -> initiating shutdown")
                        break

                    # if there is no queued work and no inflight work, we're done
                    if qsize == 0 and inflight == 0:
                        print("ℹ️ controller: queue empty and no inflight -> initiating shutdown")
                        break

                # send sentinel None to each worker so they shut down cleanly
                for _ in range(n_workers):
                    await self.to_visit.put(None)

                # wait for workers to finish
                await asyncio.gather(*tasks, return_exceptions=True)

            finally:
                # save results
                out_path = Path("data/crawled_data.json")
                with out_path.open("w", encoding="utf-8") as f:
                    json.dump(self.results, f, ensure_ascii=False, indent=2)
                print(f"\n✅ Crawled {len(self.results)} pages. Saved to {out_path}")
if __name__ == "__main__":
    

    start_url = "https://fastapi.tiangolo.com"   # You can change this to any site you want to test
    max_pages = 30                              # Crawl up to 3 pages (change as needed)
    crawler_delay = 0.5                          # Delay between requests (seconds)
    n_workers = 1                            # Start with 5 workers for better performance

    crawler = WebsiteCrawler(start_url, max_pages, crawler_delay)

    print("\n🚀 Starting crawler...")
    try:
        asyncio.run(crawler.crawl(n_workers=n_workers))
    except KeyboardInterrupt:
        print("\n🛑 Crawler interrupted manually.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import json
import os
import random
import re
import time
import threading
from typing import List, Dict, Optional

class AdultScraper:
    """
    A class to scrape video information from adult websites like Pornhub and XNXX.
    """
    def __init__(self, base_url: str = "https://www.xvideos.com", proxies: Optional[Dict[str, str]] = None):
        """
        Initializes the scraper with a base URL and optional proxies.
        """
        self.base_url = base_url
        self.site_type = self._detect_site_type()
        self.session = self._create_session(proxies)
        self.is_search_page = "?k=" in base_url or "/search/" in base_url or "/search?" in base_url or "brazzers.com/search" in base_url

    def _detect_site_type(self) -> str:
        """
        Detects the type of adult site based on the base URL.
        """
        if "xnxx.com" in self.base_url:
            return "xnxx"
        elif "pornhub.com" in self.base_url:
            return "pornhub"
        elif "xvideos.com" in self.base_url:
            return "xvideos"
        elif "youporn.com" in self.base_url:
            return "youporn"
        elif "brazzers.com" in self.base_url:
            return "brazzers"
        else:
            return "unknown"

    def _create_session(self, proxies: Optional[Dict[str, str]] = None) -> requests.Session:
        """
        Creates a requests session with retry logic and optional proxies.
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        if proxies:
            session.proxies.update(proxies)
            
        retries = Retry(
            total=10,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def _get_free_proxies(self) -> List[str]:
        """
        Fetches a list of free proxies from a public API.
        """
        try:
            response = requests.get("https://free-proxy-list.net/", timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            proxies = []
            table = soup.find("table", {"class": "table-striped"})
            if table:
                rows = table.find_all("tr")[1:21]  # Get first 20 proxies
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 7 and cols[4].text == "elite proxy" and cols[6].text == "yes":
                        ip = cols[0].text
                        port = cols[1].text
                        proxies.append(f"{ip}:{port}")
            return proxies
        except:
            return []

    def _test_proxy(self, proxy: str) -> bool:
        """
        Tests if a proxy works by trying to connect to httpbin.org
        """
        try:
            test_session = requests.Session()
            test_session.proxies = {"http": f"http://{proxy}", "https": f"https://{proxy}"}
            response = test_session.get("https://httpbin.org/ip", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetches the content of a URL and returns a BeautifulSoup object.
        """
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            if "timeout" in str(e).lower():
                print("Connection timed out. This may be due to network restrictions or blocking of adult content sites.")
                print("Consider using a VPN or proxy to access the site.")
            return None

    def _parse_video_page(self, video_url: str, title: str, thumbnail_url: str) -> Optional[Dict[str, str]]:
        """
        Parses a video page to extract video details.
        """
        soup = self._fetch_page(video_url)
        if not soup:
            return None

        # Use the provided thumbnail_url, or try to find one if not provided
        if not thumbnail_url:
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content') and not "blank" in og_image['content'].lower():
                thumbnail_url = og_image['content']
            else:
                twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                if twitter_image and twitter_image.get('content') and not "blank" in twitter_image['content'].lower():
                    thumbnail_url = twitter_image['content']
                else:
                    # Generic fallback: look for the first img tag that might be a thumbnail
                    # Prioritize images that are likely video thumbnails
                    main_image = soup.find('img', class_=re.compile(r'(thumbnail|poster|video-img|preview)', re.IGNORECASE), src=True)
                    if not main_image:
                        main_image = soup.find('img', src=True, alt=re.compile(r'video', re.IGNORECASE))
                    if not main_image:
                        # As a last resort, just take the first img with a decent-looking src
                        all_images = soup.find_all('img', src=True)
                        for img in all_images:
                            if "blank" not in img['src'].lower() and "pixel" not in img['src'].lower() and "logo" not in img['src'].lower():
                                thumbnail_url = img['src']
                                break
                    else:
                        thumbnail_url = main_image['src']
        
        embed_src = ""

        if self.site_type == "xnxx":
            # XNXX parsing logic
            # Title is often available directly from the listing, but can re-confirm here
            if not title: # If title wasn't passed, try to get it from video page
                title_element = soup.find('h1', class_='page-title') or soup.find('title')
                title = title_element.get_text(strip=True) if title_element else 'No Title'

            # XNXX embed URLs follow the pattern: https://www.xnxx.com/embedframe/video_id
            # First, check if this is a search result URL and convert to direct video URL
            direct_video_url = video_url
            if '/search/' in video_url and '/video-' in video_url:
                # Extract video ID from search result URL
                # Format: https://www.xnxx.com/search/keyword/video-VIDEOID/title
                video_id_match = re.search(r'/video-([a-z0-9]+)/', video_url)
                if video_id_match:
                    video_id = video_id_match.group(1)
                    # Construct direct video URL
                    title_part = video_url.split('/video-' + video_id + '/')[1].split('&')[0] if '&' in video_url.split('/video-' + video_id + '/')[1] else video_url.split('/video-' + video_id + '/')[1]
                    direct_video_url = f"https://www.xnxx.com/video{video_id}/{title_part}"

            # If we converted to direct URL, fetch that page for embed info
            if direct_video_url != video_url:
                video_soup = self._fetch_page(direct_video_url)
                if video_soup:
                    soup = video_soup

            # Extract video ID and construct embed URL
            video_id_match = re.search(r'/video([a-z0-9]+)/', direct_video_url)
            if video_id_match:
                video_id = video_id_match.group(1)
                embed_src = f"https://www.xnxx.com/embedframe/{video_id}"
            else:
                # Fallback: look for embed iframe in the page
                embed_iframe = soup.find('iframe', {'src': re.compile(r'embed')})
                if embed_iframe and embed_iframe.get('src'):
                    embed_src = embed_iframe['src']
                    if not embed_src.startswith('http'):
                        embed_src = f"https://www.xnxx.com{embed_src}" if embed_src.startswith('/') else embed_src


        elif self.site_type == "pornhub":
            # Pornhub parsing logic
            embed_iframe = soup.find('iframe', {'id': 'player'})
            if not embed_iframe:
                embed_div = soup.find('div', class_='video-embed-container')
                if embed_div and 'data-g-embed-src' in embed_div.attrs:
                     embed_src = embed_div['data-g-embed-src']
                else:
                    print(f"Could not find embed code for {video_url}")
                    return None
            else:
                embed_src = embed_iframe['src']

            if not title: # If title wasn't passed, try to get it from video page
                title_element = soup.find('h1', class_='title')
                title = title_element.get_text(strip=True) if title_element else 'No Title'
        
        elif self.site_type == "xvideos":
            if not title: # If title wasn't passed, try to get it from video page
                title_element = soup.find('h1') or soup.find('title')
                title = title_element.get_text(strip=True) if title_element else 'No Title'

            # For xvideos, construct embed URL from video URL
            # Video URL: https://www.xvideos.com/video.CODE/ID/0/title
            # Embed URL: https://www.xvideos.com/embedframe/CODE
            video_id_match = re.search(r'/video\.([a-z0-9]+)/', video_url)
            if video_id_match:
                embed_src = f"https://www.xvideos.com/embedframe/{video_id_match.group(1)}"
            else:
                # Fallback to looking for embed in page
                embed_iframe = soup.find('iframe', {'src': re.compile(r'embed')})
                if embed_iframe:
                    embed_src = embed_iframe['src']
                    if not embed_src.startswith('http'):
                        embed_src = self.base_url.rstrip('/') + embed_src

            # If no thumbnail was provided, try to find it on the video page
            if not thumbnail_url:
                # Look for script containing video data
                script_tags = soup.find_all('script', string=True)
                for script in script_tags:
                    script_text = script.string
                    # Look for thumbnail URL in script
                    thumb_match = re.search(r'"url":"([^"]*\.(?:jpg|jpeg|png|gif|webp))"', script_text)
                    if thumb_match:
                        thumb_url = thumb_match.group(1).replace('\\', '')
                        if thumb_url and 'http' in thumb_url:
                            thumbnail_url = thumb_url
                            break

                # Fallback: look for img tags with specific classes or attributes
                if not thumbnail_url:
                    thumb_img = soup.find('img', {'class': re.compile(r'thumb')}) or \
                               soup.find('img', {'alt': re.compile(r'video|preview', re.IGNORECASE)})
                    if thumb_img and thumb_img.get('src'):
                        thumbnail_url = thumb_img['src']
                        if not thumbnail_url.startswith('http'):
                            thumbnail_url = f"https://www.xvideos.com{thumbnail_url}" if thumbnail_url.startswith('/') else thumbnail_url

        elif self.site_type == "brazzers":
            if not title: # If title wasn't passed, try to get it from video page
                title_element = soup.find('h1') or soup.find('title')
                title = title_element.get_text(strip=True) if title_element else 'No Title'

            # Brazzers typically uses iframe embeds for videos
            embed_iframe = soup.find('iframe', {'src': re.compile(r'(embed|brazzers)', re.IGNORECASE)})
            if embed_iframe and embed_iframe.get('src'):
                embed_src = embed_iframe['src']
                if not embed_src.startswith('http'):
                    embed_src = self.base_url.rstrip('/') + embed_src

        elif self.site_type == "youporn":
            if not title: # If title wasn't passed, try to get it from video page
                title_element = soup.find('h1') or soup.find('title')
                title = title_element.get_text(strip=True) if title_element else 'No Title'

            # YouPorn embed URLs follow the pattern: https://www.youporn.com/embed/{video_id}
            # Extract video ID from URL
            video_id_match = re.search(r'/watch/(\d+)/', video_url)
            if video_id_match:
                video_id = video_id_match.group(1)
                embed_src = f"https://www.youporn.com/embed/{video_id}"
            else:
                # Fallback: look for embed iframe in the page
                embed_iframe = soup.find('iframe', {'src': re.compile(r'embed')})
                if embed_iframe and embed_iframe.get('src'):
                    embed_src = embed_iframe['src']
                    if not embed_src.startswith('http'):
                        embed_src = f"https://www.youporn.com{embed_src}" if embed_src.startswith('/') else embed_src

        elif self.site_type == "unknown":
            if not title: # If title wasn't passed, try to get it from video page
                title_element = soup.find('h1') or soup.find('title')
                title = title_element.get_text(strip=True) if title_element else 'No Title'

            # Look for embed iframe
            embed_iframe = soup.find('iframe', {'src': re.compile(r'embed')})
            if embed_iframe:
                embed_src = embed_iframe['src']
                if not embed_src.startswith('http'):
                    embed_src = self.base_url.rstrip('/') + embed_src


        return {
            "title": title,
            "thumbnail": thumbnail_url,
            "embed_url": embed_src,
            "video_url": video_url
        }

    def scrape_front_page(self, limit: int = 50) -> List[Dict[str, str]]:
        """
        Scrapes the front page for video information.
        """
        print(f"Fetching front page: {self.base_url}")
        front_page_soup = self._fetch_page(self.base_url)
        if not front_page_soup:
            print("Failed to fetch front page")
            return []

        videos = []
        print(f"Detected site type: {self.site_type}")

        video_thumbs_elements = []

        if self.site_type == "xnxx":
            video_thumbs_elements = front_page_soup.find_all('div', class_='thumb-block', limit=limit)
            print(f"Found {len(video_thumbs_elements)} XNXX thumb blocks")
        elif self.site_type == "pornhub":
            video_thumbs_elements = front_page_soup.find_all('a', class_='pcVideoListItemJs', limit=limit)
            print(f"Found {len(video_thumbs_elements)} Pornhub video links")
        elif self.site_type == "xvideos":
            # For XVideos, we need to find video containers that have both links and thumbnails
            if self.is_search_page:
                # Search pages have different structure - look for divs with class containing 'thumb'
                video_thumbs_elements = front_page_soup.find_all('div', class_=re.compile(r'thumb'), limit=limit)
                print(f"Found {len(video_thumbs_elements)} XVideos thumb divs on search page")
            else:
                # Front page structure
                video_thumbs_elements = front_page_soup.find_all('a', href=lambda x: x and '/video' in x and len(x) > 20, limit=limit)
                # Filter to get links with meaningful text (not just quality like "1080p")
                video_thumbs_elements = [a for a in video_thumbs_elements if len(a.get_text(strip=True)) > 10]
                print(f"Found {len(video_thumbs_elements)} XVideos video links")
        elif self.site_type == "youporn":
            video_thumbs_elements = front_page_soup.find_all('a', href=lambda x: x and '/watch' in x, limit=limit)
            print(f"Found {len(video_thumbs_elements)} YouPorn video links")
        elif self.site_type == "brazzers":
            video_thumbs_elements = front_page_soup.find_all('a', href=lambda x: x and ('/video' in x or '/scene' in x), limit=limit)
            print(f"Found {len(video_thumbs_elements)} Brazzers video links")
        else:
            video_thumbs_elements = front_page_soup.find_all('a', href=lambda x: x and ('/video' in x or '/watch' in x), limit=limit)
            print(f"Found {len(video_thumbs_elements)} generic video links")

        # Deduplicate video URLs to avoid processing the same video multiple times
        seen_urls = set()
        unique_video_data_from_listing = []

        for video_thumb_element in video_thumbs_elements:
            video_url = ""
            title = ""
            thumbnail_url = ""

            if self.site_type == "xnxx":
                link = video_thumb_element.find('a')
                if not link: continue
                href = link['href']
                video_url = href if href.startswith('http') else self.base_url + href

                title_elem = video_thumb_element.find('p', class_='title') or link.get('title')
                title = title_elem.get_text(strip=True) if hasattr(title_elem, 'get_text') else str(title_elem or '')

                img_tag = video_thumb_element.find('img')
                if img_tag and img_tag.get('data-src'): # XNXX often uses data-src for lazy loading
                    thumbnail_url = img_tag['data-src']
                elif img_tag and img_tag.get('src'):
                    thumbnail_url = img_tag['src']

            elif self.site_type == "pornhub":
                href = video_thumb_element['href']
                video_url = href if href.startswith('http') else self.base_url + href

                title = video_thumb_element.get('title') or "Unknown Title"

                img_tag = video_thumb_element.find('img')
                if img_tag and img_tag.get('data-src'): # Pornhub also uses data-src
                    thumbnail_url = img_tag['data-src']
                elif img_tag and img_tag.get('src'):
                    thumbnail_url = img_tag['src']

            elif self.site_type == "brazzers":
                href = video_thumb_element['href']
                video_url = href if href.startswith('http') else self.base_url + href

                title = video_thumb_element.get('title') or video_thumb_element.get_text(strip=True) or "Unknown Title"

                img_tag = video_thumb_element.find('img')
                if img_tag and img_tag.get('data-src'):
                    thumbnail_url = img_tag['data-src']
                elif img_tag and img_tag.get('src'):
                    thumbnail_url = img_tag['src']

            elif self.site_type == "xvideos":
                if self.is_search_page:
                    # For search pages, video_thumb_element is a div with class 'thumb'
                    # Find the link inside this div
                    link = video_thumb_element.find('a', href=lambda x: x and '/video' in x)
                    if not link:
                        continue

                    href = link['href']
                    # Handle search result URLs that have /?k=keyword/video.ID/title format
                    if "/video." in href and "?k=" in href:
                        # Extract video ID and construct proper video URL
                        video_id_match = re.search(r'/video\.([a-z0-9]+)/', href)
                        if video_id_match:
                            video_id = video_id_match.group(1)
                            video_url = f"https://www.xvideos.com/video.{video_id}/"
                        else:
                            video_url = href if href.startswith('http') else self.base_url + href
                    else:
                        video_url = href if href.startswith('http') else self.base_url + href

                    title = link.get('title') or link.get_text(strip=True) or "Unknown Title"

                    # Find thumbnail in the thumb div - XVideos uses data-src for lazy loading
                    img_tag = video_thumb_element.find('img')
                    if img_tag:
                        # XVideos uses data-src for real thumbnails, src is just placeholder
                        thumbnail_url = img_tag.get('data-src') or img_tag.get('src') or ""

                        # Ensure it's a proper thumbnail URL, not a placeholder
                        if thumbnail_url and ('lightbox-blank.gif' in thumbnail_url or 'logo' in thumbnail_url.lower()):
                            thumbnail_url = ""  # Force video page parsing for real thumbnail

                        # For XVideos, thumbnails should be absolute URLs
                        if thumbnail_url and not thumbnail_url.startswith('http'):
                            thumbnail_url = f"https://www.xvideos.com{thumbnail_url}" if thumbnail_url.startswith('/') else thumbnail_url
                    else:
                        thumbnail_url = ""  # Force video page parsing

                    # For search pages, if thumbnail is missing or is a logo/placeholder, force video page parsing
                    if not thumbnail_url or "logo" in thumbnail_url.lower() or "blank" in thumbnail_url.lower():
                        thumbnail_url = ""  # Force _parse_video_page to get the real thumbnail
                else:
                    # Front page structure - video_thumb_element is a link
                    href = video_thumb_element['href']
                    video_url = href if href.startswith('http') else self.base_url + href

                    title = video_thumb_element.get('title') or video_thumb_element.get_text(strip=True) or "Unknown Title"

                    img_tag = video_thumb_element.find('img')
                    if img_tag:
                        # Try data-src first (lazy loading), then src
                        thumbnail_url = img_tag.get('data-src') or img_tag.get('src') or ""

                        # For XVideos search pages, thumbnails might be relative or missing
                        if thumbnail_url and not thumbnail_url.startswith('http'):
                            thumbnail_url = f"https://www.xvideos.com{thumbnail_url}" if thumbnail_url.startswith('/') else thumbnail_url

                    # For search pages, if thumbnail is missing or is a logo, force video page parsing
                    if self.is_search_page and (not thumbnail_url or "logo" in thumbnail_url.lower() or "blank" in thumbnail_url.lower()):
                        thumbnail_url = ""  # Force _parse_video_page to get the real thumbnail

            elif self.site_type in ["youporn", "unknown"]:
                href = video_thumb_element['href']

                # Handle search result URLs that have /?k=keyword/video.ID/title format
                if self.is_search_page and "/video." in href and "?k=" in href:
                    # Extract video ID and construct proper video URL
                    video_id_match = re.search(r'/video\.([a-z0-9]+)/', href)
                    if video_id_match:
                        video_id = video_id_match.group(1)
                        video_url = f"https://www.xvideos.com/video.{video_id}/"
                    else:
                        video_url = href if href.startswith('http') else self.base_url + href
                else:
                    video_url = href if href.startswith('http') else self.base_url + href

                title = video_thumb_element.get('title') or video_thumb_element.get_text(strip=True) or "Unknown Title"

                img_tag = video_thumb_element.find('img')
                if img_tag and img_tag.get('data-src'):
                    thumbnail_url = img_tag['data-src']
                elif img_tag and img_tag.get('src'):
                    thumbnail_url = img_tag['src']

                # For search pages, if we couldn't get a proper thumbnail from listing, pass empty string
                # so _parse_video_page will fetch the proper thumbnail from the video page
                if self.is_search_page and thumbnail_url and ("logo" in thumbnail_url or "blank" in thumbnail_url):
                    thumbnail_url = ""  # Force _parse_video_page to get the real thumbnail


            if video_url and video_url not in seen_urls:
                seen_urls.add(video_url)
                # Ensure thumbnail_url is absolute
                if thumbnail_url and not thumbnail_url.startswith('http'):
                    thumbnail_url = f"{self.base_url.rstrip('/')}{thumbnail_url}" if thumbnail_url.startswith('/') else thumbnail_url

                # Check if the thumbnail is a known placeholder or empty
                is_placeholder_thumbnail = False
                if not thumbnail_url or \
                   "lightbox-blank.gif" in thumbnail_url or \
                   (thumbnail_url.startswith("data:image/png;base64") and len(thumbnail_url) < 100) : # Heuristic for small base64 images
                    is_placeholder_thumbnail = True

                # If it's a placeholder, force _parse_video_page to find a better one
                thumbnail_to_pass = "" if is_placeholder_thumbnail else thumbnail_url

                unique_video_data_from_listing.append({
                    "video_url": video_url,
                    "title": title,
                    "thumbnail": thumbnail_to_pass
                })

        print(f"After deduplication: {len(unique_video_data_from_listing)} unique videos to process from listings")

        for video_listing_data in unique_video_data_from_listing:
            video_data = self._parse_video_page(
                video_listing_data["video_url"],
                video_listing_data["title"],
                video_listing_data["thumbnail"]
            )
            if video_data:
                videos.append(video_data)
                print(f"Scraped: {video_data['title']}")

        return videos

    def save_to_json(self, data: List[Dict[str, str]], filename: str = "videos.json"):
        """
        Saves the scraped data to a JSON file.
        """
        with open(filename, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Scraped {len(data)} videos and saved to {filename}")

        # Automatically clean up invalid videos after saving
        removed_count = cleanup_invalid_videos(filename)
        if removed_count > 0:
            print(f"Automatically removed {removed_count} videos without valid embed URLs")

    def scrape_all_sites(self, limit_per_site: int = 50) -> List[Dict[str, str]]:
        """
        Scrapes videos from all supported adult sites and removes duplicates.
        """
        sites = [
            ("https://www.xvideos.com", "xvideos"),
            ("https://www.youporn.com", "youporn"),
            ("https://www.xnxx.com", "xnxx"),
            ("https://www.pornhub.com", "pornhub"),
            ("https://www.brazzers.com", "brazzers")
        ]

        all_videos = []
        seen_urls = set()
        seen_titles = set()

        for site_url, site_name in sites:
            print(f"\n{'='*50}")
            print(f"Starting scrape of {site_name.upper()}: {site_url}")
            print(f"{'='*50}")

            try:
                scraper = AdultScraper(base_url=site_url)
                site_videos = scraper.scrape_front_page(limit=limit_per_site)

                new_videos = 0
                for video in site_videos:
                    # Check for duplicates by URL and title
                    video_url = video.get('video_url', '')
                    video_title = video.get('title', '').lower().strip()

                    if video_url not in seen_urls and video_title not in seen_titles:
                        seen_urls.add(video_url)
                        seen_titles.add(video_title)
                        all_videos.append(video)
                        new_videos += 1

                print(f"Added {new_videos} new unique videos from {site_name}")

            except Exception as e:
                print(f"Failed to scrape {site_name}: {e}")

        print(f"\n{'='*50}")
        print(f"TOTAL: Collected {len(all_videos)} unique videos from all sites")
        print(f"{'='*50}")

        return all_videos

def shuffle_videos(filename: str = "videos.json") -> bool:
    """
    Randomly shuffle the order of videos in the JSON file.
    Returns True if successful, False otherwise.
    """
    try:
        with open(filename, "r", encoding='utf-8') as f:
            videos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Could not load {filename} for shuffling")
        return False

    if len(videos) <= 1:
        print("Not enough videos to shuffle")
        return True

    # Shuffle the videos array
    random.shuffle(videos)

    try:
        with open(filename, "w", encoding='utf-8') as f:
            json.dump(videos, f, indent=4, ensure_ascii=False)
        print(f"Successfully shuffled {len(videos)} videos")
        return True
    except Exception as e:
        print(f"Error saving shuffled videos: {e}")
        return False

def start_shuffle_scheduler():
    """
    Start a background thread that shuffles videos every 23 hours.
    """
    def shuffle_worker():
        while True:
            # Sleep for 23 hours (23 * 60 * 60 seconds)
            time.sleep(23 * 60 * 60)
            print("23 hours elapsed - shuffling videos...")
            shuffle_videos()

    # Start the shuffle thread
    shuffle_thread = threading.Thread(target=shuffle_worker, daemon=True)
    shuffle_thread.start()
    print("Video shuffle scheduler started - will shuffle every 23 hours")

def cleanup_invalid_videos(filename: str = "videos.json") -> int:
    """
    Remove videos that don't have valid embed URLs (would redirect to source site).
    Returns the number of videos removed.
    """
    try:
        with open(filename, "r", encoding='utf-8') as f:
            videos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Could not load {filename}")
        return 0

    original_count = len(videos)
    valid_videos = []

    for video in videos:
        embed_url = video.get('embed_url', '').strip()
        video_url = video.get('video_url', '').strip()

        # Keep videos that have valid embed URLs
        if embed_url and len(embed_url) > 10 and 'http' in embed_url:
            valid_videos.append(video)
        else:
            print(f"Removing video without valid embed URL: {video.get('title', 'Unknown Title')}")

    removed_count = original_count - len(valid_videos)

    if removed_count > 0:
        with open(filename, "w", encoding='utf-8') as f:
            json.dump(valid_videos, f, indent=4, ensure_ascii=False)
        print(f"Cleaned up {removed_count} videos without valid embed URLs. {len(valid_videos)} videos remaining.")

    return removed_count

def scrape_with_keyword(keyword: str, limit_per_site: int = 10) -> List[Dict[str, str]]:
    """
    Scrape videos using a specific keyword search from multiple sites.
    """
    print(f"Scraping videos for keyword: '{keyword}' from all sites")

    sites = [
        ("xnxx", f"https://www.xnxx.com/search/{keyword.replace(' ', '+')}"),
        ("xvideos", f"https://www.xvideos.com/?k={keyword.replace(' ', '+')}"),
        ("youporn", f"https://www.youporn.com/search?query={keyword.replace(' ', '+')}"),
        ("brazzers", f"https://www.brazzers.com/search?q={keyword.replace(' ', '+')}")
    ]

    all_new_videos = []

    # Load existing videos to check for duplicates
    try:
        with open("videos.json", "r", encoding='utf-8') as f:
            existing_videos = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_videos = []

    seen_urls = set(v['video_url'] for v in existing_videos)

    for site_name, search_url in sites:
        print(f"Searching {site_name.upper()} for '{keyword}'...")

        try:
            scraper = AdultScraper(base_url=search_url)
            scraped_videos = scraper.scrape_front_page(limit=limit_per_site)

            if scraped_videos:
                # Filter out duplicates
                new_videos = [v for v in scraped_videos if v['video_url'] not in seen_urls]
                if new_videos:
                    all_new_videos.extend(new_videos)
                    seen_urls.update(v['video_url'] for v in new_videos)
                    print(f"Found {len(new_videos)} new videos from {site_name}")
                else:
                    print(f"No new videos from {site_name} (all duplicates)")
            else:
                print(f"No videos found on {site_name}")

        except Exception as e:
            print(f"Error scraping {site_name}: {e}")

    if all_new_videos:
        existing_videos.extend(all_new_videos)
        with open("videos.json", "w", encoding='utf-8') as f:
            json.dump(existing_videos, f, indent=4, ensure_ascii=False)
        print(f"Total: Added {len(all_new_videos)} new videos for keyword '{keyword}' from all sites")

        # Clean up invalid videos after adding new ones
        removed_count = cleanup_invalid_videos("videos.json")
        if removed_count > 0:
            print(f"Cleaned up {removed_count} invalid videos after keyword search")

        return all_new_videos
    else:
        print(f"No new videos found for keyword '{keyword}' on any site")
        return []

if __name__ == "__main__":
    import sys

    # Check if keyword is provided as command line argument
    if len(sys.argv) > 1:
        keyword = ' '.join(sys.argv[1:])
        limit_per_site = 20  # Increased to ensure minimum 20 total results
        scrape_with_keyword(keyword, limit_per_site)
        sys.exit(0)

    # Allow user to specify different site via environment variable
    custom_site = os.environ.get("ADULT_SITE_URL")
    if custom_site:
        print(f"Using custom site: {custom_site}")
        base_url = custom_site
    else:
        base_url = "https://www.xvideos.com"

    # Example of how to use a proxy
    # You can get proxies from environment variables or define them directly
    http_proxy = os.environ.get("HTTP_PROXY")
    https_proxy = os.environ.get("HTTPS_PROXY")

    proxy_dict = None
    if http_proxy and https_proxy:
        proxy_dict = {
            "http": http_proxy,
            "https": https_proxy,
        }
        print("Using proxies from environment variables.")
    else:
        # Check if user wants to skip proxy fetching
        skip_proxy = os.environ.get("SKIP_PROXY_FETCH", "false").lower() == "true"
        if not skip_proxy:
            # Try to fetch and use free proxies if no environment proxies are set
            print("No proxies set in environment variables. Attempting to fetch free proxies...")
            scraper_temp = AdultScraper(base_url=base_url)
            proxies = scraper_temp._get_free_proxies()
            print(f"Found {len(proxies)} potential proxies. Testing...")

            working_proxy = None
            random.shuffle(proxies)  # Shuffle to try different ones
            for proxy in proxies[:5]:  # Test first 5
                print(f"Testing proxy: {proxy}")
                if scraper_temp._test_proxy(proxy):
                    working_proxy = proxy
                    print(f"Found working proxy: {proxy}")
                    break

            if working_proxy:
                proxy_dict = {
                    "http": f"http://{working_proxy}",
                    "https": f"https://{working_proxy}",
                }
                print("Using automatically found proxy.")
            else:
                print("No working free proxies found. The scraper may fail due to network restrictions.")
        else:
            print("Skipping proxy fetching as requested.")

    # Check if user wants to scrape all sites
    scrape_all = os.environ.get("SCRAPE_ALL_SITES", "false").lower() == "true"

    if scrape_all:
        print("Scraping all sites...")
        scraper = AdultScraper()  # Create instance for all sites scraping
        scraped_videos = scraper.scrape_all_sites(limit_per_site=50)
        if scraped_videos:
            scraper.save_to_json(scraped_videos)
    else:
        # Default: scrape single site
        scraper = AdultScraper(base_url=base_url, proxies=proxy_dict)
        scraped_videos = scraper.scrape_front_page()
        if scraped_videos:
            scraper.save_to_json(scraped_videos)

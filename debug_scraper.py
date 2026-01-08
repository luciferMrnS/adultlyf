#!/usr/bin/env python3

import requests
import re
from bs4 import BeautifulSoup

# Debug XVideos search page structure more thoroughly
def debug_xvideos_detailed():
    print("Detailed XVideos search page analysis...")

    url = "https://www.xvideos.com/?k=milf"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Look for thumb divs
    thumb_divs = soup.find_all('div', class_=re.compile(r'thumb'))
    print(f"Found {len(thumb_divs)} thumb divs")

    for i, div in enumerate(thumb_divs[:3]):
        print(f"\nThumb div {i+1}:")
        print(f"  Class: {div.get('class')}")
        print(f"  ID: {div.get('id')}")

        # Look for all elements inside
        link = div.find('a')
        if link:
            print(f"  Link href: {link.get('href')}")
            print(f"  Link title: {link.get('title')}")
            print(f"  Link text: {link.get_text(strip=True)[:50]}...")

        img = div.find('img')
        if img:
            print(f"  Img src: {img.get('src')}")
            print(f"  Img data-src: {img.get('data-src')}")
            print(f"  Img alt: {img.get('alt')}")

        # Look for any script tags in the div
        scripts = div.find_all('script')
        if scripts:
            print(f"  Found {len(scripts)} script tags in div")
            for j, script in enumerate(scripts):
                if script.string and len(script.string) < 200:
                    print(f"    Script {j}: {script.string[:100]}...")

    # Also check for any JSON data in scripts
    all_scripts = soup.find_all('script', string=True)
    print(f"\nTotal scripts with content: {len(all_scripts)}")

    for script in all_scripts:
        if script.string and 'thumb' in script.string.lower():
            print("Found script with 'thumb' content:")
            print(script.string[:300] + "..." if len(script.string) > 300 else script.string)
            break

if __name__ == "__main__":
    debug_xvideos_detailed()
#!/usr/bin/env python3
"""
Ghana Legal Case PDF Downloader
Downloads Supreme Court judgment PDFs from ghalii.org
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

# Configuration
BASE_URL = "https://ghalii.org"
CASES_URL = "https://ghalii.org/judgments/GHASC/?q=&sort=-date"
OUTPUT_DIR = Path("/Users/silasgah/Documents/llm/agents_project/philoagents-course/ghana-legal-ai/data/cases")
MAX_CASES = 50  # Start with 50 for testing
DELAY_SECONDS = 0.5  # Be respectful to the server

def get_case_links(page_url: str, max_cases: int = 100) -> list[dict]:
    """Extract case page links from the listing page."""
    print(f"📄 Fetching case listing from: {page_url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GhanaLegalAI/1.0"
    }
    
    response = requests.get(page_url, headers=headers)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    cases = []
    # Find all links that match the case URL pattern
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/akn/gh/judgment/ghasc/' in href and 'source' not in href:
            # Extract case info
            case_text = link.get_text(strip=True)
            if case_text and '[' in case_text:  # Valid case citation
                cases.append({
                    'url': urljoin(BASE_URL, href),
                    'title': case_text,
                    'pdf_url': urljoin(BASE_URL, href + '/source.pdf')
                })
                
        if len(cases) >= max_cases:
            break
    
    # Remove duplicates
    seen = set()
    unique_cases = []
    for case in cases:
        if case['url'] not in seen:
            seen.add(case['url'])
            unique_cases.append(case)
    
    print(f"✅ Found {len(unique_cases)} unique cases")
    return unique_cases

def download_pdf(case: dict, output_dir: Path) -> bool:
    """Download a single PDF."""
    # Create safe filename from title
    safe_title = re.sub(r'[^\w\s-]', '', case['title'])[:80]
    safe_title = re.sub(r'\s+', '_', safe_title)
    filename = f"{safe_title}.pdf"
    filepath = output_dir / filename
    
    if filepath.exists():
        print(f"⏭️  Already exists: {filename}")
        return True
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GhanaLegalAI/1.0"
    }
    
    try:
        response = requests.get(case['pdf_url'], headers=headers, timeout=30)
        if response.status_code == 200 and 'application/pdf' in response.headers.get('content-type', ''):
            filepath.write_bytes(response.content)
            print(f"✅ Downloaded: {filename} ({len(response.content) / 1024:.1f} KB)")
            return True
        else:
            print(f"❌ Failed: {filename} (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error downloading {filename}: {e}")
        return False

def main():
    """Main function to download all cases."""
    print("🇬🇭 Ghana Legal Case PDF Downloader")
    print("=" * 50)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {OUTPUT_DIR}")
    
    # Get case links
    cases = get_case_links(CASES_URL, MAX_CASES)
    
    if not cases:
        print("❌ No cases found!")
        return
    
    # Download PDFs
    print(f"\n📥 Downloading {len(cases)} PDFs...")
    successful = 0
    
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {case['title'][:60]}...")
        if download_pdf(case, OUTPUT_DIR):
            successful += 1
        time.sleep(DELAY_SECONDS)  # Be respectful
    
    print(f"\n✅ Complete! Downloaded {successful}/{len(cases)} PDFs")
    print(f"📁 Files saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()

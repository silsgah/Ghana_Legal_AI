
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Optional

# Configuration
BASE_URL = "https://ghalii.org"
CASES_URL = "https://ghalii.org/judgments/GHASC/?q=&sort=-date"

def get_case_links(page_url: str, max_cases: int = 10) -> List[Dict]:
    """Extract case page links from the listing page."""
    print(f"📄 Fetching case listing from: {page_url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GhanaLegalAI/1.0"
    }
    
    try:
        response = requests.get(page_url, headers=headers)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error fetching listing: {e}")
        return []
    
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

def download_pdf(case: dict, output_dir: Path) -> Optional[str]:
    """Download a single PDF and return filepath if successful."""
    # Create safe filename from title
    safe_title = re.sub(r'[^\w\s-]', '', case['title'])[:80]
    safe_title = re.sub(r'\s+', '_', safe_title)
    filename = f"{safe_title}.pdf"
    filepath = output_dir / filename
    
    if filepath.exists():
        print(f"⏭️  Already exists: {filename}")
        return None
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) GhanaLegalAI/1.0"
    }
    
    try:
        response = requests.get(case['pdf_url'], headers=headers, timeout=30)
        if response.status_code == 200 and 'application/pdf' in response.headers.get('content-type', ''):
            filepath.write_bytes(response.content)
            print(f"✅ Downloaded: {filename} ({len(response.content) / 1024:.1f} KB)")
            return str(filepath)
        else:
            print(f"❌ Failed: {filename} (Status: {response.status_code})")
            return None
    except Exception as e:
        print(f"❌ Error downloading {filename}: {e}")
        return None

def fetch_new_cases(output_dir: str, limit: int = 10) -> List[str]:
    """
    Main function to download new cases.
    Returns list of paths to newly downloaded files.
    """
    print(f"🚀 Job started at {datetime.now()}")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    cases = get_case_links(CASES_URL, max_cases=limit)
    
    new_files = []
    if not cases:
        print("❌ No cases found!")
        return []
    
    print(f"\n📥 Processing {len(cases)} candidates (Limit: {limit})...")
    
    for i, case in enumerate(cases, 1):
        if len(new_files) >= limit:
            print(f"🛑 Limit of {limit} new files reached.")
            break
            
        print(f"\n[{i}/{len(cases)}] {case['title'][:60]}...")
        filepath = download_pdf(case, output_path)
        if filepath:
            new_files.append(filepath)
        time.sleep(0.5)  # Be respectful
    
    print(f"\n✅ Summary: {len(new_files)} new files downloaded.")
    return new_files

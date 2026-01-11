import os
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Alternate stable URL for Ghana 1992 Constitution
PDF_URL = "https://constitutionnet.org/sites/default/files/Ghana%20Constitution.pdf"
DEST_DIR = "data/ghana_legal/constitution"
DEST_FILE = os.path.join(DEST_DIR, "Constitution_of_Ghana_1992.pdf")

def download_constitution():
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        logger.info(f"Created directory: {DEST_DIR}")

    if os.path.exists(DEST_FILE):
        logger.info(f"File already exists: {DEST_FILE}")
        return

    logger.info(f"Downloading PDF from {PDF_URL}...")
    try:
        response = requests.get(PDF_URL, timeout=30)
        response.raise_for_status()
        
        with open(DEST_FILE, "wb") as f:
            f.write(response.content)
            
        logger.info(f"✅ Downloaded: {DEST_FILE}")
    except Exception as e:
        logger.error(f"Failed to download: {e}")

if __name__ == "__main__":
    download_constitution()

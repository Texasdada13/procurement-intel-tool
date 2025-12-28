"""
RFP Document Auto-Download functionality.
Downloads and organizes RFP attachments and documents.
"""

import os
import sys
import logging
import re
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse, unquote
import requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database as db

logger = logging.getLogger(__name__)

# Document storage path
DOCUMENTS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'documents')

# Common document extensions
DOCUMENT_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.rtf', '.csv', '.zip', '.rar', '.7z'
}

# Max file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024


class DocumentDownloader:
    """Downloads and organizes RFP documents."""

    def __init__(self, base_path: str = None):
        """
        Initialize the document downloader.

        Args:
            base_path: Base path for document storage
        """
        self.base_path = base_path or DOCUMENTS_PATH
        os.makedirs(self.base_path, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_rfp_folder(self, rfp_id: int, rfp_title: str = None) -> str:
        """
        Get or create folder for an RFP's documents.

        Args:
            rfp_id: RFP database ID
            rfp_title: Optional title for folder naming

        Returns:
            Path to RFP folder
        """
        # Create sanitized folder name
        if rfp_title:
            # Clean title for folder name
            clean_title = re.sub(r'[^\w\s-]', '', rfp_title)[:50]
            clean_title = re.sub(r'\s+', '_', clean_title)
            folder_name = f"{rfp_id}_{clean_title}"
        else:
            folder_name = str(rfp_id)

        folder_path = os.path.join(self.base_path, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        return folder_path

    def get_filename_from_response(self, response: requests.Response, url: str) -> str:
        """
        Extract filename from response headers or URL.

        Args:
            response: HTTP response
            url: Request URL

        Returns:
            Suggested filename
        """
        # Try Content-Disposition header
        cd = response.headers.get('Content-Disposition', '')
        if cd:
            match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', cd)
            if match:
                filename = match.group(1).strip('"\'')
                return unquote(filename)

        # Fall back to URL path
        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = os.path.basename(path)

        if filename:
            return filename

        # Generate from content type
        content_type = response.headers.get('Content-Type', '')
        ext_map = {
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'application/zip': '.zip',
            'text/plain': '.txt',
        }

        for ct, ext in ext_map.items():
            if ct in content_type:
                return f"document{ext}"

        return 'document'

    def is_document_url(self, url: str) -> bool:
        """
        Check if URL likely points to a document.

        Args:
            url: URL to check

        Returns:
            True if likely a document URL
        """
        parsed = urlparse(url)
        path = parsed.path.lower()

        # Check extension
        _, ext = os.path.splitext(path)
        if ext in DOCUMENT_EXTENSIONS:
            return True

        # Check for common document paths
        doc_patterns = [
            '/download/', '/attachment/', '/document/', '/file/',
            '/getfile', '/docview', '/blob/', '/files/'
        ]
        for pattern in doc_patterns:
            if pattern in path.lower():
                return True

        return False

    def download_document(self, url: str, save_folder: str,
                          filename: str = None) -> Optional[Dict]:
        """
        Download a document from URL.

        Args:
            url: Document URL
            save_folder: Folder to save document
            filename: Optional specific filename

        Returns:
            Document info dict or None if failed
        """
        try:
            # Make request with stream for large files
            response = self.session.get(url, stream=True, timeout=60, allow_redirects=True)
            response.raise_for_status()

            # Check file size
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_FILE_SIZE:
                logger.warning(f"File too large: {url}")
                return None

            # Get filename
            if not filename:
                filename = self.get_filename_from_response(response, url)

            # Ensure unique filename
            filepath = os.path.join(save_folder, filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(filepath):
                filename = f"{base}_{counter}{ext}"
                filepath = os.path.join(save_folder, filename)
                counter += 1

            # Download and save
            total_size = 0
            hasher = hashlib.md5()

            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        hasher.update(chunk)
                        total_size += len(chunk)

                        if total_size > MAX_FILE_SIZE:
                            f.close()
                            os.remove(filepath)
                            logger.warning(f"File exceeded max size during download: {url}")
                            return None

            logger.info(f"Downloaded: {filename} ({total_size:,} bytes)")

            return {
                'filename': filename,
                'filepath': filepath,
                'url': url,
                'size': total_size,
                'md5': hasher.hexdigest(),
                'content_type': response.headers.get('Content-Type'),
                'downloaded_at': datetime.now().isoformat()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download {url}: {e}")
            return None

    def extract_document_links(self, html_content: str, base_url: str) -> List[str]:
        """
        Extract document links from HTML content.

        Args:
            html_content: Page HTML
            base_url: Base URL for resolving relative links

        Returns:
            List of document URLs
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, 'html.parser')
        links = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)

            if self.is_document_url(full_url):
                links.append(full_url)

        # Also check for direct file references
        for pattern in [r'href=["\']([^"\']+\.(pdf|doc|docx|xls|xlsx|zip))["\']',
                        r'src=["\']([^"\']+\.(pdf|doc|docx|xls|xlsx|zip))["\']']:
            for match in re.finditer(pattern, html_content, re.IGNORECASE):
                url = urljoin(base_url, match.group(1))
                if url not in links:
                    links.append(url)

        return links

    def download_rfp_documents(self, rfp_id: int, force: bool = False) -> Dict:
        """
        Download all documents for an RFP.

        Args:
            rfp_id: RFP database ID
            force: Force re-download even if documents exist

        Returns:
            Download statistics
        """
        rfp = db.get_rfp(rfp_id)
        if not rfp:
            return {'error': 'RFP not found', 'downloaded': 0}

        folder = self.get_rfp_folder(rfp_id, rfp.get('title'))

        # Check for existing downloads
        if not force and os.listdir(folder):
            return {
                'skipped': True,
                'message': 'Documents already downloaded',
                'folder': folder
            }

        stats = {
            'downloaded': 0,
            'failed': 0,
            'documents': [],
            'folder': folder
        }

        # Download from attachments URL if available
        if rfp.get('attachments_url'):
            urls_to_try = [rfp['attachments_url']]
        elif rfp.get('source_url'):
            # Fetch the RFP page and extract document links
            try:
                response = self.session.get(rfp['source_url'], timeout=30)
                urls_to_try = self.extract_document_links(response.text, rfp['source_url'])
            except Exception as e:
                logger.error(f"Failed to fetch RFP page: {e}")
                urls_to_try = []
        else:
            urls_to_try = []

        # Download each document
        for url in urls_to_try:
            doc = self.download_document(url, folder)
            if doc:
                stats['downloaded'] += 1
                stats['documents'].append(doc)
            else:
                stats['failed'] += 1

        return stats

    def download_all_rfp_documents(self, status: str = 'open',
                                    relevant_only: bool = True) -> Dict:
        """
        Download documents for all matching RFPs.

        Args:
            status: RFP status filter
            relevant_only: Only download for relevant RFPs

        Returns:
            Overall download statistics
        """
        rfps = db.get_all_rfps(status=status, relevant_only=relevant_only)

        overall_stats = {
            'total_rfps': len(rfps),
            'processed': 0,
            'total_downloaded': 0,
            'total_failed': 0,
            'errors': []
        }

        for rfp in rfps:
            try:
                stats = self.download_rfp_documents(rfp['id'])
                overall_stats['processed'] += 1
                overall_stats['total_downloaded'] += stats.get('downloaded', 0)
                overall_stats['total_failed'] += stats.get('failed', 0)
            except Exception as e:
                overall_stats['errors'].append({
                    'rfp_id': rfp['id'],
                    'error': str(e)
                })

        return overall_stats

    def get_rfp_documents(self, rfp_id: int) -> List[Dict]:
        """
        Get list of downloaded documents for an RFP.

        Args:
            rfp_id: RFP database ID

        Returns:
            List of document info dicts
        """
        rfp = db.get_rfp(rfp_id)
        if not rfp:
            return []

        folder = self.get_rfp_folder(rfp_id, rfp.get('title'))

        if not os.path.exists(folder):
            return []

        documents = []
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                documents.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        return documents


def download_rfp_documents(rfp_id: int) -> Dict:
    """Convenience function to download documents for an RFP."""
    downloader = DocumentDownloader()
    return downloader.download_rfp_documents(rfp_id)


def download_all_documents() -> Dict:
    """Convenience function to download all RFP documents."""
    downloader = DocumentDownloader()
    return downloader.download_all_rfp_documents()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("RFP Document Downloader")
    print(f"Storage path: {DOCUMENTS_PATH}")

    # Test download for first open RFP
    rfps = db.get_open_rfps(relevant_only=True)
    if rfps:
        print(f"\nTesting download for RFP: {rfps[0]['title'][:50]}...")
        result = download_rfp_documents(rfps[0]['id'])
        print(f"Result: {result}")
    else:
        print("\nNo open RFPs found to test with.")

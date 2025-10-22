"""
downloader.py - File Download Module
"""
import os
import re
import requests
import tempfile
import math
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Timeouts
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 1800  # 30 minutes for large files

# Chunk size for streaming (8KB)
CHUNK_SIZE = 8192


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing illegal characters.
    Prevents path traversal and other file system attacks.
    """
    # Remove path separators and other dangerous characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = "downloaded_file"
    
    # Limit filename length (255 is max on most systems)
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename


def extract_filename_from_url(url: str) -> str:
    """Extract and sanitize filename from URL."""
    # Get the last part of the path
    path_parts = url.split('/')
    filename = path_parts[-1] if path_parts else "downloaded_file"
    
    # Remove query parameters
    filename = filename.split('?')[0]
    
    # Fallback if empty
    if not filename or filename == '':
        filename = "downloaded_file"
    
    return sanitize_filename(filename)


def extract_filename_from_headers(headers: dict) -> Optional[str]:
    """
    Try to extract filename from Content-Disposition header.
    Returns None if not found.
    """
    content_disposition = headers.get('Content-Disposition', '')
    if not content_disposition:
        return None
    
    # Look for filename*= or filename= patterns
    matches = re.findall(r'filename\*?=(["\']?)(.+?)\1(?:;|$)', content_disposition)
    if matches:
        filename = matches[0][1]
        # Remove encoding prefix if present (e.g., UTF-8'')
        if "''" in filename:
            filename = filename.split("''", 1)[1]
        return sanitize_filename(filename)
    
    return None


def download_file(
    url: str,
    progress_callback: Optional[Callable[[int], None]] = None,
    timeout: int = READ_TIMEOUT
) -> str:
    """
    Download file from URL with progress tracking.
    
    Args:
        url: The download URL
        progress_callback: Optional callback function(percent: int)
        timeout: Read timeout in seconds
        
    Returns:
        Path to the downloaded file
        
    Raises:
        requests.exceptions.Timeout: On timeout
        requests.exceptions.RequestException: On other request errors
        ValueError: On invalid response
    """
    logger.info(f"Starting download from: {url}")
    
    # Prepare timeout tuple (connect, read)
    full_timeout = (CONNECT_TIMEOUT, timeout)
    
    try:
        # Send HEAD request first to get Content-Length and filename
        head_response = requests.head(
            url,
            timeout=(CONNECT_TIMEOUT, 10),
            allow_redirects=True
        )
        
        # Try to get filename from headers, fallback to URL
        filename = extract_filename_from_headers(head_response.headers)
        if not filename:
            filename = extract_filename_from_url(url)
        
        # Get file size if available
        total_size = int(head_response.headers.get('Content-Length', 0))
        if total_size > 0:
            logger.info(f"File size: {total_size / (1024**2):.2f} MB")
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"HEAD request failed, proceeding with GET: {e}")
        filename = extract_filename_from_url(url)
        total_size = 0
    
    # Create temp file path
    temp_dir = tempfile.gettempdir()
    local_path = os.path.join(temp_dir, filename)
    
    # Ensure temp directory exists
    os.makedirs(temp_dir, exist_ok=True)
    
    # Download the file
    try:
        with requests.get(
            url,
            stream=True,
            timeout=full_timeout,
            allow_redirects=True
        ) as response:
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Update total size if not found in HEAD request
            if total_size == 0:
                total_size = int(response.headers.get('Content-Length', 0))
            
            # Download and write to file
            received = 0
            last_percent = -1
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        received += len(chunk)
                        
                        # Update progress
                        if progress_callback and total_size > 0:
                            current_percent = math.floor(received / total_size * 100)
                            if current_percent > last_percent:
                                progress_callback(current_percent)
                                last_percent = current_percent
            
            # Ensure 100% callback
            if progress_callback and total_size > 0 and last_percent < 100:
                progress_callback(100)
            
            logger.info(f"Download complete: {local_path} ({received / (1024**2):.2f} MB)")
            return local_path
    
    except requests.exceptions.Timeout as e:
        logger.error(f"Download timeout for {url}: {e}")
        # Clean up partial file
        if os.path.exists(local_path):
            os.remove(local_path)
        raise TimeoutError(
            f"Download timed out after {timeout}s. "
            "The server may be slow or the file too large."
        ) from e
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error downloading {url}: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise ValueError(f"HTTP error: {e.response.status_code} - {e.response.reason}") from e
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error downloading {url}: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise ConnectionError("Failed to connect to the server. Check the URL and try again.") from e
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error downloading {url}: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise RuntimeError(f"Download failed: {str(e)}") from e
    
    except OSError as e:
        logger.error(f"File system error: {e}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise OSError(f"Failed to write file: {str(e)}") from e
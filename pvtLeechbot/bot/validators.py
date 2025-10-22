"""
validators.py - Input Validation and Rate Limiting
"""
import time
import logging
from urllib.parse import urlparse
from typing import Tuple

logger = logging.getLogger(__name__)

# Rate limiting: Track last request time per user
user_last_request = {}
REQUEST_COOLDOWN = 10  # seconds between requests per user

# Optional: Allowed domains whitelist (uncomment to enable)
# ALLOWED_DOMAINS = [
#     'drive.google.com',
#     'dropbox.com',
#     'mega.nz',
#     'mediafire.com',
#     'wetransfer.com',
#     'gofile.io',
# ]


def is_valid_url(url: str) -> Tuple[bool, str]:
    """
    Validate URL for security and format.
    
    Args:
        url: The URL to validate
        
    Returns:
        Tuple of (is_valid: bool, error_message: str)
        If valid, error_message will be empty string
    """
    try:
        parsed = urlparse(url)
        
        # Check for valid HTTP/HTTPS scheme
        if parsed.scheme not in ['http', 'https']:
            return False, "❌ Only HTTP/HTTPS URLs are allowed"
        
        # Check for valid network location (domain)
        if not parsed.netloc:
            return False, "❌ Invalid URL format"
        
        # Check for suspicious characters that could indicate injection
        if any(char in url for char in ['<', '>', '"', "'"]):
            return False, "❌ URL contains invalid characters"
        
        # Optional: Whitelist domain checking (uncomment to enable)
        # domain = parsed.netloc.lower()
        # if not any(allowed in domain for allowed in ALLOWED_DOMAINS):
        #     allowed_list = ', '.join(ALLOWED_DOMAINS)
        #     return False, f"❌ Domain not allowed. Supported: {allowed_list}"
        
        return True, ""
    
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False, "❌ Invalid URL format"


def check_rate_limit(user_id: int) -> Tuple[bool, int]:
    """
    Check if user is rate limited.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        Tuple of (is_allowed: bool, seconds_to_wait: int)
        If allowed, seconds_to_wait will be 0
    """
    current_time = time.time()
    last_time = user_last_request.get(user_id, 0)
    time_passed = current_time - last_time
    
    if time_passed < REQUEST_COOLDOWN:
        wait_time = int(REQUEST_COOLDOWN - time_passed)
        logger.info(f"User {user_id} rate limited. Wait: {wait_time}s")
        return False, wait_time
    
    # Update last request time
    user_last_request[user_id] = current_time
    return True, 0
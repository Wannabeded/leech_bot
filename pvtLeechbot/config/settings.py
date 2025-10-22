"""
config/settings.py - Bot Configuration
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Bot Token from BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

# Dump Channel ID (where files are stored before sending to user)
DUMP_CHANNEL_ID = os.getenv("DUMP_CHANNEL_ID")
if not DUMP_CHANNEL_ID:
    raise ValueError("DUMP_CHANNEL_ID not found in environment variables!")

# Convert to integer if it's numeric
try:
    DUMP_CHANNEL_ID = int(DUMP_CHANNEL_ID)
except ValueError:
    # It's a username like @channel_name, keep as string
    pass

# File size limit (2GB in bytes)
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

# Rate limiting
REQUEST_COOLDOWN = 10  # seconds between requests per user

# Download timeouts
CONNECT_TIMEOUT = 30  # seconds to establish connection
READ_TIMEOUT = 1800  # seconds for download (30 minutes)

# Thread pool settings
MAX_WORKERS = 3  # Maximum concurrent downloads
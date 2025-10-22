#!/bin/bash

# Navigate to the script directory (so it works from anywhere)
cd "$(dirname "$0")"

# Activate the virtual environment
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Virtual environment not found! Please create one first."
    exit 1
fi

# Load environment variables from .env
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo ".env file not found! Please create one with BOT_TOKEN and other settings."
fi

# Start the bot
echo "Starting Telegram bot..."
python3 main.py

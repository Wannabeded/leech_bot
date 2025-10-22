"""
handlers.py - Bot Command and Message Handlers
"""
import os
import asyncio
import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters, 
    ContextTypes
)
from telegram.error import RetryAfter, TelegramError
from bot.downloader import download_file
from bot.validators import is_valid_url, check_rate_limit
from config.settings import DUMP_CHANNEL_ID, MAX_FILE_SIZE
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for concurrent downloads
executor = ThreadPoolExecutor(max_workers=3)

# Throttling for progress updates
last_update_time = {}
MIN_EDIT_DELAY = 2.0  # seconds between progress edits


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome_message = (
        "👋 **Welcome to File Download Bot!**\n\n"
        "Send me a direct download link and I'll:\n"
        "✅ Download the file\n"
        "✅ Let you choose format (Document/Video)\n"
        "✅ Upload it to you\n\n"
        "⚠️ Limits:\n"
        "• Max file size: 2GB\n"
        "• Cooldown: 10 seconds between requests\n\n"
        "Just send a link to get started!"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming download links."""
    user_message = update.message.text.strip()
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id

    # Validate URL format
    is_valid, error_msg = is_valid_url(user_message)
    if not is_valid:
        await update.message.reply_text(error_msg)
        return

    # Check rate limiting
    is_allowed, wait_time = check_rate_limit(user_id)
    if not is_allowed:
        await update.message.reply_text(
            f"⏳ Please wait {wait_time} seconds before sending another request."
        )
        return

    # Store URL in user context for later use
    context.user_data['download_url'] = user_message
    
    # Ask user for format preference
    keyboard = [
        [
            InlineKeyboardButton("📄 Document", callback_data="format_document"),
            InlineKeyboardButton("🎬 Video", callback_data="format_video")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "How would you like to receive this file?",
        reply_markup=reply_markup
    )


async def handle_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's format selection (document or video)."""
    query = update.callback_query
    await query.answer()
    
    # Get the selected format
    format_type = query.data.split('_')[1]  # 'document' or 'video'
    download_url = context.user_data.get('download_url')
    
    if not download_url:
        await query.edit_message_text("❌ Session expired. Please send the link again.")
        return
    
    chat_id = query.message.chat_id
    status_msg = await query.edit_message_text("⏳ Starting download...")
    msg_key = f"{chat_id}_{status_msg.message_id}"
    
    loop = asyncio.get_running_loop()

    def progress_callback(percent: int):
        """Update download progress with throttling."""
        current_time = time.time()
        
        if current_time - last_update_time.get(msg_key, 0) < MIN_EDIT_DELAY and percent < 100:
            return

        last_update_time[msg_key] = current_time

        async def edit_status():
            try:
                bar_length = 20
                filled = int(bar_length * percent / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"⏳ Downloading...\n\n{bar} {percent}%"
                )
            except RetryAfter as e:
                logger.warning(f"Throttled during progress: Retry in {e.retry_after}s")
            except TelegramError:
                pass  # Ignore "message not modified" errors
        
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(edit_status(), loop)

    local_path = None
    try:
        # Download file in thread pool
        local_path = await loop.run_in_executor(
            executor,
            download_file,
            download_url,
            progress_callback
        )

        # Check file size
        file_size = os.path.getsize(local_path)
        if file_size > MAX_FILE_SIZE:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"❌ File too large ({file_size / (1024**3):.2f} GB). Max: 2GB"
            )
            return

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="✅ Download complete. Uploading to dump channel..."
        )

        # Upload to dump channel
        with open(local_path, "rb") as f:
            if format_type == "video":
                sent_message = await context.bot.send_video(
                    chat_id=DUMP_CHANNEL_ID,
                    video=f,
                    supports_streaming=True
                )
            else:
                sent_message = await context.bot.send_document(
                    chat_id=DUMP_CHANNEL_ID,
                    document=f
                )
        
        logger.info(f"File sent to dump channel as {format_type}")

        # Send to user using file_id
        file_id = sent_message.video.file_id if format_type == "video" else sent_message.document.file_id
        
        if format_type == "video":
            await query.message.reply_video(video=file_id)
        else:
            await query.message.reply_document(document=file_id)
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✅ Done! File sent as {format_type}."
        )

    except RetryAfter as e:
        error_text = f"⏳ Telegram rate limit hit. Please wait {e.retry_after} seconds and try again."
        logger.error(f"Flood control: {error_text}")
        await query.message.reply_text(error_text)
        
    except FileNotFoundError:
        error_text = "❌ Download failed: File not found at URL"
        logger.error(error_text)
        await query.message.reply_text(error_text)
        
    except TimeoutError:
        error_text = "❌ Download timeout. The server is too slow or file is too large."
        logger.error(error_text)
        await query.message.reply_text(error_text)
        
    except Exception as e:
        error_text = f"❌ An error occurred: {str(e)[:100]}"
        logger.error(f"Error processing {download_url}: {e}", exc_info=True)
        await query.message.reply_text(error_text)

    finally:
        # Clean up temp file
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
                logger.info(f"Cleaned up: {local_path}")
            except OSError as e:
                logger.warning(f"Failed to remove {local_path}: {e}")
        
        # Clear user data
        context.user_data.pop('download_url', None)


def register_handlers(app):
    """Register all command and message handlers."""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_format_selection, pattern="^format_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


def cleanup_executor():
    """Gracefully shutdown the thread pool."""
    logger.info("Shutting down thread pool executor...")
    executor.shutdown(wait=True, cancel_futures=False)
    logger.info("Thread pool executor shut down.")
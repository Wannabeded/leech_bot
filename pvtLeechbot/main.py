"""
main.py - Bot Entry Point
"""
from telegram.ext import ApplicationBuilder
from telegram.request import HTTPXRequest
from config.settings import BOT_TOKEN
from bot.handlers import register_handlers, cleanup_executor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the Telegram bot."""
    # Increase timeout for handling large file downloads
    request = HTTPXRequest(
        read_timeout=600,
        connect_timeout=60
    )

    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()
    register_handlers(app)

    logger.info("🚀 Bot started polling...")
    try:
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Received shutdown signal...")
    finally:
        # Gracefully shut down resources
        logger.info("🧹 Cleaning up resources...")
        cleanup_executor()
        logger.info("✅ Bot stopped gracefully.")


if __name__ == "__main__":
    main()
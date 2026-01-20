"""Main entry point for xert-poller."""

import asyncio
import logging
import signal
import sys

from .config import get_settings
from .poller import run_poller


def setup_logging(level: str) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from aiohttp
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def main() -> None:
    """Main entry point."""
    try:
        settings = get_settings()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("\nRequired environment variables:", file=sys.stderr)
        print("  XERT_USERNAME - Xert account email", file=sys.stderr)
        print("  XERT_PASSWORD - Xert account password", file=sys.stderr)
        print("  XERT_HA_WEBHOOK_ID - Home Assistant webhook ID", file=sys.stderr)
        print("\nOptional environment variables:", file=sys.stderr)
        print("  XERT_HA_URL - Home Assistant URL (default: http://homeassistant:8123)", file=sys.stderr)
        print("  XERT_HA_TOKEN - Home Assistant access token", file=sys.stderr)
        print("  XERT_TRAINING_INFO_INTERVAL - Training info poll interval (default: 900)", file=sys.stderr)
        print("  XERT_ACTIVITIES_INTERVAL - Activities poll interval (default: 900)", file=sys.stderr)
        print("  XERT_LOOKBACK_DAYS - Days of activity history (default: 90)", file=sys.stderr)
        print("  XERT_LOG_LEVEL - Logging level (default: INFO)", file=sys.stderr)
        sys.exit(1)

    setup_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Starting xert-poller")
    logger.info("  HA URL: %s", settings.ha_url)
    logger.info("  Training info interval: %ds", settings.training_info_interval)
    logger.info("  Activities interval: %ds", settings.activities_interval)
    logger.info("  Lookback days: %d", settings.lookback_days)

    # Set up signal handlers for graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal(sig: signal.Signals) -> None:
        logger.info("Received signal %s, shutting down...", sig.name)
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        loop.run_until_complete(run_poller(settings))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        loop.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()

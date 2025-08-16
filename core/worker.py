# core/worker.py
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.engine import engine
from config.logging import setup_logging
from config.settings import settings

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    asyncio.create_task(shutdown())

async def shutdown():
    """Graceful shutdown"""
    logger.info("Shutting down JobAgent worker...")
    await engine.stop()
    sys.exit(0)

async def main():
    """Main worker function"""
    logger.info("Starting JobAgent worker...")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start the engine
        await engine.start()
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check if we're in worker mode
    if not settings.worker_mode:
        logger.error("Worker mode not enabled. Set WORKER_MODE=true in environment.")
        sys.exit(1)
    
    # Run the worker
    asyncio.run(main())

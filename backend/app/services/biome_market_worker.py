"""
Biome Market Background Worker
Handles periodic attention-based redistribution
"""

import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.services.biome_market_service import biome_market_service
from app.services.websocket_service import connection_manager

logger = logging.getLogger(__name__)


class BiomeMarketWorker:
    """Background worker for periodic market redistribution."""

    def __init__(self, interval_seconds: float = 0.5):
        """
        Initialize worker.
        
        Args:
            interval_seconds: Time between redistribution cycles (default 0.5s)
        """
        self.interval_seconds = interval_seconds
        self.running = False
        self.task = None

    async def redistribution_cycle(self):
        """Execute single redistribution cycle."""
        async with AsyncSessionLocal() as db:
            try:
                result = await biome_market_service.execute_redistribution(db)
                
                if result["redistributed"]:
                    logger.info(
                        f"Redistribution cycle complete: "
                        f"TMC={result['total_market_cash']}, "
                        f"Pool={result['pool']}, "
                        f"Attention={result['total_attention']}"
                    )

                    # Broadcast market update to subscribers
                    message = {
                        "type": "biome_market_update",
                        "timestamp": datetime.utcnow().isoformat(),
                        "markets": result.get("markets", []),
                        "redistributions": result.get("redistributions", {}),
                        "total_market_cash": result.get("total_market_cash"),
                        "pool": result.get("pool"),
                        "total_attention": result.get("total_attention")
                    }

                    await connection_manager.broadcast_to_room(message, "biome_market_all")

                    # Broadcast per-biome rooms
                    for biome_key, data in result.get("redistributions", {}).items():
                        await connection_manager.broadcast_to_room({
                            **message,
                            "biome": biome_key,
                            "redistribution": data
                        }, f"biome_market:{biome_key}")
                else:
                    logger.debug(f"Redistribution skipped: {result.get('reason', 'unknown')}")
                    
            except Exception as e:
                logger.error(f"Error in redistribution cycle: {e}", exc_info=True)

    async def run(self):
        """Main worker loop."""
        logger.info(f"Starting biome market worker (interval={self.interval_seconds}s)")
        self.running = True

        while self.running:
            try:
                await self.redistribution_cycle()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                logger.info("Biome market worker cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                await asyncio.sleep(self.interval_seconds)

        logger.info("Biome market worker stopped")

    def start(self):
        """Start the background worker."""
        if not self.running:
            self.task = asyncio.create_task(self.run())
            logger.info("Biome market worker started")

    async def stop(self):
        """Stop the background worker."""
        if self.running:
            logger.info("Stopping biome market worker...")
            self.running = False
            
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Biome market worker stopped")


# Global worker instance
biome_market_worker = BiomeMarketWorker(interval_seconds=0.5)


@asynccontextmanager
async def lifespan(app):
    """FastAPI lifespan context manager for worker lifecycle."""
    # Startup
    logger.info("Initializing biome markets...")
    async with AsyncSessionLocal() as db:
        await biome_market_service.initialize_markets(db)
    
    # Start worker
    biome_market_worker.start()
    
    yield
    
    # Shutdown
    await biome_market_worker.stop()

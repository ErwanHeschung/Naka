import asyncio

from configs.config_manager import config
from engines.gemini_live_engine import GeminiLiveEngine
from registry import CommandRegistry
from utils.logger import log


async def main() -> None:
    log.info(f"Starting {config.ai.assistant.name}")

    reg = CommandRegistry()
    reg.discover()

    engine = GeminiLiveEngine(reg)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())

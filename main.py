import asyncio

from commands.light_control import LightControl
from commands.system_info import SystemInfo
from commands.weather import Weather
from configs.config_manager import config
from engines.gemini_live_engine import GeminiLiveEngine
from registry import CommandRegistry
from utils.logger import log


async def main() -> None:
    log.info(f"Starting {config.ai.assistant.name}")

    reg = CommandRegistry()
    reg.register(LightControl())
    reg.register(SystemInfo())
    reg.register(Weather())

    engine = GeminiLiveEngine(reg)
    await engine.run()


if __name__ == "__main__":
    asyncio.run(main())

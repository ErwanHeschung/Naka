import os
import tomllib
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AssistantConfig(BaseModel):
    name: str
    wake_word: str
    language: str
    gemini_voice: str
    wake_word_threshold: float = 0.6


class PersonalityConfig(BaseModel):
    role: str
    style: str
    instructions: str


class AIConfig(BaseModel):
    assistant: AssistantConfig
    personality: PersonalityConfig


class GeminiConfig(BaseModel):
    model: str = "gemini-3.1-flash-live-preview"
    api_key: str = ""


class AudioConfig(BaseModel):
    input_device: int | None = None
    output_device: int | None = None
    chunk_size: int = 1280
    inactivity_timeout: float = 15.0


class InfraConfig(BaseModel):
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)


class ConfigManager:
    ai: AIConfig
    infra: InfraConfig
    root: Path

    def __init__(self) -> None:
        current_file = Path(__file__).resolve()
        base_dir = Path(__file__).parent.absolute()

        self.root = next(
            (p for p in current_file.parents
             if (p / ".git").exists() or (p / "pyproject.toml").exists()),
            base_dir,
        )

        load_dotenv(self.root / ".env")

        self.ai = AIConfig(**self._load_toml(base_dir / "ai_config.toml"))

        raw_infra = self._load_toml(base_dir / "infra_config.toml")
        raw_infra.setdefault("gemini", {})
        if not raw_infra["gemini"].get("api_key"):
            raw_infra["gemini"]["api_key"] = os.environ.get("GEMINI_API_KEY", "")
        self.infra = InfraConfig(**raw_infra)

    @staticmethod
    def _load_toml(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"Config file missing: {path}")
        with open(path, "rb") as f:
            return tomllib.load(f)


config = ConfigManager()

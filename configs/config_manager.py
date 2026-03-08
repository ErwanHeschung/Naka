import tomllib
from pathlib import Path

class ConfigManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent.absolute()
        self.ai = self._load_toml(self.base_dir / "ai_config.toml")
        self.infra = self._load_toml(self.base_dir / "infra_config.toml")
        
        current_file = Path(__file__).resolve()
        self.root = next(
            (p for p in current_file.parents if (p / ".git").exists() or (p / "pyproject.toml").exists()),
            current_file.parent
        )

    def _load_toml(self, filename: str):
        path = Path(filename)
        if not path.exists():
            raise FileNotFoundError(f"Critical Error: {filename} missing!")
        with open(path, "rb") as f:
            return tomllib.load(f)

config = ConfigManager()
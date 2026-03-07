from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any, Dict

class CommandArguments(BaseModel):
    """Container for validated tool arguments."""
    args: Dict[str, Any]

class BaseCommand(ABC):
    """Abstract Base Class for all AI-executable commands."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The unique identifier of the command for the LLM."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Clear instructions for the LLM on what this tool does."""
        pass

    @abstractmethod
    def execute(self, cmd_args: CommandArguments) -> str:
        """The logic to perform the action and return a status message."""
        pass
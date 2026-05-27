from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class CommandArguments(BaseModel):
    args: dict[str, Any]


class BaseCommand(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema for the command parameters."""
        pass

    @abstractmethod
    def execute(self, cmd_args: CommandArguments) -> str:
        pass

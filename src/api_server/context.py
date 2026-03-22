from dataclasses import dataclass

from ..backend.config import Config
from ..backend.database import Database

@dataclass
class ApplicationContext:
    database: Database
    config: Config

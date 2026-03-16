from dataclasses import dataclass

from ..backend.database import Database

@dataclass
class ApplicationContext:
    database: Database

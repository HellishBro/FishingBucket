import json
import os
from pathlib import Path
from typing import Any


class DataReader:
    instance: DataReader

    def __init__(self, data_directory: str):
        DataReader.instance = self
        self.data_directory = Path(data_directory)
        self.loaded_files: dict[str, Any] = {}
        self.load_data()

    def load_data(self):
        self.loaded_files = {}
        for file in os.listdir(self.data_directory):
            with open(self.data_directory / file) as f:
                if file.endswith(".json"):
                    self.loaded_files[file] = json.loads(f.read())
                else:
                    self.loaded_files[file] = f.read()

    def __getitem__(self, item: str) -> Any:
        if item in self.loaded_files:
            return self.loaded_files[item]
        raise KeyError(f"Data file {item!r} is not found. Data directory is configured to {self.data_directory!r}.")

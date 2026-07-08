import json
from src.backend.config import Config_

with open("../config.schema.json", "w+") as f:
    f.write(json.dumps(Config_.model_json_schema(), indent=2))
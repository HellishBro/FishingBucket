from src.main import run
import typer
import os

def main(config_file: str):
    run(os.path.abspath(config_file))

typer.run(main)
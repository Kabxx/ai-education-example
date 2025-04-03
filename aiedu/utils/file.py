import pickle
from typing import Any


def file_read(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def pickle_dump(
    data: Any,
    path: str,
) -> Any:
    with open(path, "wb") as f:
        pickle.dump(data, f)
    return data


def pickle_load(
    path: str,
) -> Any:
    with open(path, "rb") as f:
        return pickle.load(f)

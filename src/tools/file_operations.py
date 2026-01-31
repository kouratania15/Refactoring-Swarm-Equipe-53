from pathlib import Path
from tools.security import is_path_allowed

def read_file(file_path: str) -> str:
    path = Path(file_path)
    if not is_path_allowed(path):
        raise PermissionError("Access outside sandbox is forbidden")
    return path.read_text(encoding="utf-8")


def write_file(file_path: str, content: str):
    path = Path(file_path)
    if not is_path_allowed(path):
        raise PermissionError("Access outside sandbox is forbidden")
    path.write_text(content, encoding="utf-8")

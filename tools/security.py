from pathlib import Path

SANDBOX_DIR = Path("sandbox").resolve()

def is_path_allowed(path: Path) -> bool:
    try:
        return SANDBOX_DIR in path.resolve().parents or path.resolve() == SANDBOX_DIR
    except Exception:
        return False

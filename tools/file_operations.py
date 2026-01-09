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



    
def list_python_files(directory: str) -> list[str]:
    """
    Liste tous les fichiers .py dans un dossier (récursivement).
    
    Args:
        directory: Chemin du dossier à scanner
        
    Returns:
        Liste des chemins absolus des fichiers .py
    """
    path = Path(directory)
    
    if not is_path_allowed(path):
        raise PermissionError("Access outside sandbox is forbidden")
    
    if not path.exists():
        return []
    
    # Récupérer tous les fichiers .py récursivement
    python_files = []
    for py_file in path.rglob("*.py"):
        # Ignorer les fichiers de test (optionnel)
        if "__pycache__" not in str(py_file):
            python_files.append(str(py_file.resolve()))
    
    return python_files
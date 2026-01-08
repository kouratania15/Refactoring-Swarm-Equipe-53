import subprocess
import sys

def run_command(cmd: list[str]) -> dict:
    """
    Exécute une commande shell.
    
    Args:
        cmd: Liste des arguments de la commande
        
    Returns:
        dict avec:
        - code: Code de retour (int)
        - out: Sortie standard (str)
        - err: Sortie d'erreur (str)
    """
    if not cmd:
        return {
            "code": -1,
            "out": "",
            "err": "Commande vide"
        }
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        return {
            "code": result.returncode,
            "out": result.stdout,
            "err": result.stderr
        }
        
    except FileNotFoundError:
        return {
            "code": -1,
            "out": "",
            "err": f"Commande non trouvée: {cmd[0]}"
        }
    except Exception as e:
        return {
            "code": -1,
            "out": "",
            "err": f"Erreur d'exécution: {str(e)}"
        }
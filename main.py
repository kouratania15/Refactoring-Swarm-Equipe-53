#!/usr/bin/env python3
"""
Point d'entrée principal du système de refactoring Python multi-agents.

Usage:
    python main.py --target_dir <directory>
    python main.py --target_dir ./sandbox/test_code
    python main.py --target_dir ./src --max-iterations 10
"""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Import de l'orchestrateur
from src.agents.orchestrator import CodeRefactorOrchestrator, validate_environment


def parse_arguments():
    """Parse les arguments de la ligne de commande."""
    parser = argparse.ArgumentParser(
        description="Système de refactoring Python automatique multi-agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  %(prog)s --target_dir ./sandbox/test_code
  %(prog)s --target_dir ./my_project --max-iterations 10
  %(prog)s --target_dir ./code --model mistral-large-latest
  %(prog)s --target_dir ./app --max-iterations 5 --verbose

Le système utilise 3 agents:
  - Auditor: Détecte les erreurs syntaxiques et logiques
  - Fixer: Corrige les erreurs détectées
  - Judge: Valide les corrections avec des tests

Configuration:
  - Créez un fichier .env avec MISTRAL_API_KEY=votre_clé
  - Assurez-vous d'avoir pytest installé pour les tests
        """
    )
    
    parser.add_argument(
        "--target_dir",
        type=str,
        required=True,
        help="Répertoire contenant le code Python à refactoriser"
    )
    
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Nombre maximum d'itérations de correction (défaut: 10)"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="mistral-large-latest",
        choices=[
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest"
        ],
        help="Modèle Mistral à utiliser (défaut: mistral-large-latest)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Affichage détaillé (mode debug)"
    )
    
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Ignorer l'exécution des tests (analyse et correction uniquement)"
    )
    
    return parser.parse_args()


def print_banner():
    """Prints the application banner."""
    print("\n" + "="*70)
    print("PYTHON REFACTORING SYSTEM - MULTI-AGENT")
    print("="*70)
    print("Agents: Auditor (detects issues) -> Fixer (fixes) -> Judge (validates)")
    print("="*70 + "\n")


def validate_target_directory(target_dir: Path) -> bool:
    """Valide que le répertoire cible existe et contient des fichiers Python."""
    
    # Vérifier l'existence
    if not target_dir.exists():
        print(f"❌ ERREUR: Le répertoire '{target_dir}' n'existe pas")
        return False
    
    # Vérifier que c'est un répertoire
    if target_dir.is_file():
        # Si c'est un fichier .py unique, créer un dossier temporaire
        if str(target_dir).endswith('.py'):
            print(f"📄 Fichier Python détecté: {target_dir}")
            return True
        else:
            print(f"❌ ERREUR: '{target_dir}' n'est pas un répertoire Python valide")
            return False
    
    # Vérifier qu'il y a des fichiers Python
    python_files = list(target_dir.rglob("*.py"))
    if not python_files:
        print(f"⚠️  ATTENTION: Aucun fichier Python trouvé dans '{target_dir}'")
        
        # Lister les fichiers présents pour aider l'utilisateur
        all_files = list(target_dir.glob("*"))
        if all_files:
            print(f"\nFichiers trouvés dans le répertoire:")
            for f in all_files[:10]:  # Limiter à 10 fichiers
                print(f"  - {f.name}")
            if len(all_files) > 10:
                print(f"  ... et {len(all_files) - 10} autre(s)")
        
        return False
    
    print(f"[DIR] Directory detected: {target_dir}")
    print(f"[PY] {len(python_files)} fichier(s) Python trouvé(s)")
    
    # Lister les fichiers qui seront analysés
    if len(python_files) <= 10:
        print("\nFichiers à analyser:")
        for py_file in python_files:
            print(f"  - {py_file.relative_to(target_dir)}")
    else:
        print(f"\nExemples de fichiers à analyser:")
        for py_file in python_files[:5]:
            print(f"  - {py_file.relative_to(target_dir)}")
        print(f"  ... et {len(python_files) - 5} autre(s)")
    
    print()
    return True


def main():
    """Fonction principale."""
    # Afficher la bannière
    print_banner()
    
    # Parser les arguments
    args = parse_arguments()
    
    # Convertir le chemin en Path
    target_dir = Path(args.target_dir)
    
    # Valider le répertoire cible
    if not validate_target_directory(target_dir):
        return 1
    
    # Valider l'environnement
    print("[CHECK] Validating environment...")
    if not validate_environment():
        print("\n[ERROR] Configuration invalid. Fix errors above.")
        print("\nTo configure:")
        print("1. Create .env file at project root")
        print("2. Add: MISTRAL_API_KEY=your_api_key")
        print("3. Get your key from: https://console.mistral.ai/")
        return 1
    
    # Créer l'orchestrateur
    try:
        orchestrator = CodeRefactorOrchestrator(
            max_iterations=args.max_iterations,
            model_name=args.model
        )
    except Exception as e:
        print(f"❌ ERREUR lors de l'initialisation: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    # Lancer le refactoring
    try:
        stats = orchestrator.refactor(target_dir)
        
        # Déterminer le code de sortie
        if stats["final_status"] == "SUCCESS":
            print("✅ Refactoring terminé avec succès!")
            return 0
        elif stats["final_status"] in ["PARTIAL", "STOPPED"]:
            print("⚠️  Refactoring partiel - voir le résumé ci-dessus")
            
            # Afficher des conseils selon le statut
            if stats["total_files_modified"] == 0:
                print("\n💡 Conseils:")
                print("  - Vérifiez que les erreurs détectées sont bien des erreurs")
                print("  - Augmentez --max-iterations si nécessaire")
                print("  - Utilisez --verbose pour plus de détails")
            
            return 0
        else:
            print("❌ Refactoring incomplet - intervention requise")
            
            # Conseils selon le type d'échec
            if stats["final_status"] == "NEEDS_HUMAN":
                print("\n💡 Une intervention manuelle est nécessaire.")
                print("   Consultez les logs pour identifier le problème.")
            elif stats["final_status"] == "MAX_ITERATIONS":
                print("\n💡 Nombre maximum d'itérations atteint.")
                print("   Relancez avec --max-iterations plus élevé")
                print(f"   Exemple: python main.py --target_dir {args.target_dir} --max-iterations 10")
            
            return 1
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption utilisateur (Ctrl+C)")
        print("Le refactoring a été arrêté.")
        return 130
    
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        if args.verbose:
            import traceback
            print("\n📋 Traceback complet:")
            traceback.print_exc()
        else:
            print("\n💡 Utilisez --verbose pour voir le traceback complet")
        return 1


if __name__ == "__main__":
    sys.exit(main())
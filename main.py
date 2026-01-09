import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Fix encodage UTF-8 sur Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

from src.agents.auditor_agent import AuditorAgent
from src.agents.fixer_agent import FixerAgent
from src.agents.judge_agent import JudgeAgent

# Charger les variables d'environnement
load_dotenv()


def main():
    """
    Point d'entrée du Refactoring Swarm.
    Commande: python main.py --target_dir "./sandbox/test_code"
    """
    
    # 1. Parser les arguments CLI (OBLIGATOIRE)
    parser = argparse.ArgumentParser(
        description="The Refactoring Swarm - Système multi-agents de refactoring automatique"
    )
    parser.add_argument(
        '--target_dir',
        required=True,
        help='Dossier contenant le code Python à refactorer'
    )
    args = parser.parse_args()
    
    target_dir = Path(args.target_dir)
    
    # Vérifications de sécurité
    if not target_dir.exists():
        print(f"❌ ERREUR: Le dossier {target_dir} n'existe pas")
        sys.exit(1)
    
    if not target_dir.is_dir():
        print(f"❌ ERREUR: {target_dir} n'est pas un dossier")
        sys.exit(1)
    
    # Bannière de démarrage
    print("=" * 70)
    print("🤖 REFACTORING SWARM - SYSTÈME MULTI-AGENTS")
    print("=" * 70)
    print(f"📁 Dossier cible    : {target_dir.resolve()}")
    print(f"🔄 Itérations max   : 10")
    print("=" * 70)
    
    # 2. Initialiser les 3 agents
    try:
        auditor = AuditorAgent()
        fixer = FixerAgent()
        judge = JudgeAgent()
        print("✅ Agents initialisés avec succès\n")
    except Exception as e:
        print(f"❌ ERREUR lors de l'initialisation des agents: {e}")
        sys.exit(1)
    
    # 3. Boucle de refactoring (MAX 10 itérations)
    MAX_ITERATIONS = 10
    iteration = 0
    mission_success = False
    
    while iteration < MAX_ITERATIONS and not mission_success:
        iteration += 1
        
        print("\n" + "=" * 70)
        print(f"🔄 ITÉRATION {iteration}/{MAX_ITERATIONS}")
        print("=" * 70)
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 1: AUDIT
        # ─────────────────────────────────────────────────────────────
        print("\n📋 PHASE 1: AUDIT DU CODE")
        print("─" * 70)
        
        audit_result = auditor.analyze(target_dir)
        
        # Si aucun problème détecté, mission terminée
        if audit_result['issues_found'] == 0:
            print("\n🎉 Aucun problème détecté! Le code est propre.")
            mission_success = True
            break
        
        print(f"\n⚠️  {audit_result['issues_found']} problème(s) détecté(s) dans {len(audit_result['plan'])} fichier(s)")
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 2: CORRECTION
        # ─────────────────────────────────────────────────────────────
        print("\n📋 PHASE 2: CORRECTION DU CODE")
        print("─" * 70)
        
        fix_result = fixer.fix_issues(target_dir, audit_result['plan'])
        
        print(f"\n✏️  {fix_result['files_modified']} fichier(s) modifié(s)")
        
        # ─────────────────────────────────────────────────────────────
        # PHASE 3: VALIDATION PAR TESTS
        # ─────────────────────────────────────────────────────────────
        print("\n📋 PHASE 3: VALIDATION PAR TESTS")
        print("─" * 70)
        
        test_result = judge.run_tests(target_dir)
        
        # Vérifier si tous les tests passent
        if test_result['all_passed']:
            print("\n🎉 SUCCÈS: Tous les tests passent!")
            mission_success = True
        else:
            print(f"\n⚠️  {test_result['failures']} test(s) échoué(s)")
            print("🔁 Une nouvelle itération est nécessaire...")
            
            # Afficher un extrait des erreurs
            if test_result['error_logs']:
                print("\n📝 Extrait des erreurs:")
                print(test_result['error_logs'][:300])
    
    # ─────────────────────────────────────────────────────────────
    # RÉSULTAT FINAL
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    if mission_success:
        print(f"✅ MISSION RÉUSSIE EN {iteration} ITÉRATION(S)!")
        print("=" * 70)
        print("\n📊 Résumé:")
        print(f"   • Fichiers analysés : {len(audit_result.get('files_analyzed', []))}")
        print(f"   • Itérations        : {iteration}")
        print(f"   • Tests             : ✅ TOUS PASSENT")
        print("\n💾 Les logs ont été sauvegardés dans logs/experiment_data.json")
        sys.exit(0)
    else:
        print(f"❌ ÉCHEC APRÈS {MAX_ITERATIONS} ITÉRATIONS")
        print("=" * 70)
        print("\n📊 Résumé:")
        print(f"   • Itérations        : {MAX_ITERATIONS}")
        print(f"   • Problèmes restants: {audit_result.get('issues_found', '?')}")
        print(f"   • Tests échoués     : {test_result.get('failures', '?')}")
        print("\n💡 Suggestion: Vérifiez les logs dans logs/experiment_data.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
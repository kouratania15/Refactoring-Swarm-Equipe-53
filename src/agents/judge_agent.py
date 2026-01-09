import os
import sys
import json
from mistralai import Mistral
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.run_pytest import run_pytest
from src.utils.logger import log_experiment, ActionType

# Charger les variables d'environnement
load_dotenv()


class JudgeAgent:
    """
    Agent Testeur : Exécute les tests et valide le code.
    """
    
    def __init__(self, model_name="mistral-large-latest"):  
        self.model_name = model_name
        self.agent_name = "Judge_Agent"
        
        # Configuration Mistral
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY non trouvée dans .env")
        
        self.client = Mistral(api_key=api_key)
        self.model = model_name
    
    def run_tests(self, target_dir: Path) -> dict:
        """
        Exécute pytest et analyse les résultats.
        
        Returns:
            {
                'all_passed': bool,
                'total_tests': int,
                'passed': int,
                'failures': int,
                'error_logs': str
            }
        """
        print(f"\n🧪 {self.agent_name}: Exécution des tests...")
        
        try:
            # Exécuter pytest
            pytest_result = run_pytest(str(target_dir))
            
            success = pytest_result.get("success", False)
            stdout = pytest_result.get("stdout", "")
            stderr = pytest_result.get("stderr", "")
            
            # Parser les résultats
            test_summary = self._parse_pytest_output(stdout, stderr)
            
            # Logger l'action (OBLIGATOIRE)
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.DEBUG if not success else ActionType.GENERATION,
                details={
                    "tests_executed": test_summary["total_tests"],
                    "input_prompt": "Analyse des résultats de tests pytest",
                    "output_response": stdout[:500] if stdout else stderr[:500],
                    "all_passed": success
                },
                status="SUCCESS" if success else "FAILED"
            )
            
            if success:
                print(f"   ✅ Tous les tests passent ({test_summary['total_tests']} test(s))")
            else:
                print(f"   ❌ {test_summary['failures']} test(s) échoué(s)")
            
            return {
                "all_passed": success,
                "total_tests": test_summary["total_tests"],
                "passed": test_summary["passed"],
                "failures": test_summary["failures"],
                "error_logs": stderr if stderr else stdout
            }
        
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution des tests: {e}")
            
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.DEBUG,
                details={
                    "error": str(e),
                    "input_prompt": "Tentative d'exécution pytest",
                    "output_response": str(e)
                },
                status="FAILED"
            )
            
            return {
                "all_passed": False,
                "total_tests": 0,
                "passed": 0,
                "failures": 0,
                "error_logs": str(e)
            }
    
    def _parse_pytest_output(self, stdout: str, stderr: str) -> dict:
        """Parse la sortie de pytest pour extraire les statistiques."""
        
        output = stdout + stderr
        
        # Valeurs par défaut
        total_tests = 0
        passed = 0
        failures = 0
        
        # Chercher le résumé pytest (ex: "5 passed, 2 failed")
        if "passed" in output:
            import re
            
            # Rechercher "X passed"
            passed_match = re.search(r'(\d+)\s+passed', output)
            if passed_match:
                passed = int(passed_match.group(1))
            
            # Rechercher "X failed"
            failed_match = re.search(r'(\d+)\s+failed', output)
            if failed_match:
                failures = int(failed_match.group(1))
            
            total_tests = passed + failures
        
        return {
            "total_tests": total_tests,
            "passed": passed,
            "failures": failures
        }
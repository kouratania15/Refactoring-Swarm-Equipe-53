import os
import sys
import json
import ast
import time
from mistralai import Mistral
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.file_operations import read_file, list_python_files
from tools.run_pylint import run_pylint
from src.utils.logger import log_experiment, ActionType

# Charger les variables d'environnement
load_dotenv()


class AuditorAgent:
    """
    Agent Auditeur : Analyse le code et crée un plan de refactoring.
    """
    
   
    def __init__(self, model_name="mistral-large-latest"):  
        self.model_name = model_name
        self.agent_name = "Auditor_Agent"
        
        # Configuration Mistral
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY non trouvée dans .env")
        
        self.client = Mistral(api_key=api_key)
        self.model = model_name
    
    def analyze(self, target_dir: Path) -> dict:
        """
        Analyse tous les fichiers Python et crée un plan de refactoring.
        
        Returns:
            {
                'issues_found': int,
                'plan': dict,
                'files_analyzed': list
            }
        """
        print(f"\n🔍 {self.agent_name}: Démarrage de l'analyse...")
        
        try:
            # 1. Lister tous les fichiers Python
            python_files = list_python_files(str(target_dir))
            
            if not python_files:
                print(f"⚠️  Aucun fichier Python trouvé dans {target_dir}")
                return {
                    "issues_found": 0,
                    "plan": {},
                    "files_analyzed": []
                }
            
            print(f"📄 {len(python_files)} fichier(s) Python détecté(s)")
            
            # 2. Analyser chaque fichier
            global_plan = {}
            total_issues = 0
            
            for file_path in python_files:
                print(f"   → Analyse de {Path(file_path).name}...")
                
                # Lire le code
                code_content = read_file(file_path)
                
                # 🔴 D'abord: Détacter les erreurs de SYNTAXE directement
                syntax_errors = self._check_syntax(file_path, code_content)
                if syntax_errors:
                    global_plan[file_path] = syntax_errors
                    total_issues += len(syntax_errors)
                    continue  # Passer au fichier suivant si erreur de syntaxe
                
                # Exécuter pylint
                pylint_result = run_pylint(file_path)
                
                # Analyser avec le LLM
                file_plan = self._analyze_file(file_path, code_content, pylint_result)
                
                if file_plan and file_plan.get("issues"):
                    global_plan[file_path] = file_plan["issues"]
                    total_issues += len(file_plan["issues"])
            
            print(f"\n✅ Analyse terminée: {total_issues} problème(s) total(aux)")
            
            return {
                "issues_found": total_issues,
                "plan": global_plan,
                "files_analyzed": python_files
            }
        
        except Exception as e:
            print(f"❌ Erreur dans l'analyse: {e}")
            
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.ANALYSIS,
                details={
                    "error": str(e),
                    "input_prompt": "",
                    "output_response": ""
                },
                status="FAILED"
            )
            
            return {
                "issues_found": 0,
                "plan": {},
                "files_analyzed": []
            }
    
    def _check_syntax(self, file_path: str, code: str) -> list:
        """Vérifie les erreurs de syntaxe Python sans dépendre de l'API."""
        issues = []
        
        try:
            ast.parse(code)  # Si ça marche, pas d'erreur de syntaxe
        except SyntaxError as e:
            error_msg = f"[ERREUR SYNTAXE ligne {e.lineno}] {e.msg}"
            print(f"   {error_msg}")
            issues.append(error_msg)
        except Exception as e:
            error_msg = f"[ERREUR ligne ?] {str(e)}"
            print(f"   {error_msg}")
            issues.append(error_msg)
        
        return issues
    
    def _analyze_file(self, file_path: str, code: str, pylint_result: dict) -> dict:
        """Analyse un fichier avec le LLM."""
        
        # Construire le prompt
        prompt = self._build_analysis_prompt(code, pylint_result)
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Appeler Mistral
                response = self.client.chat.complete(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}]
                )
                llm_output = response.choices[0].message.content
                
                # Parser la réponse JSON
                # Le LLM peut entourer le JSON de ```json ... ```
                clean_output = llm_output.strip()
                if clean_output.startswith("```json"):
                    clean_output = clean_output[7:]
                if clean_output.endswith("```"):
                    clean_output = clean_output[:-3]
                
                analysis = json.loads(clean_output.strip())
                
                # Logger l'action (OBLIGATOIRE)
                log_experiment(
                    agent_name=self.agent_name,
                    model_used=self.model_name,
                    action=ActionType.ANALYSIS,
                    details={
                        "file_analyzed": file_path,
                        "input_prompt": prompt,
                        "output_response": llm_output,
                        "issues_found": len(analysis.get("issues", []))
                    },
                    status="SUCCESS"
                )
                
                return analysis
            
            except Exception as e:
                error_str = str(e)
                
                # Si erreur 429 (quota dépassé), attendre et retry
                if "429" in error_str or "quota" in error_str.lower():
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 5 * retry_count  # 5s, 10s, 15s
                        print(f"   ⏳ Quota API dépassé. Attente {wait_time}s avant retry... ({retry_count}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"   ⚠️  Quota API dépassé après {max_retries} tentatives. Passage du fichier.")
                        return {"issues": []}
                
                # Autres erreurs
                print(f"⚠️  Erreur LLM pour {Path(file_path).name}: {e}")
                return {"issues": []}
        
        return {"issues": []}
    
    def _build_analysis_prompt(self, code: str, pylint_result: dict) -> str:
        """Construit le prompt d'analyse."""
        
        # Parser les résultats pylint (format JSON)
        pylint_issues = ""
        try:
            if pylint_result.get("stdout"):
                pylint_data = json.loads(pylint_result["stdout"])
                if pylint_data:
                    pylint_issues = "\n".join([
                        f"- Ligne {item.get('line', '?')}: {item.get('message', 'Erreur inconnue')}"
                        for item in pylint_data[:10]  # Limiter à 10 pour le contexte
                    ])
        except:
            pylint_issues = "Aucun problème pylint détecté"
        
        if not pylint_issues:
            pylint_issues = "Aucun problème pylint détecté"
        
        prompt = f"""Tu es un expert en analyse de code Python et en refactoring.

📋 CODE À ANALYSER:
```python
{code[:3000]}  
```

🔍 RÉSULTATS PYLINT:
{pylint_issues}

📝 TA MISSION:
1. Identifier TOUS les problèmes de qualité:
   - Bugs potentiels
   - Fonctions sans docstring
   - Variables mal nommées
   - Code non PEP8
   - Imports inutilisés
   - Gestion d'erreurs manquante

2. Pour CHAQUE problème, créer une instruction de correction PRÉCISE.

⚠️ IMPORTANT: Réponds UNIQUEMENT au format JSON suivant (sans texte avant/après):
{{
    "issues": [
        "Ajouter docstring à la fonction calculate() ligne 15",
        "Renommer variable 'x' en 'total_amount' ligne 22",
        "Corriger indentation ligne 42"
    ]
}}

Si aucun problème: {{"issues": []}}
"""
        return prompt
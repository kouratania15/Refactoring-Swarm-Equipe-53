import os
import sys
import json
import re
from mistralai import Mistral
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.file_operations import read_file, write_file
from src.utils.logger import log_experiment, ActionType

# Charger les variables d'environnement
load_dotenv()


class FixerAgent:
    """
    Agent Correcteur : Corrige le code selon le plan de l'Auditor.
    """
    
    def __init__(self, model_name="mistral-large-latest"):  
        self.model_name = model_name
        self.agent_name = "Fixer_Agent"
        
        # Configuration Mistral
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY non trouvée dans .env")
        
        self.client = Mistral(api_key=api_key)
        self.model = model_name
    
    def fix_issues(self, target_dir: Path, plan: dict) -> dict:
        """
        Applique les corrections selon le plan.
        
        Args:
            plan: {
                'file_path': ['instruction1', 'instruction2', ...]
            }
        """
        print(f"\n🔧 {self.agent_name}: Démarrage des corrections...")
        
        if not plan:
            print("ℹ️  Aucune correction à appliquer")
            return {
                "files_modified": 0,
                "changes_applied": []
            }
        
        files_modified = 0
        all_changes = []
        
        for file_path, instructions in plan.items():
            print(f"   → Correction de {Path(file_path).name}...")
            
            try:
                # Lire le code original
                original_code = read_file(file_path)
                
                # Corriger avec le LLM
                fixed_code = self._fix_file(file_path, original_code, instructions)
                
                if fixed_code and fixed_code.strip() != original_code.strip():
                    # Sauvegarder le code corrigé
                    write_file(file_path, fixed_code)
                    files_modified += 1
                    all_changes.append(f"{Path(file_path).name}: {len(instructions)} correction(s)")
                    print(f"      ✅ {len(instructions)} correction(s) appliquée(s)")
                else:
                    print(f"      ⚠️  Aucun changement nécessaire")
            
            except Exception as e:
                print(f"      ❌ Erreur: {e}")
                all_changes.append(f"{Path(file_path).name}: ÉCHEC - {str(e)}")
        
        print(f"\n✅ Corrections terminées: {files_modified} fichier(s) modifié(s)")
        
        return {
            "files_modified": files_modified,
            "changes_applied": all_changes
        }
    
    def _fix_file(self, file_path: str, code: str, instructions: list) -> str:
        """Corrige un fichier avec le LLM."""
        
        # Construire le prompt
        prompt = self._build_fix_prompt(code, instructions)
        
        try:
            # Premièrement: tentative locale d'autocorrection pour erreurs de syntaxe
            if any("ERREUR SYNTAXE" in instr or "syntax" in instr.lower() for instr in instructions):
                fixed_local = self._auto_fix_syntax(code)
                if fixed_local and fixed_local.strip() != code.strip():
                    print("      🔧 Correction syntaxe appliquée localement (heuristique)")
                    return fixed_local

            # Appeler Mistral
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            llm_output = response.choices[0].message.content

            # Extraire le code corrigé
            fixed_code = self._extract_code(llm_output)
            
            # Logger l'action (OBLIGATOIRE)
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "file_fixed": file_path,
                    "input_prompt": prompt[:500] + "...",  # Tronquer pour les logs
                    "output_response": llm_output[:500] + "...",
                    "instructions_count": len(instructions)
                },
                status="SUCCESS"
            )
            
            return fixed_code
        
        except Exception as e:
            print(f"⚠️  Erreur LLM: {e}")
            
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "file_fixed": file_path,
                    "input_prompt": prompt[:500],
                    "output_response": str(e),
                    "error": str(e)
                },
                status="FAILED"
            )
            
            return code  # Retourner le code original si échec

    def _auto_fix_syntax(self, code: str) -> str:
        """Applique des corrections simples pour erreurs de syntaxe courantes.

        Actuellement implémente:
        - parenthèse fermante manquante sur une définition de fonction
        - fermeture de guillemets manquante avant docstring (si applicable)
        """
        lines = code.splitlines()
        changed = False

        # Rechercher une ligne de def qui semble incomplète (manque "):")
        for i, line in enumerate(lines):
            m = re.match(r"^(\s*def\s+\w+\s*\([^)]*$", line)
            if m:
                # Si la ligne suivante commence par une docstring, on ajoute "):" à la fin
                next_idx = i + 1
                if next_idx < len(lines):
                    next_line = lines[next_idx].lstrip()
                    if next_line.startswith('"') or next_line.startswith("'") or next_line.startswith('"""'):
                        lines[i] = lines[i] + "):"  # fermer la signature
                        changed = True
                        break

        if changed:
            return "\n".join(lines) + ("\n" if code.endswith("\n") else "")
        return None
    
    def _build_fix_prompt(self, code: str, instructions: list) -> str:
        """Construit le prompt de correction."""
        
        instructions_text = "\n".join([f"{i+1}. {instr}" for i, instr in enumerate(instructions)])
        
        prompt = f"""Tu es un expert en refactoring Python.

📋 CODE ORIGINAL:
```python
{code}
```

🔧 INSTRUCTIONS DE CORRECTION:
{instructions_text}

📝 TA MISSION:
Applique TOUTES les corrections demandées tout en:
- Préservant la logique du code
- Respectant PEP8
- Gardant le même comportement fonctionnel

⚠️ IMPORTANT: 
- Réponds UNIQUEMENT avec le code corrigé complet
- NE mets PAS de texte explicatif avant/après
- NE mets PAS de balises ```python
- Juste le code Python pur

CODE CORRIGÉ:
"""
        return prompt
    
    def _extract_code(self, llm_output: str) -> str:
        """Extrait le code Python de la réponse du LLM."""
        
        clean_output = llm_output.strip()
        
        # Enlever les balises markdown si présentes
        if "```python" in clean_output:
            # Extraire entre ```python et ```
            start = clean_output.find("```python") + 9
            end = clean_output.find("```", start)
            if end != -1:
                clean_output = clean_output[start:end].strip()
        elif "```" in clean_output:
            # Extraire entre ``` et ```
            start = clean_output.find("```") + 3
            end = clean_output.find("```", start)
            if end != -1:
                clean_output = clean_output[start:end].strip()
        
        return clean_output
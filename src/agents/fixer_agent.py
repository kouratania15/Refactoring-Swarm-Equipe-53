
import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.tools.file_operations import read_file, write_file
from src.utils.logger import log_experiment, ActionType
from src.prompts.fixer_prompt import get_fixer_prompt
from src.utils.llm_factory import get_llm

load_dotenv()


class FixerAgent:
    """Agent Correcteur : Applique des corrections au code (Gemini Version)."""

    def __init__(self, model_name="gemini-1.5-flash"):
        self.model_name = model_name
        self.agent_name = "Fixer_Agent"
        try:
            self.llm = get_llm(model_name=model_name)
        except Exception as e:
             print(f"Error initializing LLM: {e}")
             raise

    def fix_issues(self, target_dir: Path, plan: dict, detected_issues: dict) -> dict:
        """Apply fixes based on the plan."""
        print(f"\n🔧 {self.agent_name}: Applying fixes...")
        
        files_modified = 0
        fixes_log = []

        for file_path, issues in plan.items():
            if not issues:
                continue

            print(f"   → Fixing {Path(file_path).name}...")
            try:
                original_code = read_file(file_path)
                modified_code = self._apply_targeted_fixes(original_code, issues)

                if modified_code != original_code:
                    write_file(file_path, modified_code)
                    files_modified += 1
                    fixes_log.append({"file": file_path, "status": "FIXED"})
                    print(f"      ✅ Fixed")
                else:
                    fixes_log.append({"file": file_path, "status": "NO_CHANGE"})
                    print(f"      ℹ️  No changes needed")
                    
            except Exception as e:
                print(f"      ❌ Error fixing file: {e}")
                fixes_log.append({"file": file_path, "status": "ERROR", "error": str(e)})

        return {
            "files_modified": files_modified,
            "fixes_log": fixes_log
        }

    def _apply_targeted_fixes(self, code: str, issues: list) -> str:
        """Apply fixes - handles Syntax errors directly, others via LLM."""
        fixed = code
        # Filter for SYNTAX issues first (simple replacements if possible)
        for issue in issues:
            if isinstance(issue, str):
                 try:
                    issue = json.loads(issue)
                 except: as_dict = False
            
            if isinstance(issue, dict):
                issue_type = issue.get("type", "UNKNOWN")
                line_num = issue.get("line", 0)
                description = issue.get("description", "")
                
                if issue_type == 'SYNTAX':
                    fixed = self._fix_syntax_error(fixed, line_num, description)

        # If LLM is needed for complex fixes (or if syntax fix didn't resolve everything)
        # We pass all issues to LLM for a comprehensive fix
        if len(issues) > 0:
             fixed = self._apply_fixes_with_llm(fixed, issues)
             
        return fixed

    def _fix_syntax_error(self, code: str, line_num: int, description: str) -> str:
        """Tries very simple heuristic repairs for syntax."""
        lines = code.split('\n')
        if not (0 <= line_num - 1 < len(lines)):
            return code
        
        line = lines[line_num - 1]
        
        # Missing colon
        if "Missing colon" in description and not line.strip().endswith(':'):
            lines[line_num - 1] = line + ":"
            return '\n'.join(lines)
            
        # Missing parenthesis (basic check)
        if "Missing closing parenthesis" in description:
             if '(' in line and ')' not in line:
                  lines[line_num - 1] = line + ")"
                  return '\n'.join(lines)

        return code

    def _apply_fixes_with_llm(self, code: str, issues: list) -> str:
        """Use LLM to rewrite code with fixes."""
        try:
            prompt_template = get_fixer_prompt()
            issues_str = json.dumps(issues, indent=2)
            prompt = prompt_template.format(code=code, issues=issues_str)

            print("      ⏳ Rate Check: Waiting 10s before LLM Fix...")
            time.sleep(10)
            response = self.llm.invoke(prompt)
            new_code = response.content

            # Extract code block
            if "```python" in new_code:
                new_code = new_code.split("```python")[1].split("```")[0].strip()
            elif "```" in new_code:
                new_code = new_code.split("```")[1].split("```")[0].strip()

            # Logging
            log_experiment(
                agent_name=self.agent_name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "input_prompt": prompt[:500] + "...",
                    "output_response": new_code[:500] + "...",
                    "code_length_before": len(code),
                    "code_length_after": len(new_code)
                },
                status="SUCCESS"
            )

            return new_code

        except Exception as e:
            print(f"      ⚠️  LLM Fix failed: {e}")
            return code

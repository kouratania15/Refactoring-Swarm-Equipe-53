
import os
import sys
import json
import ast
import time
from pathlib import Path
from dotenv import load_dotenv
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.tools.file_operations import read_file
from src.tools.run_pylint import run_pylint
from src.utils.logger import log_experiment, ActionType
from src.prompts.auditor_prompt import get_auditor_prompt
from src.utils.llm_factory import get_llm

load_dotenv()


class AuditorAgent:
    """Agent Auditeur : Détecte les erreurs de syntaxe et logique (Gemini Version)."""
    
    def __init__(self, model_name="gemini-1.5-flash"):
        self.model_name = model_name
        self.agent_name = "Auditor_Agent"
        try:
            self.llm = get_llm(model_name=model_name)
        except Exception as e:
             # Fallback if specific model fails, though factory handles key check
             print(f"Error initializing LLM: {e}")
             raise

    def analyze(self, target_dir: Path) -> dict:
        """Analyze all Python files in target directory."""
        print(f"\n🔍 {self.agent_name}: Analyzing files...\n")
        plan = {}
        python_files = list(target_dir.rglob("*.py"))

        if not python_files:
            print(f"⚠️  No Python files found in {target_dir}")
            return {}

        for py_file in python_files:
            if "__pycache__" in str(py_file):
                continue
            print(f"   📄 Analyzing {py_file.name}...")
            file_plan = self._analyze_file(str(py_file))
            if file_plan:
                plan[str(py_file)] = file_plan
                print(f"      → {len(file_plan)} issue(s) detected")
            else:
                print(f"      → OK")

        return plan

    def _analyze_file(self, file_path: str) -> list:
        """Analyze a single file for errors."""
        code = read_file(file_path)
        issues = []

        # Check syntax
        syntax_errors = self._check_syntax(code)
        issues.extend(syntax_errors)

        # Run pylint
        pylint_output = run_pylint(file_path)

        # Analyze logic with LLM
        logic_errors = self._analyze_logic_with_llm(code, pylint_output)
        issues.extend(logic_errors)

        return issues

    def _check_syntax(self, code: str) -> list:
        """Check syntax using ast.parse() and manual checks."""
        errors = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(json.dumps({
                "type": "SYNTAX",
                "line": e.lineno or 1,
                "severity": "CRITICAL",
                "description": f"SyntaxError: {e.msg}",
                "fix_instruction": f"Fix syntax error: {e.msg}"
            }))
        
        # Also check for common syntax issues manually
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith(('def ', 'class ')):
                if '(' in stripped and ')' not in stripped:
                    errors.append(json.dumps({
                        "type": "SYNTAX",
                        "line": i,
                        "severity": "CRITICAL",
                        "description": f"Missing closing parenthesis on line {i}",
                        "fix_instruction": f"Add missing ')' on line {i}"
                    }))
            
            if stripped.startswith(('def ', 'class ', 'if ', 'elif ', 'for ', 'while ', 'try:', 'except', 'with ')):
                if not stripped.endswith(':') and not stripped.endswith('('):
                    errors.append(json.dumps({
                        "type": "SYNTAX",
                        "line": i,
                        "severity": "CRITICAL",
                        "description": f"Missing colon at end of statement on line {i}",
                        "fix_instruction": f"Add ':' at end of line {i}"
                    }))
        
        return errors

    def _analyze_logic_with_llm(self, code: str, pylint_issues: str) -> list:
        """Call LLM to detect logic errors."""
        try:
            template = get_auditor_prompt()
            prompt = template.format(
                code=code,
                pylint_issues=pylint_issues or "No issues detected"
            )

            # LangChain Invoke via Gemini (with rate limit pause)
            print("   ⏳ Rate Check: Waiting 10s before LLM call...")
            time.sleep(10)
            response1 = self.llm.invoke(prompt)
            llm_output_1 = response1.content
            print(f"   [LLM RAW]: {llm_output_1[:400]}")

            # Try to parse the first output
            issues = self._parse_llm_response(llm_output_1)
            parsed_first = bool(issues) or ('"issues"' in (llm_output_1 or ""))

            # If first parse failed (malformed JSON), ask LLM to reformat
            llm_output_2 = None
            parsed_second = False
            if not parsed_first and '{' in llm_output_1:
                reformat_prompt = (
                    "The previous response was not valid JSON. "
                    "Please reformat the exact content of your previous reply as a single VALID JSON object that matches the schema:\n"
                    "{\"summary\": \"...\", \"issues\": [...], \"global_recommendation\": \"...\"}\n"
                    "ONLY return the JSON object and nothing else.\n\n"
                    "Previous response:\n" + llm_output_1[:2000]
                )

                try:
                    time.sleep(5) # Shorter pause for retry
                    response2 = self.llm.invoke(reformat_prompt)
                    llm_output_2 = response2.content
                    issues2 = self._parse_llm_response(llm_output_2)
                    parsed_second = bool(issues2) or ('"issues"' in (llm_output_2 or ""))
                    if issues2:
                        issues = issues2
                except Exception:
                    parsed_second = False

            # Log
            try:
                log_experiment(
                    agent_name=self.agent_name,
                    model_used=self.model_name,
                    action=ActionType.ANALYSIS,
                    details={
                        "input_prompt": prompt[:1000],
                        "output_response": f"[FIRST]\n{llm_output_1[:500]}\n\n[REFORMAT]\n{llm_output_2[:500] if llm_output_2 else '(none)'}",
                        "parsed_first": parsed_first,
                        "parsed_second": parsed_second,
                        "issues_count": len(issues) if issues else 0
                    },
                    status="SUCCESS" if (parsed_first or parsed_second) else "PARTIAL"
                )
            except Exception as e:
                print(f"   ⚠️  Logging error: {str(e)[:200]}")

            return issues
        except Exception as e:
            print(f"   ⚠️  LLM error: {str(e)[:400]}")
            print(traceback.format_exc())
            return []

    def _parse_llm_response(self, response: str) -> list:
        """Parse LLM response to extract issues."""
        issues = []
        try:
            start = response.find('{')
            if start < 0:
                return []
            
            brace_count = 0
            end = -1
            for i in range(start, len(response)):
                if response[i] == '{':
                    brace_count += 1
                elif response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            
            if end > start:
                json_str = response[start:end]
                data = json.loads(json_str)
                if isinstance(data, dict) and "issues" in data:
                    return data.get("issues", [])
        except json.JSONDecodeError:
            pass
        except Exception:
            pass

        # Fallback
        for line in response.split('\n'):
            if line.strip().startswith('-'):
                issues.append(line.strip())

        return issues

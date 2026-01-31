import os
import sys
import json
import re
import ast
from mistralai import Mistral
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.tools.file_operations import read_file, write_file
from logs.logger import log_experiment, ActionType
from src.prompts.fixer_prompt import get_fixer_prompt

load_dotenv()


class FixerAgent:
    """Agent Correcteur : Applique les corrections au code."""

    def __init__(self, model_name="mistral-large-latest"):
        self.model_name = model_name
        self.agent_name = "Fixer_Agent"
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in .env")
        self.client = Mistral(api_key=api_key)
        self.model = model_name
        self.fixes_applied = []  # Track all fixes applied

    def fix_issues(self, target_dir: Path, plan: dict, detected_issues: dict = None) -> dict:
        """Apply fixes to all files in the plan."""
        print(f"\n🔧 {self.agent_name}: Applying fixes...")

        if not plan and not detected_issues:
            print("ℹ️  No fixes to apply")
            return {"files_modified": 0, "changes_applied": [], "fixes_log": []}

        files_modified = 0
        all_changes = []
        self.fixes_applied = []

        # Combine both sources of issues
        all_files_to_fix = set()
        if plan:
            all_files_to_fix.update(plan.keys())
        if detected_issues:
            all_files_to_fix.update(detected_issues.keys())

        for file_path in all_files_to_fix:
            print(f"   → Fixing {Path(file_path).name}...")

            try:
                original_code = read_file(file_path)
                
                # Get issues for this file
                file_issues = []
                if detected_issues and file_path in detected_issues:
                    file_issues = detected_issues[file_path]
                if plan and file_path in plan:
                    file_issues.extend(plan[file_path] if isinstance(plan[file_path], list) else [])
                
                # Apply fixes based on detected issues
                fixed_code = self._apply_targeted_fixes(original_code, file_issues)
                
                # Validate final syntax
                if not self._has_syntax_error(fixed_code):
                    if fixed_code != original_code:
                        write_file(file_path, fixed_code)
                        files_modified += 1
                        all_changes.append({
                            "file": str(file_path),
                            "status": "FIXED",
                            "fixes": len([f for f in self.fixes_applied if f['file'] == str(file_path)])
                        })
                        print(f"      ✅ Fixed")
                    else:
                        print(f"      ℹ️  No changes needed")
                else:
                    print(f"      ⚠️  Fixed code still has syntax errors, using LLM...")
                    fixed_code = self._apply_fixes_with_llm(original_code, file_issues)
                    if not self._has_syntax_error(fixed_code) and fixed_code != original_code:
                        write_file(file_path, fixed_code)
                        files_modified += 1
                        all_changes.append({
                            "file": str(file_path),
                            "status": "FIXED_LLM"
                        })
                        print(f"      ✅ Fixed (LLM)")

            except Exception as e:
                print(f"      ❌ Error: {str(e)[:50]}")

        print(f"\n✅ Fixes applied: {files_modified} file(s) modified")
        return {
            "files_modified": files_modified, 
            "changes_applied": all_changes,
            "fixes_log": self.fixes_applied
        }

    def _apply_targeted_fixes(self, code: str, issues: list) -> str:
        """Apply targeted fixes based on detected issues."""
        fixed = code
        
        # Parse issues to identify what needs to be fixed
        for issue in issues:
            if isinstance(issue, str):
                # Try to parse JSON from string
                try:
                    import json as json_module
                    match = re.search(r'\{.*\}', issue, re.DOTALL)
                    if match:
                        issue = json_module.loads(match.group())
                except:
                    continue
            
            if not isinstance(issue, dict):
                continue
            
            issue_type = issue.get('type', '')
            line_num = issue.get('line', 0)
            description = issue.get('description', '')
            
            # Fix SYNTAX errors with basic fixes
            if issue_type == 'SYNTAX':
                fixed = self._fix_syntax_error(fixed, line_num, description)
            
            # Use LLM for complex issues (STYLE, DOC, BUG, DESIGN)
            elif issue_type in ('STYLE', 'DOC', 'BUG', 'DESIGN'):
                # Accumulate issues for batch LLM fix
                pass  # Will be handled by LLM below
        
        # If no basic fixes changed the code, use LLM for all issues
        if fixed == code and issues:
            fixed = self._apply_fixes_with_llm(code, issues)
        
        return fixed

    def _fix_syntax_error(self, code: str, line_num: int, description: str) -> str:
        """Fix specific syntax errors."""
        lines = code.split('\n')
        
        if line_num <= 0 or line_num > len(lines):
            return code
        
        # Convert to 0-based index
        idx = line_num - 1
        line = lines[idx] if idx < len(lines) else ''
        
        # Fix: Missing closing parenthesis on function/class definition
        if 'missing closing parenthesis' in description.lower() or 'parenthesis' in description.lower():
            if idx < len(lines):
                stripped = lines[idx].rstrip()
                if stripped.startswith(('def ', 'class ')):
                    if '(' in stripped and ')' not in stripped:
                        # Find the opening paren and add closing
                        lines[idx] = stripped + '):'
                        self.fixes_applied.append({
                            "file": "unknown",
                            "line": line_num,
                            "type": "MISSING_CLOSING_PAREN",
                            "original": stripped,
                            "fixed": lines[idx]
                        })
        
        # Fix: Missing colon at end of statement
        elif 'missing colon' in description.lower():
            if idx < len(lines):
                stripped = lines[idx].rstrip()
                # Check if it's a control flow statement
                if any(stripped.startswith(kw) for kw in ['if ', 'elif ', 'else', 'for ', 'while ', 'try', 'except', 'class ', 'def ']):
                    if not stripped.endswith(':'):
                        # Don't add colon if it looks incomplete
                        if ')' in stripped or '(' not in stripped or 'def ' in stripped or 'class ' in stripped:
                            lines[idx] = stripped + ':'
                            self.fixes_applied.append({
                                "file": "unknown",
                                "line": line_num,
                                "type": "MISSING_COLON",
                                "original": stripped,
                                "fixed": lines[idx]
                            })
        
        # Fix: Unterminated string
        elif 'unterminated' in description.lower() and 'string' in description.lower():
            if idx < len(lines):
                stripped = lines[idx].rstrip()
                # Try to find unclosed quote
                if '"' in stripped or "'" in stripped:
                    quote_char = '"' if stripped.count('"') % 2 != 0 else "'"
                    if quote_char in stripped and not stripped.endswith(quote_char):
                        lines[idx] = stripped + quote_char
                        self.fixes_applied.append({
                            "file": "unknown",
                            "line": line_num,
                            "type": "UNTERMINATED_STRING",
                            "original": stripped,
                            "fixed": lines[idx]
                        })
        
        # Fix: Invalid indentation (simple fix)
        elif 'indentation' in description.lower():
            if idx < len(lines):
                # Try to fix obvious indentation issues
                stripped = lines[idx].lstrip()
                if stripped and not stripped.startswith(('def ', 'class ', 'if ', 'elif ', 'else', 'for ', 'while ')):
                    # Add proper indentation (4 spaces)
                    if idx > 0:
                        prev_line = lines[idx - 1]
                        indent = len(prev_line) - len(prev_line.lstrip())
                        if prev_line.rstrip().endswith(':'):
                            indent += 4
                        lines[idx] = ' ' * indent + stripped
        
        return '\n'.join(lines)

    def _apply_fixes_with_llm(self, code: str, instructions: list) -> str:
        """Apply fixes using LLM when basic fixes aren't enough."""
        try:
            template = get_fixer_prompt()
            prompt = template.format(
                code=code,
                instructions='\n'.join([str(i)[:100] for i in instructions[:5]])
            )

            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            llm_output = response.choices[0].message.content
            fixed_code = self._extract_code(llm_output)

            try:
                # Log to experiment data
                log_experiment(
                    agent_name=self.agent_name,
                    model_used=self.model_name,
                    action=ActionType.GENERATION,
                    details={
                        "input_prompt": prompt[:500],
                        "output_response": llm_output[:500]
                    },
                    status="SUCCESS"
                )
            except Exception as e:
                print(f"   ⚠️  Logging error: {str(e)[:50]}")

            return fixed_code if fixed_code else code

        except Exception as e:
            print(f"   ⚠️  LLM error: {str(e)[:50]}")
            return code

    def _apply_basic_syntax_fixes(self, code: str, instructions: list) -> str:
        """Apply basic syntax fixes automatically."""
        fixed = code
        lines = fixed.split('\n')
        
        # Fix missing closing parenthesis on def/class lines
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            # Check for function/class definitions with missing closing paren
            if stripped.startswith(('def ', 'class ')):
                # If it has opening paren but no closing paren
                if '(' in stripped and ')' not in stripped:
                    # Add closing paren and colon
                    lines[i] = stripped + '):'
        
        fixed = '\n'.join(lines)
        
        # Fix missing colons on control flow statements
        lines = fixed.split('\n')
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            # Only fix lines that start with keywords but don't end with colon
            if stripped.startswith(('if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except', 'with ', 'finally:')):
                if not stripped.endswith(':'):
                    # Don't add colon if line is incomplete (no closing paren yet)
                    if ')' in stripped or '(' not in stripped:
                        lines[i] = stripped + ':'
        
        return '\n'.join(lines)

    def _has_syntax_error(self, code: str) -> bool:
        """Check if code has syntax errors."""
        if not code or not code.strip():
            return True
        try:
            ast.parse(code)
            return False
        except SyntaxError:
            return True

    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        # Try to find code blocks
        pattern = r'```(?:python)?\n(.*?)\n```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1)
        
        return response

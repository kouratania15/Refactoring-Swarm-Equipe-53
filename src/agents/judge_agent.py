import os
import sys
import json
import re
from mistralai import Mistral
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.tools.run_pytest import run_pytest
from logs.logger import log_experiment, ActionType
from src.prompts.judge_prompt import get_judge_prompt

load_dotenv()


class JudgeAgent:
    """Agent Juge : Exécute les tests et valide le code."""

    def __init__(self, model_name="mistral-large-latest"):
        self.model_name = model_name
        self.agent_name = "Judge_Agent"
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in .env")
        self.client = Mistral(api_key=api_key)
        self.model = model_name

    def run_tests(self, target_dir: Path) -> dict:
        """Run tests and analyze results."""
        print(f"\n🧪 {self.agent_name}: Running tests...")

        try:
            # Run pytest
            pytest_result = run_pytest(str(target_dir))
            success = pytest_result.get("success", False)
            stdout = pytest_result.get("stdout", "")
            stderr = pytest_result.get("stderr", "")

            # Parse test results
            test_summary = self._parse_pytest_output(stdout, stderr)

            # Get LLM judgment
            judge_decision = self._get_llm_judgment(stdout, stderr, success)

            # Display detailed test results in JSON
            test_report = {
                "tests_success": success,
                "test_summary": test_summary,
                "judge_decision": judge_decision
            }
            
            print("\n" + "="*70)
            print("TEST RESULTS JSON REPORT:")
            print("="*70)
            print(json.dumps(test_report, indent=2, ensure_ascii=False))
            print("="*70 + "\n")

            # Log experiment
            try:
                log_experiment(
                    agent_name=self.agent_name,
                    model_used=self.model_name,
                    action=ActionType.VALIDATION,
                    details={
                        "input_prompt": f"Analyze test results for {target_dir}",
                        "output_response": json.dumps(test_report, ensure_ascii=False)[:1000],
                        "tests_summary": test_summary
                    },
                    status="SUCCESS"
                )
            except Exception as e:
                print(f"   ⚠️  Logging error: {str(e)[:50]}")

            # Prepare response
            return {
                "all_passed": success,
                "total_tests": test_summary.get("total", 0),
                "passed": test_summary.get("passed", 0),
                "failures": test_summary.get("failed", 0),
                "judge_status": judge_decision.get("status", "UNKNOWN"),
                "judge_reason": judge_decision.get("reason", "No reason provided"),
                "judge_action": judge_decision.get("action", "STOP")
            }

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:50]}")
            error_report = {
                "error": str(e),
                "judge_status": "ERROR",
                "judge_action": "STOP"
            }
            print("\n" + "="*70)
            print("ERROR REPORT JSON:")
            print("="*70)
            print(json.dumps(error_report, indent=2, ensure_ascii=False))
            print("="*70 + "\n")
            return {
                "all_passed": False,
                "judge_status": "FAIL_UNCERTAIN",
                "judge_reason": f"Error running tests: {str(e)[:100]}",
                "judge_action": "STOP"
            }

    def _parse_pytest_output(self, stdout: str, stderr: str) -> dict:
        """Parse pytest output to extract test counts."""
        summary = {"total": 0, "passed": 0, "failed": 0}
        
        output = stdout + stderr
        
        # Look for pytest summary line
        match = re.search(r'(\d+) passed', output)
        if match:
            summary["passed"] = int(match.group(1))
        
        match = re.search(r'(\d+) failed', output)
        if match:
            summary["failed"] = int(match.group(1))
        
        summary["total"] = summary["passed"] + summary["failed"]
        
        return summary

    def _get_llm_judgment(self, stdout: str, stderr: str, success: bool) -> dict:
        """Use LLM to analyze test results and make decision."""
        try:
            # Extract failed test names
            failed_tests = self._extract_failed_tests(stdout, stderr)
            
            # Extract error details from stderr
            error_details = self._extract_error_details(stderr)
            
            template = get_judge_prompt()
            prompt = template.format(
                test_output=f"Success: {success}\n\nFailed tests: {failed_tests}\n\nError details:\n{error_details}\n\nFull output:\n{stdout[:500]}\n\nStderr:\n{stderr[:500]}"
            )

            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            llm_output = response.choices[0].message.content
            
            # Try to parse JSON response with improved extraction
            try:
                decision = self._extract_json_from_response(llm_output)
                return decision
            except Exception as parse_error:
                print(f"   [DEBUG] JSON parse error: {str(parse_error)[:100]}")
                print(f"   [DEBUG] Raw LLM output: {llm_output[:200]}")

            # Build detailed response based on test success
            if success:
                return {
                    "status": "SUCCESS",
                    "reason": "All tests passed",
                    "action": "STOP",
                    "recommendation": "Code is ready",
                    "failed_tests": [],
                    "error_type": "NONE"
                }
            else:
                return {
                    "status": "FAIL_TEST",
                    "reason": f"Tests failed: {', '.join(failed_tests) if failed_tests else 'Unknown'}",
                    "action": "REQUIRE_HUMAN",
                    "recommendation": "Review and fix test failures",
                    "failed_tests": failed_tests,
                    "error_details": error_details,
                    "error_type": self._classify_error(error_details)
                }

        except Exception as e:
            print(f"   [ERROR] LLM judgment error: {str(e)[:50]}")
            return {
                "status": "ERROR",
                "reason": f"Could not analyze tests",
                "action": "STOP",
                "error_type": "ANALYSIS_ERROR"
            }
    
    def _extract_json_from_response(self, llm_output: str) -> dict:
        """Extract JSON from LLM response, handling markdown code blocks."""
        cleaned = llm_output.strip()
        
        # Remove markdown code blocks if present
        if '```json' in cleaned:
            cleaned = cleaned.split('```json')[1]
            if '```' in cleaned:
                cleaned = cleaned.split('```')[0]
        elif '```' in cleaned:
            parts = cleaned.split('```')
            if len(parts) >= 2:
                cleaned = parts[1]
        
        cleaned = cleaned.strip()
        
        # Try to find JSON object
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = cleaned[start:end]
            return json.loads(json_str)
        
        raise ValueError("No valid JSON found in response")
    
    def _extract_failed_tests(self, stdout: str, stderr: str) -> list:
        """Extract failed test names from pytest output."""
        failed_tests = []
        output = stdout + stderr
        
        # Look for FAILED test patterns
        pattern = r'FAILED ([\w/:\.]+::\w+)'
        matches = re.findall(pattern, output)
        failed_tests.extend(matches)
        
        # Also look for test names with assertion errors
        pattern = r'(test_\w+).*(?:AssertionError|Error|Exception)'
        matches = re.findall(pattern, output)
        for match in matches:
            if match not in failed_tests:
                failed_tests.append(match)
        
        return failed_tests
    
    def _extract_error_details(self, stderr: str) -> str:
        """Extract detailed error information from stderr."""
        lines = stderr.split('\n')
        errors = []
        
        for i, line in enumerate(lines):
            # Look for common error indicators
            if any(keyword in line for keyword in ['Error', 'error', 'FAILED', 'AssertionError', 'TypeError', 'ValueError', 'SyntaxError']):
                # Capture this line and the next few lines
                context = '\n'.join(lines[i:min(i+3, len(lines))])
                if context not in errors:
                    errors.append(context)
        
        return '\n'.join(errors[:5]) if errors else "No specific error details found"
    
    def _classify_error(self, error_details: str) -> str:
        """Classify the type of error."""
        if 'AssertionError' in error_details:
            return 'LOGIC_ERROR'
        elif 'SyntaxError' in error_details or 'IndentationError' in error_details:
            return 'SYNTAX_ERROR'
        elif 'TypeError' in error_details or 'AttributeError' in error_details:
            return 'TYPE_ERROR'
        elif 'ImportError' in error_details or 'ModuleNotFoundError' in error_details:
            return 'IMPORT_ERROR'
        else:
            return 'UNKNOWN_ERROR'

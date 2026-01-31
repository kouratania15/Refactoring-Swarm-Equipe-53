"""
Orchestrator for multi-agent Python refactoring system.
Coordinates Auditor, Fixer, and Judge agents in an iterative loop.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Import agents
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.agents.auditor_agent import AuditorAgent
from src.agents.fixer_agent import FixerAgent
from src.agents.judge_agent import JudgeAgent
from logs.logger import log_experiment, ActionType

load_dotenv()


class CodeRefactorOrchestrator:
    """
    Main orchestrator for code refactoring.
    Coordinates 3 agents in iterative loop until convergence.
    """
    
    def __init__(self, max_iterations: int = 5, model_name: str = "mistral-large-latest"):
        """
        Initialize orchestrator with agents.
        
        Args:
            max_iterations: Maximum number of refactoring iterations
            model_name: LLM model to use for all agents
        """
        self.max_iterations = max_iterations
        self.model_name = model_name
        
        print(f"\n{'='*70}")
        print(f"🚀 PYTHON REFACTORING ORCHESTRATOR")
        print(f"{'='*70}")
        print(f"📊 Configuration:")
        print(f"   - LLM Model: {model_name}")
        print(f"   - Max Iterations: {max_iterations}")
        
        # Initialize agents
        try:
            self.auditor = AuditorAgent(model_name=model_name)
            self.fixer = FixerAgent(model_name=model_name)
            self.judge = JudgeAgent(model_name=model_name)
            print(f"   ✅ Agents initialized successfully\n")
        except Exception as e:
            print(f"   ❌ Initialization error: {e}\n")
            raise
    
    def refactor(self, target_dir: Path) -> dict:
        """
        Launch complete refactoring process.
        
        Args:
            target_dir: Directory containing code to analyze
        
        Returns:
            dict: Refactoring summary with statistics
        """
        if not target_dir.exists():
            raise ValueError(f"Directory {target_dir} does not exist")
        
        print(f"📂 Target directory: {target_dir}")
        print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        stats = {
            "start_time": datetime.now(),
            "target_dir": str(target_dir),
            "iterations": 0,
            "total_issues_found": 0,
            "total_files_modified": 0,
            "final_status": "UNKNOWN",
            "final_message": "",
            "all_issues_detected": [],
            "all_fixes_applied": []
        }
        
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            stats["iterations"] = iteration
            
            print(f"\n{'='*70}")
            print(f"🔄 ITERATION {iteration}/{self.max_iterations}")
            print(f"{'='*70}")
            
            # PHASE 1: AUDIT
            print(f"\n┌─ PHASE 1: AUDIT")
            plan = self.auditor.analyze(target_dir)
            
            if not plan:
                print(f"└─ ✅ No issues detected!")
                stats["final_status"] = "SUCCESS"
                stats["final_message"] = "Code is clean"
                break
            
            total_issues = sum(len(issues) for issues in plan.values())
            stats["total_issues_found"] += total_issues
            
            # Store all detected issues for logging
            for file_path, issues in plan.items():
                stats["all_issues_detected"].append({
                    "file": str(file_path),
                    "count": len(issues),
                    "issues": issues
                })
            
            print(f"└─ 📋 {total_issues} issue(s) found in {len(plan)} file(s)")
            
            # PHASE 2: FIX
            print(f"\n┌─ PHASE 2: FIX")
            fix_result = self.fixer.fix_issues(target_dir, plan, detected_issues=plan)
            
            files_modified = fix_result.get("files_modified", 0)
            fixes_log = fix_result.get("fixes_log", [])
            stats["total_files_modified"] += files_modified
            
            # Store all fixes applied
            stats["all_fixes_applied"].extend(fixes_log)
            
            if files_modified == 0:
                print(f"└─ ⚠️  No files modified")
                stats["final_status"] = "PARTIAL"
                stats["final_message"] = "Fixer could not apply fixes"
                break
            
            print(f"└─ ✅ {files_modified} file(s) modified")
            
            # PHASE 3: VALIDATE
            print(f"\n┌─ PHASE 3: VALIDATE")
            test_result = self.judge.run_tests(target_dir)
            
            all_passed = test_result.get("all_passed", False)
            judge_status = test_result.get("judge_status", "UNKNOWN")
            judge_action = test_result.get("judge_action", "STOP")
            judge_reason = test_result.get("judge_reason", "")
            
            if all_passed:
                print(f"└─ 🎉 All tests pass!")
                stats["final_status"] = "SUCCESS"
                stats["final_message"] = f"Refactoring succeeded after {iteration} iteration(s)"
                break
            else:
                print(f"└─ ❌ Tests failed")
                print(f"   📝 Status: {judge_status}")
                print(f"   💡 Action: {judge_action}")
                print(f"   📄 Reason: {judge_reason[:150]}")
                
                # Decision based on judge
                if judge_action == "REQUIRE_HUMAN":
                    stats["final_status"] = "NEEDS_HUMAN"
                    stats["final_message"] = "Human intervention required: " + judge_reason
                    break
                elif judge_action == "STOP":
                    stats["final_status"] = "STOPPED"
                    stats["final_message"] = "Judge stopped process: " + judge_reason
                    break
                elif iteration >= self.max_iterations:
                    stats["final_status"] = "MAX_ITERATIONS"
                    stats["final_message"] = f"Max iterations reached ({self.max_iterations})"
                    break
                else:
                    print(f"\n   🔄 Retrying...")
        
        # Calculate duration
        stats["end_time"] = datetime.now()
        stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()
        
        # Print summary
        self._print_summary(stats)
        
        # Save detailed report
        self._save_report(stats)
        
        # Log orchestration
        log_experiment(
            agent_name="Orchestrator",
            model_used=self.model_name,
            action=ActionType.GENERATION,
            details={
                "input_prompt": f"Refactor code in {stats['target_dir']}",
                "output_response": (
                    f"Status: {stats['final_status']}, "
                    f"Iterations: {stats['iterations']}, "
                    f"Issues: {stats['total_issues_found']}, "
                    f"Files modified: {stats['total_files_modified']}"
                ),
                "iterations": stats["iterations"],
                "issues_found": stats["total_issues_found"],
                "files_modified": stats["total_files_modified"]
            },
            status="SUCCESS" if stats["final_status"] == "SUCCESS" else "PARTIAL"
        )
        
        return stats
    
    def _print_summary(self, stats: dict):
        """Print formatted refactoring summary."""
        print(f"\n{'='*70}")
        print(f"📊 REFACTORING SUMMARY")
        print(f"{'='*70}")
        print(f"🎯 Final Status: {stats['final_status']}")
        print(f"💬 Message: {stats['final_message']}")
        print(f"🔄 Iterations: {stats['iterations']}/{self.max_iterations}")
        print(f"🔍 Issues Found: {stats['total_issues_found']}")
        print(f"📝 Files Modified: {stats['total_files_modified']}")
        print(f"⏱️  Duration: {stats['duration_seconds']:.2f}s")
        print(f"⏰ End time: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        # Status emoji
        status_emoji = {
            "SUCCESS": "🎉",
            "PARTIAL": "⚠️",
            "NEEDS_HUMAN": "👤",
            "STOPPED": "🛑",
            "MAX_ITERATIONS": "⏸️",
            "UNKNOWN": "❓"
        }
        emoji = status_emoji.get(stats["final_status"], "❓")
        
        print(f"{emoji} {stats['final_status']}: {stats['final_message']}\n")
    
    def _save_report(self, stats: dict):
        """Save summary refactoring report to file."""
        import json
        
        try:
            # Create reports directory
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            
            # Generate report filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"refactoring_report_{timestamp}.json"
            
            # Prepare report data - ONLY SUMMARY
            report_data = {
                "timestamp": datetime.now().isoformat(),
                "status": stats["final_status"],
                "message": stats["final_message"],
                "target_directory": stats["target_dir"],
                "iterations": stats["iterations"],
                "max_iterations": self.max_iterations,
                "duration_seconds": stats["duration_seconds"],
                "summary": {
                    "total_issues_detected": stats["total_issues_found"],
                    "total_files_modified": stats["total_files_modified"]
                }
            }
            
            # Write report to file
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"\n📄 Report saved: {report_file}")
            return report_file
            
        except Exception as e:
            print(f"\n⚠️  Could not save report: {str(e)[:50]}")


def validate_environment():
    """Validate that environment is correctly configured."""
    errors = []
    
    # Check API key
    if not os.getenv("MISTRAL_API_KEY"):
        errors.append("[ERROR] MISTRAL_API_KEY not found in .env")
    else:
        print("[OK] MISTRAL_API_KEY found")
    
    # Check imports
    try:
        from mistralai import Mistral
        print("[OK] mistralai package imported")
    except ImportError:
        errors.append("[ERROR] mistralai package not installed (pip install mistralai)")
    
    if errors:
        print("\n⚠️  CONFIGURATION ERRORS:")
        for error in errors:
            print(f"   {error}")
        return False
    
    return True

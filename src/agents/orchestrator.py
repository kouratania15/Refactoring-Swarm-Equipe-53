
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

# Import agents
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.agents.auditor_agent import AuditorAgent
from src.agents.fixer_agent import FixerAgent
from src.agents.judge_agent import JudgeAgent
from src.utils.logger import log_experiment, ActionType

load_dotenv()


class RefactoringState(TypedDict):
    """État global du graphe de refactoring."""
    iteration: int
    max_iterations: int
    target_dir: str
    plan: Dict[str, Any]
    detected_issues: Dict[str, Any]
    fix_results: Dict[str, Any]
    judge_result: Dict[str, Any]
    final_status: str
    final_message: str
    statistics: Dict[str, Any]


class CodeRefactorOrchestrator:
    """
    Main orchestrator for code refactoring using LangGraph.
    Coordinates agents in a StateGraph workflow.
    """
    
    def __init__(self, max_iterations: int = 5, model_name: str = "gemini-1.5-flash"):
        self.max_iterations = max_iterations
        self.model_name = model_name
        
        print(f"\n{'='*70}")
        print(f"🚀 PYTHON REFACTORING ORCHESTRATOR (LangGraph + Gemini)")
        print(f"{'='*70}")
        
        # Initialize agents
        try:
            self.auditor = AuditorAgent(model_name=model_name)
            self.fixer = FixerAgent(model_name=model_name)
            self.judge = JudgeAgent(model_name=model_name)
            print(f"   ✅ Agents initialized successfully\n")
        except Exception as e:
            print(f"   ❌ Initialization error: {e}\n")
            raise

        # Build Graph
        self.workflow = self._build_graph()

    def _build_graph(self):
        """Constructs the LangGraph state machine."""
        workflow = StateGraph(RefactoringState)

        # Define Nodes
        workflow.add_node("audit", self.audit_node)
        workflow.add_node("fix", self.fix_node)
        workflow.add_node("judge", self.judge_node)

        # Define Edges
        workflow.set_entry_point("audit")
        workflow.add_edge("audit", "fix")
        workflow.add_edge("fix", "judge")
        
        # Conditional Edge after Judge
        workflow.add_conditional_edges(
            "judge",
            self.check_completion,
            {
                "continue": "audit",
                "stop": END
            }
        )

        return workflow.compile()

    # --- NODE FUNCTIONS ---

    def audit_node(self, state: RefactoringState) -> RefactoringState:
        """Phase 1: Auditor analyzes code."""
        iteration = state["iteration"] + 1
        print(f"\n{'='*70}")
        print(f"🔄 ITERATION {iteration}/{state['max_iterations']}")
        print(f"{'='*70}")
        print(f"\n┌─ PHASE 1: AUDIT")

        target_dir = Path(state["target_dir"])
        plan = self.auditor.analyze(target_dir)
        
        total_issues = sum(len(issues) for issues in plan.values())
        print(f"└─ 📋 {total_issues} issue(s) found in {len(plan)} file(s)")
        
        # Update Stats
        state["statistics"]["total_issues_found"] += total_issues
        
        return {
            "iteration": iteration,
            "plan": plan,
            "detected_issues": plan,
            "statistics": state["statistics"]
        }

    def fix_node(self, state: RefactoringState) -> RefactoringState:
        """Phase 2: Fixer applies patches."""
        print(f"\n┌─ PHASE 2: FIX")
        
        target_dir = Path(state["target_dir"])
        plan = state["plan"]
        
        # If no issues, skip fix (technically fix_result is empty)
        if not plan:
             print(f"└─ ✅ No issues to fix")
             return {
                 "fix_results": {"files_modified": 0}, 
                 "statistics": state["statistics"]
             }

        fix_result = self.fixer.fix_issues(target_dir, plan, detected_issues=plan)
        
        files_modified = fix_result.get("files_modified", 0)
        print(f"└─ ✅ {files_modified} file(s) modified")
        
        state["statistics"]["total_files_modified"] += files_modified
        
        return {
            "fix_results": fix_result,
            "statistics": state["statistics"]
        }

    def judge_node(self, state: RefactoringState) -> RefactoringState:
        """Phase 3: Judge validates code."""
        print(f"\n┌─ PHASE 3: VALIDATE")
        
        target_dir = Path(state["target_dir"])
        test_result = self.judge.run_tests(target_dir)
        
        judge_status = test_result.get("judge_status", "UNKNOWN")
        judge_action = test_result.get("judge_action", "STOP")
        judge_reason = test_result.get("judge_reason", "")
        
        if test_result.get("all_passed", False):
            print(f"└─ 🎉 All tests pass!")
        else:
            print(f"└─ ❌ Tests failed")
            print(f"   📝 Status: {judge_status}")
            print(f"   📄 Reason: {judge_reason[:150]}")
            
        return {
            "judge_result": test_result,
            "final_status": judge_status,  # Provisional status
            "final_message": judge_reason
        }

    def check_completion(self, state: RefactoringState) -> str:
        """Decide whether to continue or stop."""
        judge_action = state["judge_result"].get("judge_action", "STOP")
        
        if judge_action == "STOP":
            return "stop"
        
        if judge_action == "REQUIRE_HUMAN":
            return "stop"
            
        if state["iteration"] >= state["max_iterations"]:
            # Hard stop on max iterations
            return "stop"
            
        # If Fixer made no changes but issues persist, we should probably stop to avoid infinite loop
        # But if Auditor found issues and Fixer failed, maybe retry? 
        # For this implementation, if Fixer modified 0 files AND Auditor found issues, we stop to avoid loop.
        if state["fix_results"].get("files_modified", 0) == 0 and sum(len(issues) for issues in state["plan"].values()) > 0:
             print("   ⚠️  Loop detected: issues found but not fixed. Stopping.")
             return "stop"

        print(f"\n   🔄 Retrying...")
        return "continue"

    # --- MAIN ENTRY POINT ---

    def refactor(self, target_dir: Path) -> dict:
        """Launch complete refactoring process using LangGraph."""
        if not target_dir.exists():
            raise ValueError(f"Directory {target_dir} does not exist")
        
        print(f"📂 Target directory: {target_dir}")
        print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Initial State
        initial_state: RefactoringState = {
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "target_dir": str(target_dir),
            "plan": {},
            "detected_issues": {},
            "fix_results": {},
            "judge_result": {},
            "final_status": "STARTING",
            "final_message": "",
            "statistics": {
                "start_time": datetime.now(),
                "total_issues_found": 0,
                "total_files_modified": 0
            }
        }
        
        # Execute Graph
        final_state = self.workflow.invoke(initial_state)
        
        # Post-process statistics for return format
        stats = final_state["statistics"]
        stats["end_time"] = datetime.now()
        stats["duration_seconds"] = (stats["end_time"] - stats["start_time"]).total_seconds()
        stats["iterations"] = final_state["iteration"]
        stats["final_status"] = final_state["final_status"]
        stats["final_message"] = final_state["final_message"]
        # Compatibility keys
        stats["target_dir"] = final_state["target_dir"]
        
        self._print_summary(stats)
        
        # Log final result
        log_experiment(
            agent_name="Orchestrator",
            model_used=self.model_name,
            action=ActionType.GENERATION,
            details={
                "input_prompt": f"Refactor code in {stats['target_dir']}",
                "output_response": f"Status: {stats['final_status']}",
                 "iterations": stats["iterations"]
            },
            status="SUCCESS"
        )
        
        return stats

    def _print_summary(self, stats: dict):
        """Print formatted refactoring summary."""
        print(f"\n{'='*70}")
        print(f"📊 REFACTORING SUMMARY")
        print(f"{'='*70}")
        print(f"🎯 Final Status: {stats.get('final_status', 'UNKNOWN')}")
        print(f"💬 Message: {stats.get('final_message', '')}")
        print(f"🔄 Iterations: {stats.get('iterations', 0)}/{self.max_iterations}")
        print(f"🔍 Issues Found: {stats.get('total_issues_found', 0)}")
        print(f"📝 Files Modified: {stats.get('total_files_modified', 0)}")
        print(f"⏱️  Duration: {stats.get('duration_seconds', 0):.2f}s")
        print(f"{'='*70}\n")


def validate_environment():
    """Validate that environment is correctly configured."""
    errors = []
    
    # Check API key (Updated for Google)
    if not os.getenv("GOOGLE_API_KEY"):
        errors.append("[ERROR] GOOGLE_API_KEY not found in .env")
    else:
        print("[OK] GOOGLE_API_KEY found")
    
    # Check imports
    try:
        import langchain_google_genai
        import langgraph
        print("[OK] langchain-google-genai & langgraph imported")
    except ImportError as e:
        errors.append(f"[ERROR] Missing dependency: {e} (pip install -r requirements.txt)")
    
    if errors:
        print("\n⚠️  CONFIGURATION ERRORS:")
        for error in errors:
            print(f"   {error}")
        return False
    
    return True

import subprocess
import sys
import os

def run_pytest(target_dir: str) -> dict:
    # Run pytest from the target directory to ensure proper imports
    result = subprocess.run(
        [sys.executable, "-m", "pytest", ".", "-v"],
        capture_output=True,
        text=True,
        cwd=target_dir
    )

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

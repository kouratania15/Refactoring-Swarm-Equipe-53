import subprocess
import sys

def run_pylint(target_dir: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "pylint", target_dir, "--output-format=json"],
        capture_output=True,
        text=True
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

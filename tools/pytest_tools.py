import subprocess

def run_pytest(target_dir: str) -> dict:
    result = subprocess.run(
        ["pytest", target_dir],
        capture_output=True,
        text=True
    )

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

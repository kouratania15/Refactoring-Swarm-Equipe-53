import subprocess

def run_pylint(target_dir: str) -> dict:
    result = subprocess.run(
        ["pylint", target_dir, "--output-format=json"],
        capture_output=True,
        text=True
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }

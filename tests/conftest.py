import os
import subprocess
import sys
import tempfile

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
TRANSLATOR = os.path.join(ROOT, "src", "translator.py")
MACHINE = os.path.join(ROOT, "src", "machine.py")


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite expected_output in golden/*.yaml instead of asserting",
    )


def run_lisp(lisp_file: str, schedule_file: str | None = None) -> str:
    """Compile lisp_file, run the simulator, and return the program output."""

    if not os.path.isabs(lisp_file):
        lisp_file = os.path.join(ROOT, lisp_file)
    if schedule_file and not os.path.isabs(schedule_file):
        schedule_file = os.path.join(ROOT, schedule_file)

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        bin_file = tmp.name

    try:
        r = subprocess.run(
            [PYTHON, TRANSLATOR, lisp_file, bin_file],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r.returncode == 0, f"Translator failed for {lisp_file}:\n{r.stdout}\n{r.stderr}"

        cmd = [PYTHON, MACHINE, bin_file]
        if schedule_file:
            cmd.append(schedule_file)

        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r.returncode == 0, f"Machine failed for {lisp_file}:\n{r.stdout}\n{r.stderr}"

        # Parse "Output: <data>\n" from stdout.
        stdout = r.stdout
        prefix = "Output: "
        idx = stdout.find(prefix)
        if idx != -1:
            raw = stdout[idx + len(prefix) :]
            if raw.endswith("\n"):
                raw = raw[:-1]
            return raw

        return stdout

    finally:
        if os.path.exists(bin_file):
            os.remove(bin_file)


def load_golden(name: str) -> dict:
    """Load golden/<name>.yaml and return it as a dict."""
    golden_path = os.path.join(ROOT, "golden", f"{name}.yaml")
    with open(golden_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def check(request):
    """Fixture used in each test: check(name) either asserts or updates the golden file.

    Normal run:
        assert actual_output == golden["expected_output"]

    With --update-golden:
        writes actual_output back into golden/<name>.yaml and always passes.
    """

    def _check(name: str):
        g = load_golden(name)
        output = run_lisp(g["source_file"], g["input_file"])

        if request.config.getoption("--update-golden"):
            g["expected_output"] = output
            golden_path = os.path.join(ROOT, "golden", f"{name}.yaml")
            with open(golden_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    g, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120
                )
            return

        assert output == g["expected_output"]

    return _check

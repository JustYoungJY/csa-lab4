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

_LOG_LINES = 200


class LiteralStr(str):
    """YAML scalar subclass that forces literal block style (| or |-)."""


def _literal_representer(dumper: yaml.Dumper, data: LiteralStr) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(LiteralStr, _literal_representer)


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite all fields in golden/*.yaml instead of asserting",
    )


def run_lisp(
    lisp_file: str, schedule_file: str | None = None
) -> tuple[str, str, str, str, str | None]:

    if not os.path.isabs(lisp_file):
        lisp_file = os.path.join(ROOT, lisp_file)
    if schedule_file and not os.path.isabs(schedule_file):
        schedule_file = os.path.join(ROOT, schedule_file)

    with open(lisp_file, encoding="utf-8") as f:
        source_text = f.read().rstrip("\n")

    stdin_text: str | None = None
    if schedule_file:
        with open(schedule_file, encoding="utf-8") as f:
            stdin_text = f.read().rstrip("\n")

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        bin_file = tmp.name
    bin_log = bin_file + ".log"

    try:
        r = subprocess.run(
            [PYTHON, TRANSLATOR, lisp_file, bin_file],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r.returncode == 0, f"Translator failed for {lisp_file}:\n{r.stdout}\n{r.stderr}"

        with open(bin_log, encoding="utf-8") as f:
            code_hex = f.read().rstrip("\n")

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
        # We search by index rather than splitlines() so that embedded newlines
        # inside the output are not lost.
        stdout = r.stdout
        prefix = "Output: "
        idx = stdout.find(prefix)
        if idx != -1:
            raw = stdout[idx + len(prefix) :]
            if raw.endswith("\n"):
                raw = raw[:-1]
            output = raw
        else:
            output = stdout

        log_lines = [line for line in r.stderr.splitlines() if not line.startswith("Ticks:")]
        log = "\n".join(log_lines[:_LOG_LINES])

        return output, code_hex, log, source_text, stdin_text

    finally:
        for path in (bin_file, bin_log):
            if os.path.exists(path):
                os.remove(path)


def load_golden(name: str) -> dict:
    """Load golden/<name>.yaml and return it as a dict."""
    golden_path = os.path.join(ROOT, "golden", f"{name}.yaml")
    with open(golden_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def check(request):
    """Fixture used in each test: check(name) either asserts or updates the golden file.

    Normal run:
        assert actual_output == golden["out_stdout"]

    With --update-golden:
        re-runs the translator + machine, then writes all fields back into
        golden/<name>.yaml. Always passes.
    """

    def _check(name: str):
        g = load_golden(name)
        output, code_hex, log, source_text, stdin_text = run_lisp(g["source_file"], g["input_file"])

        if request.config.getoption("--update-golden"):
            new_g: dict = {
                "source_file": g["source_file"],
                "in_source": LiteralStr(source_text),
                "input_file": g["input_file"],
                "in_stdin": LiteralStr(stdin_text) if stdin_text is not None else None,
                "out_stdout": LiteralStr(output),
                "out_code_hex": LiteralStr(code_hex),
                "out_log": LiteralStr(log),
            }
            golden_path = os.path.join(ROOT, "golden", f"{name}.yaml")
            with open(golden_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    new_g,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                    width=120,
                )
            return

        assert output == g["out_stdout"]

    return _check

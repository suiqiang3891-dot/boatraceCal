import json
import os
import subprocess
import sys

from boatrace_cal import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"


def test_package_module_entrypoint_runs_cli(tmp_path) -> None:
    output_path = tmp_path / "openapi.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "boatrace_cal",
            "openapi-spec",
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
    )

    assert result.returncode == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["openapi"] == "3.1.0"

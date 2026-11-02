"""Tests for the top-level `symbols` command, which exports the symbols of a project as JSON."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from serena.cli import ProjectCommands, TopLevelCommands

pytestmark = [pytest.mark.filterwarnings("ignore::UserWarning"), pytest.mark.python]

_MODULE_SOURCE = """\
import os


class Greeter:
    def greet(self, name):
        return "hello " + name


def standalone():
    return 1
"""


@pytest.fixture
def python_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "module.py").write_text(_MODULE_SOURCE, encoding="utf-8")
    (tmp_path / "other.py").write_text("def elsewhere():\n    pass\n", encoding="utf-8")
    ProjectCommands._create_project(str(tmp_path), None, ("python",))
    return tmp_path


def _symbols(runner: CliRunner, project: Path, *paths: str) -> list[dict]:
    result = runner.invoke(TopLevelCommands.symbols, [*paths, "--json", "--project", str(project)])
    assert result.exit_code == 0, f"{result.stderr}"
    document = json.loads(result.stdout)
    assert document["schema_version"] == 1
    return document["symbols"]


class TestSymbols:
    def test_stdout_is_a_json_document_with_one_based_lines_and_forward_slash_paths(self, python_project: Path) -> None:
        symbols = _symbols(CliRunner(), python_project, "pkg")

        by_name = {symbol["name"]: symbol for symbol in symbols}
        assert by_name["Greeter"] == {"name": "Greeter", "kind": "Class", "path": "pkg/module.py", "start_line": 4, "end_line": 6}
        assert by_name["Greeter/greet"]["kind"] == "Method"
        assert (by_name["Greeter/greet"]["start_line"], by_name["Greeter/greet"]["end_line"]) == (5, 6)
        assert (by_name["standalone"]["start_line"], by_name["standalone"]["end_line"]) == (9, 10)

    def test_paths_restrict_the_export(self, python_project: Path) -> None:
        runner = CliRunner()

        only_package = {symbol["path"] for symbol in _symbols(runner, python_project, "pkg")}
        everything = {symbol["path"] for symbol in _symbols(runner, python_project)}

        assert only_package == {"pkg/module.py"}
        assert everything == {"pkg/module.py", "other.py"}

    def test_a_file_path_selects_that_file(self, python_project: Path) -> None:
        paths = {symbol["path"] for symbol in _symbols(CliRunner(), python_project, str(python_project / "other.py"))}

        assert paths == {"other.py"}

    def test_progress_goes_to_stderr_not_stdout(self, python_project: Path) -> None:
        result = CliRunner().invoke(TopLevelCommands.symbols, ["--json", "--project", str(python_project)])

        assert result.exit_code == 0
        assert result.stdout.lstrip().startswith("{")
        assert "Indexing" in result.stderr

    def test_a_path_outside_the_project_is_rejected(self, python_project: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
        outside = tmp_path_factory.mktemp("outside")

        result = CliRunner().invoke(TopLevelCommands.symbols, [str(outside), "--json", "--project", str(python_project)])

        assert result.exit_code != 0
        assert "outside of the project root" in result.stderr
        assert result.stdout == ""

    def test_json_flag_is_required(self, python_project: Path) -> None:
        result = CliRunner().invoke(TopLevelCommands.symbols, ["--project", str(python_project)])

        assert result.exit_code != 0
        assert os.path.exists(python_project)

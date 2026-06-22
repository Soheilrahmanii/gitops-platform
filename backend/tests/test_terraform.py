import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from services.terraform import TerraformService


def _ok() -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    return m


def _fail(stderr: str = "something went wrong") -> MagicMock:
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = stderr
    return m


# ── call order ─────────────────────────────────────────────────────────────────

def test_apply_runs_init_before_apply():
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        TerraformService().apply("platform", "hello-world")

    commands = [c.args[0][1] for c in mock_run.call_args_list]
    assert commands == ["init", "apply"]


def test_apply_passes_auto_approve_flag():
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        TerraformService().apply("platform", "hello-world")

    apply_call = mock_run.call_args_list[1]
    assert "-auto-approve" in apply_call.args[0]


# ── tfvars content ─────────────────────────────────────────────────────────────

def test_apply_writes_team_name_to_tfvars(tmp_path):
    written_content = {}

    def fake_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("-var-file="):
                path = arg.split("=", 1)[1]
                try:
                    written_content["content"] = Path(path).read_text()
                except FileNotFoundError:
                    pass
        return _ok()

    with patch("subprocess.run", side_effect=fake_run):
        TerraformService(terraform_dir=tmp_path).apply("my-team", "my-app")

    assert 'team_name = "my-team"' in written_content["content"]


def test_apply_writes_app_name_to_tfvars(tmp_path):
    written_content = {}

    def fake_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("-var-file="):
                path = arg.split("=", 1)[1]
                try:
                    written_content["content"] = Path(path).read_text()
                except FileNotFoundError:
                    pass
        return _ok()

    with patch("subprocess.run", side_effect=fake_run):
        TerraformService(terraform_dir=tmp_path).apply("my-team", "my-app")

    assert 'app_name  = "my-app"' in written_content["content"]


# ── temp file cleanup ──────────────────────────────────────────────────────────

def test_apply_deletes_tfvars_after_success(tmp_path):
    created_paths = []

    def fake_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("-var-file="):
                created_paths.append(Path(arg.split("=", 1)[1]))
        return _ok()

    with patch("subprocess.run", side_effect=fake_run):
        TerraformService(terraform_dir=tmp_path).apply("platform", "hello-world")

    for p in created_paths:
        assert not p.exists(), f"tfvars file was not cleaned up: {p}"


def test_apply_deletes_tfvars_even_on_failure(tmp_path):
    created_paths = []

    def fake_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("-var-file="):
                created_paths.append(Path(arg.split("=", 1)[1]))
        return _fail()

    with patch("subprocess.run", side_effect=fake_run), pytest.raises(RuntimeError):
        TerraformService(terraform_dir=tmp_path).apply("platform", "hello-world")

    for p in created_paths:
        assert not p.exists()


# ── error propagation ──────────────────────────────────────────────────────────

def test_run_raises_runtime_error_on_nonzero_exit(tmp_path):
    with patch("subprocess.run", return_value=_fail("Provider not found")):
        with pytest.raises(RuntimeError, match="Provider not found"):
            TerraformService(terraform_dir=tmp_path).apply("platform", "hello-world")


def test_error_message_includes_command(tmp_path):
    with patch("subprocess.run", return_value=_fail("some error")):
        with pytest.raises(RuntimeError, match="terraform"):
            TerraformService(terraform_dir=tmp_path).apply("platform", "hello-world")


# ── terraform dir ──────────────────────────────────────────────────────────────

def test_apply_uses_injected_terraform_dir(tmp_path):
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        TerraformService(terraform_dir=tmp_path).apply("platform", "hello-world")

    for c in mock_run.call_args_list:
        assert c.kwargs["cwd"] == tmp_path


# ── destroy ────────────────────────────────────────────────────────────────────

def test_destroy_runs_init_then_destroy():
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        TerraformService().destroy("platform", "hello-world")

    commands = [c.args[0][1] for c in mock_run.call_args_list]
    assert commands == ["init", "destroy"]


def test_destroy_passes_auto_approve():
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        TerraformService().destroy("platform", "hello-world")

    destroy_call = mock_run.call_args_list[1]
    assert "-auto-approve" in destroy_call.args[0]


def test_destroy_writes_correct_tfvars(tmp_path):
    written = {}

    def fake_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("-var-file="):
                path = arg.split("=", 1)[1]
                try:
                    written["content"] = Path(path).read_text()
                except FileNotFoundError:
                    pass
        return _ok()

    with patch("subprocess.run", side_effect=fake_run):
        TerraformService(terraform_dir=tmp_path).destroy("platform", "hello-world")

    assert 'team_name = "platform"' in written["content"]
    assert 'app_name  = "hello-world"' in written["content"]


def test_destroy_cleans_up_tfvars(tmp_path):
    created_paths = []

    def fake_run(cmd, **kwargs):
        for arg in cmd:
            if arg.startswith("-var-file="):
                created_paths.append(Path(arg.split("=", 1)[1]))
        return _ok()

    with patch("subprocess.run", side_effect=fake_run):
        TerraformService(terraform_dir=tmp_path).destroy("platform", "hello-world")

    for p in created_paths:
        assert not p.exists()


def test_destroy_raises_on_failure(tmp_path):
    with patch("subprocess.run", return_value=_fail("No state file")):
        with pytest.raises(RuntimeError, match="No state file"):
            TerraformService(terraform_dir=tmp_path).destroy("platform", "hello-world")

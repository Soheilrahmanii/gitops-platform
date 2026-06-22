"""
TerraformService — shells out to the `terraform` CLI.

Why subprocess instead of the Terraform CDK or python-hcl2?
- No extra runtime dependencies.
- The same shell commands work in CI and locally.
- Terraform state stays in files, making it inspectable after a failed demo.
"""
import os
import subprocess
import tempfile
from pathlib import Path

# Resolves to /app/terraform inside the container (docker-compose mounts ./terraform:/app/terraform).
_TERRAFORM_DIR = Path(__file__).parent.parent / "terraform"


class TerraformService:
    def __init__(self, terraform_dir: Path = _TERRAFORM_DIR) -> None:
        self._dir = terraform_dir

    def apply(self, team_name: str, app_name: str) -> None:
        """Writes a tfvars file and runs terraform apply."""
        tfvars_content = (
            f'team_name = "{team_name}"\n'
            f'app_name  = "{app_name}"\n'
        )

        # Write vars to a temp file so we never mutate the shared terraform dir.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tfvars", delete=False
        ) as f:
            f.write(tfvars_content)
            tfvars_path = f.name

        try:
            self._run(["terraform", "init", "-input=false"])
            self._run([
                "terraform", "apply",
                "-auto-approve",
                "-input=false",
                f"-var-file={tfvars_path}",
                "-var=kubeconfig_path=/root/.kube/config",
            ])
        finally:
            os.unlink(tfvars_path)

    def destroy(self, team_name: str, app_name: str) -> None:
        """Destroys all Terraform-managed resources for the given team/app."""
        tfvars_content = (
            f'team_name = "{team_name}"\n'
            f'app_name  = "{app_name}"\n'
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tfvars", delete=False
        ) as f:
            f.write(tfvars_content)
            tfvars_path = f.name

        try:
            self._run(["terraform", "init", "-input=false"])
            self._run([
                "terraform", "destroy",
                "-auto-approve",
                "-input=false",
                f"-var-file={tfvars_path}",
                "-var=kubeconfig_path=/root/.kube/config",
            ])
        finally:
            os.unlink(tfvars_path)

    def _run(self, cmd: list[str]) -> None:
        env = os.environ.copy()
        env["KUBE_CONFIG_PATH"] = "/root/.kube/config"
        result = subprocess.run(
            cmd,
            cwd=self._dir,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Terraform command failed: {' '.join(cmd)}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

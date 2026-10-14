"""CI's `manage.py check --deploy` step must satisfy production validation.

It drifted once: the storage swap made five new variables required and CI run
38524126702 (29c6bf7) failed. The required names come from validation.py itself
(by booting production with an empty env), so a newly required setting fails this
test until ci.yml sets it too.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml
from django.core.management.utils import get_random_secret_key

BACKEND_DIR = Path(__file__).resolve().parent.parent
CI_YML = BACKEND_DIR.parent / ".github" / "workflows" / "ci.yml"
_ENV_NAME = re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b")


def _deploy_step() -> tuple[dict[str, str], str]:
    workflow = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    job = workflow["jobs"]["backend"]
    step = next(s for s in job["steps"] if "check --deploy" in s.get("name", ""))
    env = {**job.get("env", {}), **step.get("env", {})}
    # GitHub expressions (e.g. PYTHONPATH: ${{ github.workspace }}/ml) can't be evaluated here.
    env = {k: str(v) for k, v in env.items() if "${{" not in str(v)}
    return env, step["run"]


def _boot_production(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if k in {"PATH", "SYSTEMROOT", "HOME"}}
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=BACKEND_DIR,
        env={**clean, **env, "DJANGO_SETTINGS_MODULE": "config.settings",
             "PYTHONPATH": str(BACKEND_DIR.parent / "ml")},
        capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip


def required_by_validation() -> set[str]:
    """Every variable validation.py complains about when production gets nothing.

    DATABASE_URL is given without SSL only so base.py lets validation run (and still
    report DATABASE_URL, for the missing sslmode).
    """
    result = _boot_production(
        {"DJANGO_ENV": "production", "DATABASE_URL": "postgres://u:p@db.invalid/x"}
    )
    assert result.returncode != 0
    problems = [line for line in result.stderr.splitlines() if line.startswith("- ")]
    assert problems, result.stderr[-1500:]
    return {name for line in problems for name in _ENV_NAME.findall(line)}


def test_validation_requires_the_expected_core_settings() -> None:
    required = required_by_validation()
    # Sanity check that the extraction works; the real list is whatever validation.py says.
    expected = {"SECRET_KEY", "DATABASE_URL", "PRIVATE_BUCKET", "MEDIA_BUCKET",
                "STORAGE_ACCESS_KEY_ID", "STORAGE_SECRET_ACCESS_KEY", "MEDIA_URL"}  # fmt: skip
    assert expected <= required


def test_ci_check_deploy_step_sets_every_required_name() -> None:
    env, run = _deploy_step()
    # SECRET_KEY is generated inside the step's script, never written into the workflow.
    assert "SECRET_KEY" not in env and "export SECRET_KEY=" in run
    missing = required_by_validation() - set(env) - {"SECRET_KEY"}
    assert not missing, f"ci.yml check --deploy step does not set: {sorted(missing)}"
    assert env["PRIVATE_BUCKET"] != env["MEDIA_BUCKET"]


def test_ci_check_deploy_env_boots_production() -> None:
    env, _ = _deploy_step()
    result = _boot_production({**env, "SECRET_KEY": get_random_secret_key()})
    assert result.returncode == 0, result.stderr[-1500:]


# --- operations workflows (Render free tier: no pre-deploy command, no cron) -------

WORKFLOWS = BACKEND_DIR.parent / ".github" / "workflows"
_SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _steps(wf: dict) -> list[dict]:
    return [step for job in wf["jobs"].values() for step in job["steps"]]


def test_every_workflow_pins_third_party_actions_to_a_commit() -> None:
    for path in WORKFLOWS.glob("*.yml"):
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        for step in _steps(wf):
            if "uses" in step:
                assert _SHA_PIN.match(step["uses"]), f"{path.name}: {step['uses']}"


def test_maintenance_runs_clearsessions_daily_as_the_app_role() -> None:
    wf = _workflow("maintenance.yml")
    triggers = wf[True]  # PyYAML reads the bare `on:` key as boolean True
    (cron,) = [s["cron"] for s in triggers["schedule"]]
    minute, hour, dom, month, dow = cron.split()
    assert minute.isdigit() and hour.isdigit() and (dom, month, dow) == ("*", "*", "*")
    assert "workflow_dispatch" in triggers
    assert wf["permissions"] == {"contents": "read"}
    job = wf["jobs"]["clearsessions"]
    assert job["env"]["DJANGO_ENV"] == "maintenance"
    (step,) = [s for s in job["steps"] if "clearsessions" in s.get("run", "")]
    assert step["env"] == {"DATABASE_URL": "${{ secrets.NEON_APP_DATABASE_URL }}"}
    assert "python manage.py clearsessions" in step["run"]


def test_deploy_migrates_as_owner_before_triggering_render() -> None:
    wf = _workflow("deploy-backend.yml")
    assert wf["permissions"] == {"contents": "read"}
    steps = wf["jobs"]["migrate-then-deploy"]["steps"]
    migrate = next(i for i, s in enumerate(steps) if "manage.py migrate" in s.get("run", ""))
    deploy = next(i for i, s in enumerate(steps) if "RENDER_DEPLOY_HOOK_URL" in s.get("run", ""))
    assert migrate < deploy
    assert steps[migrate]["env"] == {"DATABASE_URL": "${{ secrets.NEON_OWNER_DATABASE_URL }}"}
    assert steps[deploy]["env"] == {
        "RENDER_DEPLOY_HOOK_URL": "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
    }
    assert wf["jobs"]["migrate-then-deploy"]["env"]["DJANGO_ENV"] == "maintenance"


def test_operations_workflows_hold_no_literal_secrets() -> None:
    """Database URLs, hooks and keys only ever come from GitHub encrypted secrets."""
    sensitive = re.compile(r"postgres(ql)?://|api\.render\.com/deploy|SECRET_KEY=[^\"$]")
    for name in ("maintenance.yml", "deploy-backend.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert not sensitive.search(text), name
        for step in _steps(yaml.safe_load(text)):
            for value in step.get("env", {}).values():
                assert str(value).startswith("${{ secrets."), (name, value)

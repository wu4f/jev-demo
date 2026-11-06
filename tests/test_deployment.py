import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cloud_cli(tmp_path, monkeypatch):
    log = tmp_path / "gcloud-calls.jsonl"
    fake = tmp_path / "gcloud"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['GCLOUD_TEST_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:4] == ['secrets', 'versions', 'describe']:\n"
        "    print(os.environ.get('GCLOUD_TEST_SECRET_STATE', 'ENABLED'))\n"
        "if sys.argv[1:4] == ['iam', 'service-accounts', 'list']:\n"
        "    print(os.environ.get('GCLOUD_TEST_EXISTING_ACCOUNT', ''))\n"
        "if sys.argv[1:3] == ['services', 'enable']:\n"
        "    sys.exit(int(os.environ.get('GCLOUD_TEST_ENABLE_STATUS', '0')))\n"
    )
    fake.chmod(0o700)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GCLOUD_TEST_LOG", str(log))
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("GOOGLE_CLOUD_REGION", "us-central1")
    monkeypatch.setenv("K_SERVICE", "jev-lab")
    monkeypatch.setenv("TYPESAFE_SECRET", "typesafe-api-key")
    monkeypatch.setenv("TYPESAFE_SECRET_VERSION", "3")
    monkeypatch.setenv("TYPESAFE_DEFAULT_MODEL", "jev-latest")
    return log


def run_script(mode):
    return subprocess.run(
        ["bash", str(ROOT / "scripts/cloud-run.sh"), mode],
        capture_output=True,
        text=True,
        check=False,
    )


def calls(log):
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def runtime_account():
    suffix = hashlib.sha256(b"jev-lab").hexdigest()[:20]
    return f"jev-{suffix}@test-project.iam.gserviceaccount.com"


def test_deploy_uses_secret_reference_and_public_service(cloud_cli):
    result = run_script("deploy")
    assert result.returncode == 0, result.stderr
    commands = calls(cloud_cli)
    grant = next(
        command for command in commands if command[:2] == ["secrets", "add-iam-policy-binding"]
    )
    assert "--role=roles/secretmanager.secretAccessor" in grant
    assert f"--member=serviceAccount:{runtime_account()}" in grant
    deploy = commands[-1]
    assert deploy[:3] == ["run", "deploy", "jev-lab"]
    assert "--update-secrets=TYPESAFE_API_KEY=typesafe-api-key:3" in deploy
    assert f"--service-account={runtime_account()}" in deploy
    assert "--allow-unauthenticated" in deploy
    assert "--ingress=all" in deploy
    assert not any("JEV_PROXY_ORIGIN=" in flag for flag in deploy)
    assert "--max-instances=2" in deploy
    assert "--concurrency=8" in deploy
    assert not any(command[:3] == ["secrets", "versions", "access"] for command in commands)


def test_button_attach_sets_runtime_identity_and_secret(cloud_cli):
    result = run_script("attach")
    assert result.returncode == 0, result.stderr
    command, public_access = calls(cloud_cli)
    assert command[:4] == ["run", "services", "update", "jev-lab"]
    assert "--update-secrets=TYPESAFE_API_KEY=typesafe-api-key:3" in command
    assert f"--service-account={runtime_account()}" in command
    assert "--ingress=all" in command
    assert public_access[:4] == ["run", "services", "add-iam-policy-binding", "jev-lab"]
    assert "--member=allUsers" in public_access
    assert "--role=roles/run.invoker" in public_access


@pytest.mark.parametrize("version", ["latest", "0", "-1", "1,OTHER=value"])
def test_version_must_be_pinned_before_cloud_changes(cloud_cli, monkeypatch, version):
    monkeypatch.setenv("TYPESAFE_SECRET_VERSION", version)
    result = run_script("deploy")
    assert result.returncode != 0
    assert "positive integer" in result.stderr
    assert calls(cloud_cli) == []


def test_disabled_secret_stops_deployment(cloud_cli, monkeypatch):
    monkeypatch.setenv("GCLOUD_TEST_SECRET_STATE", "DISABLED")
    result = run_script("deploy")
    assert result.returncode != 0
    assert "not enabled" in result.stderr
    assert len(calls(cloud_cli)) == 2


def test_prepare_reuses_existing_account(cloud_cli, monkeypatch):
    monkeypatch.setenv("GCLOUD_TEST_EXISTING_ACCOUNT", runtime_account())
    result = run_script("prepare")
    assert result.returncode == 0, result.stderr
    assert not any(
        command[:3] == ["iam", "service-accounts", "create"] for command in calls(cloud_cli)
    )


def test_cloud_failure_does_not_continue_to_deployment(cloud_cli, monkeypatch):
    monkeypatch.setenv("GCLOUD_TEST_ENABLE_STATUS", "1")
    result = run_script("deploy")
    assert result.returncode != 0
    assert len(calls(cloud_cli)) == 1

"""Tests for the gated SSH remote-host connector."""

from __future__ import annotations

from cogniprime.approval import AutoApproveGate, AutoDenyGate
from omegax.infra.ssh import (
    HostRegistry,
    RemoteResult,
    SSHConnector,
    SSHHost,
    default_lab_registry,
)


def _registry() -> HostRegistry:
    reg = HostRegistry()
    reg.register(SSHHost(name="ubuntu", hostname="10.0.0.9", user="ops", port=2222))
    return reg


def _recording_executor(calls: list[list[str]]):
    def run(argv: list[str]) -> RemoteResult:
        calls.append(argv)
        return RemoteResult(exit_code=0, stdout="ok")

    return run


def test_ssh_argv_includes_port_user_and_command() -> None:
    host = SSHHost(name="k", hostname="kali.local", user="kali", port=2200)
    argv = host.ssh_argv("uname -a")
    assert argv[:3] == ["ssh", "-p", "2200"]
    assert "kali@kali.local" in argv
    assert argv[-1] == "uname -a"


def test_scp_argv_push_and_pull() -> None:
    host = SSHHost(name="u", hostname="host", user="ubuntu")
    push = host.scp_argv("./local.txt", "/tmp/remote.txt", push=True)
    assert push[-2:] == ["./local.txt", "ubuntu@host:/tmp/remote.txt"]
    pull = host.scp_argv("./local.txt", "/tmp/remote.txt", push=False)
    assert pull[-2:] == ["ubuntu@host:/tmp/remote.txt", "./local.txt"]


def test_identity_file_and_strict_host_key_opts() -> None:
    host = SSHHost(
        name="p",
        hostname="172.16.42.1",
        user="root",
        identity_file="~/.ssh/id_ed25519",
        strict_host_key_checking=False,
    )
    argv = host.ssh_argv("ls")
    assert "-i" in argv and "~/.ssh/id_ed25519" in argv
    assert "StrictHostKeyChecking=no" in argv


def test_run_denied_without_approval_does_not_execute() -> None:
    calls: list[list[str]] = []
    conn = SSHConnector(
        registry=_registry(),
        approval=AutoDenyGate(),
        executor=_recording_executor(calls),
    )
    result = conn.run("ubuntu", "whoami")
    assert result.ok is False
    assert result.exit_code == 126
    assert calls == []  # never contacted the host
    assert any("DENIED" in line for line in conn.audit_log)


def test_run_executes_with_approval() -> None:
    calls: list[list[str]] = []
    conn = SSHConnector(
        registry=_registry(),
        approval=AutoApproveGate(),
        executor=_recording_executor(calls),
    )
    result = conn.run("ubuntu", "uname -a")
    assert result.ok is True
    assert calls and calls[0][0] == "ssh"
    assert calls[0][-1] == "uname -a"


def test_dangerous_command_is_blocked_even_with_approval() -> None:
    calls: list[list[str]] = []
    conn = SSHConnector(
        registry=_registry(),
        approval=AutoApproveGate(),  # approved, but sanitizer still blocks
        executor=_recording_executor(calls),
    )
    result = conn.run("ubuntu", "rm -rf / --no-preserve-root")
    assert result.exit_code == 126
    assert calls == []
    assert any("BLOCKED" in line for line in conn.audit_log)


def test_transfer_is_gated() -> None:
    calls: list[list[str]] = []
    denied = SSHConnector(
        registry=_registry(), approval=AutoDenyGate(), executor=_recording_executor(calls)
    )
    assert denied.transfer("ubuntu", "a.txt", "/tmp/a.txt").ok is False
    assert calls == []

    approved = SSHConnector(
        registry=_registry(), approval=AutoApproveGate(), executor=_recording_executor(calls)
    )
    assert approved.transfer("ubuntu", "a.txt", "/tmp/a.txt").ok is True
    assert calls and calls[0][0] == "scp"


def test_default_lab_registry_has_expected_hosts() -> None:
    reg = default_lab_registry()
    assert {"kali", "ubuntu", "pineapple"} <= set(
        reg.get(n).name for n in ("kali", "ubuntu", "pineapple")
    )
    assert reg.get("pineapple").hostname == "172.16.42.1"

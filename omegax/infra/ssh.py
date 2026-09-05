"""SSH remote-host connector for CogniPrime / Omega-X.

Lets the system connect to hosts **you own or are authorized to manage** (a Kali
box, an Ubuntu server, a WiFi Pineapple, etc.) to run commands and transfer
files. It shells out to the system ``ssh`` / ``scp`` binaries, so there are no
paid or third-party dependencies.

This is a neutral remote-execution/ops layer, not an attack tool. It keeps the
same safety spine as the rest of the codebase:

* every remote command passes an :class:`~cogniprime.approval.ApprovalGate`
  (deny-by-default) before it runs,
* a dangerous-command sanitizer (reused from the lifecycle hooks) blocks
  obviously destructive input,
* every attempt is appended to an audit log.

Intended for authorized administration and testing of your own infrastructure.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable

from cogniprime.approval import ActionRequest, ApprovalGate, AutoDenyGate
from omegax.core.orchestration.hooks import ToolCall, shell_sanitizer

# An executor turns an argv list into (exit_code, stdout, stderr). The default
# uses subprocess; tests inject a fake so no real network access is needed.
Executor = Callable[[list[str]], "RemoteResult"]


@dataclass(slots=True, frozen=True)
class SSHHost:
    """Connection profile for one host you manage."""

    name: str
    hostname: str
    user: str = "root"
    port: int = 22
    identity_file: str | None = None  # path to a private key
    strict_host_key_checking: bool = True

    def ssh_argv(self, command: str) -> list[str]:
        """Build the ``ssh`` argv to run ``command`` on this host."""
        argv = ["ssh", "-p", str(self.port)]
        argv += self._common_opts()
        argv.append(f"{self.user}@{self.hostname}")
        argv.append(command)
        return argv

    def scp_argv(self, local_path: str, remote_path: str, *, push: bool = True) -> list[str]:
        """Build the ``scp`` argv to push (default) or pull a file."""
        argv = ["scp", "-P", str(self.port)]
        argv += self._common_opts()
        remote = f"{self.user}@{self.hostname}:{remote_path}"
        argv += [local_path, remote] if push else [remote, local_path]
        return argv

    def _common_opts(self) -> list[str]:
        opts: list[str] = []
        if self.identity_file:
            opts += ["-i", self.identity_file]
        if not self.strict_host_key_checking:
            # Opt-out is explicit; default keeps host-key verification ON.
            opts += ["-o", "StrictHostKeyChecking=no"]
        return opts


@dataclass(slots=True)
class RemoteResult:
    """Outcome of a remote command or transfer."""

    exit_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class HostRegistry:
    """A named set of manageable hosts."""

    def __init__(self) -> None:
        self._hosts: dict[str, SSHHost] = {}

    def register(self, host: SSHHost) -> None:
        self._hosts[host.name] = host

    def get(self, name: str) -> SSHHost:
        return self._hosts[name]

    def __contains__(self, name: str) -> bool:
        return name in self._hosts

    def __len__(self) -> int:
        return len(self._hosts)


def _subprocess_executor(argv: list[str]) -> RemoteResult:  # pragma: no cover - network
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    return RemoteResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


class SSHConnector:
    """Runs gated, audited commands on registered hosts over SSH."""

    def __init__(
        self,
        *,
        registry: HostRegistry | None = None,
        approval: ApprovalGate | None = None,
        executor: Executor | None = None,
    ) -> None:
        self.registry = registry or HostRegistry()
        self.approval = approval or AutoDenyGate()
        self._executor = executor or _subprocess_executor
        self.audit_log: list[str] = []

    def run(self, host_name: str, command: str) -> RemoteResult:
        """Run ``command`` on a host, gated by sanitizer + approval.

        Returns a non-zero :class:`RemoteResult` (without contacting the host)
        when the command is blocked by the sanitizer or denied by the gate.
        """
        host = self.registry.get(host_name)

        allowed, reason = shell_sanitizer(ToolCall(tool="bash", args={"command": command}))
        if not allowed:
            self.audit_log.append(f"BLOCKED {host_name}: {command} ({reason})")
            return RemoteResult(exit_code=126, stderr=f"blocked: {reason}")

        request = ActionRequest(
            kind="ssh_exec",
            summary=f"Run on {host_name} ({host.user}@{host.hostname}): {command}",
            reversible=False,
        )
        if not self.approval.review(request):
            self.audit_log.append(f"DENIED {host_name}: {command}")
            return RemoteResult(exit_code=126, stderr="approval denied")

        self.audit_log.append(f"RUN {host_name}: {command}")
        return self._executor(host.ssh_argv(command))

    def transfer(
        self, host_name: str, local_path: str, remote_path: str, *, push: bool = True
    ) -> RemoteResult:
        """Push or pull a file, gated by approval (no sanitizer — paths only)."""
        host = self.registry.get(host_name)
        direction = "push" if push else "pull"
        request = ActionRequest(
            kind="ssh_transfer",
            summary=f"{direction} {local_path} <-> {host_name}:{remote_path}",
            reversible=False,
        )
        if not self.approval.review(request):
            self.audit_log.append(f"DENIED {host_name}: {direction} {local_path}")
            return RemoteResult(exit_code=126, stderr="approval denied")
        self.audit_log.append(f"{direction.upper()} {host_name}: {local_path} <-> {remote_path}")
        return self._executor(host.scp_argv(local_path, remote_path, push=push))


def default_lab_registry() -> HostRegistry:
    """A starter registry with common lab-host profiles.

    Hostnames/users are conventional defaults you should edit to match your own
    devices. The WiFi Pineapple's default management address is 172.16.42.1.
    Only add hosts you are authorized to manage.
    """
    registry = HostRegistry()
    registry.register(SSHHost(name="kali", hostname="kali.local", user="kali"))
    registry.register(SSHHost(name="ubuntu", hostname="ubuntu.local", user="ubuntu"))
    registry.register(
        SSHHost(name="pineapple", hostname="172.16.42.1", user="root")
    )
    return registry

# -*- coding: utf-8 -*-
"""Background-service runtime substrate (BG-1 … BG-4) — stdlib-only.

The shared runtime the Librarian / Session-Review / Evaluator services plug into:
- BG-1: cron-like scheduling on Windows / Linux / macOS.
- BG-2: runs persistently + restarts on boot (uptime guarantee) — expressed as
  per-OS install descriptors (systemd unit / launchd plist / Task Scheduler).
- BG-3: an internal self-check that verifies the service is actually doing its job.
- BG-4: reliably ships output off-machine — a `LogShipper` interface with a
  stdlib local-JSONL fallback; the off-machine HTTP shipper is an adapter.

The deterministic core (the scheduler's due/run/health logic + the descriptor
generators + the file shipper) is stdlib-only and unit-tested. The actual daemon
process, boot-time registration, and network log-shipping are the operator's to
apply (this module GENERATES what they install/run; it does not itself daemonize).
"""
from __future__ import annotations

import json
import time
import xml.sax.saxutils as _saxutils
from pathlib import Path
from typing import Any, Callable, Optional


def _reject_control(value: Any, field: str) -> str:
    """Guard against descriptor injection: a newline / control char in a
    line-oriented unit/INI field (systemd, schtasks) would inject an arbitrary
    directive. Reject it rather than emit it."""
    s = str(value)
    if any((ord(c) < 32 and c != "\t") for c in s):
        raise ValueError(f"{field} contains a control character (descriptor-injection guard)")
    return s


def _xml(value: Any) -> str:
    """XML-escape a value for safe interpolation into a launchd plist / Task
    Scheduler XML (so `&` / `<` / `>` / quotes can't break or inject markup)."""
    return _saxutils.escape(str(value), {'"': "&quot;", "'": "&apos;"})


class ServiceTask:
    """A scheduled unit of background work: run `fn` no more than once per
    `interval_seconds`. Tracks last-run / last-success / last-error for the
    self-check (BG-3)."""

    def __init__(self, name: str, interval_seconds: int, fn: Optional[Callable[[], Any]] = None):
        self.name = name
        self.interval = int(interval_seconds)
        self.fn = fn
        self.last_run: Optional[int] = None
        self.last_success: Optional[int] = None
        self.last_error: Optional[str] = None
        self.runs = 0

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name, "interval": self.interval, "runs": self.runs,
            "last_run": self.last_run, "last_success": self.last_success,
            "last_error": self.last_error,
        }


class Scheduler:
    """A cron-like scheduler (BG-1). Deterministic: `due(now)` / `run_due(now)` /
    `health(now)` take the current epoch time so they are testable without sleeping.
    `run_forever` is the thin daemon loop (inject `now_fn`/`sleep_fn`)."""

    def __init__(self) -> None:
        self.tasks: dict[str, ServiceTask] = {}

    def register(self, task: ServiceTask) -> ServiceTask:
        if task.name in self.tasks:
            raise ValueError(f"duplicate task name: {task.name}")
        self.tasks[task.name] = task
        return task

    def due(self, now: int) -> list[str]:
        return sorted(
            t.name for t in self.tasks.values()
            if t.last_run is None or (now - t.last_run) >= t.interval
        )

    def run_due(self, now: int) -> dict[str, str]:
        results: dict[str, str] = {}
        for name in self.due(now):
            t = self.tasks[name]
            t.last_run = now
            t.runs += 1
            try:
                if t.fn is not None:
                    t.fn()
                t.last_success = now
                t.last_error = None
                results[name] = "ok"
            except Exception as exc:  # a failing task must not crash the runtime
                t.last_error = repr(exc)
                results[name] = "error"
        return results

    def health(self, now: int, stale_factor: float = 2.0) -> dict[str, Any]:
        """BG-3 self-check — a task is STALE if it has not SUCCEEDED within
        `stale_factor * interval`. `healthy` is True only if no task is stale."""
        stale = []
        for t in self.tasks.values():
            if t.last_success is None or (now - t.last_success) > stale_factor * t.interval:
                stale.append(t.name)
        return {
            "healthy": not stale,
            "stale_tasks": sorted(stale),
            "tasks": {name: t.summary() for name, t in self.tasks.items()},
        }

    def run_forever(
        self,
        now_fn: Callable[[], int] = lambda: int(time.time()),
        sleep_fn: Callable[[float], Any] = time.sleep,
        tick_seconds: float = 1.0,
        max_ticks: Optional[int] = None,
    ) -> int:
        """The daemon loop (BG-1/BG-2-at-runtime). Each tick runs due tasks then
        sleeps. `max_ticks` bounds it for tests; production passes None (forever).
        Returns the number of ticks executed."""
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            self.run_due(now_fn())
            sleep_fn(tick_seconds)
            ticks += 1
        return ticks


# --- per-OS install descriptors (BG-1 cron-like + BG-2 boot-start/restart) --- #

def systemd_unit(name: str, exec_start: str, *, description: str = "",
                 user: Optional[str] = None, working_dir: Optional[str] = None,
                 restart: str = "always", restart_sec: int = 10) -> str:
    """A Linux systemd `.service` unit — `Restart=always` (BG-2 uptime) +
    `WantedBy=multi-user.target` (start on boot). String inputs are guarded
    against newline/control-char injection of extra directives."""
    name = _reject_control(name, "name")
    exec_start = _reject_control(exec_start, "exec_start")
    description = _reject_control(description, "description")
    if user:
        user = _reject_control(user, "user")
    if working_dir:
        working_dir = _reject_control(working_dir, "working_dir")
    lines = [
        "[Unit]",
        f"Description={description or name}",
        "After=network-online.target",
        "Wants=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"ExecStart={exec_start}",
        f"Restart={restart}",
        f"RestartSec={restart_sec}",
    ]
    if user:
        lines.append(f"User={user}")
    if working_dir:
        lines.append(f"WorkingDirectory={working_dir}")
    lines += ["", "[Install]", "WantedBy=multi-user.target", ""]
    return "\n".join(lines)


def launchd_plist(label: str, program_args: list[str], *,
                  keep_alive: bool = True, run_at_load: bool = True,
                  working_dir: Optional[str] = None) -> str:
    """A macOS launchd `.plist` — `KeepAlive` (BG-2 restart) + `RunAtLoad` (boot).
    All substitutions are XML-escaped against markup injection."""
    args_xml = "\n".join(f"    <string>{_xml(a)}</string>" for a in program_args)
    extra = f"  <key>WorkingDirectory</key>\n  <string>{_xml(working_dir)}</string>\n" if working_dir else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        f"  <key>Label</key>\n  <string>{_xml(label)}</string>\n"
        "  <key>ProgramArguments</key>\n  <array>\n" + args_xml + "\n  </array>\n"
        f"  <key>KeepAlive</key>\n  <{str(keep_alive).lower()}/>\n"
        f"  <key>RunAtLoad</key>\n  <{str(run_at_load).lower()}/>\n"
        + extra +
        "</dict>\n</plist>\n"
    )


def schtasks_command(name: str, command: str) -> str:
    """A Windows `schtasks` create line — `/sc ONSTART` (boot) so the service
    comes back after a reboot (BG-2). Restart-on-failure is set via the companion
    Task Scheduler XML (`windows_task_xml`). Inputs are control-char guarded."""
    name = _reject_control(name, "name")
    command = _reject_control(command, "command")
    return f'schtasks /create /tn "{name}" /tr "{command}" /sc ONSTART /ru SYSTEM /f'


def windows_task_xml(name: str, command: str, *, author: str = "CT6") -> str:
    """A Windows Task Scheduler XML with a boot trigger + restart-on-failure
    (BG-2). Register with `schtasks /create /tn <name> /xml <file>`."""
    return (
        '<?xml version="1.0" encoding="UTF-16"?>\n'
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">\n'
        f"  <RegistrationInfo><Author>{_xml(author)}</Author><Description>{_xml(name)}</Description></RegistrationInfo>\n"
        "  <Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger></Triggers>\n"
        "  <Settings>\n"
        "    <RestartOnFailure><Interval>PT1M</Interval><Count>999</Count></RestartOnFailure>\n"
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>\n"
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>\n"
        "    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>\n"
        "  </Settings>\n"
        f"  <Actions><Exec><Command>{_xml(command)}</Command></Exec></Actions>\n"
        "</Task>\n"
    )


_PLATFORMS = ("linux", "darwin", "windows")


def install_descriptor(platform: str, name: str, command: str, **kwargs) -> dict[str, str]:
    """Return the boot-start/restart install descriptor for `platform`
    (`linux` / `darwin` / `windows`): `{kind, filename, content, register_hint}`."""
    platform = platform.lower()
    if platform == "linux":
        return {
            "kind": "systemd",
            "filename": f"{name}.service",
            "content": systemd_unit(name, command, **kwargs),
            "register_hint": f"sudo systemctl enable --now {name}",
        }
    if platform == "darwin":
        return {
            "kind": "launchd",
            "filename": f"{name}.plist",
            "content": launchd_plist(name, command.split() if isinstance(command, str) else command),
            "register_hint": f"launchctl load -w ~/Library/LaunchAgents/{name}.plist",
        }
    if platform == "windows":
        return {
            "kind": "schtasks",
            "filename": f"{name}.xml",
            "content": windows_task_xml(name, command),
            "register_hint": f'schtasks /create /tn "{name}" /xml {name}.xml',
        }
    raise ValueError(f"unsupported platform {platform!r} (one of {_PLATFORMS})")


# --- log shipping (BG-4) ----------------------------------------------------- #

class LogShipper:
    """Abstract off-machine log shipper (BG-4). `ship(record)` returns True on
    success. The off-machine HTTP shipper is an adapter (needs network + a server);
    `FileLogShipper` is the stdlib local-JSONL fallback."""

    def ship(self, record: dict[str, Any]) -> bool:
        raise NotImplementedError


class FileLogShipper(LogShipper):
    """Stdlib fallback (BG-4): append each record as a JSON line to a local file.
    The operator syncs/forwards the file off-machine out of band."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def ship(self, record: dict[str, Any]) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True) + "\n")
            return True
        except OSError:
            return False

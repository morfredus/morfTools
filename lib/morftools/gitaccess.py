"""Detect the Git access a machine really has, before cloning -- never configure it.

`morf clone` must run on a fresh machine, not only on the developer's box. That
box has had Git, SSH, a key and a GitHub-known key set up for so long that the
dependency became invisible; a new machine may have none of it. This module
answers what is actually usable so `clone` can choose or propose a protocol.

It only ever READS the environment. It never generates a key, edits ~/.ssh, adds
a key to an agent or changes any remote: detection and configuration are two
different responsibilities, and this is the detection half.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def git_available() -> bool:
    return shutil.which("git") is not None


def ssh_available() -> bool:
    return shutil.which("ssh") is not None


def ssh_key_present() -> bool:
    """A private key sitting in ~/.ssh -- a hint, not proof access works.

    Presence of a key says nothing about whether GitHub accepts it; that is what
    ssh_github_access verifies. This only distinguishes "no identity at all" from
    "an identity exists", which shapes the guidance shown to the user.
    """
    ssh_dir = Path.home() / ".ssh"
    if not ssh_dir.is_dir():
        return False
    for name in ("id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"):
        if (ssh_dir / name).is_file():
            return True
    return any(ssh_dir.glob("*.pub"))


def ssh_github_access(sample_ssh_url: str, timeout: int = 20) -> bool:
    """True when Git can actually reach a repository over SSH.

    The real test, not a proxy: `git ls-remote` against a genuine repository, in
    batch mode so it never blocks on a passphrase or a host-key prompt. A key
    that exists but is not registered with GitHub, or an agent that is not
    running, both correctly answer False here.
    """
    if not (git_available() and ssh_available() and sample_ssh_url):
        return False
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": ("ssh -o BatchMode=yes "
                            "-o StrictHostKeyChecking=accept-new "
                            "-o ConnectTimeout=10"),
    }
    try:
        result = subprocess.run(["git", "ls-remote", sample_ssh_url],
                                capture_output=True, env=env,
                                timeout=timeout, check=False)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def https_reachable(sample_https_url: str, timeout: int = 20) -> bool:
    """True when Git can list the repo over HTTPS WITHOUT any interaction.

    For a private repository this needs credentials, so a False does not mean
    HTTPS is impossible -- only that it is not usable without a credential helper
    or a prompt (a fresh Git for Windows brings the Git Credential Manager, which
    would authenticate interactively at clone time). Reported as such, never used
    to forbid HTTPS.
    """
    if not (git_available() and sample_https_url):
        return False
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        result = subprocess.run(["git", "ls-remote", sample_https_url],
                                capture_output=True, env=env,
                                timeout=timeout, check=False)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def diagnose(sample_ssh_url: str, sample_https_url: str) -> dict:
    """A read-only snapshot of Git access, for `doctor` and for `clone` to decide."""
    ssh_ok = ssh_github_access(sample_ssh_url) if sample_ssh_url else False
    return {
        "git": git_available(),
        "ssh": ssh_available(),
        "ssh_key": ssh_key_present(),
        "ssh_github": ssh_ok,
        "https": https_reachable(sample_https_url) if sample_https_url else False,
    }


def ssh_setup_hint() -> str:
    """What a user must do to enable SSH -- printed, never performed by us."""
    return (
        "To enable SSH access to GitHub (done once, by you):\n"
        "  1. Generate a key:   ssh-keygen -t ed25519 -C \"your-email\"\n"
        "  2. Copy the public key:  ~/.ssh/id_ed25519.pub\n"
        "  3. Add it at:  https://github.com/settings/keys\n"
        "  4. Test:  ssh -T git@github.com\n"
        "Then re-run the clone. morfTools never creates or installs keys for you."
    )

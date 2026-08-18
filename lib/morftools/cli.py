"""The driver: parse, ask what is missing, run over every project.

One implementation for Windows, Linux and the Raspberry Pi. It replaces
morf.sh and morf.ps1, which were the same algorithm written twice -- iterate
the projects, run git, read a JSON manifest -- with no platform-specific
mechanism anywhere in them.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from . import gitaccess
from .commands import (COMMANDS, CONFIG_MODES, PRESET_COMMANDS, cmd_doctor,
                       deploy_one, elevated, is_service_project, purge_catalog,
                       service_purge, service_uninstall, update_status)
from .config import SHARED_CONSUMERS, shared_config_path
from .report import Reporter
from .workspace import Workspace, WorkspaceError


def prompt(question: str) -> str | None:
    """Ask on the terminal, or give up honestly.

    Returns None when there is no terminal -- cron, CI, a pipe. A required
    answer is never guessed: a default preset silently chosen in CI produces
    artefacts nobody can account for.
    """
    if not sys.stdin or not sys.stdin.isatty():
        return None
    try:
        return input(question)
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return None


def _detect_platform_preset(available: set) -> str:
    """The preset this machine's OS and architecture call for, if it is offered.

    Detection follows §18: architecture and OS, never the machine's identity (an
    ARM64 server is linux-arm64 as much as a Raspberry Pi is). Only a preset the
    projects actually declare is proposed -- detecting a name nothing builds would
    help no one. Returned only when unambiguous; the caller keeps the last word.
    """
    import platform
    if platform.system() == "Windows":
        candidate = "mingw"
    elif platform.machine().lower() in ("aarch64", "arm64"):
        candidate = "linux-arm64"
    elif platform.system() == "Linux":
        candidate = "linux"
    else:
        return ""
    return candidate if candidate in available else ""


def choose_preset(workspace: Workspace) -> str:
    presets = workspace.all_presets()
    if not presets:
        return ""    # no CMake project cloned: nothing to ask

    # Priority (§18): an explicit --preset already won upstream; here, a reliable
    # detection is used before falling back to asking. The person still overrides
    # by passing --preset.
    detected = _detect_platform_preset({name for name, _, _ in presets})
    if detected:
        print(f"[INFO] no --preset given; auto-detected for this machine: {detected}",
              file=sys.stderr)
        return detected

    print("No preset given. Available presets:", file=sys.stderr)
    for index, (name, count, total) in enumerate(presets, start=1):
        print(f"  {index}) {name:<20} ({count}/{total} projects)", file=sys.stderr)

    while True:
        reply = prompt(f"Choice [1-{len(presets)}]: ")
        if reply is None:
            print("Not a terminal: rerun with --preset <name>.", file=sys.stderr)
            raise SystemExit(2)
        if reply.isdigit() and 1 <= int(reply) <= len(presets):
            chosen = presets[int(reply) - 1][0]
            print(f"[INFO] selected preset: {chosen}", file=sys.stderr)
            return chosen
        print("Invalid answer.", file=sys.stderr)


def ask_message() -> str:
    while True:
        reply = prompt("Commit message: ")
        if reply is None:
            print(
                "A commit message is required (not a terminal: use --message).",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if reply.strip():
            return reply.strip()


#: Ecosystem passes, each a named area in the report. Running them separately
#: (rather than the script's default "all") lets the summary name which one
#: failed instead of a single opaque "ecosystem".
ECOSYSTEM_PASSES = [
    ("ports", "Plan d'adressage"),
    ("versions", "Versions"),
    ("vendor", "Copies vendorées"),
    ("manifests", "Manifestes de déploiement"),
]


def _progress(active: bool, done: int, total: int, name: str):
    """Live one-line progress on stderr, so the update check is never a silent wait.

    On a terminal it rewrites a single line with a carriage return; piped or
    logged, it stays quiet rather than littering the output with spinner frames.
    stderr is used so it never contaminates the report, which is stdout.
    """
    if active:
        print(f"\r  vérification des versions… {done}/{total} {name:<24}",
              end="", file=sys.stderr, flush=True)


def _project_banner(name: str) -> None:
    """A hard separator before each project processed.

    A run over the whole parc (install, update, upgrade, build...) is otherwise
    one continuous wall of output where the boundary between two services is a
    single faint `[name]` line. A full-width rule turns it into distinct blocks
    the eye can scan in the terminal. ASCII only, so it renders the same on the
    Windows console, Linux and the Raspberry Pi.
    """
    bar = "=" * 72
    print()
    print(bar)
    print(f"  {name}")
    print(bar)


def _progress_clear(active: bool):
    if active:
        print("\r" + " " * 56 + "\r", end="", file=sys.stderr, flush=True)


def _shared_config_relevant() -> bool:
    """Cette machine consomme-t-elle le fichier partage morfsystem.json ?

    Vrai si le fichier est deja deploye, ou si morfMonitor / morfDashboard tourne
    ici. Sur une machine de build pur (aucun consommateur, aucun /etc), on ne va
    pas semer un fichier de configuration partagee dont rien ne se sert.
    """
    if shared_config_path().exists():
        return True
    import platform
    for name in SHARED_CONSUMERS:
        if platform.system() == "Windows":
            probe = subprocess.run(["sc.exe", "query", name],
                                   capture_output=True, check=False)
            if probe.returncode == 0:
                return True
        else:
            probe = subprocess.run(
                ["systemctl", "list-unit-files", f"{name}.service"],
                capture_output=True, text=True, check=False)
            if probe.returncode == 0 and name in probe.stdout:
                return True
    return False


def _merge_shared_config() -> None:
    """Mise a niveau NON destructive du fichier partage, pendant `upgrade`.

    Le pendant, pour /etc/morfsystem/morfsystem.json, du merge que service.py
    update fait deja pour la config propre de chaque service : ajoute les cles
    nouvelles du clone, garde tous les choix locaux. Delegue a `config.py shared
    merge`, ELEVE car il ecrit sous /etc -- comme le deploiement d'un service,
    c'est la seule etape qui demande les droits, jamais le git.
    """
    config_py = Path(__file__).resolve().parents[2] / "config.py"
    _project_banner("configuration partagee (morfsystem.json)")
    rc = subprocess.run(
        elevated([sys.executable, str(config_py), "shared", "merge"]),
        check=False).returncode
    if rc != 0:
        print("[WARN] la mise a niveau de la config partagee n'a pas abouti "
              "(relancer depuis un shell eleve si elle a demande des droits)",
              file=sys.stderr)


def run_doctor(workspace: Workspace, projects: list, verbose: bool,
               check_updates: bool) -> int:
    """Doctor with a readable report: capture every check, summarise, advise.

    Nothing is lost -- `--verbose` still prints each line. What changes by
    default is that the sixty green lines collapse to a count, and the run ends
    with the failures and what to do about each.

    The check for newer versions is a NETWORK step (a git fetch per clone), so it
    is off by default: a routine `doctor` stays local and instant. `--update`
    turns it on, with a live progress line so the wait is never a silent one.
    """
    reporter = Reporter(verbose, updates_checked=check_updates)
    scripts = workspace.tool_dir / "scripts"

    def capture(cmd):
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout + result.stderr

    for which, label in ECOSYSTEM_PASSES:
        text = capture([sys.executable, str(scripts / "ecosystem-check.py"),
                        str(workspace.root), str(workspace.manifest_path), which])
        reporter.feed(text, group="Écosystème", name=label)

    text = capture([sys.executable, str(scripts / "exec-bits.py"),
                    str(workspace.root), "--check"])
    reporter.feed(text, group="Écosystème", name="Bits exécutables")

    # Git access: what a fresh machine can actually do, so `clone` is understood
    # before it is run. The cheap local checks always show; the live GitHub tests
    # are a network step, gated on --update like the version check.
    sample = projects[0].local_name if projects else ""
    ssh_url = workspace.clone_url(sample, "ssh") if sample else ""
    https_url = workspace.clone_url(sample, "https") if sample else ""
    lines = [
        "[OK] git présent" if gitaccess.git_available() else "[FAIL] git absent",
        "[OK] ssh présent" if gitaccess.ssh_available()
        else "[WARN] ssh absent (clone HTTPS possible)",
        "[OK] clé SSH présente" if gitaccess.ssh_key_present()
        else "[WARN] clé SSH absente",
    ]
    if check_updates and ssh_url:
        lines.append("[OK] accès GitHub SSH vérifié"
                     if gitaccess.ssh_github_access(ssh_url)
                     else "[WARN] accès GitHub SSH indisponible "
                          "(utiliser --protocol https)")
        lines.append("[OK] clone HTTPS accessible"
                     if gitaccess.https_reachable(https_url)
                     else "[WARN] clone HTTPS : identifiants requis à la demande")
    else:
        lines.append("[SKIP] accès GitHub SSH/HTTPS (réseau ; --update)")
    reporter.feed("\n".join(lines), group="Accès Git", name="environnement")

    branch = workspace.branch
    live = check_updates and sys.stderr.isatty()
    total = len(projects) + 1        # the projects, plus morfTools itself

    for index, project in enumerate(projects, start=1):
        if not project.exists:
            reporter.feed("[SKIP] not cloned", group="Projets",
                          name=project.local_name)
            continue
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            ok = cmd_doctor(workspace, project)
        captured = buffer.getvalue()
        text = captured
        if check_updates:
            _progress(live, index, total, project.name)
            name = project.name
            # The remedy follows what runs here, read from the probe cmd_doctor
            # just did -- no second round trip:
            #   - service answering (version reported)     -> upgrade
            #   - installed but stopped (maybe on purpose) -> update, and only if
            #     wanted, upgrade -- shown on two lines, with the state noted
            #   - not installed / GUI / cannot tell        -> update
            # Upgrading a service that is not running would rebuild and restart
            # what this machine does not, or was deliberately stopped.
            answering = ("matches project" in captured
                         or "differs from project" in captured)
            note = ""
            if answering:
                remedy = f"-> python3 morf.py upgrade --only {name}"
            elif "installed but not running" in captured:
                note = "service installé mais inactif"
                remedy = (f"-> python3 morf.py update --only {name}\n"
                          f"   puis, si vous le souhaitez : "
                          f"python3 morf.py upgrade --only {name}")
            else:
                remedy = f"-> python3 morf.py update --only {name}"
            text += update_status(project.path, branch, remedy, note)
        reporter.feed(text, group="Projets",
                      name=project.local_name, forced_fail=(ok is False))

    # morfTools checks ITSELF, but only when the network step is on: it is not a
    # project in the manifest, so nothing else would ever tell you the tool is
    # out of date. The remedy is a plain 'git pull --ff-only', with no path:
    # every morf command is already run from this directory (that is how
    # 'python3 morf.py ...' resolves at all), so the self-update runs from the
    # same place. An absolute path baked into the message would be specific to
    # one machine and break on the next, which is exactly what the rest of the
    # tool avoids by deriving everything from its own location.
    if check_updates:
        _progress(live, total, total, "morfTools")
        reporter.feed(update_status(workspace.tool_dir, branch, "-> git pull --ff-only"),
                      group="Outil", name="morfTools")
        _progress_clear(live)

    return reporter.render()



def _confirm_destructive_purge(destructive_lines: list, machine_wide: bool,
                               assume_yes: bool) -> bool:
    """Guard a real purge that would lose data for good.

    `--yes` is the explicit override. Without it, a terminal is asked to type a
    word -- not a bare y/N a fast Enter could sail through -- and a
    non-interactive run is refused rather than guessed at: a cron job must say
    --yes to erase, never have it assumed. A purge spanning the whole machine
    asks for the stronger token, so `morf purge --all` cannot be a reflex.
    """
    print("\nThis will PERMANENTLY erase:")
    for line in destructive_lines:
        print(f"    {line}")
    if assume_yes:
        return True
    token = "PURGE ALL" if machine_wide else "PURGE"
    reply = prompt(f'\nType "{token}" to confirm (anything else cancels): ')
    if reply is None:
        print("Not a terminal: re-run with --yes to confirm.", file=sys.stderr)
        return False
    return reply.strip() == token


def _print_purge_summary(results: list, dry_run: bool) -> None:
    """One block at the end saying exactly what each project did (or did not).

    morfTools must never hide what the projects actually ran: after a sweep, the
    reader needs to see per project whether the erasure happened, was a dry-run
    preview, or failed -- not a single opaque line.
    """
    print()
    print("=" * 72)
    print("  purge --dry-run (rien supprimé)" if dry_run else "  purge")
    print("=" * 72)
    for name, outcome, ids in results:
        shown = ", ".join(ids) if ids else "--all"
        print(f"  {name:<24} {shown:<28} {outcome}")


def run_purge(workspace: Workspace, args) -> int:
    """Erase declared data across the machine, driven by what each project announces.

    morfTools reads no service.json and knows no data location: it asks each
    clone what it can erase (`purge --list`), shows or forwards the chosen
    categories, and lets the project do the erasing. The plan is built the same
    way for a dry-run and for the real run; only whether service.py finally
    removes anything differs.
    """
    projects = workspace.projects()

    target = None
    ids: list = []
    if args.targets:
        wanted = args.targets[0].lower()
        matches = [p for p in projects if p.name.lower() == wanted]
        if not matches:
            print(f"No project named '{args.targets[0]}' in the manifest.",
                  file=sys.stderr)
            return 2
        target = matches[0]
        ids = args.targets[1:]

    if ids and args.all_categories:
        print("Give category ids or --all, not both.", file=sys.stderr)
        return 2

    # What is purgeable HERE: cloned projects that actually declare categories.
    # Asked of each project, never inferred, so a machine only ever offers what
    # its own components announce.
    scope = [target] if target else projects
    catalog = []
    for project in scope:
        if not project.exists:
            if target is not None:
                print(f"[SKIP] {project.local_name} (not cloned)", file=sys.stderr)
            continue
        categories = purge_catalog(project)
        if categories:
            catalog.append((project, categories))

    if not catalog:
        where = target.local_name if target else "this machine"
        print(f"No purgeable data on {where}.")
        return 0

    # No selection given: this is discovery, not a no-op. Show what is available
    # and how to name it, rather than doing something unasked.
    if not ids and not args.all_categories:
        print("Purgeable data on this machine:\n")
        for project, categories in catalog:
            print(f"  {project.name}")
            for category in categories:
                mark = "  [destructive]" if category.get("destructive") else ""
                print(f"      {category['id']:<18}{category.get('label', '')}{mark}")
        first_project, first_cats = catalog[0]
        print("\nName what to purge, for example:")
        print(f"  morf purge {first_project.name} {first_cats[0]['id']}")
        print(f"  morf purge {first_project.name} --all")
        print("  morf purge --all            (every category above)")
        print("Add --dry-run to preview, --yes to skip confirmation.")
        return 0

    # A named list of ids is validated against the one targeted project.
    if ids:
        valid = {c["id"] for c in catalog[0][1]}
        unknown = [i for i in ids if i not in valid]
        if unknown:
            plural = "y" if len(unknown) == 1 else "ies"
            print(f"Unknown categor{plural} for {target.name}: {', '.join(unknown)}.",
                  file=sys.stderr)
            print(f"Available: {', '.join(sorted(valid))}", file=sys.stderr)
            return 2

    # Build the plan, identically for dry-run and real.
    plan = []          # (project, ids | None-for-all, selected categories)
    for project, categories in catalog:
        if ids:
            selected = [c for c in categories if c["id"] in ids]
            plan.append((project, ids, selected))
        else:
            plan.append((project, None, categories))

    machine_wide = target is None and args.all_categories
    destructive_lines = [
        f"{project.name}: {c.get('label', c['id'])}"
        for project, _, selected in plan for c in selected if c.get("destructive")
    ]
    if not args.dry_run and destructive_lines:
        if not _confirm_destructive_purge(destructive_lines, machine_wide, args.yes):
            print("Aborted.", file=sys.stderr)
            return 1

    results = []
    for project, id_list, selected in plan:
        _project_banner(project.local_name)
        rc = service_purge(project, id_list or [], all_flag=(id_list is None),
                           dry_run=args.dry_run, force=args.force)
        outcome = "OK" if rc == 0 else f"FAILED ({rc})"
        results.append((project.local_name, outcome, [c["id"] for c in selected]))

    _print_purge_summary(results, args.dry_run)
    return 0 if all(outcome == "OK" for _, outcome, _ in results) else 1


def _select_services_interactive(candidates: list):
    """A numbered toggle on the terminal -- the brief's `[x]` selection, kept a
    plain terminal script usable over SSH, not a full-screen UI. Returns the
    chosen projects, or None if the person gave up.
    """
    print("Services deployable on this machine:\n")
    for index, project in enumerate(candidates, start=1):
        print(f"  {index}) {project.name}")
    reply = prompt("\nSelect (numbers, space-separated, or 'all'): ")
    if reply is None:
        return None
    reply = reply.strip().lower()
    if reply in ("all", "*"):
        return list(candidates)
    chosen = []
    for token in reply.replace(",", " ").split():
        if token.isdigit() and 1 <= int(token) <= len(candidates):
            picked = candidates[int(token) - 1]
            if picked not in chosen:
                chosen.append(picked)
    return chosen


def _choose_config_mode():
    """Ask keep/merge/replace, defaulting to the safe keep. None if given up."""
    print("\nConfiguration:")
    print("  1) keep    (default, never overwrite an existing configuration)")
    print("  2) merge   (add the clone's new keys, keep local values)")
    print("  3) replace (overwrite from the repo; a backup is written first)")
    reply = prompt("Choice [1-3, default 1]: ")
    if reply is None:
        return None
    return {"": "keep", "1": "keep", "2": "merge",
            "3": "replace"}.get(reply.strip(), None)


def run_deploy(workspace: Workspace, args) -> int:
    """Install selected services on this machine, with a chosen config behaviour.

    Selection follows the brief's priority: an explicit CLI list or --all wins;
    otherwise a terminal offers a numbered choice; a non-interactive run with no
    selection is an error, never a guess. `--dry-run` prints the plan and touches
    nothing. Only the interactive path asks for the config mode; a scripted run
    keeps the safe default (keep) unless --config says otherwise.
    """
    projects = workspace.projects()
    candidates = [p for p in projects if p.exists and is_service_project(p)]

    interactive_selection = False
    if args.targets:
        selected = []
        for name in args.targets:
            match = [p for p in candidates if p.name.lower() == name.lower()]
            if not match:
                known = any(p.name.lower() == name.lower() for p in projects)
                if known:
                    print(f"'{name}' is not a deployable service.", file=sys.stderr)
                else:
                    print(f"No project named '{name}' in the manifest.",
                          file=sys.stderr)
                return 2
            if match[0] not in selected:
                selected.append(match[0])
    elif args.all_categories:
        selected = list(candidates)
    else:
        if not candidates:
            print("No deployable services cloned on this machine.")
            return 0
        if not (sys.stdin and sys.stdin.isatty()):
            print("Nothing selected: name one or more services, or pass --all "
                  "(a non-interactive run needs an explicit selection).",
                  file=sys.stderr)
            return 2
        selected = _select_services_interactive(candidates)
        interactive_selection = True
        if selected is None:
            print("Aborted.", file=sys.stderr)
            return 1

    if not selected:
        print("No service selected.")
        return 0

    # Config behaviour: an explicit --config wins; an interactive selection is
    # asked; a scripted run keeps the safe default.
    config_mode = args.config
    if config_mode is None:
        if interactive_selection:
            config_mode = _choose_config_mode()
            if config_mode is None:
                print("Aborted.", file=sys.stderr)
                return 1
        else:
            config_mode = "keep"

    # A build needs a preset; asked only for a real run of a CMake service.
    preset = args.preset
    if any(p.is_cmake for p in selected) and not preset and not args.dry_run:
        preset = choose_preset(workspace)

    print("\nDeployment plan:" if args.dry_run else "\nDeploying:")
    for project in selected:
        print(f"  {project.name}  [config {config_mode}]")

    if not args.dry_run and not args.yes:
        if sys.stdin and sys.stdin.isatty():
            reply = prompt("Proceed? [y/N]: ")
            if reply is None or reply.strip().lower() not in ("y", "yes", "o", "oui"):
                print("Aborted.", file=sys.stderr)
                return 1
        elif config_mode == "replace":
            # replace overwrites the deployed configuration: never silently in a
            # script. install and merge keep local values, so they may proceed.
            print("config replace overwrites configuration: pass --yes to confirm "
                  "it non-interactively.", file=sys.stderr)
            return 2

    results = []
    for project in selected:
        _project_banner(project.local_name)
        rc, steps = deploy_one(project, preset, config_mode, args.dry_run)
        outcome = "OK" if rc == 0 else f"FAILED ({rc})"
        results.append((project.local_name, outcome, steps))

    print()
    print("=" * 72)
    print("  deploy --dry-run (rien exécuté)" if args.dry_run else "  deploy")
    print("=" * 72)
    for name, outcome, steps in results:
        print(f"  {name:<24} {', '.join(steps):<40} {outcome}")
    return 0 if all(outcome == "OK" for _, outcome, _ in results) else 1


def run_uninstall(workspace: Workspace, args) -> int:
    """Uninstall selected services, with a dry-run and destructive protections.

    Removing a service is one act; removing its configuration and data (--purge)
    is a heavier, separate one -- so --purge asks for a typed token, and a sweep
    of the whole machine asks for the stronger one. A non-interactive run must
    say --yes to remove anything: a fast Enter must never destroy years of data.
    """
    projects = workspace.projects()
    candidates = [p for p in projects if p.exists and is_service_project(p)]

    def resolve(name):
        match = [p for p in candidates if p.name.lower() == name.lower()]
        if match:
            return match[0]
        known = any(p.name.lower() == name.lower() for p in projects)
        print(f"'{name}' is not a deployable service." if known
              else f"No project named '{name}' in the manifest.", file=sys.stderr)
        return None

    if args.targets:
        selected = []
        for name in args.targets:
            project = resolve(name)
            if project is None:
                return 2
            if project not in selected:
                selected.append(project)
        machine_wide = False
    elif args.only:
        project = resolve(args.only)
        if project is None:
            return 2
        selected, machine_wide = [project], False
    else:
        # Bare `uninstall` or `--all`: the whole machine.
        selected, machine_wide = list(candidates), True

    if not selected:
        print("No service to uninstall on this machine.")
        return 0

    if not args.dry_run and not args.yes:
        if not (sys.stdin and sys.stdin.isatty()):
            print("Refusing to uninstall non-interactively without --yes.",
                  file=sys.stderr)
            return 2
        print("\nWill uninstall:" if not args.purge
              else "\nWill uninstall AND erase configuration/data of:")
        for project in selected:
            print(f"    {project.name}")
        if args.purge:
            token = "PURGE ALL" if machine_wide else "PURGE"
            reply = prompt(f'\nThis also erases configuration and data. '
                           f'Type "{token}" to confirm: ')
            if reply is None or reply.strip() != token:
                print("Aborted.", file=sys.stderr)
                return 1
        else:
            reply = prompt("Proceed? [y/N]: ")
            if reply is None or reply.strip().lower() not in ("y", "yes", "o", "oui"):
                print("Aborted.", file=sys.stderr)
                return 1

    results = []
    for project in selected:
        _project_banner(project.local_name)
        rc = service_uninstall(project, args.purge, args.backup, args.dry_run)
        results.append((project.local_name, "OK" if rc == 0 else f"FAILED ({rc})"))

    print()
    print("=" * 72)
    action = "uninstall --purge" if args.purge else "uninstall"
    print(f"  {action} --dry-run (rien retiré)" if args.dry_run else f"  {action}")
    print("=" * 72)
    for name, outcome in results:
        print(f"  {name:<28} {outcome}")
    return 0 if all(outcome == "OK" for _, outcome in results) else 1


def _print_git_access(diag: dict) -> None:
    """The Git-access snapshot, aligned, for clone diagnostics and doctor."""
    def mark(ok):
        return "OK" if ok else "non"
    print(f"  Git              : {mark(diag['git'])}")
    print(f"  SSH              : {mark(diag['ssh'])}")
    print(f"  SSH key          : {'présente' if diag['ssh_key'] else 'absente'}")
    print(f"  GitHub SSH access: {'disponible' if diag['ssh_github'] else 'indisponible'}")
    print(f"  HTTPS clone      : {'disponible' if diag['https'] else 'identifiants requis / à confirmer'}")


def resolve_clone_protocol(workspace: Workspace, args) -> str | None:
    """Pick or propose the Git protocol for cloning on THIS machine.

    Detect first, never assume the developer's setup. Returns 'ssh' or 'https' to
    proceed, or None to stop (message already printed). Never configures SSH: the
    'configure' path only shows how, then leaves it to the user.
    """
    if not gitaccess.git_available():
        print("git is not available on this machine. Install Git, then re-run.",
              file=sys.stderr)
        return None

    projects = workspace.projects()
    sample = projects[0].local_name if projects else ""
    ssh_url = workspace.clone_url(sample, "ssh") if sample else ""
    https_url = workspace.clone_url(sample, "https") if sample else ""
    interactive = bool(sys.stdin and sys.stdin.isatty())

    if args.protocol == "https":
        if not https_url:
            print("No HTTPS URL could be derived from the manifest "
                  "(set httpsUrlTemplate).", file=sys.stderr)
            return None
        return "https"

    if args.protocol == "ssh":
        if gitaccess.ssh_github_access(ssh_url):
            return "ssh"
        print("SSH access to GitHub is not operational, but --protocol ssh was "
              "requested.", file=sys.stderr)
        _print_git_access(gitaccess.diagnose(ssh_url, https_url))
        print("\nConfigure SSH (below) or use --protocol https.", file=sys.stderr)
        print(gitaccess.ssh_setup_hint(), file=sys.stderr)
        return None

    # auto
    if gitaccess.ssh_available() and gitaccess.ssh_github_access(ssh_url):
        print("[INFO] SSH access to GitHub verified; cloning over SSH.",
              file=sys.stderr)
        return "ssh"

    if not gitaccess.ssh_available():
        if not https_url:
            print("SSH is unavailable and no HTTPS URL could be derived.",
                  file=sys.stderr)
            return None
        print("SSH is not available on this machine; cloning can use HTTPS.")
        if args.yes or not interactive:
            print("[INFO] proceeding over HTTPS.")
            return "https"
        reply = prompt("Continue with HTTPS? [Y/n] ")
        if reply is not None and reply.strip().lower() in ("", "y", "yes", "o", "oui"):
            return "https"
        return None

    # SSH present but not authenticated to GitHub.
    print("Git SSH access is not configured: no working SSH authentication to "
          "GitHub was detected.")
    if not interactive:
        if args.yes and https_url:
            print("[INFO] non-interactive: falling back to HTTPS.")
            return "https"
        print("Re-run with --protocol https [--yes], or configure SSH then "
              "--protocol ssh.", file=sys.stderr)
        return None

    print("\nChoices:")
    print("  [1] Configure SSH access (show how)")
    print("  [2] Use HTTPS")
    print("  [3] Cancel")
    reply = prompt("Choice [1-3]: ")
    if reply is None:
        return None
    choice = reply.strip()
    if choice == "1":
        print("\n" + gitaccess.ssh_setup_hint())
        print("\nSSH not changed. Re-run `morf clone` once configured.")
        return None
    if choice == "2":
        return "https" if https_url else None
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="morf",
        description="Operate on every project declared in ecosystem.json.",
    )
    parser.add_argument("command",
                        choices=sorted(set(COMMANDS) | {"purge", "dev", "deploy"}),
                        help="What to do (admin surface); or 'dev <subcommand>' for "
                             "the developer surface (git and build)")
    parser.add_argument("targets", nargs="*",
                        help="purge: <project> [<category-id>...] to target one "
                             "project's data")
    parser.add_argument("--preset", "-p", default="",
                        help=f"CMake preset ({', '.join(sorted(PRESET_COMMANDS))} only)")
    parser.add_argument("--protocol", choices=("auto", "ssh", "https"), default="auto",
                        help="clone: Git access protocol (auto detects SSH, else HTTPS)")
    parser.add_argument("--message", "-m", default="", help="Commit message")
    parser.add_argument("--only", default="",
                        help="Restrict to one project, by canonical name")
    parser.add_argument("--gui", action="store_true",
                        help="build/upgrade: build desktop GUI apps even on a headless machine")
    parser.add_argument("--force", action="store_true",
                        help="upgrade: redeploy and restart each service even when "
                             "nothing changed. purge: erase even while the service "
                             "is running (overrides the safety guard)")
    parser.add_argument("--purge", action="store_true",
                        help="uninstall: also remove the configuration and binary")
    parser.add_argument("--backup", default="", metavar="DIR",
                        help="uninstall --purge: copy every config into DIR first")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="doctor: print every check line instead of the summary")
    parser.add_argument("--update", "-u", action="store_true", dest="update",
                        help="doctor: also check each clone against origin/main for a "
                             "newer version (a network step; adds a few seconds)")
    parser.add_argument("--services", action="store_true",
                        help="install: deploy every service too, via each project's "
                             "service.py (Linux, Raspberry Pi or Windows)")
    parser.add_argument("--all", action="store_true", dest="all_categories",
                        help="purge: every declared category (of the named project, "
                             "or of every project on this machine)")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would happen without doing it "
                             "(purge, deploy, uninstall, pull/update, upgrade)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="purge: skip the confirmation prompt (required in "
                             "non-interactive use to erase destructive data)")
    parser.add_argument("--config", choices=CONFIG_MODES, default=None,
                        help="deploy: how to treat each service's configuration -- "
                             "keep (default, never overwrite), merge (add the "
                             "clone's new keys, keep local values), or replace "
                             "(overwrite from the repo; a backup is written first)")
    return parser


#: The developer surface: Git and build. These operate on the clones as source
#: code, not on the machine as an administered host -- a different job from
#: deploy/update/upgrade/purge/uninstall/doctor. They stay callable flat
#: (`morf clone`) so existing habits and scripts keep working, and are also
#: reachable as `morf dev clone`, which is how the help presents them so the two
#: surfaces read as two surfaces.
#: `update` is deliberately NOT here: the developer surface names the Git pull
#: `pull`. `morf update` survives as a deprecated alias of `morf dev pull` (with a
#: warning) during the transition, and is reserved to mean "update the installed
#: components" once that period ends -- the sense someone on a production machine
#: expects from it.
DEV_COMMANDS = {"clone", "fetch", "pull", "status", "push", "commit",
                "build", "clean"}


def _expand_dev(args) -> int | None:
    """Turn `morf dev <subcommand> ...` into the plain command it stands for.

    Returns an exit code to stop on (a usage error, or the dev listing), or None
    to continue with `args` rewritten. Keeping this a rewrite rather than a
    second dispatcher means every dev command goes through exactly the same
    handling, checks and elevation rules as its flat form -- there is only ever
    one code path per command.
    """
    if args.command != "dev":
        return None
    if not args.targets:
        print("Developer surface. Usage: morf dev <subcommand> [options]")
        print(f"Subcommands: {', '.join(sorted(DEV_COMMANDS))}")
        return 0
    sub = args.targets[0]
    if sub not in DEV_COMMANDS:
        print(f"'{sub}' is not a dev subcommand.", file=sys.stderr)
        print(f"Dev subcommands: {', '.join(sorted(DEV_COMMANDS))}", file=sys.stderr)
        print("(deploy/update/upgrade/purge/uninstall/doctor are admin commands, "
              "run without 'dev'.)", file=sys.stderr)
        return 2
    # Rewrite in place: the command becomes the subcommand, and the rest of the
    # positionals move on with it (none of the dev commands take any today, but
    # this keeps the shape correct if one ever does).
    args.command = sub
    args.targets = args.targets[1:]
    return None


def main(argv: list | None = None) -> int:
    # Line buffering, set once. This driver interleaves its own prints with the
    # output of git and of the check scripts, which write straight to the
    # descriptor. Buffered, our lines surface after the subprocess output they
    # introduce -- and on stderr summaries, before lines that came first.
    # Fixing it here covers every command, including ones not yet written.
    for stream in (sys.stdout, sys.stderr):
        try:
            # UTF-8 with replacement: the report uses accented French and box
            # markers. A Windows console defaults to cp1252, where an unmapped
            # character raises UnicodeEncodeError and aborts the run mid-report.
            stream.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)

    # `morf dev <subcommand>` is rewritten to the plain command before anything
    # else, so the developer surface shares one code path with the flat form.
    stop = _expand_dev(args)
    if stop is not None:
        return stop

    # Transition (§17): `morf update` as a Git pull is deprecated in favour of
    # `morf dev pull`. It still pulls for now, with a warning, so habits and
    # scripts keep working; a later release will repurpose `morf update` to mean
    # "update the installed components". The warning goes to stderr so it never
    # contaminates output a script might read.
    if args.command == "update":
        print("Warning: `morf update` as a Git operation is deprecated; "
              "use `morf dev pull`.", file=sys.stderr)
        print("         (a future release will repurpose `morf update` to update "
              "the installed components.)", file=sys.stderr)

    # Git must run as YOU, never under sudo. Elevated, it authenticates with
    # root's SSH key -- which does not exist, so every repository answers
    # 'Permission denied (publickey)' -- and the fetch it attempts first leaves
    # root-owned files (FETCH_HEAD, objects) inside your .git, so later runs as
    # yourself fail on your own repositories with 'cannot open .git/FETCH_HEAD'.
    # Both happened, across thirteen repositories at once, from one sudo out of
    # habit. Only 'uninstall' needs elevation, and it delegates to service.py.
    # A genuine root login (no SUDO_USER) owns its clones and is left alone.
    GIT_COMMANDS = {"clone", "fetch", "pull", "update", "push", "commit",
                    "upgrade", "build"}
    if (args.command in GIT_COMMANDS and hasattr(os, "geteuid")
            and os.geteuid() == 0 and os.environ.get("SUDO_USER")):
        print(f"Refusing to run '{args.command}' under sudo.", file=sys.stderr)
        print("Git operations must run as your user: elevated, they use root's",
              file=sys.stderr)
        print("missing SSH key and leave root-owned files inside your .git.",
              file=sys.stderr)
        print(f"Run instead:  python3 morf.py {args.command}", file=sys.stderr)
        print("(only 'uninstall' and each project's service.py need sudo)",
              file=sys.stderr)
        return 2

    # `install --services` builds as YOU, then elevates each service.py itself.
    # Run wholesale under sudo it would build as root -- the same trap. Refuse it
    # the same way, pointing at the form that works.
    if (args.command == "install" and args.services and hasattr(os, "geteuid")
            and os.geteuid() == 0 and os.environ.get("SUDO_USER")):
        print("Refusing to run 'install --services' under sudo.", file=sys.stderr)
        print("It builds as your user, then elevates each service.py on its own.",
              file=sys.stderr)
        print("Run instead:  python3 morf.py install --services", file=sys.stderr)
        return 2

    if args.services and args.command != "install":
        print("--services only applies to install.", file=sys.stderr)
        return 2

    if args.preset and args.command not in PRESET_COMMANDS:
        print(f"--preset is only supported by {', '.join(sorted(PRESET_COMMANDS))}.",
              file=sys.stderr)
        return 2

    if (args.purge or args.backup) and args.command != "uninstall":
        print("--purge and --backup only apply to uninstall.", file=sys.stderr)
        return 2
    if args.verbose and args.command != "doctor":
        print("--verbose only applies to doctor.", file=sys.stderr)
        return 2
    if args.update and args.command != "doctor":
        print("--update only applies to doctor.", file=sys.stderr)
        return 2
    if args.gui and args.command not in ("build", "upgrade"):
        print("--gui only applies to build and upgrade.", file=sys.stderr)
        return 2
    if args.force and args.command not in ("upgrade", "purge"):
        print("--force only applies to upgrade and purge.", file=sys.stderr)
        return 2
    if args.backup and not args.purge:
        print("--backup only applies with --purge.", file=sys.stderr)
        return 2
    # The purge-only surface. Refused elsewhere rather than ignored, same rule as
    # every other option: a flag that silently did nothing is how someone trusts
    # an effect that never happened.
    if args.targets and args.command not in ("purge", "deploy", "uninstall"):
        print("positional project/category arguments only apply to purge, "
              "deploy and uninstall.", file=sys.stderr)
        return 2
    if args.all_categories and args.command not in ("purge", "deploy", "uninstall"):
        print("--all only applies to purge, deploy and uninstall.", file=sys.stderr)
        return 2
    if args.dry_run and args.command not in ("purge", "deploy", "uninstall",
                                             "pull", "update", "upgrade"):
        print("--dry-run only applies to purge, deploy, uninstall, "
              "pull/update and upgrade.", file=sys.stderr)
        return 2
    if args.yes and args.command not in ("purge", "deploy", "uninstall", "clone"):
        print("--yes only applies to purge, deploy, uninstall and clone.",
              file=sys.stderr)
        return 2
    if args.protocol != "auto" and args.command != "clone":
        print("--protocol only applies to clone.", file=sys.stderr)
        return 2
    if args.config and args.command != "deploy":
        print("--config only applies to deploy.", file=sys.stderr)
        return 2

    try:
        workspace = Workspace(Path(__file__).resolve().parents[2])
    except WorkspaceError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # Purge and deploy orchestrate across projects with selection, confirmation
    # and a summary, so each gets its own path rather than the generic loop.
    if args.command == "purge":
        return run_purge(workspace, args)
    if args.command == "deploy":
        return run_deploy(workspace, args)
    if args.command == "uninstall":
        return run_uninstall(workspace, args)

    preset = args.preset
    # A plain `install` (Python deps only) never builds, so it must not ask for a
    # preset; `install --services` does build, and needs one like build/upgrade.
    needs_preset = args.command in ("build", "upgrade") or (
        args.command == "install" and args.services)
    # A dry-run never builds, so it must not stop to ask for a build preset: the
    # plan simply reports "preset default" for the rebuild it would run.
    if needs_preset and not preset and not args.dry_run:
        preset = choose_preset(workspace)

    message = args.message
    if args.command == "commit" and not message:
        message = ask_message()

    handler = COMMANDS[args.command]
    projects = workspace.projects()
    if args.only:
        wanted = args.only.lower()
        projects = [p for p in projects if p.name.lower() == wanted]
        if not projects:
            print(f"No project named '{args.only}' in the manifest.", file=sys.stderr)
            return 2

    # Doctor is read-only and produces a lot of output: it gets its own path,
    # which captures every check and renders a summary instead of the flood.
    if args.command == "doctor":
        return run_doctor(workspace, projects, args.verbose, args.update)

    # Clone resolves the Git protocol ONCE, up front, from what this machine can
    # actually do -- so a fresh box without SSH is handled before the first clone,
    # not by thirteen identical failures.
    clone_protocol = "ssh"
    if args.command == "clone":
        clone_protocol = resolve_clone_protocol(workspace, args)
        if clone_protocol is None:
            return 2

    failed = []

    for project in projects:
        # Banner first, so every project reads as its own block -- including the
        # ones skipped below, which otherwise blur into the previous project's
        # output.
        _project_banner(project.local_name)
        if args.command != "clone" and not project.exists:
            print(f"[SKIP] {project.local_name} (not cloned)")
            continue

        try:
            # Extra arguments go only to the handlers that take them, so a
            # command's signature states what it actually depends on.
            if handler.__name__ == "cmd_upgrade":
                ok = handler(workspace, project, preset, args.gui, args.force,
                             args.dry_run)
            elif handler.__name__ == "cmd_build":
                ok = handler(workspace, project, preset, args.gui)
            elif handler.__name__ == "cmd_install":
                ok = handler(workspace, project, args.services, preset)
            elif handler.__name__ == "cmd_commit":
                ok = handler(workspace, project, message)
            elif handler.__name__ == "cmd_uninstall":
                ok = handler(workspace, project, args.purge, args.backup)
            elif handler.__name__ == "cmd_pull":
                ok = handler(workspace, project, args.dry_run)
            elif handler.__name__ == "cmd_clone":
                ok = handler(workspace, project, clone_protocol)
            else:
                ok = handler(workspace, project)
            if ok is False:
                failed.append(project.local_name)
        except (RuntimeError, OSError) as exc:
            # One project failing must never stop the others: the remaining
            # ones would stay stale with nothing saying so.
            print(f"[FAIL] {project.local_name}: {exc}", file=sys.stderr)
            failed.append(project.local_name)

    # Apres avoir mis a niveau le CODE (binaires + config propre de chaque service
    # via service.py update), `upgrade` met aussi a niveau le CONTRAT de config
    # PARTAGEE : les cles nouvelles de morfsystem.json arrivent sans qu'aucun choix
    # local ne soit ecrase. Une seule fois, apres les projets, sur une machine qui
    # consomme ce fichier. Sautee avec --only, qui cible un projet precis plutot
    # qu'une mise a niveau complete de la machine (utiliser alors `./config.py
    # shared merge` a la main).
    if (args.command == "upgrade" and not args.only and not args.dry_run
            and _shared_config_relevant()):
        _merge_shared_config()
    elif (args.command == "upgrade" and not args.only and args.dry_run
          and _shared_config_relevant()):
        print("\n[dry-run] would merge the shared morfsystem.json contract "
              "(non-destructive; keeps every local value).")

    if failed:
        sys.stdout.flush()
        print(file=sys.stderr)
        print(f"[FAILED] {args.command} failed on: {' '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

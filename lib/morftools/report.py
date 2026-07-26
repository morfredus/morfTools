"""Turn the doctor's line-by-line output into something a person can read.

`doctor` runs many checks, and each prints a line per item. Healthy, that is
sixty-odd `[OK]` lines: a real failure drowns in green. This module keeps every
line for `--verbose`, but by default collapses the passes into a compact status
and ends with the one thing wanted when something is wrong -- what to do about
it.

It parses, rather than being told: every check already prints `[OK]`, `[WARN]`,
`[FAIL]` or `[SKIP]`, sometimes followed by indented continuation lines carrying
a diff or a remediation command. The reporter reuses those continuations as the
action, so a check that improves its own hint improves this summary for free.
"""

from __future__ import annotations

OK, WARN, FAIL, SKIP, UPDATE = "[OK]", "[WARN]", "[FAIL]", "[SKIP]", "[UPDATE]"

# Markers, not colours: the output is piped and logged as often as it is read,
# and a glyph survives that where an escape code becomes noise.
MARK = {"ok": "OK ", "update": " ^ ", "warn": " ! ", "fail": " X "}


class _Problem:
    def __init__(self, kind: str, message: str):
        self.kind = kind          # "fail" | "warn" | "update"
        self.message = message
        self.detail: list[str] = []
        # Set when a notice is already conveyed by another entry of the same
        # area (a stopped service noted inside its update entry): kept for
        # --verbose, hidden from the summary so nothing is said twice.
        self.folded = False


class _Area:
    """One check pass, or one project: a named unit with an overall verdict."""

    def __init__(self, group: str, name: str):
        self.group = group
        self.name = name
        self.status = "ok"        # worst seen: ok < warn < fail
        self.problems: list[_Problem] = []
        self.raw: list[str] = []


# An available update is not a defect: it ranks above "ok" so the project leaves
# the conforming count, but below "warn" so it never inflates the failure or
# warning tallies. Being behind upstream is information, not a problem.
_RANK = {"ok": 0, "update": 1, "warn": 2, "fail": 3}


class Reporter:
    def __init__(self, verbose: bool, updates_checked: bool = False):
        self.verbose = verbose
        # Whether the remote update check ran. It distinguishes "no update found"
        # from "not checked": showing "0 mise(s) à jour" when the network step was
        # skipped would claim a verification that never happened.
        self.updates_checked = updates_checked
        self.areas: list[_Area] = []

    def feed(self, text: str, group: str, name: str, forced_fail: bool = False):
        """Absorb one producer's output as a single named area."""
        area = _Area(group, name)
        current: _Problem | None = None

        for line in text.splitlines():
            area.raw.append(line)
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith(FAIL):
                current = _Problem("fail", stripped[len(FAIL):].strip())
                area.problems.append(current)
                area.status = "fail"
            elif stripped.startswith(WARN):
                message = stripped[len(WARN):].strip()
                # "check unavailable" / "cannot be queried" means the check could
                # not run here, not that something is wrong: a dev machine cannot
                # reach services that live on the Pi. Treating it as a warning
                # would flag six healthy services on every workstation run. It is
                # a non-evaluation, so it is dropped like a SKIP.
                low = message.lower()
                if "unavailable" in low or "cannot be queried" in low:
                    current = None
                    continue
                current = _Problem("warn", message)
                area.problems.append(current)
                if _RANK[area.status] < _RANK["warn"]:
                    area.status = "warn"
            elif stripped.startswith(UPDATE):
                current = _Problem("update", stripped[len(UPDATE):].strip())
                area.problems.append(current)
                if _RANK[area.status] < _RANK["update"]:
                    area.status = "update"
            elif stripped.startswith((OK, SKIP)):
                current = None
            elif stripped.startswith(("---", "[")):
                current = None        # a section header, not a continuation
            elif current is not None:
                current.detail.append(stripped)

        # A handler can report failure through its return value while printing
        # only OK lines (a build that failed to link, say). Trust the verdict.
        if forced_fail and area.status == "ok":
            area.status = "fail"
            area.problems.append(_Problem("fail", f"{name}: échec (voir --verbose)"))

        # Fold "installed but not running" into the area's update entry when both
        # are present: the update already states the service is inactive, so the
        # standalone notice would only repeat it, in another section.
        if any(p.kind == "update" for p in area.problems):
            for problem in area.problems:
                if problem.kind == "warn" and "installed but not running" in problem.message:
                    problem.folded = True

        # The verdict is the worst of the problems that still count. Recomputing
        # here lets a folded notice stop inflating the status (a stopped service
        # with an update reads as an update, not a warning).
        area.status = "ok"
        for problem in area.problems:
            if problem.folded:
                continue
            if _RANK[problem.kind] > _RANK[area.status]:
                area.status = problem.kind

        self.areas.append(area)

    # -- rendering -----------------------------------------------------------

    def render(self) -> int:
        """Print the report; return the process exit code (1 if any failure)."""
        if self.verbose:
            for area in self.areas:
                for line in area.raw:
                    print(line)
        else:
            self._render_quiet()

        failed = sum(1 for a in self.areas if a.status == "fail")
        return 1 if failed else 0

    def _render_quiet(self):
        groups: list[str] = []
        for area in self.areas:
            if area.group not in groups:
                groups.append(area.group)

        print("morf doctor")
        for group in groups:
            areas = [a for a in self.areas if a.group == group]
            print(f"\n{group}")
            healthy = [a.name for a in areas if a.status == "ok"]
            # The green majority collapses to one line; the exceptions each get
            # their own, because those are the ones worth reading.
            if healthy:
                print(f"  {MARK['ok']} {len(healthy)} conforme(s)"
                      + (f" : {', '.join(_short(n) for n in healthy)}"
                         if len(healthy) <= 8 else ""))
            for area in areas:
                if area.status != "ok":
                    print(f"  {MARK[area.status]} {_short(area.name)}")

        self._render_summary()

    def _render_summary(self):
        ok = sum(1 for a in self.areas if a.status == "ok")
        update = sum(1 for a in self.areas if a.status == "update")
        warn = sum(1 for a in self.areas if a.status == "warn")
        fail = sum(1 for a in self.areas if a.status == "fail")

        tally = f"\nRésumé  {ok} OK   "
        if self.updates_checked:
            tally += f"{update} mise(s) à jour   "
        tally += f"{warn} avertissement(s)   {fail} échec(s)"
        print(tally)

        problems = [(a, p) for a in self.areas for p in a.problems if not p.folded]
        updates = [(a, p) for a, p in problems if p.kind == "update"]
        fails = [(a, p) for a, p in problems if p.kind == "fail"]
        warns = [(a, p) for a, p in problems if p.kind == "warn"]

        if not updates and not fails and not warns:
            # "Not checked" is not "up to date": say which it is.
            suffix = "et à jour" if self.updates_checked else "(versions non vérifiées)"
            print(f"Tout est conforme {suffix}.")
            if not self.updates_checked:
                print("Vérifier les nouvelles versions : python3 morf.py doctor --update")
            return

        # Updates first: they are the routine reason to act, and unlike failures
        # they carry a ready command rather than a diagnosis.
        if updates:
            print("\nMises à jour disponibles")
            for area, problem in updates:
                _print_problem(area, problem)
        if fails:
            print("\nÀ corriger")
            for area, problem in fails:
                _print_problem(area, problem)
        if warns:
            print("\nÀ surveiller")
            for area, problem in warns:
                _print_problem(area, problem)


def _print_problem(area: _Area, problem: _Problem):
    print(f"  {MARK[problem.kind]} {_short(area.name)} — {problem.message}")
    if problem.kind == "update":
        # The update remedy is fully formed by update_status -- one or two lines
        # already carrying their own arrows -- so it is printed verbatim rather
        # than run through the single-line action heuristic.
        for line in problem.detail:
            print(f"        {line}")
        return
    action = _action(area, problem)
    if action:
        print(f"        -> {action}")


def _short(name: str) -> str:
    # The sandbox suffixes every clone; the canonical name is what a command
    # takes, and what reads cleanly here.
    return name[:-len("_travail")] if name.endswith("_travail") else name


def _action(area: _Area, problem: _Problem) -> str | None:
    """What to do about a problem.

    A producer that already printed a remediation line (a resync script, an
    upgrade command) has said it better than any generic rule could: reuse it.
    Only when there is none do we map the message to an action ourselves.
    """
    for line in problem.detail:
        low = line.lower()
        if (low.startswith(("git ", "python3 ", "->"))
                or "morf.py" in low or "sync-morf" in low
                or "run " in low or ".sh" in low):
            return line.lstrip("-> ").strip()

    m = problem.message.lower()
    canonical = _short(area.name)

    # A stopped service may be deliberate: state it, force no action. This must
    # precede the "does not answer" rule below, whose wording it shares.
    if "installed but not running" in m or "may be intentional" in m:
        return None
    if "differs from project" in m:
        return f"python3 morf.py upgrade --only {canonical}"
    if "does not answer" in m or "active service" in m:
        return "le service devrait tourner mais ne répond pas — vérifier son état"
    if any(k in m for k in ("allocated to", "allocated twice", "template range",
                            "absent from the registry", "registry allocates",
                            "key '", "configuration not found", "unreadable configuration")):
        return "corriger morfTools/ecosystem.json et la configuration du projet, puis relancer 'morf doctor'"
    if "drifted from" in m:
        return f"resynchroniser la copie vendorée : {canonical}/scripts/sync-morf.sh"
    if "version is" in m:
        return "aligner le fichier VERSION du projet (ou celui de sa dépendance vendorée)"
    if "not a git repository" in m:
        return "python3 morf.py clone"
    if "origin" in m:
        return "configurer le remote 'origin' du dépôt"
    if "executable" in m:
        return "python3 morf.py commit -m 'chore: restore executable bit' puis push"
    return None

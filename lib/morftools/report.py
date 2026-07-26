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

OK, WARN, FAIL, SKIP = "[OK]", "[WARN]", "[FAIL]", "[SKIP]"

# Markers, not colours: the output is piped and logged as often as it is read,
# and a glyph survives that where an escape code becomes noise.
MARK = {"ok": "OK ", "warn": " ! ", "fail": " X "}


class _Problem:
    def __init__(self, kind: str, message: str):
        self.kind = kind          # "fail" | "warn"
        self.message = message
        self.detail: list[str] = []


class _Area:
    """One check pass, or one project: a named unit with an overall verdict."""

    def __init__(self, group: str, name: str):
        self.group = group
        self.name = name
        self.status = "ok"        # worst seen: ok < warn < fail
        self.problems: list[_Problem] = []
        self.raw: list[str] = []


_RANK = {"ok": 0, "warn": 1, "fail": 2}


class Reporter:
    def __init__(self, verbose: bool):
        self.verbose = verbose
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
        warn = sum(1 for a in self.areas if a.status == "warn")
        fail = sum(1 for a in self.areas if a.status == "fail")

        print(f"\nRésumé  {ok} OK   {warn} avertissement(s)   {fail} échec(s)")

        problems = [(a, p) for a in self.areas for p in a.problems]
        fails = [(a, p) for a, p in problems if p.kind == "fail"]
        warns = [(a, p) for a, p in problems if p.kind == "warn"]

        if not fails and not warns:
            print("Tout est conforme.")
            return

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
        if ("morf.py" in low or "sync-morf" in low or low.startswith("->")
                or "run " in low or ".sh" in low):
            return line.lstrip("-> ").strip()

    m = problem.message.lower()
    canonical = _short(area.name)

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

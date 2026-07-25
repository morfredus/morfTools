# Ecosystem checks

`morf doctor` verifies two rules that no single project can verify on its own.
This document explains what they cover, why they exist, and how to work with
them.

## Why these checks are not project-level

Every other morfTools command walks the manifest and runs the same operation
inside each project. That decomposition works because `git status`, `cmake
--build` or `git push` are project-local questions.

Two rules are not project-local. They describe a **shared resource**, so each
project can be individually valid while the ecosystem as a whole is broken:

| Rule | Shared resource | Why a project cannot see the fault |
| --- | --- | --- |
| `ports` | The parc addressing plan | A service reads only its own configuration. Two services declaring the same port are each perfectly consistent. |
| `vendor` | The libraries copied into `third_party/morf/` | A copy that drifted from its canonical source still compiles, and still passes that project's own build. |

Both rules were previously enforced by attention alone. The addressing plan in
particular lived in a `_comment_port` field inside `morfMonitor/config/morfmonitor.example.json`
— a component with no authority over the others, holding a partial copy of a
parc-wide fact. That copy had already fallen out of date, and the template
service shipped a configuration colliding with morfAnalytics as a direct result.

## The addressing registry

`ecosystem.json` now owns the plan under `ports`. It is the **only** description
of parc addressing; no other file may restate it.

```jsonc
"ports": {
  "beaconUdp": 45454,
  "serviceRange":  [8787, 8799],   // parc services
  "templateRange": [8900, 8999],   // templates and examples, never production
  "allocations": [
    {
      "project": "morfSensor",
      "http":    8788,
      "config":  "config/morfsensor.example.json",
      "key":     "http_port",
      "note":    "Sensors: LD2410C presence, probes."
    }
  ]
}
```

Each allocation binds a port to the file that is supposed to declare it:

- `project` — canonical name, as in `projects`. The sandbox `_travail` suffix is
  resolved at runtime, so the registry never mentions it.
- `http` — the allocated port.
- `config` — path, relative to the project, of the configuration expected to
  declare that port. `null` when the value does not live in a file (see
  `morfBeacon` below).
- `key` — the JSON key holding the port inside that file. It is not always
  `http_port`: morfSync uses `port` in a root-level `config.example.json`.
- `note` — what the service does, so an allocation can be judged without
  opening the project.

`morfBeacon` carries `"config": null` because `8787` is the default value of
`PresenceConfig::statusPort`, compiled into the library rather than configured.
It is registered anyway: an unreserved port is a port some future service will
take.

### What the check enforces

`check_ports` runs three passes, each catching a different failure:

1. **Registry self-consistency.** Two allocations sharing a port are reported.
   A registry that contradicts itself cannot arbitrate anything, so this runs
   before any file is read.
2. **Registry against configuration.** For every allocation with a `config`, the
   file is parsed and the value under `key` compared to `http`. A mismatch, a
   missing key, an unreadable or absent file are all failures. This is the pass
   that catches the template collision.
3. **Configuration against registry.** Every `config/*.example.json` in every
   cloned project is scanned for `http_port`. A port declared there but absent
   from the registry is reported as an unmanaged allocation.

Pass 3 is what keeps the registry exhaustive over time. Passes 1 and 2 only
verify what is already registered; without pass 3, a service could quietly take
a port and the registry would stay green while becoming incomplete — exactly how
the previous comment-based plan decayed.

### Allocating a port for a new service

1. Add an entry to `ports.allocations` in `ecosystem.json`, choosing a free port
   inside `serviceRange`.
2. Write that same port into the new service's configuration.
3. Run `morf doctor`. It fails until both agree.

Do this **before** writing the configuration. The registry is the decision; the
configuration records it.

### Why the template sits at 8901

`morfTemplateService` is allocated `8901`, inside `templateRange` and outside
the service block. A template shipping a production-range port is a defect
generator: every clone starts on a port that looks legitimate and may already be
taken — which is precisely what happened with `8799`.

## Active service version

The project directory and the process that answers requests are two different
things: an `update` can retrieve a new `VERSION` while the installed service is
still running its previous binary. During its per-project pass, `morf doctor`
therefore checks every locally installed service that declares `status_url` in
`service.json`. It reads the `version` field returned by that URL and compares
it with the project's `VERSION` file.

A mismatch, an unavailable status endpoint, or a response that omits `version`
is a failure and names the relevant
`python3 morf.py upgrade --only <project>` command.
Services not installed on the current machine are reported as skipped. If the
status endpoint does not answer and the current user cannot query the service
manager, the result is an explicit warning rather than a false claim that the
service is not installed.

A port in the 8900 range cannot be mistaken for a parc allocation, so a clone
that forgets step 1 above is visibly unfinished rather than silently
conflicting.

## The vendored copy check

Shared libraries are copied into each consumer under `third_party/morf/<module>`
and built with `add_subdirectory`. **This check does not question that choice.**
The copy strategy buys a reproducible build across Windows, Linux x64 and
Raspberry Pi with no external repository, which matters for cross-compiled
targets. What it lacked was verification.

```jsonc
"vendored": {
  "modules": [
    { "module": "beacon", "source": "morfBeacon", "compare": ["src", "include"] },
    { "module": "update", "source": "morfUpdate", "compare": ["src", "include"] }
  ],
  "consumers": ["ComponentHub", "SiteWatch", "morfAnalytics", "…"]
}
```

For each consumer and each module it embeds, `check_vendor` compares
`<consumer>/third_party/morf/<module>/<sub>` against `<source>/<sub>` for every
`sub` in `compare`, and reports files that differ, files missing from the copy,
and files missing from the canonical source.

Only `src` and `include` are compared. `CMakeLists.txt` and `VERSION` are
excluded on purpose: the vendored build file is legitimately adapted to its
embedding context, and comparing it would produce noise on every run.

### Line endings are normalised

Content is compared with `\r\n` folded to `\n`. A copy converted to CRLF differs
at the byte level while being identical at the logical level — this is already
the case for `morfTemplateService`. Reporting that as drift would bury real
divergences under a permanent false positive, and a check that is always red is
a check nobody reads.

### When drift is reported

```text
[FAIL] morfSensor/third_party/morf/beacon drifted from morfBeacon:
       content differs: Heartbeat.cpp
       resynchronise with: morfSensor/scripts/sync-morf.(sh|ps1)
```

Drift is not automatically a fault — it may be a deliberate local fix that was
never pushed upstream. The check reports; it never rewrites. Decide which side
is right:

- The canonical source is right → run the project's `sync-morf` script.
- The copy is right → port the change into the canonical project first, then
  resynchronise every consumer.

The second case is the one worth catching. A fix applied in one copy and nowhere
else is invisible without this check.

## Running the checks

Included in `doctor`, before the per-project pass:

```bash
./morfTools/doctor.sh
```

```powershell
.\morfTools\doctor.ps1
```

Or directly, to run one family at a time:

```bash
python3 morfTools/scripts/ecosystem-check.py <workspace-root> morfTools/ecosystem.json ports
python3 morfTools/scripts/ecosystem-check.py <workspace-root> morfTools/ecosystem.json vendor
```

Omitting the third argument runs both. Exit status is `0` when everything
conforms and `1` otherwise, so the script can gate a CI job or a pre-push hook.
Inside `doctor`, a failure adds `ecosystem` to the failed list and makes the
whole command exit non-zero, consistent with how project failures are handled.

A project that is not cloned is reported `[SKIP]` and never fails the run: a
partial workspace is a normal state, not an error.

## Implementation note

The logic lives in one Python script called by both `morf.sh` and `morf.ps1`.
`morf.sh` already depends on `python3` for manifest parsing, and `morf.ps1` uses
`python` for `install`, so this introduces no new dependency. Reimplementing the
comparison in PowerShell would create two checkers free to disagree — which is
the same duplication problem the `vendor` check exists to detect.

## Out of scope: the service skeleton

These checks deliberately do **not** verify the infrastructure skeleton
(`HttpServer`, `Service`, `ModuleRegistry`, `ModuleFactory`) that every service
inherits from `morfTemplateService`.

This is an architectural decision, not an omission. `morfTemplateService` is a
**creation template, not a runtime framework**. Services are autonomous
components with one business responsibility each, not modules of a single
application. Sharing a starting point does not mean sharing an implementation
for the rest of their lifecycle: once created, a service owns its infrastructure
and evolves it to fit its own needs. morfAnalytics already runs a substantially
richer HTTP server than the template, because its requirements differ.

Extracting that skeleton into a shared library would reintroduce exactly the
coupling the split into autonomous services exists to prevent. The accepted cost
is a controlled duplication of infrastructure code; the benefit is that each
service stays autonomous, independently publishable, and free to evolve without
risking a regression elsewhere.

A conformance check would therefore be wrong here: divergence is the expected
state, so a check reporting it would be permanently red and would pressure
services toward a uniformity the architecture does not want.

What the naming harmonisation does buy is **traceability**. Since every service
now names its infrastructure bricks identically, their common lineage can be
read at a glance and a genuine infrastructure defect found in one service can be
looked for in the others — as a deliberate inspection, never as an automatic
propagation.

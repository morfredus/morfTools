#!/usr/bin/env python3
"""Ecosystem-wide checks for the morfSystem workspace.

Every other morfTools command operates project by project. Two rules escape
that decomposition by nature, because they describe a SHARED resource:

  ports   the parc addressing plan. A collision is invisible from inside any
          single project: each one is individually valid.

  vendor  the conformance of the libraries copied into third_party/morf/. A
          copy that drifts still compiles, and nothing reports it.

Both rules previously relied on human vigilance. They are mechanised here and
wired into `morf doctor`.

Usage:
    ecosystem-check.py <workspace-root> <manifest.json> [ports|vendor]

Exit code: 0 when everything conforms, 1 otherwise.
"""

import json
import os
import sys

OK, WARN, FAIL = "[OK]", "[WARN]", "[FAIL]"


def load(path):
    # utf-8-sig: a manifest edited with a Windows editor may carry a BOM, which
    # plain utf-8 would surface as an invalid leading character.
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def local_dir(root, project):
    """Resolve the local directory name of a project.

    The manifest holds canonical production names; the sandbox workspace
    suffixes every directory with '_travail'. Both are accepted without
    assuming the mode, because a workspace may be only partially cloned.
    """
    for candidate in (f"{project}_travail", project):
        path = os.path.join(root, candidate)
        if os.path.isdir(path):
            return path
    return None


# --------------------------------------------------------------------------
# ports
# --------------------------------------------------------------------------

def check_ports(root, manifest):
    ports = manifest.get("ports")
    if not ports:
        print(f"{WARN} no 'ports' registry in the manifest: check skipped")
        return True

    allocations = ports.get("allocations", [])
    problems = 0

    # 1. Internal consistency. A registry that contradicts itself cannot
    #    arbitrate any allocation.
    seen = {}
    for entry in allocations:
        port, project = entry.get("http"), entry.get("project", "?")
        if port is None:
            continue
        if port in seen:
            print(f"{FAIL} port {port} allocated twice in the registry: {seen[port]} and {project}")
            problems += 1
        else:
            seen[port] = project

    # 2. Does each configuration declare the port it was allocated? This is the
    #    check that would have caught the template collision.
    for entry in allocations:
        project = entry.get("project", "?")
        port, config, key = entry.get("http"), entry.get("config"), entry.get("key")

        if not config or not key:
            print(f"{OK} {project}: {port} reserved (no configuration file)")
            continue

        base = local_dir(root, project)
        if base is None:
            print(f"[SKIP] {project} (not cloned)")
            continue

        path = os.path.join(base, config)
        if not os.path.isfile(path):
            print(f"{FAIL} {project}: configuration not found ({config})")
            problems += 1
            continue

        try:
            declared = load(path).get(key)
        except ValueError as error:
            print(f"{FAIL} {project}: unreadable configuration ({config}): {error}")
            problems += 1
            continue

        if declared is None:
            print(f"{FAIL} {project}: key '{key}' missing from {config}")
            problems += 1
        elif declared != port:
            print(f"{FAIL} {project}: registry allocates {port}, configuration declares {declared} ({config})")
            problems += 1
        else:
            print(f"{OK} {project}: {port}")

    # 3. A port declared somewhere but absent from the registry is an unmanaged
    #    allocation: the registry would stop being exhaustive, which is the
    #    failure mode the previous comment-based plan already exhibited.
    registered = set(seen)
    for project in manifest.get("projects", []):
        base = local_dir(root, project)
        if base is None:
            continue
        config_dir = os.path.join(base, "config")
        if not os.path.isdir(config_dir):
            continue
        for name in sorted(os.listdir(config_dir)):
            if not name.endswith(".example.json"):
                continue
            try:
                declared = load(os.path.join(config_dir, name)).get("http_port")
            except (OSError, ValueError):
                continue
            if declared is not None and declared not in registered:
                print(f"{FAIL} {project}: port {declared} declared in {name} but absent from the registry")
                problems += 1

    return problems == 0


# --------------------------------------------------------------------------
# vendor
# --------------------------------------------------------------------------

def read_normalised(path):
    """Read a file with line endings neutralised.

    A copy converted to CRLF differs at the byte level while being identical at
    the logical level. Reporting that as drift would bury the real divergences,
    so content is compared, not newline encoding.
    """
    with open(path, "rb") as handle:
        return handle.read().replace(b"\r\n", b"\n")


def compare_tree(canonical, copy):
    """Return the list of differences between two directory trees."""
    differences = []

    def walk(base):
        found = {}
        for directory, _, names in os.walk(base):
            for name in names:
                full = os.path.join(directory, name)
                found[os.path.relpath(full, base).replace("\\", "/")] = full
        return found

    left, right = walk(canonical), walk(copy)

    for relative in sorted(set(left) | set(right)):
        if relative not in right:
            differences.append(f"missing from the copy: {relative}")
        elif relative not in left:
            differences.append(f"missing from the canonical source: {relative}")
        elif read_normalised(left[relative]) != read_normalised(right[relative]):
            differences.append(f"content differs: {relative}")

    return differences


def check_vendor(root, manifest):
    vendored = manifest.get("vendored")
    if not vendored:
        print(f"{WARN} no 'vendored' registry in the manifest: check skipped")
        return True

    modules = {entry["module"]: entry for entry in vendored.get("modules", [])}
    problems = 0

    for consumer in vendored.get("consumers", []):
        base = local_dir(root, consumer)
        if base is None:
            print(f"[SKIP] {consumer} (not cloned)")
            continue

        for name, module in modules.items():
            copy = os.path.join(base, "third_party", "morf", name)
            if not os.path.isdir(copy):
                continue    # not every consumer embeds every module

            source = local_dir(root, module["source"])
            if source is None:
                print(f"[SKIP] {consumer}/{name} (canonical source {module['source']} not cloned)")
                continue

            differences = []
            for sub in module.get("compare", []):
                canonical_sub, copy_sub = os.path.join(source, sub), os.path.join(copy, sub)
                if not os.path.isdir(canonical_sub):
                    differences.append(f"missing from the canonical source: {sub}/")
                elif not os.path.isdir(copy_sub):
                    differences.append(f"missing from the copy: {sub}/")
                else:
                    differences += compare_tree(canonical_sub, copy_sub)

            if differences:
                print(f"{FAIL} {consumer}/third_party/morf/{name} drifted from {module['source']}:")
                for line in differences:
                    print(f"       {line}")
                print(f"       resynchronise with: {consumer}/scripts/sync-morf.(sh|ps1)")
                problems += 1
            else:
                print(f"{OK} {consumer}/third_party/morf/{name} matches {module['source']}")

    return problems == 0


# --------------------------------------------------------------------------

def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2

    root, manifest_path = argv[1], argv[2]
    which = argv[3] if len(argv) > 3 else "all"

    try:
        manifest = load(manifest_path)
    except (OSError, ValueError) as error:
        print(f"{FAIL} unreadable manifest ({manifest_path}): {error}")
        return 1

    healthy = True
    if which in ("all", "ports"):
        print("--- addressing plan ---")
        healthy &= check_ports(root, manifest)
    if which in ("all", "vendor"):
        print("--- vendored copies ---")
        healthy &= check_vendor(root, manifest)

    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

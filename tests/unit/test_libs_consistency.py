import itertools
import shlex
import subprocess
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PROJECTS = ["chaoscenter", "auth", "backend"]
REQUIRED_CHARMLIBS = [
    "charms.loki_k8s.v1.loki_push_api",
    "charms.tempo_coordinator_k8s.v0.tracing",
]

_LIBPATCH_RE = re.compile(r".*/lib/(.+)\.py:\d+:LIBPATCH = (\d+).*")


def _get_charmlibs_versions(project: str):
    cmd = f"grep -rnw {REPO_ROOT}/{project}/lib -e 'LIBPATCH ='"
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    out = {}
    for line in proc.stdout.splitlines():
        match = _LIBPATCH_RE.match(line)
        libpath, libv = match.groups()
        out[libpath.replace("/", ".")] = libv
    return out


INSTALLED_CHARMLIBS = {
    project: _get_charmlibs_versions(project) for project in PROJECTS
}


def test_charmlibs_version_consistent():
    errors = []
    for proj, other_proj in itertools.combinations(PROJECTS, r=2):
        for lib, libv in INSTALLED_CHARMLIBS[proj].items():
            other_libv = INSTALLED_CHARMLIBS[other_proj].get(lib)
            if other_libv is not None and other_libv != libv:
                errors.append(
                    f"{lib} has revision {libv} in {proj} but {other_libv} in {other_proj}"
                )
    if errors:
        raise AssertionError("\n".join(errors))


def test_required_charmlibs_installed():
    errors = []

    for lib in REQUIRED_CHARMLIBS:
        for project in PROJECTS:
            if lib not in INSTALLED_CHARMLIBS[project]:
                errors.append(f"{project} is missing required charmlib {lib}")

    if errors:
        raise AssertionError("\n".join(errors))

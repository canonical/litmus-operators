import shlex
import subprocess
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
PROJECTS = ["chaoscenter", "auth", "backend"]
REQUIRED_CHARMLIBS = [
    "charms.loki_k8s.v1.loki_push_api",
    "charms.tempo_coordinator_k8s.v0.tracing",
    "charms.prometheus_k8s.v0.prometheus_scrape",
    "charms.grafana_k8s.v0.grafana_dashboard",
]

_LIBPATCH_RE = re.compile(r".*/lib/(.+)\.py:\d+:LIBPATCH = (\d+).*")

def _get_charmlibs_versions(project: str):
    cmd = f"grep -rnw {REPO_ROOT}/{project}/lib -e 'LIBPATCH ='"
    proc = subprocess.run(shlex.split(cmd),capture_output=True, text=True)
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
    for i in range(3):
        projs = PROJECTS.copy()
        p = projs.pop(i)

        for lib, libv in INSTALLED_CHARMLIBS[p].items():
            for other_project in projs:
                other_libv = INSTALLED_CHARMLIBS[other_project].get(lib)
                if other_libv is not None and other_libv != libv:
                    errors.append(f"{lib} has revision {libv} in {p} but {other_libv} in {other_project}")
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








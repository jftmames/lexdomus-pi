#!/usr/bin/env python3
"""Generate/check the locked package inventory without third-party tooling or network.

Run with the Python interpreter containing requirements.api.txt. npm metadata comes
from package-lock.json, including optional packages absent from this machine.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("docs/dependencies")
INPUTS = (
    ".python-version",
    "requirements.in",
    "requirements.api.in",
    "requirements.txt",
    "requirements.api.txt",
    "web/package.json",
    "web/package-lock.json",
)
PIN = re.compile(r"([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[A-Za-z0-9_,.-]+\])?==([^\s;]+)")
HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def lock_requirements(path: Path) -> dict:
    """Read pip-compile's exact, hashed lock syntax; fail on unsupported lines."""
    result = {}
    logical = path.read_text(encoding="utf-8").replace("\\\n", " ")
    for line in logical.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = PIN.match(line)
        if not match:
            raise ValueError(f"{path.name}: unsupported requirement: {line[:120]}")
        name, version = match.groups()
        tail = line[match.end():].strip()
        hashes = sorted(set(HASH.findall(tail)))
        if not hashes or HASH.sub("", tail).strip():
            raise ValueError(f"{path.name}: {name} must have only SHA-256 hashes")
        name = normalized(name)
        if name in result:
            raise ValueError(f"{path.name}: duplicate package {name}")
        result[name] = {"version": version, "sha256": hashes}
    if not result:
        raise ValueError(f"{path.name}: empty lock")
    return result


def direct_requirements(path: Path, seen: frozenset = frozenset()) -> dict:
    if path in seen:
        raise ValueError(f"recursive requirements include: {path}")
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-r "):
            result.update(direct_requirements(path.parent / line[3:].strip(), seen | {path}))
            continue
        match = PIN.fullmatch(line)
        if not match:
            raise ValueError(f"{path.name}: unsupported direct requirement: {line}")
        result[normalized(match[1])] = match[2]
    return result


def python_components(root: Path) -> tuple[list, list]:
    lock_paths = {"core": "requirements.txt", "api": "requirements.api.txt"}
    locks = {env: lock_requirements(root / path) for env, path in lock_paths.items()}
    direct = {
        "core": direct_requirements(root / "requirements.in"),
        "api": direct_requirements(root / "requirements.api.in"),
    }
    for env, packages in direct.items():
        for name, version in packages.items():
            if locks[env].get(name, {}).get("version") != version:
                raise ValueError(f"{env}: direct pin {name}=={version} differs from lock")
    for name, pinned in locks["core"].items():
        if locks["api"].get(name, {}).get("version") != pinned["version"]:
            raise ValueError(f"core/API lock version disagreement: {name}")

    components, notices = [], []
    for name, pinned in sorted(locks["api"].items()):
        # Deliberately do not enumerate the environment: pip, audit tools and
        # unrelated distributions must never enter the application inventory.
        dist = metadata.distribution(name)
        if dist.version != pinned["version"]:
            raise ValueError(f"{name}: installed {dist.version}, locked {pinned['version']}")
        md = dist.metadata
        if normalized(md["Name"]) != name:
            raise ValueError(f"{name}: installed metadata has a different package name")
        expression = md.get("License-Expression")
        declared = md.get("License")
        if expression and expression.strip().upper() == "UNKNOWN":
            expression = None
        if declared and declared.strip().upper() == "UNKNOWN":
            declared = None
        classifiers = sorted(x for x in md.get_all("Classifier", []) if x.startswith("License ::"))
        license_files = sorted(set(md.get_all("License-File", [])))
        environments = sorted(env for env, values in locks.items() if name in values)
        components.append({
            "ecosystem": "pypi",
            "name": name,
            "version": pinned["version"],
            "purl": f"pkg:pypi/{name}@{quote(pinned['version'], safe='')}",
            "scope": "runtime",
            "environments": environments,
            "directIn": sorted(env for env in environments if name in direct[env]),
            "lockedArtifactSha256": {
                lock_paths[env]: locks[env][name]["sha256"] for env in environments
            },
            "license": {
                "source": "installed distribution METADATA",
                "expression": expression,
                "declaredName": declared,
                "classifiers": classifiers,
                "declaredFiles": license_files,
                "status": "declared" if expression or declared or classifiers else "unknown",
            },
        })
        files = []
        for license_file in license_files:
            text = None
            location = None
            for candidate in (f"licenses/{license_file}", license_file):
                text = dist.read_text(candidate)
                if text is not None:
                    location = candidate
                    break
            files.append({
                "declaredPath": license_file,
                "distributionMetadataPath": location,
                "available": text is not None,
                "utf8TextSha256": sha256(text.encode("utf-8")) if text is not None else None,
                "text": text,
            })
        notices.append({"name": name, "version": pinned["version"], "files": files})
    return components, notices


def npm_components(root: Path) -> list:
    lock = json.loads((root / "web/package-lock.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "web/package.json").read_text(encoding="utf-8"))
    if lock.get("lockfileVersion") != 3 or "" not in lock.get("packages", {}):
        raise ValueError("web/package-lock.json: expected npm lockfileVersion 3 with root entry")
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        if manifest.get(key, {}) != lock["packages"][""].get(key, {}):
            raise ValueError(f"web/package.json and package-lock.json differ: {key}")
    result = []
    for path, package in sorted(lock["packages"].items()):
        if not path:
            continue
        if package.get("link") or "node_modules/" not in path or not package.get("version"):
            raise ValueError(f"unsupported npm lock entry: {path}")
        name = package.get("name") or path.rsplit("node_modules/", 1)[1]
        integrity = package.get("integrity")
        if not integrity:
            raise ValueError(f"npm package missing locked integrity: {path}")
        hashes = []
        for token in integrity.split():
            algorithm, value = token.split("-", 1)
            algorithm = {"sha1": "SHA-1", "sha256": "SHA-256", "sha384": "SHA-384", "sha512": "SHA-512"}[algorithm]
            hashes.append({"alg": algorithm, "content": base64.b64decode(value, validate=True).hex()})
        direct_in = []
        if path == f"node_modules/{name}":
            direct_in = sorted(key for key in ("dependencies", "devDependencies", "optionalDependencies") if name in manifest.get(key, {}))
        declared = package.get("license")
        if declared is not None and not isinstance(declared, str):
            raise ValueError(f"npm package has unsupported license field: {path}")
        result.append({
            "ecosystem": "npm",
            "name": name,
            "version": package["version"],
            "purl": f"pkg:npm/{quote(name, safe='/')}@{quote(package['version'], safe='')}",
            "lockPath": path,
            "scope": "build/development" if package.get("dev", False) else "runtime",
            "directIn": direct_in,
            "optional": package.get("optional", False),
            "os": package.get("os", []),
            "cpu": package.get("cpu", []),
            "libc": package.get("libc", []),
            "installationStatus": "not assessed; inventory of lock entries",
            "resolved": package.get("resolved"),
            "integrity": integrity,
            "artifactHashes": hashes,
            "license": {
                "source": "web/package-lock.json license field",
                "declaredName": declared,
                "status": "declared" if declared and declared.upper() != "UNLICENSED" else "unknown",
            },
        })
    return result


def prop(name: str, value: object) -> dict:
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return {"name": f"lexdomus:{name}", "value": value}


def cyclonedx(inventory: dict) -> dict:
    components = []
    for item in inventory["components"]:
        component = {
            "type": "library",
            "bom-ref": item["purl"] if item["ecosystem"] == "pypi" else f"npm:{item['lockPath']}",
            "name": item["name"],
            "version": item["version"],
            "purl": item["purl"],
        }
        license_info = item["license"]
        # Only the standardized Python License-Expression field is emitted as
        # an SPDX expression. Free text, including vague/legacy names, stays text.
        if license_info.get("expression"):
            component["licenses"] = [{"expression": license_info["expression"]}]
        elif license_info.get("declaredName"):
            component["licenses"] = [{"license": {"name": license_info["declaredName"]}}]
        properties = [
            prop("ecosystem", item["ecosystem"]),
            prop("dependency:scope", item["scope"]),
            prop("dependency:directIn", item["directIn"]),
            prop("license:source", license_info["source"]),
            prop("license:status", license_info["status"]),
        ]
        if item["ecosystem"] == "pypi":
            properties += [
                prop("python:environments", item["environments"]),
                prop("python:lockedArtifactSha256", item["lockedArtifactSha256"]),
                prop("python:licenseClassifiers", license_info["classifiers"]),
                prop("python:declaredLicenseFiles", license_info["declaredFiles"]),
            ]
        else:
            component["hashes"] = item["artifactHashes"]
            properties += [
                prop("npm:lockPath", item["lockPath"]),
                prop("npm:optional", item["optional"]),
                prop("npm:os", item["os"]),
                prop("npm:cpu", item["cpu"]),
                prop("npm:libc", item["libc"]),
                prop("npm:installationStatus", item["installationStatus"]),
            ]
        component["properties"] = properties
        components.append(component)
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": "LexDomus", "bom-ref": "lexdomus-application"},
            "properties": [
                prop("inventory:generator", "tools/dependency_inventory.py"),
                prop("inventory:scope", inventory["scope"]),
                *[prop(f"input:sha256:{item['path']}", item["sha256"]) for item in inventory["inputs"]],
            ],
        },
        "components": components,
    }


def cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", "").replace("\n", " ")


def license_report(inventory: dict) -> str:
    lines = [
        "# Declared package licenses",
        "",
        "Generated by `python tools/dependency_inventory.py`; do not edit manually.",
        "Declarations describe package metadata, not a legal assessment or an exhaustive list of bundled code licenses.",
        "Python SPDX expressions are identified explicitly; other values remain literal names, with no inferred SPDX identifier.",
        "Raw classifiers, declared filenames and hash provenance are in `inventory.json`; declared Python license file texts are in `python-licenses.json`.",
        "npm declarations come from the lock, including optional platform packages that may not be installed.",
        "",
        "Attention: uvloop declares `MIT License` but ships both MIT and Apache license files. NumPy and lxml wheel notices describe additional bundled native code; inspect their full notices before distribution.",
        "",
        "| Ecosystem | Package | Version | Dependency scope | License declaration |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in inventory["components"]:
        info = item["license"]
        license_name = info.get("expression") or info.get("declaredName") or "UNKNOWN (see classifiers if present)"
        if info.get("expression"):
            license_name += " (SPDX expression)"
        scope = ", ".join(item["environments"]) if item["ecosystem"] == "pypi" else item["scope"]
        if item.get("optional"):
            scope += "; optional"
        lines.append("| " + " | ".join(cell(x) for x in (item["ecosystem"], item["name"], item["version"], scope, license_name)) + " |")
    return "\n".join(lines) + "\n"


def readme(inventory: dict, notices: list) -> str:
    python = [x for x in inventory["components"] if x["ecosystem"] == "pypi"]
    npm = [x for x in inventory["components"] if x["ecosystem"] == "npm"]
    core = sum("core" in x["environments"] for x in python)
    unknown = sum(x["license"]["status"] == "unknown" for x in inventory["components"])
    notice_files = [f for item in notices for f in item["files"]]
    available = sum(f["available"] for f in notice_files)
    no_files = ", ".join(item["name"] for item in notices if not item["files"]) or "none"
    return f"""# Locked dependency inventory

Generated by `python tools/dependency_inventory.py`. Do not edit generated files manually.

| Coverage | Count |
| --- | ---: |
| Python core packages | {core} |
| Python complete API packages (includes core) | {len(python)} |
| npm lock entries | {len(npm)} |
| npm runtime entries | {sum(x['scope'] == 'runtime' for x in npm)} |
| npm build/development-only entries | {sum(x['scope'] == 'build/development' for x in npm)} |
| npm optional entries (overlaps scopes above) | {sum(x['optional'] for x in npm)} |
| Total package entries | {len(inventory['components'])} |
| Entries without a declared license | {unknown} |
| Declared Python license files extracted | {available}/{len(notice_files)} |

Every Python entry uses installed metadata for the exact locked version. Every npm entry uses the committed lock's license and integrity metadata, without reading `node_modules`. Python packages with no `License-File` metadata: {no_files}. Missing declarations are not evidence that no license applies.

## Reproduce and check

Use the project's pinned Python on Linux and an isolated environment installed with the complete API lock:

```sh
python -m venv /tmp/lexdomus-inventory
/tmp/lexdomus-inventory/bin/python -m pip install --require-hashes -r requirements.api.txt
/tmp/lexdomus-inventory/bin/python tools/dependency_inventory.py
/tmp/lexdomus-inventory/bin/python tools/dependency_inventory.py --check
```

The generator uses only the Python standard library. It makes no network calls. `--check` writes nothing and fails if any generated artifact differs from the current manifests, exact lock versions/hashes or installed Python license metadata/notices. Missing packages and installed version mismatches fail. No timestamps, machine paths or environment tooling enter the output. Lockfile and input SHA-256 values are embedded in both JSON inventories so staleness is reviewable. Reproduce on the same Linux wheel platform: platform-specific wheel notices can legitimately differ and require regeneration/review.

## Files and interpretation

- `inventory.json`: native package inventory with exact versions, PURLs, environments, direct roots, original declarations and every allowed Python lock artifact hash.
- `sbom.cdx.json`: CycloneDX 1.6 package SBOM, using the [official JSON schema](https://cyclonedx.org/schema/bom-1.6.schema.json). npm archive integrity is represented as component hashes. Python lock hashes identify alternative allowed wheels/source archives, so they are recorded as properties rather than presented as hashes of a single installed artifact.
- `LICENSES.md`: readable package license declarations. Only Python's explicit `License-Expression` field is represented as an SPDX expression; legacy names remain names, including `Apache2.0` and `MIT License`.
- `python-licenses.json`: unmodified text returned by installed distribution metadata for declared license files, with SHA-256 of the UTF-8 text. It includes notices and attribution files listed as `License-File`, not just license names.

The API list includes the core packages once. npm `dev: true` means build/development-only; other entries can serve runtime and also participate in builds. Optional flags and OS/CPU restrictions come directly from the lock. The SBOM describes all locked package entries, including platform alternatives, and does not assert that every entry is installed. It deliberately does not claim a complete resolved dependency graph.

## Boundaries and license caveats

This is an application package inventory. OS/container packages, the Python/Node runtimes, npm/pip/lock/audit tooling, hosted services/models and a separate enumeration of native libraries bundled inside wheels/npm archives are outside its component list. Package-level declarations are not an exhaustive license assessment of bundled code. In particular, uvloop's `MIT License` field coexists with MIT and Apache notices; NumPy's wheel notices include additional native runtime licenses and exceptions, and lxml carries bundled-code notices. Consult their complete extracted files before distribution. npm full license texts are not copied here; review the exact locked packages for redistribution notices. Unknown declarations remain explicit rather than receiving guessed SPDX identifiers.
"""


def generate(root: Path) -> dict[str, str]:
    python, notices = python_components(root)
    inventory = {
        "format": "LexDomus locked package inventory",
        "formatVersion": 1,
        "generator": "tools/dependency_inventory.py",
        "scope": "Locked Python core/API and npm runtime/build packages; optional npm platform entries included; excludes OS/container/runtime/tooling components and a separate enumeration of bundled native libraries.",
        "inputs": [{"path": path, "sha256": sha256((root / path).read_bytes())} for path in INPUTS],
        "components": python + npm_components(root),
    }
    return {
        "inventory.json": json_text(inventory),
        "sbom.cdx.json": json_text(cyclonedx(inventory)),
        "python-licenses.json": json_text({"source": "Installed locked Python distributions: declared License-File metadata", "packages": notices}),
        "LICENSES.md": license_report(inventory),
        "README.md": readme(inventory, notices),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if committed artifacts differ; never write files")
    args = parser.parse_args()
    try:
        outputs = generate(ROOT)
        if args.check:
            stale = []
            for filename, content in outputs.items():
                path = ROOT / OUTPUT / filename
                if not path.is_file() or path.read_bytes() != content.encode("utf-8"):
                    stale.append(str(OUTPUT / filename))
            if stale:
                print("Dependency inventory is stale: " + ", ".join(stale), file=sys.stderr)
                print("Regenerate with the locked API environment: python tools/dependency_inventory.py", file=sys.stderr)
                return 1
            print("Dependency inventory matches locks and installed Python license metadata.")
        else:
            (ROOT / OUTPUT).mkdir(parents=True, exist_ok=True)
            for filename, content in outputs.items():
                (ROOT / OUTPUT / filename).write_text(content, encoding="utf-8")
            print(f"Wrote {len(outputs)} dependency artifacts to {OUTPUT}.")
    except (OSError, ValueError, KeyError, metadata.PackageNotFoundError) as error:
        print(f"Dependency inventory failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

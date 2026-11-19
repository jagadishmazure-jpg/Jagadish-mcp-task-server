"""Fail when an MCP server is unpinned or not on the allowlist.

Scans client configs (mcp.json, Codex toml) and dependency manifests. A server
must be an exact pin recorded in security/mcp-server-allowlist.json. Reference
servers fixed in modelcontextprotocol/servers v2.5.0 cannot be approved below
the versions in REQUIRED_FLOORS. This module only reads files. It does not
install packages or run server commands.

Stdlib only, so the CI job can run it with no network install.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RELEASE_URL = "https://github.com/modelcontextprotocol/servers/releases/tag/v2.5.0"
ALLOWLIST_REL = Path("security") / "mcp-server-allowlist.json"

# Published fixed versions. The allowlist file must repeat these exactly.
REQUIRED_FLOORS: dict[str, str] = {
    "mcp-server-git": "2026.11.18",
    "@modelcontextprotocol/server-filesystem": "2.4.0",
    "@modelcontextprotocol/server-everything": "2.3.1",
}
# npm ranks every 2025.x / 2026.x date version above the semver fix.
DATE_VERSION_REJECTED = frozenset(
    {
        "@modelcontextprotocol/server-filesystem",
        "@modelcontextprotocol/server-everything",
    }
)

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}
DLX_LAUNCHERS = {"npx", "uvx", "pipx", "bunx"}
FROM_FLAGS = {"--from", "--with"}
SUBCOMMANDS = {"exec", "dlx", "x", "tool", "run", "install"}
EXACT_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")
DATE_VERSION = re.compile(r"^([0-9]{4})\.([0-9]{1,2})\.([0-9]{1,2})$")
SCOPED_SPEC = re.compile(r"^(@[^@\s/]+/[^@\s]+)(?:@(.+))?$")
NAME_SPEC = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(.*)$")
OPERATOR = re.compile(r"^(?:\[[^\]]*\])?\s*(===|==|~=|!=|<=|>=|<|>)\s*(.+)$")
REQUIREMENT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*([^;]*)")
SERVER_NAME_IN_TEXT = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:mcp-server-[A-Za-z0-9-]+|@[A-Za-z0-9_.-]+/server-[A-Za-z0-9-]+)"
)
UNSUPPORTED_LOCKS = {"yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock"}


@dataclass(frozen=True)
class Finding:
    path: str
    message: str


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    servers: int = 0
    dependencies: int = 0


@dataclass(frozen=True)
class HttpAllow:
    id: str
    url: str


@dataclass(frozen=True)
class PackageAllow:
    id: str
    package: str
    version: str


@dataclass(frozen=True)
class CommandAllow:
    id: str
    command: str
    args: tuple[str, ...]


@dataclass(frozen=True)
class Spec:
    name: str
    version: str | None
    exact: bool


@dataclass
class Policy:
    by_id: dict[str, HttpAllow | PackageAllow | CommandAllow]
    by_package: dict[str, PackageAllow]


def canonical_package(name: str) -> str:
    name = name.strip()
    if name.startswith("@"):
        scope, _, rest = name[1:].partition("/")
        rest = re.sub(r"[-_.]+", "-", rest).lower()
        return f"@{scope.lower()}/{rest}"
    return re.sub(r"[-_.]+", "-", name).lower()


def is_server_package(name: str, extra: set[str] | None = None) -> bool:
    canon = canonical_package(name)
    if extra and canon in extra:
        return True
    if canon in {canonical_package(key) for key in REQUIRED_FLOORS}:
        return True
    if canon.startswith("mcp-server-"):
        return True
    return canon.startswith("@modelcontextprotocol/server-")


def is_date_version(version: str) -> bool:
    match = DATE_VERSION.fullmatch(version)
    return bool(match and int(match.group(1)) >= 2020)


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def floor_problem(package: str, version: str) -> str | None:
    canon = canonical_package(package)
    floors = {canonical_package(key): value for key, value in REQUIRED_FLOORS.items()}
    rejected = {canonical_package(key) for key in DATE_VERSION_REJECTED}
    if canon in rejected and is_date_version(version):
        floor = floors[canon]
        return (
            f"{package}@{version} is a date version; the fix is {floor}, and a package "
            "manager ranks every date version above that semver, so the semver must be installed explicitly"
        )
    floor = floors.get(canon)
    if floor is None:
        return None
    if not EXACT_VERSION.fullmatch(version):
        return f"{package}@{version} is not an exact release version"
    if version_key(version) < version_key(floor):
        return f"{package}@{version} is below the minimum safe version {floor} ({RELEASE_URL})"
    return None


def rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def add(report: Report, root: Path, path: Path, message: str) -> None:
    report.findings.append(Finding(rel(root, path), message))


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for name in filenames:
            yield Path(dirpath) / name


def parse_version_token(raw: str | None) -> tuple[str | None, bool]:
    if raw is None or raw == "":
        return None, False
    version = raw.strip()
    return version, bool(EXACT_VERSION.fullmatch(version))


def parse_spec(token: str) -> Spec | None:
    if token.startswith(("/", ".", "~")) or "\\" in token or (":" in token and not token.startswith("@")):
        return None
    scoped = SCOPED_SPEC.fullmatch(token)
    if scoped:
        version, exact = parse_version_token(scoped.group(2))
        return Spec(scoped.group(1), version, exact)
    named = NAME_SPEC.fullmatch(token)
    if not named:
        return None
    name, rest = named.group(1), named.group(2).strip()
    if rest == "":
        return Spec(name, None, False)
    operator = OPERATOR.fullmatch(rest)
    if not operator:
        return None
    op, version = operator.group(1), operator.group(2).strip()
    exact = op in {"==", "==="} and bool(EXACT_VERSION.fullmatch(version))
    return Spec(name, version, exact)


def launch_specs(command: str, args: list[str]) -> list[Spec]:
    base = Path(command).name
    if base.lower().endswith(".exe"):
        base = base[:-4]
    base = base.lower()
    specs: list[Spec] = []
    from_names: set[str] = set()
    saw_dlx = base in DLX_LAUNCHERS
    index = 0
    while index < len(args):
        token = args[index]
        flag = token.split("=", 1)[0]
        if base in {"uv", "uvx", "pipx"} and flag in FROM_FLAGS:
            raw = token.split("=", 1)[1] if "=" in token else ""
            if raw == "":
                index += 1
                if index >= len(args):
                    break
                raw = args[index]
            spec = parse_spec(raw) or Spec(raw, None, False)
            specs.append(spec)
            from_names.add(canonical_package(spec.name))
            saw_dlx = True
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        if token in SUBCOMMANDS and base in {"npm", "pnpm", "yarn", "uv"}:
            saw_dlx = token in {"dlx", "x"} or saw_dlx
            index += 1
            continue
        spec = parse_spec(token)
        if spec and (spec.version is not None or token.startswith("@")):
            if spec.version is None and canonical_package(spec.name) in from_names:
                index += 1
                continue
            specs.append(spec)
            index += 1
            continue
        if spec and canonical_package(spec.name) in from_names and spec.version is None:
            index += 1
            continue
        if saw_dlx and specs == [] and spec is not None:
            specs.append(spec)
        elif spec is not None and is_server_package(spec.name) and specs == []:
            specs.append(spec)
        index += 1
    command_spec = parse_spec(base)
    if command_spec and (command_spec.version is not None or is_server_package(command_spec.name)):
        specs.insert(0, command_spec)
    return specs


def load_policy(root: Path, report: Report) -> Policy | None:
    path = root / ALLOWLIST_REL
    if not path.is_file():
        add(report, root, path, "MCP server allowlist is missing")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add(report, root, path, f"MCP server allowlist is not valid JSON ({exc})")
        return None
    if not isinstance(data, dict) or data.get("schema") != 1:
        add(report, root, path, "MCP server allowlist schema must be 1")
        return None
    if data.get("source") != RELEASE_URL:
        add(report, root, path, f"MCP server allowlist source must be {RELEASE_URL}")
        return None
    floors = data.get("floors")
    if floors != REQUIRED_FLOORS:
        add(
            report,
            root,
            path,
            "MCP server allowlist floors do not match the required floors "
            f"({', '.join(f'{name} {version}' for name, version in REQUIRED_FLOORS.items())})",
        )
        return None
    entries = data.get("servers")
    if not isinstance(entries, list):
        add(report, root, path, "MCP server allowlist servers must be a list")
        return None
    by_id: dict[str, HttpAllow | PackageAllow | CommandAllow] = {}
    by_package: dict[str, PackageAllow] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            add(report, root, path, "each allowlist server needs a string id")
            return None
        server_id = entry["id"]
        if server_id in by_id:
            add(report, root, path, f"duplicate allowlist id {server_id}")
            return None
        transport = entry.get("transport")
        if transport == "http":
            url = entry.get("url")
            if not isinstance(url, str) or not url:
                add(report, root, path, f"allowlist server {server_id} needs a url")
                return None
            by_id[server_id] = HttpAllow(server_id, url)
        elif transport == "stdio" and "package" in entry:
            package = entry.get("package")
            version = entry.get("version")
            if not isinstance(package, str) or not isinstance(version, str):
                add(report, root, path, f"allowlist server {server_id} needs string package and version")
                return None
            if not EXACT_VERSION.fullmatch(version):
                add(report, root, path, f"allowlist server {server_id} version {version} is not an exact pin")
                return None
            problem = floor_problem(package, version)
            if problem:
                add(report, root, path, f"allowlist server {server_id}: {problem}")
                return None
            canon = canonical_package(package)
            if canon in by_package:
                add(report, root, path, f"duplicate allowlist package {package}")
                return None
            allowed = PackageAllow(server_id, package, version)
            by_id[server_id] = allowed
            by_package[canon] = allowed
        elif transport == "stdio" and "command" in entry:
            command = entry.get("command")
            args = entry.get("args")
            args_ok = isinstance(args, list) and all(isinstance(item, str) for item in args)
            if not isinstance(command, str) or not args_ok:
                add(report, root, path, f"allowlist server {server_id} needs a command and string args")
                return None
            by_id[server_id] = CommandAllow(server_id, command, tuple(args))
        else:
            add(report, root, path, f"allowlist server {server_id} has an unknown shape")
            return None
    return Policy(by_id, by_package)


def approved_package(policy: Policy, package: str, version: str) -> bool:
    allowed = policy.by_package.get(canonical_package(package))
    return bool(allowed and allowed.version == version)


def check_dependency(
    report: Report, root: Path, path: Path, package: str, spec: Spec, policy: Policy
) -> None:
    report.dependencies += 1
    if not spec.exact or spec.version is None:
        shown = spec.version or "no version"
        add(report, root, path, f"dependency {package} is not exact-pinned ({shown})")
        return
    problem = floor_problem(package, spec.version)
    if problem:
        add(report, root, path, f"dependency {problem}")
        return
    if not approved_package(policy, package, spec.version):
        add(
            report,
            root,
            path,
            f"dependency {package}@{spec.version} is not on the allowlist "
            f"({ALLOWLIST_REL.as_posix()})",
        )


def requirement_spec(text: str) -> Spec | None:
    line = text.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "--")):
        return None
    match = REQUIREMENT.match(line)
    if not match:
        return None
    name = match.group(1)
    body = match.group(2).strip()
    if body == "":
        return Spec(name, None, False)
    parts = [part.strip() for part in body.split(",") if part.strip()]
    if len(parts) != 1:
        return Spec(name, body, False)
    operator = OPERATOR.fullmatch(parts[0])
    if not operator:
        return Spec(name, body, False)
    op, version = operator.group(1), operator.group(2).strip()
    exact = op in {"==", "==="} and bool(EXACT_VERSION.fullmatch(version))
    return Spec(name, version if exact or op else version, exact)


def scan_requirements(root: Path, path: Path, report: Report, policy: Policy) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        add(report, root, path, f"could not read requirements ({exc})")
        return
    for line in lines:
        spec = requirement_spec(line)
        if spec and is_server_package(spec.name, set(policy.by_package)):
            check_dependency(report, root, path, spec.name, spec, policy)


def scan_pyproject(root: Path, path: Path, report: Report, policy: Policy) -> dict[str, str]:
    direct: dict[str, str] = {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        add(report, root, path, f"could not parse pyproject.toml ({exc})")
        return direct
    reqs: list[str] = []
    project = data.get("project") or {}
    if isinstance(project, dict):
        reqs.extend(item for item in project.get("dependencies") or [] if isinstance(item, str))
        optional = project.get("optional-dependencies") or {}
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    reqs.extend(item for item in group if isinstance(item, str))
    groups = data.get("dependency-groups") or {}
    if isinstance(groups, dict):
        for group in groups.values():
            if isinstance(group, list):
                reqs.extend(item for item in group if isinstance(item, str))
    for req in reqs:
        spec = requirement_spec(req)
        if spec is None or not is_server_package(spec.name, set(policy.by_package)):
            continue
        check_dependency(report, root, path, spec.name, spec, policy)
        if spec.exact and spec.version is not None:
            direct[canonical_package(spec.name)] = spec.version
    return direct


def scan_uv_lock(root: Path, path: Path, report: Report, policy: Policy, direct: dict[str, str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add(report, root, path, f"could not read uv.lock ({exc})")
        return
    for block in text.split("[[package]]")[1:]:
        header: list[str] = []
        for line in block.splitlines():
            if line.startswith("[") and not line.startswith("[["):
                break
            header.append(line)
        head = "\n".join(header)
        name_match = re.search(r'(?m)^name = "([^"]+)"', head)
        version_match = re.search(r'(?m)^version = "([^"]+)"', head)
        if not name_match or not version_match:
            continue
        name, version = name_match.group(1), version_match.group(1)
        if not is_server_package(name, set(policy.by_package)):
            continue
        canon = canonical_package(name)
        pinned = direct.get(canon)
        if pinned is None:
            add(
                report,
                root,
                path,
                f"uv.lock contains MCP server {name} {version} without an exact direct pin",
            )
            problem = floor_problem(name, version) if EXACT_VERSION.fullmatch(version) else None
            if problem:
                add(report, root, path, f"uv.lock: {problem}")
            continue
        if version != pinned:
            add(report, root, path, f"uv.lock pins {name} {version} but the direct pin is {pinned}")


def scan_package_json(root: Path, path: Path, report: Report, policy: Policy) -> dict[str, str]:
    direct: dict[str, str] = {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add(report, root, path, f"could not parse package.json ({exc})")
        return direct
    if not isinstance(data, dict):
        return direct
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        deps = data.get(section) or {}
        if not isinstance(deps, dict):
            continue
        for name, raw in deps.items():
            if not isinstance(name, str) or not is_server_package(name, set(policy.by_package)):
                continue
            version = raw if isinstance(raw, str) else ""
            exact = bool(EXACT_VERSION.fullmatch(version))
            check_dependency(report, root, path, name, Spec(name, version or None, exact), policy)
            if exact:
                direct[canonical_package(name)] = version
    return direct


def iter_npm_lock_versions(data: object):
    if not isinstance(data, dict):
        return
    packages = data.get("packages")
    if isinstance(packages, dict):
        for key, val in packages.items():
            if not isinstance(val, dict):
                continue
            name = val.get("name") if key == "" else key.rsplit("node_modules/", 1)[-1]
            version = val.get("version")
            if isinstance(name, str) and isinstance(version, str):
                yield name, version
    deps = data.get("dependencies")
    if isinstance(deps, dict):
        for name, val in deps.items():
            if isinstance(name, str) and isinstance(val, dict) and isinstance(val.get("version"), str):
                yield name, val["version"]
                yield from iter_npm_lock_versions(val)


def scan_package_lock(root: Path, path: Path, report: Report, policy: Policy, direct: dict[str, str]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add(report, root, path, f"could not parse package-lock.json ({exc})")
        return
    seen: set[tuple[str, str]] = set()
    for name, version in iter_npm_lock_versions(data):
        if not is_server_package(name, set(policy.by_package)):
            continue
        key = (canonical_package(name), version)
        if key in seen:
            continue
        seen.add(key)
        pinned = direct.get(canonical_package(name))
        if pinned is None:
            add(
                report,
                root,
                path,
                f"package-lock.json contains MCP server {name}@{version} without an exact direct pin",
            )
        elif version != pinned:
            add(
                report,
                root,
                path,
                f"package-lock.json pins {name}@{version} but the direct pin is {pinned}",
            )
        if EXACT_VERSION.fullmatch(version):
            problem = floor_problem(name, version)
        else:
            problem = f"{name}@{version} is not an exact release version"
        if problem and (pinned is None or version != pinned):
            add(report, root, path, f"package-lock.json: {problem}")


def scan_unsupported_lock(root: Path, path: Path, report: Report) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        add(report, root, path, f"could not read lockfile ({exc})")
        return
    match = SERVER_NAME_IN_TEXT.search(text)
    if match:
        add(
            report,
            root,
            path,
            f"unsupported lockfile names MCP server {match.group(0)}; declare an exact pin "
            "in package.json or pyproject.toml and do not use this lock as the pin",
        )


def server_blocks(data: object) -> list[tuple[str, dict]]:
    if not isinstance(data, dict):
        return []
    blocks: list[tuple[str, dict]] = []
    for key in ("servers", "mcpServers"):
        raw = data.get(key)
        if isinstance(raw, dict):
            for name, entry in raw.items():
                if isinstance(name, str) and isinstance(entry, dict):
                    blocks.append((name, entry))
    return blocks


def check_http(report: Report, root: Path, path: Path, server_id: str, url: object, policy: Policy) -> None:
    report.servers += 1
    allowed = policy.by_id.get(server_id)
    if not isinstance(url, str) or not url:
        add(report, root, path, f"server {server_id} has no url")
        return
    if not isinstance(allowed, HttpAllow):
        add(report, root, path, f"server {server_id} is not on the allowlist ({ALLOWLIST_REL.as_posix()})")
        return
    if url != allowed.url:
        add(
            report,
            root,
            path,
            f"server {server_id} url {url} does not match the allowlisted url {allowed.url}",
        )


def check_stdio(report: Report, root: Path, path: Path, server_id: str, entry: dict, policy: Policy) -> None:
    report.servers += 1
    command = entry.get("command")
    args = entry.get("args", [])
    if not isinstance(command, str) or not command:
        add(report, root, path, f"server {server_id} has no command")
        return
    if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
        add(report, root, path, f"server {server_id} args must be a list of strings")
        return
    specs = launch_specs(command, args)
    allowed = policy.by_id.get(server_id)
    if not specs:
        if isinstance(allowed, CommandAllow) and allowed.command == command and allowed.args == tuple(args):
            return
        add(
            report,
            root,
            path,
            f"server {server_id} launches {command} without an exact package pin or an allowlisted argv",
        )
        return
    primary = specs[0]
    if not primary.exact or primary.version is None:
        shown = f"{primary.name}@{primary.version}" if primary.version else primary.name
        add(report, root, path, f"server {server_id} launches {shown} without an exact version pin")
        return
    problem = floor_problem(primary.name, primary.version)
    if problem:
        add(report, root, path, f"server {server_id}: {problem}")
        return
    if not isinstance(allowed, PackageAllow):
        add(report, root, path, f"server {server_id} is not on the allowlist ({ALLOWLIST_REL.as_posix()})")
        return
    same_package = canonical_package(allowed.package) == canonical_package(primary.name)
    if not same_package or allowed.version != primary.version:
        add(
            report,
            root,
            path,
            f"server {server_id} launches {primary.name}@{primary.version} but the allowlist pins "
            f"{allowed.package}@{allowed.version}",
        )
        return
    for extra in specs[1:]:
        if not is_server_package(extra.name, set(policy.by_package)):
            continue
        if not extra.exact or extra.version is None:
            add(report, root, path, f"server {server_id} extra package {extra.name} is not exact-pinned")
            continue
        extra_problem = floor_problem(extra.name, extra.version)
        if extra_problem:
            add(report, root, path, f"server {server_id}: {extra_problem}")
        elif not approved_package(policy, extra.name, extra.version):
            add(
                report,
                root,
                path,
                f"server {server_id} extra package {extra.name}@{extra.version} is not on the allowlist",
            )


def scan_config_object(root: Path, path: Path, data: object, report: Report, policy: Policy) -> None:
    for server_id, entry in server_blocks(data):
        has_url = "url" in entry
        has_command = "command" in entry
        if has_url and has_command:
            report.servers += 1
            add(report, root, path, f"server {server_id} sets both url and command")
        elif has_url:
            check_http(report, root, path, server_id, entry.get("url"), policy)
        elif has_command:
            check_stdio(report, root, path, server_id, entry, policy)
        else:
            report.servers += 1
            add(report, root, path, f"server {server_id} has neither url nor command")


def scan_mcp_json(root: Path, path: Path, report: Report, policy: Policy) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        add(report, root, path, f"could not parse MCP config ({exc})")
        return
    scan_config_object(root, path, data, report, policy)


def scan_mcp_toml(root: Path, path: Path, report: Report, policy: Policy) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add(report, root, path, f"could not read TOML config ({exc})")
        return
    if "[mcp_servers" not in text and "mcpServers" not in text:
        return
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        add(report, root, path, f"could not parse TOML config ({exc})")
        return
    shaped: dict = {}
    servers = data.get("mcp_servers")
    if isinstance(servers, dict):
        shaped["servers"] = servers
    nested = data.get("mcpServers")
    if isinstance(nested, dict):
        shaped["mcpServers"] = nested
    scan_config_object(root, path, shaped, report, policy)


def check_root(root: Path) -> Report:
    root = root.resolve()
    report = Report()
    policy = load_policy(root, report)
    if policy is None:
        report.findings.sort(key=lambda item: (item.path, item.message))
        return report
    direct_python: dict[Path, dict[str, str]] = {}
    direct_node: dict[Path, dict[str, str]] = {}
    for path in iter_files(root):
        name = path.name
        if name in {"mcp.json", ".mcp.json"}:
            scan_mcp_json(root, path, report, policy)
        elif name.endswith(".toml") or name.endswith(".toml.example"):
            if name == "pyproject.toml":
                direct_python[path.parent] = scan_pyproject(root, path, report, policy)
            else:
                scan_mcp_toml(root, path, report, policy)
        elif name == "package.json":
            direct_node[path.parent] = scan_package_json(root, path, report, policy)
        elif name.startswith("requirements") and name.endswith(".txt"):
            scan_requirements(root, path, report, policy)
    for path in iter_files(root):
        name = path.name
        if name == "uv.lock":
            scan_uv_lock(root, path, report, policy, direct_python.get(path.parent, {}))
        elif name == "package-lock.json":
            scan_package_lock(root, path, report, policy, direct_node.get(path.parent, {}))
        elif name in UNSUPPORTED_LOCKS:
            scan_unsupported_lock(root, path, report)
    report.findings.sort(key=lambda item: (item.path, item.message))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail if an MCP server is unpinned or not allowlisted.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    report = check_root(args.root)
    for finding in report.findings:
        print(f"FAIL {finding.path}: {finding.message}")
    if report.findings:
        print(f"mcp supply-chain check failed: {len(report.findings)} finding(s)")
        return 1
    print(
        "mcp supply-chain check passed: "
        f"{report.servers} server entries, {report.dependencies} server dependencies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

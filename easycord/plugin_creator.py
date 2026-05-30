"""Plugin authoring helpers for EasyCord developers."""
from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from .plugin import Plugin


PluginScaffoldMode = Literal["in-project", "package"]

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?$")
_OPTIONAL_COLLECTIONS = {
    "commands",
    "components",
    "modals",
    "events",
    "config",
    "tags",
}


@dataclass
class PluginManifest:
    """Manifest metadata for a generated EasyCord plugin."""

    name: str
    version: str
    description: str
    author: str
    module: str
    class_name: str
    easycord: str
    python: str
    schema_version: int = 1
    commands: list[dict[str, Any]] = field(default_factory=list)
    components: list[dict[str, Any]] = field(default_factory=list)
    modals: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def class_target(self) -> str:
        """Return ``module:class`` for entry-point registration."""

        return f"{self.module}:{self.class_name}"

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "PluginManifest":
        """Build a manifest object from decoded JSON data."""

        known = {
            "schema_version",
            "name",
            "version",
            "description",
            "author",
            "module",
            "class",
            "class_name",
            "easycord",
            "python",
            "commands",
            "components",
            "modals",
            "events",
            "config",
            "tags",
        }
        class_name = data.get("class_name", data.get("class", ""))
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            module=str(data.get("module", "")),
            class_name=str(class_name),
            easycord=str(data.get("easycord", "")),
            python=str(data.get("python", "")),
            commands=list(data.get("commands", []) or []),
            components=list(data.get("components", []) or []),
            modals=list(data.get("modals", []) or []),
            events=list(data.get("events", []) or []),
            config=dict(data.get("config", {}) or {}),
            tags=list(data.get("tags", []) or []),
            extra={key: value for key, value in data.items() if key not in known},
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable manifest."""

        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "module": self.module,
            "class": self.class_name,
            "easycord": self.easycord,
            "python": self.python,
            "commands": self.commands,
            "components": self.components,
            "modals": self.modals,
            "events": self.events,
            "config": self.config,
            "tags": self.tags,
        }
        data.update(self.extra)
        return data


@dataclass
class PluginScaffoldOptions:
    """Options for creating an EasyCord plugin scaffold."""

    name: str
    target: Path | str = Path(".")
    mode: PluginScaffoldMode = "in-project"
    author: str = "Unknown"
    description: str | None = None
    version: str = "0.1.0"
    easycord: str = ">=5.43.0"
    python: str = ">=3.10"
    overwrite: bool = False


@dataclass
class PluginScaffoldResult:
    """Result returned after creating a plugin scaffold."""

    mode: PluginScaffoldMode
    target: Path
    manifest: PluginManifest
    written: list[Path]

    @property
    def manifest_path(self) -> Path | None:
        for path in self.written:
            if path.name.endswith("easycord-plugin.json"):
                return path
        return None

    @property
    def plugin_path(self) -> Path | None:
        for path in self.written:
            if path.name == "plugin.py":
                return path
        for path in self.written:
            if (
                path.suffix == ".py"
                and path.parent.name == "plugins"
                and path.name != "__init__.py"
            ):
                return path
        return None

    @property
    def test_path(self) -> Path | None:
        for path in self.written:
            if path.parts and path.parent.name == "tests" and path.name.startswith("test_"):
                return path
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "target": str(self.target),
            "manifest": self.manifest.to_dict(),
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "plugin_path": str(self.plugin_path) if self.plugin_path else None,
            "test_path": str(self.test_path) if self.test_path else None,
            "written": [str(path) for path in self.written],
        }


@dataclass
class PluginCheck:
    """Single plugin authoring check result."""

    code: str
    message: str
    ok: bool
    severity: str = "error"
    path: str = ""


@dataclass
class PluginCheckReport:
    """Validation report for a plugin manifest or project."""

    checks: list[PluginCheck]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def failed(self) -> int:
        return sum(1 for check in self.checks if not check.ok and check.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "failed": self.failed,
            "checks": [check.__dict__.copy() for check in self.checks],
        }


def module_name(name: str) -> str:
    """Normalize a display name into a valid Python module name."""

    lowered = re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower()
    if not lowered:
        return "plugin"
    if lowered[0].isdigit():
        return f"plugin_{lowered}"
    return lowered


def class_name(name: str, suffix: str = "Plugin") -> str:
    """Normalize a display name into a valid Python class name."""

    parts = re.split(r"[^0-9A-Za-z]+", name)
    cleaned = "".join(part[:1].upper() + part[1:] for part in parts if part)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"Plugin{cleaned}"
    if suffix and not cleaned.endswith(suffix):
        cleaned = f"{cleaned}{suffix}"
    return cleaned


def package_name(name: str) -> str:
    """Normalize a display name into a package/distribution name."""

    return module_name(name).replace("_", "-")


def load_plugin_manifest(path: Path | str) -> PluginManifest:
    """Load ``easycord-plugin.json`` metadata from *path*."""

    manifest_path = Path(path)
    if manifest_path.is_dir():
        manifest_path = _find_manifest_path(manifest_path)
    with manifest_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{manifest_path} must contain a JSON object.")
    return PluginManifest.from_mapping(raw)


def validate_plugin_manifest(path_or_manifest: Path | str | PluginManifest) -> PluginCheckReport:
    """Validate a plugin manifest and return structured checks."""

    manifest: PluginManifest
    path = ""
    checks: list[PluginCheck] = []
    try:
        if isinstance(path_or_manifest, PluginManifest):
            manifest = path_or_manifest
        else:
            path = str(path_or_manifest)
            manifest = load_plugin_manifest(path_or_manifest)
    except Exception as exc:  # noqa: BLE001
        return PluginCheckReport(
            [PluginCheck("manifest.load", f"Could not load manifest: {exc}", False, path=path)]
        )

    def add(code: str, message: str, ok: bool, severity: str = "error") -> None:
        checks.append(PluginCheck(code, message, ok, severity=severity, path=path))

    add("manifest.schema_version", "schema_version must be 1", manifest.schema_version == 1)
    for field_name in (
        "name",
        "version",
        "description",
        "author",
        "module",
        "class_name",
        "easycord",
        "python",
    ):
        add(
            f"manifest.{field_name}",
            f"{field_name} is required",
            bool(getattr(manifest, field_name)),
        )
    add(
        "manifest.version.format",
        "manifest.version must look like X.Y.Z",
        bool(_VERSION_RE.fullmatch(manifest.version)),
    )
    module_parts = manifest.module.split(".")
    add(
        "manifest.module",
        "module must be a dotted Python identifier",
        bool(module_parts) and all(_IDENT_RE.fullmatch(part or "") for part in module_parts),
    )
    add(
        "manifest.class",
        "class must be a Python identifier",
        bool(_IDENT_RE.fullmatch(manifest.class_name)),
    )
    for name in ("commands", "components", "modals", "events"):
        value = getattr(manifest, name)
        add(f"manifest.{name}", f"{name} must be a list", isinstance(value, list))
        if isinstance(value, list):
            add(
                f"manifest.{name}.items",
                f"{name} entries must be objects",
                all(isinstance(item, dict) for item in value),
            )
    add("manifest.config", "config must be an object", isinstance(manifest.config, dict))
    add(
        "manifest.tags",
        "tags must be a list of strings",
        isinstance(manifest.tags, list)
        and all(isinstance(item, str) for item in manifest.tags),
    )
    for key in manifest.extra:
        add(
            f"manifest.extra.{key}",
            f"Unknown manifest key: {key}",
            True,
            severity="warning",
        )
    return PluginCheckReport(checks)


def check_plugin_project(path: Path | str) -> PluginCheckReport:
    """Validate the first EasyCord plugin manifest found under *path*."""

    root = Path(path)
    checks: list[PluginCheck] = []
    try:
        manifest_path = _find_manifest_path(root)
    except FileNotFoundError as exc:
        return PluginCheckReport(
            [PluginCheck("project.manifest", str(exc), False, path=str(root))]
        )
    try:
        manifest = load_plugin_manifest(manifest_path)
    except Exception:  # noqa: BLE001
        return validate_plugin_manifest(manifest_path)
    report = validate_plugin_manifest(manifest)
    checks.extend(report.checks)
    checks.append(
        PluginCheck(
            "project.module",
            f"Plugin module target exists for {manifest.module}",
            _module_exists(root, manifest),
            path=str(root),
        )
    )
    return PluginCheckReport(checks)


def create_in_project_plugin(
    name: str,
    target: Path | str = Path("."),
    **kwargs: Any,
) -> PluginScaffoldResult:
    """Create a manifest-backed plugin under an existing app's ``plugins/`` folder."""

    options = PluginScaffoldOptions(name=name, target=target, mode="in-project", **kwargs)
    return create_plugin_scaffold(options)


def create_package_plugin(
    name: str,
    target: Path | str = Path("."),
    **kwargs: Any,
) -> PluginScaffoldResult:
    """Create a standalone pip-distributable EasyCord plugin package."""

    options = PluginScaffoldOptions(name=name, target=target, mode="package", **kwargs)
    return create_plugin_scaffold(options)


def create_plugin_scaffold(options: PluginScaffoldOptions) -> PluginScaffoldResult:
    """Create an EasyCord plugin scaffold from *options*."""

    target = Path(options.target)
    if options.mode == "in-project":
        files, manifest = _in_project_files(options)
    elif options.mode == "package":
        files, manifest = _package_files(options)
    else:
        raise ValueError(f"Unknown plugin scaffold mode: {options.mode!r}")

    written: list[Path] = []
    for relative, content in files.items():
        path = target / relative
        if path.exists() and not options.overwrite:
            raise FileExistsError(f"Refusing to overwrite existing file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        written.append(path)
    return PluginScaffoldResult(
        mode=options.mode,
        target=target,
        manifest=manifest,
        written=written,
    )


def discover_plugins(group: str = "easycord.plugins") -> list[dict[str, Any]]:
    """Return metadata for installed EasyCord plugin entry points.

    This function does not load plugin code.
    """

    eps = metadata.entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
    discovered: list[dict[str, Any]] = []
    for entry_point in selected:
        dist = getattr(entry_point, "dist", None)
        dist_name = None
        if dist is not None:
            meta = getattr(dist, "metadata", {})
            dist_name = meta.get("Name") if hasattr(meta, "get") else None
        discovered.append(
            {
                "name": entry_point.name,
                "value": entry_point.value,
                "group": entry_point.group,
                "distribution": dist_name,
            }
        )
    return discovered


def load_entrypoint_plugins(group: str = "easycord.plugins") -> list[Plugin]:
    """Load and instantiate plugins from the ``easycord.plugins`` entry-point group."""

    eps = metadata.entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
    plugins: list[Plugin] = []
    for entry_point in selected:
        obj = entry_point.load()
        if isinstance(obj, type) and issubclass(obj, Plugin):
            plugin = obj()
        elif isinstance(obj, Plugin):
            plugin = obj
        elif callable(obj):
            plugin = obj()
        else:
            raise TypeError(f"Entry point {entry_point.name!r} did not load a Plugin.")
        if not isinstance(plugin, Plugin):
            raise TypeError(f"Entry point {entry_point.name!r} did not create a Plugin.")
        plugins.append(plugin)
    return plugins


def _find_manifest_path(root: Path) -> Path:
    if root.is_file():
        return root
    candidates = [root / "easycord-plugin.json"]
    candidates.extend(sorted(root.rglob("*.easycord-plugin.json")))
    candidates.extend(sorted(root.rglob("easycord-plugin.json")))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No EasyCord plugin manifest found under {root}.")


def _module_exists(root: Path, manifest: PluginManifest) -> bool:
    parts = manifest.module.split(".")
    direct = root / Path(*parts).with_suffix(".py")
    if direct.exists():
        return True
    package = root / Path(*parts) / "__init__.py"
    if package.exists():
        return True
    if parts and parts[0] == "plugins":
        local_plugin = root / "plugins" / f"{parts[-1]}.py"
        if local_plugin.exists():
            return True
    return False


def _manifest_for(options: PluginScaffoldOptions, module: str, cls: str) -> PluginManifest:
    return PluginManifest(
        name=module_name(options.name),
        version=options.version,
        description=options.description or f"EasyCord plugin for {options.name}.",
        author=options.author,
        module=module,
        class_name=cls,
        easycord=options.easycord,
        python=options.python,
        commands=[{"name": "hello", "type": "slash"}],
        tags=["easycord", "plugin"],
    )


def _manifest_json(manifest: PluginManifest) -> str:
    return json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"


def _in_project_files(options: PluginScaffoldOptions) -> tuple[dict[str, str], PluginManifest]:
    mod = module_name(options.name)
    cls = class_name(options.name)
    manifest = _manifest_for(options, f"plugins.{mod}", cls)
    files = {
        "plugins/__init__.py": "",
        f"plugins/{mod}.py": f'''\
            from easycord import Plugin, slash_command


            class {cls}(Plugin):
                name = "{manifest.name}"
                version = "{manifest.version}"
                author = "{manifest.author}"
                description = "{manifest.description}"

                @slash_command(description="Say hello")
                async def hello(self, ctx):
                    await ctx.respond(f"Hello, {{ctx.user.display_name}}!")
            ''',
        f"plugins/{mod}.easycord-plugin.json": _manifest_json(manifest),
        f"tests/test_{mod}.py": f'''\
            from easycord import Bot
            from easycord.testing import invoke

            from plugins.{mod} import {cls}


            async def test_{mod}_hello_command():
                bot = Bot(auto_sync=False, db_backend="memory")
                try:
                    bot.add_plugin({cls}())
                    ctx = await invoke(bot, "hello")
                    ctx.assert_contains("Hello")
                finally:
                    await bot.close()
            ''',
    }
    return files, manifest


def _package_files(options: PluginScaffoldOptions) -> tuple[dict[str, str], PluginManifest]:
    mod = module_name(options.name)
    pkg = module_name(f"easycord_{mod}")
    dist = package_name(f"easycord-{mod}")
    cls = class_name(options.name)
    manifest = _manifest_for(options, f"{pkg}.plugin", cls)
    files = {
        "README.md": f'''\
            # {cls}

            Manifest-backed EasyCord plugin package.

            This scaffold is local-safe by default: generated tests use
            `Bot(auto_sync=False, db_backend="memory")`.
            ''',
        "pyproject.toml": f'''\
            [project]
            name = "{dist}"
            version = "{manifest.version}"
            description = "{manifest.description}"
            readme = "README.md"
            requires-python = "{manifest.python}"
            dependencies = ["easycord{manifest.easycord}"]

            [project.optional-dependencies]
            dev = ["pytest>=7", "pytest-asyncio>=0.21"]

            [project.entry-points."easycord.plugins"]
            {manifest.name} = "{manifest.class_target}"

            [tool.pytest.ini_options]
            asyncio_mode = "auto"
            ''',
        f"{pkg}/__init__.py": f"from .plugin import {cls}\n\n__all__ = [\"{cls}\"]\n",
        f"{pkg}/plugin.py": f'''\
            from easycord import Plugin, slash_command


            class {cls}(Plugin):
                name = "{manifest.name}"
                version = "{manifest.version}"
                author = "{manifest.author}"
                description = "{manifest.description}"

                @slash_command(description="Say hello")
                async def hello(self, ctx):
                    await ctx.respond(f"Hello, {{ctx.user.display_name}}!")
            ''',
        f"{pkg}/easycord-plugin.json": _manifest_json(manifest),
        f"tests/test_{mod}.py": f'''\
            from easycord import Bot
            from easycord.testing import invoke

            from {pkg} import {cls}


            async def test_{mod}_hello_command():
                bot = Bot(auto_sync=False, db_backend="memory")
                try:
                    bot.add_plugin({cls}())
                    ctx = await invoke(bot, "hello")
                    ctx.assert_contains("Hello")
                finally:
                    await bot.close()
            ''',
    }
    return files, manifest

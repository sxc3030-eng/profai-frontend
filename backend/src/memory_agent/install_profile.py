"""Profil local non secret utilisé par l'installateur Windows MAT Nexus.

Le profil est lu dans cet ordre : variables d'environnement explicites,
registre utilisateur créé par l'installateur, puis valeurs locales sûres.
Il ne contient jamais de mot de passe, de jeton ou de contenu employeur.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
from typing import Mapping


REGISTRY_KEY = r"Software\MAT Nexus"
_TRUE = frozenset({"1", "true", "yes", "oui", "on"})
_FALSE = frozenset({"0", "false", "no", "non", "off"})
_SAFE_BACKENDS = frozenset({"sqlite", "postgresql"})


def _default_base() -> Path:
    drive = Path("D:/")
    if os.name == "nt" and drive.exists():
        return drive / "MAT-Nexus"
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "MAT-Nexus" if local else Path.home() / ".mat-nexus"


def _clean_path(value: object, fallback: Path) -> Path:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        return fallback.resolve(strict=False)
    candidate = Path(os.path.expandvars(value.strip())).expanduser()
    if not candidate.is_absolute():
        return fallback.resolve(strict=False)
    return candidate.resolve(strict=False)


def _clean_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        folded = value.strip().casefold()
        if folded in _TRUE:
            return True
        if folded in _FALSE:
            return False
    return fallback


def _registry_values() -> dict[str, object]:
    if os.name != "nt":
        return {}
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
            values: dict[str, object] = {}
            for name in (
                "InstallRoot",
                "DataRoot",
                "ControlRoot",
                "ModelRoot",
                "IndexRoot",
                "BackupRoot",
                "AIEnabled",
                "DatabaseBackend",
                "ProductVersion",
            ):
                try:
                    values[name] = winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    continue
            return values
    except (ImportError, FileNotFoundError, OSError):
        return {}


def resource_root() -> Path:
    """Retourne la racine des ressources en source ou dans PyInstaller."""

    frozen_root = getattr(sys, "_MEIPASS", None)
    if isinstance(frozen_root, str) and frozen_root:
        return Path(frozen_root).resolve(strict=False)
    return Path(__file__).resolve().parents[2]


def executable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def portable_product_root() -> Path | None:
    """Detecte la racine du paquet portable depuis un executable composant."""

    component_root = executable_root()
    for candidate in (component_root, component_root.parent):
        if (candidate / "product-manifest.json").is_file():
            return candidate.resolve(strict=False)
    return None


@dataclass(frozen=True, slots=True)
class InstallProfile:
    install_root: Path
    data_root: Path
    control_root: Path
    model_root: Path
    index_root: Path
    backup_root: Path
    ai_enabled: bool
    database_backend: str
    product_version: str
    source: str

    @property
    def database_path(self) -> Path:
        configuration = self.control_root / "sme-config.json"
        try:
            import json

            value = json.loads(configuration.read_text(encoding="utf-8"))
            database = value.get("database")
            if isinstance(database, dict) and database.get("backend") == "sqlite":
                configured = database.get("path")
                if isinstance(configured, str):
                    return _clean_path(configured, self.data_root / "memory.sqlite3")
        except (OSError, ValueError, TypeError):
            pass
        # PostgreSQL est un connecteur de déploiement dans la version actuelle;
        # l'état interne borné de Nexus reste dans SQLite.
        return self.data_root / "memory.sqlite3"

    def model_python(self) -> Path | None:
        explicit = os.environ.get("MAT_NEXUS_MODEL_PYTHON")
        candidates = [] if not explicit else [Path(explicit)]
        candidates.extend(
            (
                self.model_root / ".venv" / "Scripts" / "python.exe",
                self.model_root / "venv" / "Scripts" / "python.exe",
            )
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve(strict=False)
        return None

    def hf_executable(self) -> Path | None:
        """Localise le CLI ``hf`` empaqueté ou celui du runtime IA."""

        explicit = os.environ.get("MAT_NEXUS_HF_EXECUTABLE")
        candidates = [] if not explicit else [Path(explicit)]
        executable = executable_root()
        candidates.extend(
            (
                executable / "MATNexusHF.exe",
                executable.parent / "MATNexusHF" / "MATNexusHF.exe",
                self.install_root / "MATNexusHF" / "MATNexusHF.exe",
                self.model_root / ".venv" / "Scripts" / "hf.exe",
                self.model_root / "venv" / "Scripts" / "hf.exe",
            )
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve(strict=False)
        return None

    def active_local_model(self) -> tuple[str, Path] | None:
        """Retourne le profil local actif après validation du registre signé."""

        registry_path = self.control_root / "model-registry.json"
        if not registry_path.is_file():
            return None
        try:
            from .sme_model_registry import ModelProfileRegistry

            snapshot = ModelProfileRegistry(registry_path).snapshot()
        except (OSError, ValueError):
            return None
        active = snapshot.get("active_profile_id")
        profiles = snapshot.get("profiles")
        if not isinstance(active, str) or not isinstance(profiles, list):
            return None
        for item in profiles:
            if (
                isinstance(item, dict)
                and item.get("profile_id") == active
                and item.get("provider_kind") == "local"
                and item.get("enabled") is True
                and isinstance(item.get("model_path"), str)
            ):
                model_path = _clean_path(item["model_path"], self.model_root / "missing")
                if model_path.is_dir():
                    return active, model_path
        return None

    def public_dict(self) -> dict[str, object]:
        return {
            "install_root": str(self.install_root),
            "data_root": str(self.data_root),
            "control_root": str(self.control_root),
            "model_root": str(self.model_root),
            "index_root": str(self.index_root),
            "backup_root": str(self.backup_root),
            "ai_enabled": self.ai_enabled,
            "database_backend": self.database_backend,
            "product_version": self.product_version,
            "source": self.source,
        }


def load_install_profile(
    environ: Mapping[str, str] | None = None,
    registry: Mapping[str, object] | None = None,
) -> InstallProfile:
    environment = os.environ if environ is None else environ
    values = _registry_values() if registry is None else dict(registry)
    portable_root = portable_product_root()
    base = portable_root if portable_root is not None else _default_base()

    def selected(env_name: str, registry_name: str) -> object | None:
        return environment.get(env_name) or values.get(registry_name)

    install_fallback = portable_root or executable_root()
    install_root = _clean_path(
        selected("MAT_NEXUS_INSTALL_ROOT", "InstallRoot"), install_fallback
    )
    data_root = _clean_path(selected("MAT_NEXUS_DATA_ROOT", "DataRoot"), base / "data")
    control_root = _clean_path(
        selected("MAT_NEXUS_CONTROL_ROOT", "ControlRoot"), base / "config"
    )
    model_default = Path("D:/MAT-LM") if os.name == "nt" and Path("D:/").exists() else base / "models"
    model_root = _clean_path(
        selected("MAT_NEXUS_MODEL_ROOT", "ModelRoot"), model_default
    )
    index_root = _clean_path(
        selected("MAT_NEXUS_INDEX_ROOT", "IndexRoot"), base / "indexes"
    )
    backup_root = _clean_path(
        selected("MAT_NEXUS_BACKUP_ROOT", "BackupRoot"), base / "backups"
    )
    ai_enabled = _clean_bool(
        selected("MAT_NEXUS_AI_ENABLED", "AIEnabled"),
        # Le mode source conserve le comportement historique; l'installateur
        # inscrit explicitement le choix de l'utilisateur.
        not getattr(sys, "frozen", False),
    )
    backend_value = selected("MAT_NEXUS_DATABASE_BACKEND", "DatabaseBackend")
    backend = str(backend_value or "sqlite").strip().casefold()
    if backend not in _SAFE_BACKENDS:
        backend = "sqlite"
    version_value = selected("MAT_NEXUS_PRODUCT_VERSION", "ProductVersion")
    if version_value is None and portable_root is not None:
        try:
            import json

            portable_manifest = json.loads(
                (portable_root / "product-manifest.json").read_text(encoding="utf-8-sig")
            )
            version_value = portable_manifest.get("product_version")
        except (OSError, ValueError, TypeError):
            pass
    product_version = str(version_value or "0.8.0").strip()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}", product_version) is None:
        product_version = "0.8.0"
    source = "environment" if any(name.startswith("MAT_NEXUS_") for name in environment) else (
        "registry" if values else "defaults"
    )
    return InstallProfile(
        install_root=install_root,
        data_root=data_root,
        control_root=control_root,
        model_root=model_root,
        index_root=index_root,
        backup_root=backup_root,
        ai_enabled=ai_enabled,
        database_backend=backend,
        product_version=product_version,
        source=source,
    )

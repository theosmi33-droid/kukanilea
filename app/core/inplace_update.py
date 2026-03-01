from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .release_validator import ReleaseValidator


class UpdateError(RuntimeError):
    """Raised when an update cannot be applied safely."""


@dataclass(frozen=True)
class InPlaceUpdateResult:
    version: str
    release_dir: Path
    previous_release: Path | None
    healthcheck_output: str


class InPlaceUpdater:
    def __init__(
        self,
        install_root: Path,
        data_dir: Path,
        release_root: Path | None = None,
        current_link: Path | None = None,
        validator: ReleaseValidator | None = None,
    ) -> None:
        self.install_root = Path(install_root).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.release_root = (
            Path(release_root).resolve()
            if release_root is not None
            else (self.install_root / "releases")
        )
        self.current_link = (
            Path(current_link).resolve()
            if current_link is not None
            else (self.install_root / "current")
        )
        self.validator = validator or ReleaseValidator()

        self.install_root.mkdir(parents=True, exist_ok=True)
        self.release_root.mkdir(parents=True, exist_ok=True)

    def apply_from_tarball(
        self,
        tarball_path: Path,
        version: str,
        *,
        healthcheck_cmd: Sequence[str] | None = None,
        manifest_path: Path | None = None,
    ) -> InPlaceUpdateResult:
        tarball = Path(tarball_path)
        if not tarball.exists():
            raise UpdateError(f"Update payload not found: {tarball}")

        with tempfile.TemporaryDirectory(prefix="kuka-update-") as tmpdir:
            extract_root = Path(tmpdir) / "payload"
            extract_root.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tarball, "r:*") as tf:
                tf.extractall(extract_root)

            source_dir = self._resolve_payload_root(extract_root)
            return self.apply_from_directory(
                source_dir,
                version,
                healthcheck_cmd=healthcheck_cmd,
                manifest_path=manifest_path,
            )

    def apply_from_directory(
        self,
        source_dir: Path,
        version: str,
        *,
        healthcheck_cmd: Sequence[str] | None = None,
        manifest_path: Path | None = None,
    ) -> InPlaceUpdateResult:
        src = Path(source_dir).resolve()
        if not src.exists() or not src.is_dir():
            raise UpdateError(f"Update source directory missing: {src}")

        self._assert_data_dir_separation()

        release_dir = self._stage_release(src, version)
        if manifest_path is not None:
            if not self.validator.verify_manifest(Path(manifest_path)):
                shutil.rmtree(release_dir, ignore_errors=True)
                raise UpdateError("Manifest signature verification failed")
            if not self.validator.verify_files(Path(manifest_path), release_dir):
                shutil.rmtree(release_dir, ignore_errors=True)
                raise UpdateError("Manifest file hash verification failed")

        previous_release = self._atomic_switch_current(release_dir)

        ok, output = self._run_healthcheck(healthcheck_cmd, cwd=release_dir)
        if not ok:
            self._rollback(previous_release)
            shutil.rmtree(release_dir, ignore_errors=True)
            raise UpdateError(
                "Healthcheck failed after switch; rollback completed. "
                f"Output: {output.strip()}"
            )

        return InPlaceUpdateResult(
            version=version,
            release_dir=release_dir,
            previous_release=previous_release,
            healthcheck_output=output,
        )

    def _assert_data_dir_separation(self) -> None:
        if self._is_subpath(self.data_dir, self.install_root):
            raise UpdateError(
                "Data directory must be outside install root for safe in-place updates"
            )
        if self._is_subpath(self.install_root, self.data_dir):
            raise UpdateError(
                "Install root must not be nested inside data directory"
            )

    @staticmethod
    def _is_subpath(child: Path, parent: Path) -> bool:
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False

    def _stage_release(self, source_dir: Path, version: str) -> Path:
        version = version.strip()
        if not version:
            raise UpdateError("Version must not be empty")

        target_release = self.release_root / version
        if target_release.exists():
            raise UpdateError(f"Target release already exists: {target_release}")

        stage_dir = self.release_root / f".stage-{version}-{uuid.uuid4().hex[:8]}"
        shutil.copytree(source_dir, stage_dir)
        os.replace(stage_dir, target_release)
        return target_release

    def _atomic_switch_current(self, new_release: Path) -> Path | None:
        previous = self._current_target()
        tmp_link = self.current_link.with_name(f"{self.current_link.name}.tmp")
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink(missing_ok=True)

        os.symlink(new_release, tmp_link)
        os.replace(tmp_link, self.current_link)
        return previous

    def _rollback(self, previous_release: Path | None) -> None:
        if previous_release is None:
            if self.current_link.exists() or self.current_link.is_symlink():
                self.current_link.unlink(missing_ok=True)
            return

        tmp_link = self.current_link.with_name(f"{self.current_link.name}.rollback")
        if tmp_link.exists() or tmp_link.is_symlink():
            tmp_link.unlink(missing_ok=True)
        os.symlink(previous_release, tmp_link)
        os.replace(tmp_link, self.current_link)

    def _current_target(self) -> Path | None:
        if not self.current_link.exists() or not self.current_link.is_symlink():
            return None
        return self.current_link.resolve()

    @staticmethod
    def _run_healthcheck(
        command: Sequence[str] | None,
        *,
        cwd: Path,
        timeout_seconds: int = 30,
    ) -> tuple[bool, str]:
        if not command:
            return True, "healthcheck skipped"

        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode == 0, output

    @staticmethod
    def _resolve_payload_root(extract_root: Path) -> Path:
        children = [p for p in extract_root.iterdir() if p.name != "__MACOSX"]
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return extract_root

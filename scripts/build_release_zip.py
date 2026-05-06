from __future__ import annotations

import os
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "astrbot_plugin_volcengine_asr"
OUT = ROOT / "output" / "astrbot_plugin_volcengine_asr.zip"
PACKAGE_DIR = "astrbot_plugin_volcengine_asr"
EXCLUDES = {".gitignore", ".DS_Store", "__pycache__"}
REQUIRED_ROOT_FILES = {"main.py", "metadata.yaml"}
EXECUTABLE_FILES = {"bin/linux-x86_64/ffmpeg"}
REQUIRED_ZIP_FILES = REQUIRED_ROOT_FILES | EXECUTABLE_FILES


def should_skip(name: str) -> bool:
    parts = name.replace("\\", "/").split("/")
    return any(part in EXCLUDES for part in parts)


def package_arcname(source_arcname: str) -> str:
    return f"{PACKAGE_DIR}/{source_arcname}"


def write_directory(zf: zipfile.ZipFile, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname)
    info.external_attr = (0o040755 << 16) | 0x10
    zf.writestr(info, b"")


def write_entry(
    zf: zipfile.ZipFile, full_path: Path, source_arcname: str, zip_arcname: str
) -> None:
    info = zipfile.ZipInfo(zip_arcname)
    mode = 0o100755 if source_arcname in EXECUTABLE_FILES else 0o100644
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, full_path.read_bytes())


def validate_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as zf:
        namelist = zf.namelist()
        if not namelist or namelist[0] != f"{PACKAGE_DIR}/":
            raise RuntimeError(
                f"Release zip must start with {PACKAGE_DIR}/ directory entry"
            )

        top_level = {name.split("/", 1)[0] for name in namelist if name}
        if top_level != {PACKAGE_DIR}:
            raise RuntimeError(
                f"Release zip must contain only {PACKAGE_DIR}/ at top level, "
                f"got {sorted(top_level)}"
            )

        names = set(namelist)
        required_zip_files = {package_arcname(arcname) for arcname in REQUIRED_ZIP_FILES}
        missing = sorted(required_zip_files - names)
        if missing:
            raise RuntimeError(f"Missing required release files in zip: {missing}")

        for source_arcname in sorted(EXECUTABLE_FILES):
            zip_arcname = package_arcname(source_arcname)
            mode = (zf.getinfo(zip_arcname).external_attr >> 16) & 0o777777
            if mode != 0o100755:
                raise RuntimeError(
                    f"Required executable has wrong zip mode: {zip_arcname} "
                    f"expected 0o100755, got {mode:#08o}"
                )


def validate_required_sources() -> None:
    missing = sorted(
        arcname for arcname in REQUIRED_ZIP_FILES if not (SRC / arcname).is_file()
    )
    if missing:
        raise RuntimeError(f"Missing required release source files: {missing}")


def build_zip() -> Path:
    validate_required_sources()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        write_directory(zf, f"{PACKAGE_DIR}/")
        for root, dirs, files in os.walk(SRC):
            dirs[:] = [directory for directory in dirs if directory not in EXCLUDES]
            rel_root = Path(root).relative_to(SRC).as_posix()
            if rel_root != ".":
                source_arc_dir = rel_root + "/"
                if should_skip(source_arc_dir):
                    continue
                write_directory(zf, package_arcname(source_arc_dir))
            for filename in files:
                if filename in EXCLUDES:
                    continue
                full_path = Path(root) / filename
                source_arcname = full_path.relative_to(SRC).as_posix()
                if should_skip(source_arcname):
                    continue
                write_entry(
                    zf,
                    full_path,
                    source_arcname,
                    package_arcname(source_arcname),
                )

    validate_zip(OUT)
    return OUT


def main() -> None:
    path = build_zip()
    print(f"OK {path} {path.stat().st_size}")


if __name__ == "__main__":
    main()

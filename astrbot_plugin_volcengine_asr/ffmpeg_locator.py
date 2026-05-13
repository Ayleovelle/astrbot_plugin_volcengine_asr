from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from astrbot.api import logger


FFMPEG_PROBE_TIMEOUT_SECONDS = 5
ProbeFn = Callable[[str], tuple[bool, str]]


def parse_ffmpeg_version_output(output: str) -> str | None:
    first_line = output.strip().splitlines()[0] if output.strip() else ""
    if not first_line.lower().startswith("ffmpeg version "):
        return None
    parts = first_line.split()
    return parts[2] if len(parts) >= 3 else None


def probe_ffmpeg_startup(ffmpeg_path: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=FFMPEG_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return False, "文件不存在"
    except PermissionError as exc:
        return False, f"没有执行权限：{exc}"
    except subprocess.TimeoutExpired:
        return False, "启动探测超时"
    except OSError as exc:
        return False, f"无法启动：{exc}"

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    if completed.returncode != 0:
        error_text = output.strip() or f"退出码 {completed.returncode}"
        if len(error_text) > 160:
            error_text = error_text[:160] + "..."
        return False, error_text

    version = parse_ffmpeg_version_output(output)
    if not version:
        return False, "无法识别 ffmpeg -version 输出"
    return True, version


def append_ffmpeg_candidate(candidates: list[tuple[str, str]], path: str | Path | None, source: str) -> None:
    if path is None:
        return
    text = str(path).strip().strip('"')
    if not text:
        return
    normalized = (
        os.path.normcase(os.path.abspath(text))
        if os.path.sep in text or (os.path.altsep and os.path.altsep in text)
        else text
    )
    seen = {
        os.path.normcase(os.path.abspath(item[0]))
        if os.path.sep in item[0] or (os.path.altsep and os.path.altsep in item[0])
        else item[0]
        for item, _ in candidates
    }
    if normalized not in seen:
        candidates.append((text, source))


def ffmpeg_executable_names() -> list[str]:
    return ["ffmpeg.exe", "ffmpeg"] if os.name == "nt" else ["ffmpeg"]


def iter_env_ffmpeg_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for name in ("ASTRBOT_VOLC_ASR_FFMPEG", "VOLC_ASR_FFMPEG", "FFMPEG_PATH", "IMAGEIO_FFMPEG_EXE"):
        value = os.environ.get(name)
        if value:
            append_ffmpeg_candidate(candidates, value, f"环境变量 {name}")
    return candidates


def iter_plugin_ffmpeg_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    plugin_dir = Path(__file__).resolve().parent
    for relative in (
        Path("ffmpeg"),
        Path("ffmpeg.exe"),
        Path("bin") / "ffmpeg",
        Path("bin") / "ffmpeg.exe",
        Path("bin") / "linux-x86_64" / "ffmpeg",
        Path("bin") / "linux-amd64" / "ffmpeg",
        Path("bin") / "win-x86_64" / "ffmpeg.exe",
        Path("bin") / "windows-x86_64" / "ffmpeg.exe",
        Path("bin") / "darwin-arm64" / "ffmpeg",
        Path("bin") / "darwin-x86_64" / "ffmpeg",
    ):
        path = plugin_dir / relative
        if path.exists():
            try:
                if os.name != "nt":
                    path.chmod(path.stat().st_mode | 0o755)
            except OSError as exc:
                logger.warning(f"设置插件目录 ffmpeg 执行权限失败：{exc}")
            append_ffmpeg_candidate(candidates, path, f"插件目录 {relative.as_posix()}")
    return candidates


def iter_path_ffmpeg_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for executable in ffmpeg_executable_names():
        resolved = shutil.which(executable)
        if resolved:
            append_ffmpeg_candidate(candidates, resolved, "PATH 解析")
    append_ffmpeg_candidate(candidates, "ffmpeg", "PATH 命令")
    return candidates


def iter_common_ffmpeg_candidates() -> list[tuple[str, str]]:
    paths: list[str] = []
    if os.name == "nt":
        paths.extend(
            [
                r"C:\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
                r"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
                r"C:\tools\ffmpeg\bin\ffmpeg.exe",
            ]
        )
    elif sys.platform == "darwin":
        paths.extend(
            [
                "/opt/homebrew/bin/ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/opt/local/bin/ffmpeg",
                "/usr/bin/ffmpeg",
            ]
        )
    else:
        paths.extend(
            [
                "/usr/bin/ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/bin/ffmpeg",
                "/snap/bin/ffmpeg",
                "/app/bin/ffmpeg",
                "/opt/bin/ffmpeg",
                "/opt/ffmpeg/bin/ffmpeg",
            ]
        )
    candidates: list[tuple[str, str]] = []
    for path in paths:
        append_ffmpeg_candidate(candidates, path, "常见路径")
    return candidates


def build_ffmpeg_candidates(configured_path: str, prefer_bundled: bool) -> list[tuple[str, str]]:
    configured_path = (configured_path or "auto").strip()
    configured_lower = configured_path.lower()
    candidates: list[tuple[str, str]] = []

    if configured_lower not in {"", "auto", "ffmpeg"}:
        append_ffmpeg_candidate(candidates, configured_path, "配置路径")
        return candidates

    for path, source in iter_env_ffmpeg_candidates():
        append_ffmpeg_candidate(candidates, path, source)

    if prefer_bundled:
        bundled = get_plugin_bundled_ffmpeg()
        if bundled:
            append_ffmpeg_candidate(candidates, bundled[0], bundled[1])

        for path, source in iter_plugin_ffmpeg_candidates():
            append_ffmpeg_candidate(candidates, path, source)

        try:
            import imageio_ffmpeg

            bundled_path = imageio_ffmpeg.get_ffmpeg_exe()
            if bundled_path:
                append_ffmpeg_candidate(candidates, bundled_path, "imageio-ffmpeg")
        except Exception as exc:
            logger.warning(f"读取 imageio-ffmpeg 内置 ffmpeg 失败，将回退到系统 PATH：{exc}")

    for path, source in iter_path_ffmpeg_candidates():
        append_ffmpeg_candidate(candidates, path, source)

    if configured_lower == "ffmpeg":
        return candidates

    for path, source in iter_common_ffmpeg_candidates():
        append_ffmpeg_candidate(candidates, path, source)

    return candidates


def select_probeable_ffmpeg(candidates: list[tuple[str, str]], probe: ProbeFn | None = None) -> tuple[str, str, str]:
    probe = probe or probe_ffmpeg_startup
    failures: list[str] = []
    for path, source in candidates:
        ok, detail = probe(path)
        if ok:
            return path, f"{source} ({detail})", ""
        failures.append(f"{source}={path}：{detail}")
    error = (
        "未找到可启动的 ffmpeg，已尝试 "
        + "；".join(failures)
        + "。请安装系统 ffmpeg，或在配置中填写可执行的 ffmpeg_path。"
    )
    fallback_path = candidates[0][0] if candidates else "ffmpeg"
    return fallback_path, "不可用", error


def resolve_ffmpeg_path(configured_path: str, prefer_bundled: bool) -> tuple[str, str, str]:
    configured_path = (configured_path or "auto").strip()
    return select_probeable_ffmpeg(build_ffmpeg_candidates(configured_path, prefer_bundled))


def get_plugin_bundled_ffmpeg() -> tuple[str, str] | None:
    if not sys.platform.startswith("linux"):
        return None

    machine = platform.machine().lower()
    if machine not in {"x86_64", "amd64"}:
        return None

    ffmpeg_path = Path(__file__).resolve().parent / "bin" / "linux-x86_64" / "ffmpeg"
    if not ffmpeg_path.exists():
        return None

    try:
        ffmpeg_path.chmod(ffmpeg_path.stat().st_mode | 0o755)
    except OSError as exc:
        logger.warning(f"设置内置 ffmpeg 执行权限失败：{exc}")

    return str(ffmpeg_path), "插件内置 ffmpeg (linux-x86_64)"

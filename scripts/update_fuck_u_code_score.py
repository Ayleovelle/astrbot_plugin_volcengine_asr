from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


SVG_PATHS = (
    Path("assets/FuckUCodeScore.svg"),
    Path("astrbot_plugin_volcengine_asr/assets/FuckUCodeScore.svg"),
)


SCORE_PATTERNS = (
    re.compile(r"(?i)\bscore\b[^0-9]{0,24}([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?i)\btotal\s+score\b[^0-9]{0,24}([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?i)\boverall\b[^0-9]{0,24}([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?i)\bfuck-u-code\b[^0-9]{0,48}([0-9]+(?:\.[0-9]+)?)"),
    re.compile(r"(?:得分|评分|总分|综合分)[^0-9]{0,24}([0-9]+(?:\.[0-9]+)?)"),
)


def normalize_score(value: str) -> str:
    number = float(value)
    if number < 0:
        number = 0.0
    if number > 100:
        number = 100.0
    return f"{number:.2f}"


def find_score(report_text: str) -> str | None:
    for pattern in SCORE_PATTERNS:
        match = pattern.search(report_text)
        if match:
            return normalize_score(match.group(1))

    numbers = [
        float(match.group(0))
        for match in re.finditer(r"\b(?:100(?:\.0+)?|[0-9]{1,2}(?:\.[0-9]+)?)\b", report_text)
    ]
    if not numbers:
        return None
    return normalize_score(str(max(numbers)))


def extract_score(report_text: str) -> str:
    return find_score(report_text) or "0.00"


def build_svg(score: str) -> str:
    escaped = html.escape(score)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="250" height="54" viewBox="0 0 250 54" role="img" aria-labelledby="title desc">
  <title id="title">Fuck-U-Code 代码质量评分</title>
  <desc id="desc">参考 ShitMountain 风格的 250x54 极简评分卡，展示由 GitHub Actions bot 自动更新的 fuck-u-code 分数 {escaped}。</desc>
  <defs>
    <style type="text/css">
      .text-bold {{ font-family: 'Helvetica Bold', Helvetica, Arial, sans-serif; font-weight: bold; }}
      .text-regular {{ font-family: Helvetica, Arial, sans-serif; }}
      .emoji {{ font-family: "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"; }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="249" height="53" rx="10" fill="#FFFFFF" stroke="#E0C9A6" stroke-width="1"/>

  <text x="28" y="38" font-size="30" class="emoji" text-anchor="middle">💬</text>

  <g fill="#5D4037" class="text-bold">
    <text x="53" y="21" font-size="9">CODE SMELL BY</text>
    <text x="52" y="41" font-size="21">Fuck-U-Code</text>
  </g>

  <g transform="translate(185, 13)" fill="#5D4037">
    <text x="35" y="10" font-size="9" class="text-regular" text-anchor="middle">SCORE</text>
    <text x="35" y="28" font-size="18" class="text-bold" text-anchor="middle">{escaped}</text>
  </g>
</svg>
"""


def update_svg(score: str, paths: tuple[Path, ...] = SVG_PATHS) -> None:
    svg = build_svg(score)
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update FuckUCodeScore.svg from a fuck-u-code markdown report."
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/fuck-u-code-report.md"),
        help="Path to the fuck-u-code markdown report.",
    )
    parser.add_argument(
        "--score",
        help="Explicit score override, useful for tests and manual runs.",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Do not rewrite SVG files when the report is missing or no score can be parsed.",
    )
    args = parser.parse_args()

    if args.score is not None:
        score = normalize_score(args.score)
    elif args.report.exists():
        score = find_score(args.report.read_text(encoding="utf-8", errors="replace"))
    else:
        score = None

    if score is None:
        message = f"fuck-u-code score not found in {args.report}"
        if args.skip_missing:
            print(f"{message}; badge update skipped")
            return
        score = "0.00"

    update_svg(score)
    print(f"fuck-u-code score: {score}")


if __name__ == "__main__":
    main()

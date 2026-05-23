#!/usr/bin/env python3
"""Export docs/presentation.html slides to PNG for README embedding."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

SLIDE_TITLES = (
    "cover",
    "the-problem",
    "what-it-is",
    "architecture",
    "citation-contract",
    "output-card",
    "oauth-security",
    "data-discipline",
    "eval-harness",
    "engineering-rigor",
    "stack",
    "story-demo",
    "results",
    "recap",
)


def export_slides(
    *,
    html_path: Path,
    output_dir: Path,
    width: int = 1600,
    height: int = 900,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_url = html_path.resolve().as_uri()
    written: list[Path] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(file_url, wait_until="networkidle")
        page.add_style_tag(
            content=(
                ".progress, .topbar, .dots, .hint, .overview { display: none !important; }"
                ".slide { padding-top: 3.5rem !important; }"
            )
        )

        for index, slug in enumerate(SLIDE_TITLES):
            page.evaluate(
                """(n) => {
                    const slides = Array.from(document.querySelectorAll(".slide"));
                    slides.forEach((slide, i) => slide.classList.toggle("active", i === n));
                }""",
                index,
            )
            page.wait_for_timeout(350)
            out = output_dir / f"slide-{index + 1:02d}-{slug}.png"
            page.screenshot(path=str(out), type="png")
            written.append(out)

        browser.close()

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--html",
        type=Path,
        default=Path("docs/presentation.html"),
        help="Path to the interactive deck HTML",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/presentation/slides"),
        help="Directory for exported PNG slides",
    )
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args()

    paths = export_slides(
        html_path=args.html,
        output_dir=args.out,
        width=args.width,
        height=args.height,
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()

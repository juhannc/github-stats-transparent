# SPDX-FileCopyrightText: 2024 Rahul Jha
# SPDX-FileCopyrightText: 2026 Johann Christensen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Module to help generate SVG images for GitHub statistics."""

import re

from gst import ROOT_FOLDER
from gst.stats import Stats


def generate_output_folder() -> None:
    """Create the output folder if it does not already exist."""
    if not (ROOT_FOLDER / "generated").is_dir():
        (ROOT_FOLDER / "generated").mkdir()


async def generate_overview(s: Stats) -> None:
    """Generate an SVG badge with summary statistics.

    Args:
        s (Stats): Represents user's GitHub statistics.
    """
    output = (ROOT_FOLDER / "templates/overview.svg").read_text(encoding="utf-8")

    output = re.sub(r"{{ name }}", await s.name, output)
    output = re.sub(r"{{ stars }}", f"{await s.stargazers:,}", output)
    output = re.sub(r"{{ forks }}", f"{await s.forks:,}", output)
    output = re.sub(r"{{ contributions }}", f"{await s.total_contributions:,}", output)
    changed = (await s.lines_changed)[0] + (await s.lines_changed)[1]
    output = re.sub(r"{{ lines_changed }}", f"{changed:,}", output)
    output = re.sub(r"{{ views }}", f"{await s.views:,}", output)
    output = re.sub(r"{{ repos }}", f"{len(await s.all_repos):,}", output)

    generate_output_folder()
    (ROOT_FOLDER / "generated/overview.svg").write_text(output, encoding="utf-8")


async def generate_languages(s: Stats) -> None:
    """Generate an SVG badge with summary languages used.

    Args:
        s (Stats): Represents user's GitHub statistics.
    """
    output = (ROOT_FOLDER / "templates/languages.svg").read_text(encoding="utf-8")

    progress = ""
    lang_list = ""
    sorted_languages = sorted(
        (await s.languages).items(), reverse=True, key=lambda t: t[1].get("size")
    )
    delay_between = 150
    for i, (lang, data) in enumerate(sorted_languages):
        color = data.get("color")
        color = color if color is not None else "#000000"
        ratio = [0.98, 0.02]
        if data.get("prop", 0) > 50:  # noqa: PLR2004
            ratio = [0.99, 0.01]
        if i == len(sorted_languages) - 1:
            ratio = [1, 0]
        progress += (
            f'<span style="background-color: {color};'
            f"width: {(ratio[0] * data.get('prop', 0)):0.3f}%;"
            f'margin-right: {(ratio[1] * data.get("prop", 0)):0.3f}%;" '
            f'class="progress-item"></span>'
        )
        lang_list += f"""
<li style="animation-delay: {i * delay_between}ms;">
<svg xmlns="http://www.w3.org/2000/svg" class="octicon" style="fill:{color};"
viewBox="0 0 16 16" version="1.1" width="16" height="16"><path
fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8z"></path></svg>
<span class="lang">{lang}</span>
<span class="percent">{data.get("prop", 0):0.2f}%</span>
</li>

"""

    output = re.sub(r"{{ progress }}", progress, output)
    output = re.sub(r"{{ lang_list }}", lang_list, output)

    generate_output_folder()
    (ROOT_FOLDER / "generated/languages.svg").write_text(output, encoding="utf-8")

# SPDX-FileCopyrightText: 2024 Rahul Jha
# SPDX-FileCopyrightText: 2026 Johann Christensen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate SVG images for GitHub statistics."""

import asyncio
import logging
import os

import aiohttp

from gst.helpers import generate_languages, generate_overview
from gst.stats import Stats

logger = logging.getLogger(__name__)


async def main() -> None:
    """Generate all badges.

    Raises:
        ValueError: If ACCESS_TOKEN is not set in the environment.
    """
    access_token = os.getenv("ACCESS_TOKEN")
    if not access_token:
        raise ValueError("A personal access token is required to proceed!")
    user = os.getenv("GITHUB_ACTOR", "")
    env_exclude_repos = os.getenv("EXCLUDED", "")
    exclude_repos = (
        {x.strip() for x in env_exclude_repos.split(",")} if env_exclude_repos else None
    )
    env_exclude_langs = os.getenv("EXCLUDED_LANGS", "")
    exclude_langs = (
        {x.strip() for x in env_exclude_langs.split(",")} if env_exclude_langs else None
    )
    consider_forked_repos = len(os.getenv("COUNT_STATS_FROM_FORKS", "")) != 0

    logger.info(
        "Starting badge generation...\n"
        f"User: {user}\n"
        f"Exclude repos: {exclude_repos}\n"
        f"Exclude languages: {exclude_langs}\n"
        f"Consider forked repos: {consider_forked_repos}\n"
    )
    async with aiohttp.ClientSession() as session:
        s = Stats(
            user,
            access_token,
            session,
            exclude_repos=exclude_repos,
            exclude_langs=exclude_langs,
            consider_forked_repos=consider_forked_repos,
        )
        await asyncio.gather(generate_languages(s), generate_overview(s))
    logger.info("Badge generation completed.")


if __name__ == "__main__":
    asyncio.run(main())

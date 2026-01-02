# SPDX-FileCopyrightText: 2024 Rahul Jha
# SPDX-FileCopyrightText: 2026 Johann Christensen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Module to retrieve and store statistics about GitHub usage."""

import logging

import aiohttp

from gst.queries import Queries

logger = logging.getLogger(__name__)


class Stats:
    """Retrieve and store statistics about GitHub usage."""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        username: str,
        access_token: str,
        session: aiohttp.ClientSession,
        exclude_repos: set | None = None,
        exclude_langs: set | None = None,
        consider_forked_repos: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        self.username = username
        self._exclude_repos = set() if exclude_repos is None else exclude_repos
        self._exclude_langs = set() if exclude_langs is None else exclude_langs
        self._consider_forked_repos = consider_forked_repos
        self.queries = Queries(username, access_token, session)

        self._name: str | None = None
        self._stargazers: int | None = None
        self._forks: int | None = None
        self._total_contributions: int | None = None
        self._languages: dict | None = None
        self._repos: set[str] | None = None
        self._lines_changed: tuple[int, int] | None = None
        self._views: int | None = None

    async def to_str(self) -> str:
        """Convert statistics to a formatted string.

        Returns:
            str: summary of all available statistics
        """
        languages = await self.languages_proportional
        formatted_languages = "\n  - ".join([
            f"{k}: {v:0.4f}%" for k, v in languages.items()
        ])
        lines_changed = await self.lines_changed
        # editorconfig-checker-disable
        return f"""Name: {await self.name}
Stargazers: {await self.stargazers:,}
Forks: {await self.forks:,}
All-time contributions: {await self.total_contributions:,}
Repositories with contributions: {len(await self.all_repos)}
Lines of code added: {lines_changed[0]:,}
Lines of code deleted: {lines_changed[1]:,}
Lines of code changed: {lines_changed[0] + lines_changed[1]:,}
Project page views: {await self.views:,}
Languages:
  - {formatted_languages}"""

    # editorconfig-checker-enable

    async def get_stats(self) -> None:  # noqa: C901, PLR0912
        """Get lots of summary statistics using one big query.

        Sets many attributes.
        """
        self._stargazers = 0
        self._forks = 0
        self._languages = {}
        self._repos = set()
        self._ignored_repos: set[str] = set()

        next_owned = None
        next_contrib = None
        while True:
            raw_results = await self.queries.query(
                Queries.repos_overview(
                    owned_cursor=next_owned, contrib_cursor=next_contrib
                )
            )
            raw_results = raw_results if raw_results is not None else {}
            logger.info(f"Raw results from repos overview query:\n{raw_results}")

            self._name = raw_results.get("data", {}).get("viewer", {}).get("name", None)
            if self._name is None:
                self._name = (
                    raw_results
                    .get("data", {})
                    .get("viewer", {})
                    .get("login", "No Name")
                )

            contrib_repos = (
                raw_results
                .get("data", {})
                .get("viewer", {})
                .get("repositoriesContributedTo", {})
            )
            owned_repos = (
                raw_results.get("data", {}).get("viewer", {}).get("repositories", {})
            )

            repos = owned_repos.get("nodes", [])
            if self._consider_forked_repos:
                repos += contrib_repos.get("nodes", [])
            else:
                for repo in contrib_repos.get("nodes", []):
                    name = repo.get("nameWithOwner")
                    if name in self._ignored_repos or name in self._exclude_repos:
                        continue
                    self._ignored_repos.add(name)

            for repo in repos:
                name = repo.get("nameWithOwner")
                if name in self._repos or name in self._exclude_repos:
                    continue
                self._repos.add(name)
                self._stargazers += repo.get("stargazers").get("totalCount", 0)
                self._forks += repo.get("forkCount", 0)

                for lang in repo.get("languages", {}).get("edges", []):
                    name = lang.get("node", {}).get("name", "Other")
                    languages = await self.languages
                    if name in self._exclude_langs:
                        continue
                    if name in languages:
                        languages[name]["size"] += lang.get("size", 0)
                        languages[name]["occurrences"] += 1
                    else:
                        languages[name] = {
                            "size": lang.get("size", 0),
                            "occurrences": 1,
                            "color": lang.get("node", {}).get("color"),
                        }

            if owned_repos.get("pageInfo", {}).get(
                "hasNextPage", False
            ) or contrib_repos.get("pageInfo", {}).get("hasNextPage", False):
                next_owned = owned_repos.get("pageInfo", {}).get(
                    "endCursor", next_owned
                )
                next_contrib = contrib_repos.get("pageInfo", {}).get(
                    "endCursor", next_contrib
                )
            else:
                break

        # TODO: Improve languages to scale by number of contributions to
        #       specific filetypes
        langs_total = sum(v.get("size", 0) for v in self._languages.values())
        for v in self._languages.values():
            v["prop"] = 100 * (v.get("size", 0) / langs_total)

    @property
    async def name(self) -> str:
        """Name of the user.

        Returns:
            str: GitHub user's name (e.g., "John Doe")
        """
        if self._name is not None:
            return self._name
        await self.get_stats()
        assert self._name is not None
        return self._name

    @property
    async def stargazers(self) -> int:
        """Total number of stargazers on user's repos.

        Returns:
            int: total number of stargazers on user's repos
        """
        if self._stargazers is not None:
            return self._stargazers
        await self.get_stats()
        assert self._stargazers is not None
        return self._stargazers

    @property
    async def forks(self) -> int:
        """Forks on user's repos.

        Returns:
            int: total number of forks on user's repos
        """
        if self._forks is not None:
            return self._forks
        await self.get_stats()
        assert self._forks is not None
        return self._forks

    @property
    async def languages(self) -> dict:
        """Languages used by the user.

        Returns:
            dict: summary of languages used by the user
        """
        if self._languages is not None:
            return self._languages
        await self.get_stats()
        assert self._languages is not None
        return self._languages

    @property
    async def languages_proportional(self) -> dict:
        """Languages used by the user with proportional usage.

        Returns:
            dict: summary of languages used by the user, with
                proportional usage
        """
        if self._languages is None:
            await self.get_stats()
            assert self._languages is not None

        return {k: v.get("prop", 0) for (k, v) in self._languages.items()}

    @property
    async def repos(self) -> set[str]:
        """Repos owned by the user.

        Returns:
            set[str]: set of names of user's repos
        """
        if self._repos is not None:
            return self._repos
        await self.get_stats()
        assert self._repos is not None
        return self._repos

    @property
    async def all_repos(self) -> set[str]:
        """All repos owned or contributed to by the user.

        Returns:
            set[str]: set of names of user's repos with contributed
            repos included irrespective of whether the ignore flag is
            set or not.
        """
        if self._repos is not None and self._ignored_repos is not None:
            return self._repos | self._ignored_repos
        await self.get_stats()
        assert self._repos is not None
        assert self._ignored_repos is not None
        return self._repos | self._ignored_repos

    @property
    async def total_contributions(self) -> int:
        """Total contributions of the user.

        Returns:
            int: count of user's total contributions as defined by
            GitHub
        """
        if self._total_contributions is not None:
            return self._total_contributions

        self._total_contributions = 0
        years = (
            (await self.queries.query(Queries.contrib_years()))
            .get("data", {})
            .get("viewer", {})
            .get("contributionsCollection", {})
            .get("contributionYears", [])
        )
        by_year = (
            (await self.queries.query(Queries.all_contribs(years)))
            .get("data", {})
            .get("viewer", {})
            .values()
        )
        for year in by_year:
            self._total_contributions += year.get("contributionCalendar", {}).get(
                "totalContributions", 0
            )
        return self._total_contributions

    @property
    async def lines_changed(self) -> tuple[int, int]:
        """Total lines changed by the user.

        Returns:
            tuple[int, int]: count of total lines added, removed, or
                modified by the user
        """
        if self._lines_changed is not None:
            return self._lines_changed
        additions = 0
        deletions = 0
        for repo in await self.all_repos:
            r = await self.queries.query_rest(f"/repos/{repo}/stats/contributors")
            for author_obj in r:
                # Handle malformed response from the API by skipping
                # this repo
                if not isinstance(author_obj, dict) or not isinstance(
                    author_obj.get("author", {}), dict
                ):
                    continue
                author = author_obj.get("author", {}).get("login", "")
                if author != self.username:
                    continue

                for week in author_obj.get("weeks", []):
                    additions += week.get("a", 0)
                    deletions += week.get("d", 0)

        self._lines_changed = (additions, deletions)
        return self._lines_changed

    @property
    async def views(self) -> int:
        """View count.

        Note: only returns views for the last 14 days (as-per GitHub
        API)

        Returns:
            int: total number of page views the user's projects have
                received.
        """
        if self._views is not None:
            return self._views

        total = 0
        for repo in await self.repos:
            r = await self.queries.query_rest(f"/repos/{repo}/traffic/views")
            for view in r.get("views", []):
                total += view.get("count", 0)

        self._views = total
        return total

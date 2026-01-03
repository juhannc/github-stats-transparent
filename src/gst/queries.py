# SPDX-FileCopyrightText: 2024 Rahul Jha
# SPDX-FileCopyrightText: 2026 Johann Christensen
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Module to handle GitHub API queries."""

import asyncio
import logging

import aiohttp
import requests

HTTP_OK = 200
HTTP_ACCEPTED = 202

logger = logging.getLogger(__name__)


class Queries:
    """Class to handle GitHub API queries.

    Class with functions to query the GitHub GraphQL (v4) API and the
    REST (v3) API. Also includes functions to dynamically generate
    GraphQL queries.
    """

    def __init__(
        self,
        username: str,
        access_token: str,
        session: aiohttp.ClientSession,
        max_connections: int = 10,
    ) -> None:
        self.username = username
        self.access_token = access_token
        self.session = session
        self.semaphore = asyncio.Semaphore(max_connections)

    async def query(self, generated_query: str) -> dict:
        """Make a request to the GraphQL API.

        The request is made using the authentication token from the
        environment.

        Args:
            generated_query (str): GraphQL query to be sent to the API

        Returns:
            dict: deserialized GraphQL JSON output.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        try:
            async with self.semaphore:
                logger.info(f"Making GraphQL request for query: {generated_query}")
                rcm = await self.session.post(
                    "https://api.github.com/graphql",
                    headers=headers,
                    json={"query": generated_query},
                )
            return await rcm.json()
        except:  # noqa: E722
            logger.warning("aiohttp failed for GraphQL query")
            # Fall back on non-async requests
            async with self.semaphore:
                logger.warning("Falling back to making GraphQL request with requests")
                logger.info(
                    "Making GraphQL request (using requests) for query: "
                    f"{generated_query}"
                )
                rr = requests.post(  # noqa: ASYNC210, S113
                    "https://api.github.com/graphql",
                    headers=headers,
                    json={"query": generated_query},
                )
                return rr.json()

    async def query_rest(self, path: str, params: dict | None = None) -> dict:
        """Make a request to the REST API.

        Args:
            path (str): API path to query
            params (dict | None): Query parameters to be passed to the
                API

        Returns:
            dict: deserialized REST JSON output.
        """
        for _ in range(60):
            headers = {
                "Authorization": f"token {self.access_token}",
            }
            if params is None:
                params = {}
            path = path.removeprefix("/")
            try:
                async with self.semaphore:
                    logger.info(f"Making REST request to {path} with params {params}")
                    rcm = await self.session.get(
                        f"https://api.github.com/{path}",
                        headers=headers,
                        params=tuple(params.items()),
                    )
                if rcm.status == HTTP_ACCEPTED:
                    logger.warning(f"{path} returned 202 ACCEPTED. Retrying...")
                    await asyncio.sleep(2)
                    continue

                result = await rcm.json()
                if result is not None:
                    logger.info(f"REST request to {path} successful.")
                    return result
            except:  # noqa: E722
                logger.warning("aiohttp failed for rest query")
                # Fall back on non-async requests
                async with self.semaphore:
                    logger.info(
                        f"Falling back to making REST request with requests to {path} "
                        f"with params {params}"
                    )
                    rr = requests.get(  # noqa: ASYNC210, S113
                        f"https://api.github.com/{path}",
                        headers=headers,
                        params=tuple(params.items()),
                    )
                    if rr.status_code == HTTP_ACCEPTED:
                        logger.warning(f"{path} returned 202 ACCEPTED. Retrying...")
                        await asyncio.sleep(2)
                        continue
                    if rr.status_code == HTTP_OK:
                        logger.info(
                            f"REST request to {path} successful."
                            f"Returning result:\n{rr.json()}"
                        )
                        return rr.json()
        logger.error(
            f"Too many 202 ACCEPTED responses for {path}. Giving up. "
            "Data for this repository will be incomplete."
        )
        return {}

    @staticmethod
    def repos_overview(
        contrib_cursor: str | None = None, owned_cursor: str | None = None
    ) -> str:
        """Create a GraphQL query to get overview of user repositories.

        Args:
            contrib_cursor (str | None): Cursor for paginating through
                contributed repositories
            owned_cursor (str | None): Cursor for paginating through
                owned repositories

        Returns:
            str: GraphQL query with overview of user repositories
        """
        return f"""{{
            viewer {{
                login,
                name,
                repositories(
                    first: 100,
                    orderBy: {{
                        field: UPDATED_AT,
                        direction: DESC
                    }},
                    isFork: false,
                    after: {"null" if owned_cursor is None else '"' + owned_cursor + '"'}
                ) {{
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    nameWithOwner
                    stargazers {{
                        totalCount
                    }}
                    forkCount
                    languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                        edges {{
                            size
                            node {{
                                name
                                color
                                }}
                            }}
                        }}
                    }}
                }}
                repositoriesContributedTo(
                    first: 100,
                    includeUserRepositories: false,
                    orderBy: {{
                        field: UPDATED_AT,
                        direction: DESC
                    }},
                    contributionTypes: [
                        COMMIT,
                        PULL_REQUEST,
                        REPOSITORY,
                        PULL_REQUEST_REVIEW
                    ]
                    after: {"null" if contrib_cursor is None else '"' + contrib_cursor + '"'}
                ) {{
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
                nodes {{
                    nameWithOwner
                    stargazers {{
                        totalCount
                    }}
                    forkCount
                    languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                        edges {{
                            size
                            node {{
                                name
                                color
                            }}
                        }}
                    }}
                    }}
                }}
                }}
            }}
        """  # noqa: E501

    @staticmethod
    def contrib_years() -> str:
        """Get all years the user has been a contributor.

        Returns:
            str: GraphQL query to get all years the user has been a
                contributor
        """
        return """
            query {
                viewer {
                    contributionsCollection {
                    contributionYears
                    }
                }
            }
        """

    @staticmethod
    def contribs_by_year(year: str) -> str:
        """GraphQL query template for contributions for a given year.

        Args:
            year (str): year to query for

        Returns:
            str: portion of a GraphQL query with desired info for a
            given year
        """
        return f"""
            year{year}: contributionsCollection(
                from: "{year}-01-01T00:00:00Z",
                to: "{int(year) + 1}-01-01T00:00:00Z"
            ) {{
            contributionCalendar {{
                totalContributions
            }}
            }}
        """

    @classmethod
    def all_contribs(cls, years: list[str]) -> str:
        """GraphQL query to get contributions for all user years.

        Args:
            years (list[str]): list of years to get contributions for

        Returns:
            str: query to retrieve contribution information for all user
                years
        """
        by_years = "\n".join(map(cls.contribs_by_year, years))
        return f"""
            query {{
                viewer {{
                    {by_years}
                }}
            }}
        """

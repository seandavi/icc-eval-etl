import asyncio
import logging
import os

import httpx
from tenacity import (
    retry,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from icc_eval_etl.models.github import GitHubRepo

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
RESULTS_PER_PAGE = 100


def _should_retry(response: httpx.Response) -> bool:
    return response.status_code in (403, 429) or response.status_code >= 500


def _raise_last_response(retry_state) -> None:
    """On retry exhaustion, raise the HTTP status error from the last response."""
    response = retry_state.outcome.result()
    response.raise_for_status()


class GitHubClient:
    """Async GitHub client for searching repositories by topic."""

    def __init__(self):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.info("GitHub client: using authenticated requests")
        else:
            logger.warning(
                "GitHub client: no GITHUB_TOKEN set, using unauthenticated requests "
                "(10 req/min limit)"
            )
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=headers,
            timeout=60.0,
        )

    @retry(
        retry=retry_if_result(_should_retry),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=120),
        retry_error_callback=_raise_last_response,
        before_sleep=lambda retry_state: logger.warning(
            "GitHub API returned %d, retrying in %.1fs (attempt %d)",
            retry_state.outcome.result().status_code,
            retry_state.next_action.sleep,
            retry_state.attempt_number,
        ),
    )
    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = await self._client.request(method, path, **kwargs)
        if _should_retry(response):
            # Check for Retry-After header on rate limit responses
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                wait = int(retry_after)
                logger.info("GitHub rate limited, waiting %ds (Retry-After)", wait)
                await asyncio.sleep(wait)
            return response  # tenacity will check _should_retry and retry
        response.raise_for_status()
        return response

    async def search_repos_by_topic(self, topic: str) -> list[GitHubRepo]:
        """Search GitHub for repositories tagged with the given topic."""
        repos: list[GitHubRepo] = []
        page = 1

        while True:
            response = await self._request(
                "GET",
                "/search/repositories",
                params={
                    "q": f"topic:{topic}",
                    "per_page": RESULTS_PER_PAGE,
                    "page": page,
                },
            )
            data = response.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                repos.append(GitHubRepo.model_validate(item))

            total_count = data.get("total_count", 0)
            logger.debug(
                "GitHub search topic=%s page=%d, got %d items (total=%d)",
                topic, page, len(items), total_count,
            )

            if len(repos) >= total_count or len(items) < RESULTS_PER_PAGE:
                break
            page += 1

        return repos

    async def fetch_repos(self, core_project_ids: list[str]) -> list[GitHubRepo]:
        """Search repos for each core project ID as a topic, deduplicate by repo id."""
        repos_by_id: dict[int, GitHubRepo] = {}

        for project_id in core_project_ids:
            topic = project_id.lower()
            logger.info("GitHub: searching repos with topic '%s'", topic)
            try:
                results = await self.search_repos_by_topic(topic)
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "GitHub: failed to search topic '%s' (HTTP %d), skipping",
                    topic, exc.response.status_code,
                )
                continue
            logger.info(
                "GitHub: found %d repos for topic '%s'", len(results), topic,
            )

            for repo in results:
                if repo.id in repos_by_id:
                    # Merge core_project_ids
                    existing = repos_by_id[repo.id]
                    if project_id not in existing.core_project_ids:
                        existing.core_project_ids.append(project_id)
                else:
                    repo.core_project_ids = [project_id]
                    repos_by_id[repo.id] = repo

        return list(repos_by_id.values())

    async def close(self) -> None:
        await self._client.aclose()

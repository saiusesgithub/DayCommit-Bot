import base64
import logging
from datetime import datetime

import httpx

from config import GITHUB_BRANCH, GITHUB_OWNER, GITHUB_REPO, GITHUB_TOKEN
from database import get_connection

logger = logging.getLogger(__name__)

_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _auth_headers() -> dict:
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN is not set in .env — cannot push to GitHub."
        )
    return {**_HEADERS, "Authorization": f"Bearer {GITHUB_TOKEN}"}


def _validate_repo_config() -> None:
    missing = []
    if not GITHUB_OWNER:
        missing.append("GITHUB_OWNER")
    if not GITHUB_REPO:
        missing.append("GITHUB_REPO")
    if not GITHUB_BRANCH:
        missing.append("GITHUB_BRANCH")

    if missing:
        raise RuntimeError(
            f"{', '.join(missing)} must be set in .env before using /push."
        )


def _file_path(date_str: str) -> str:
    """Return the repo-relative file path for a given date string (YYYY-MM-DD).
    Example: 2026/05-May/2026-05-25.md
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    month_folder = dt.strftime("%m-%B")  # e.g. "05-May"
    return f"{dt.year}/{month_folder}/{date_str}.md"


async def push_devlog(user_id: int, date_str: str, markdown: str) -> dict:
    """Push the DevLog markdown to GitHub and record the result in the DB.

    Returns a dict with keys: sha, url, path, action ('created' or 'updated').
    Raises RuntimeError for known config/auth/permission issues.
    """
    headers = _auth_headers()
    _validate_repo_config()
    file_path = _file_path(date_str)
    content_b64 = base64.b64encode(markdown.encode("utf-8")).decode("ascii")
    api_url = f"{_API}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{file_path}"

    async with httpx.AsyncClient(timeout=20) as client:
        # Check whether the file already exists to get its SHA.
        check = await client.get(api_url, headers=headers, params={"ref": GITHUB_BRANCH})

        if check.status_code == 401:
            raise RuntimeError("GitHub auth failed — check GITHUB_TOKEN.")
        if check.status_code == 403:
            raise RuntimeError("GitHub permission denied — check token scopes (needs repo write).")
        if check.status_code not in (200, 404):
            raise RuntimeError(f"GitHub API error {check.status_code}: {check.text[:200]}")

        existing_sha = check.json().get("sha") if check.status_code == 200 else None
        action = "updated" if existing_sha else "created"
        commit_message = f"{'Update' if existing_sha else 'Add'} devlog for {date_str}"

        body: dict = {
            "message": commit_message,
            "content": content_b64,
            "branch": GITHUB_BRANCH,
        }
        if existing_sha:
            body["sha"] = existing_sha

        resp = await client.put(api_url, headers=headers, json=body)

        if resp.status_code == 401:
            raise RuntimeError("GitHub auth failed — check GITHUB_TOKEN.")
        if resp.status_code == 403:
            raise RuntimeError("GitHub permission denied — check token scopes.")
        if resp.status_code == 404:
            raise RuntimeError(
                f"Repo not found: {GITHUB_OWNER}/{GITHUB_REPO}. "
                "Check GITHUB_OWNER and GITHUB_REPO in .env."
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"GitHub API error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        commit_sha = data["commit"]["sha"]
        file_url = data["content"]["html_url"]

    _record_push(user_id, date_str, file_path, commit_sha)

    return {"sha": commit_sha, "url": file_url, "path": file_path, "action": action}


def _record_push(user_id: int, date_str: str, file_path: str, commit_sha: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO github_pushes
                (telegram_user_id, entry_date, file_path, commit_sha, pushed_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT (telegram_user_id, entry_date)
            DO UPDATE SET file_path  = excluded.file_path,
                          commit_sha = excluded.commit_sha,
                          pushed_at  = excluded.pushed_at
            """,
            (user_id, date_str, file_path, commit_sha),
        )
        conn.commit()

"""Check the whole history before the repository is made public (or before any release).

Usage (from the repository root):
    uv run python tools/prepublish.py

Making a repository public publishes every version of every file ever committed, not only the
latest. This scans all of them for things that must never be published: credentials and keys,
private contact details, homework answers, and data files that belong on Zenodo instead. It exits
with an error if anything is found, and lists where.
"""

from __future__ import annotations

import re
import subprocess
import sys

# what must never appear in any committed version of any file
FORBIDDEN = {
    "a password or secret": r"(?i)\b(password|passwd|secret)\s*[:=]\s*\S{6,}",
    "an API key or token": r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*\S{8,}",
    "a GitHub token": r"\b(ghp_|github_pat_)[A-Za-z0-9_]{20,}",
    "a private key": r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----",
    "WordPress credentials": r"WP_AUTH\s*=\s*\S+",
    "a university email or ID": r"(?i)@student\.gla\.ac\.uk|\b\d{7}[A-Z]@",
    "a phone number": r"\+44\s?\d{3,4}\s?\d{3}\s?\d{3,4}|\+234\s?\d{3}\s?\d{3}\s?\d{4}",
    "homework answers": r"(?i)^#+\s*(answer key|answers?)\b",
}
# files that must never be committed, by name
FORBIDDEN_FILES = (
    r"(?i)(answers?|answer[-_]key|solutions?)\.(md|py|ipynb|json)$"  # homework answers
    r"|\.env$"  # local settings with credentials
    r"|\.(sdf|smi|parquet)(\.gz)?$"  # data files: these go on Zenodo or a release
)
TOO_LARGE = 5_000_000  # bytes; data belongs on Zenodo or a release, not in git


def git(*args: str) -> str:
    """Run git and return what it prints.

    Args:
        *args: The git arguments.

    Returns:
        Its standard output.
    """
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True).stdout  # fmt: skip


def findings() -> list[str]:
    """Everything in the history that must not be published.

    Returns:
        One line per finding, naming the commit and the problem.
    """
    found = []
    for commit in git("rev-list", "--all").split():
        diff = git("show", "--format=", "--unified=0", commit)
        for line in diff.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            for what, pattern in FORBIDDEN.items():
                if re.search(pattern, line[1:], re.M):
                    found.append(f"{commit[:8]}: {what}: {line[1:80].strip()}")
    for line in git("rev-list", "--objects", "--all").splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and re.search(FORBIDDEN_FILES, parts[1]):
            found.append(f"a file that must not be committed: {parts[1]}")
    for line in git("rev-list", "--objects", "--all").splitlines():
        sha, _, path = line.partition(" ")
        if path and git("cat-file", "-t", sha).strip() == "blob":
            size = int(git("cat-file", "-s", sha))
            if size > TOO_LARGE:
                found.append(f"a large file ({size / 1e6:.1f} MB): {path}")
    return sorted(set(found))


def main() -> None:
    """Scan the history and report."""
    found = findings()
    commits = len(git("rev-list", "--all").split())
    if found:
        print(f"Not ready to publish: {len(found)} finding(s) in {commits} commits.")
        print("\n".join(f"  {f}" for f in found))
        sys.exit(1)
    print(f"Ready to publish: nothing found in {commits} commits.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Hourly GitHub issue intake for abaddon/logos.

One run reads the open issues and creates at most two Hermes Kanban tasks on the
``logos`` board, one per picked issue, restricted to issues that can be worked
independently. The normative specification is ``docs/pipelines/issue-intake/``;
the names below (``new``, ``ready``, ``independent``, ``umbrella``, ``subsystem``)
are its section 3.1 vocabulary, so a reviewer can read the code and the spec
side by side.

    python3 tools/issue_intake.py --once                 # the cron path
    python3 tools/issue_intake.py --once --dry-run       # decide, print, write nothing
    python3 tools/issue_intake.py --once --include-backlog
    python3 tools/issue_intake.py --forget 52

Exit codes: 0 ran (including clean no-ops), 65 unrecoverable input, 75 transient.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# --- config: 06-config.md §6.2 -------------------------------------------------

REPO = os.environ.get("LOGOS_INTAKE_REPO", "abaddon/logos")
API_BASE = os.environ.get("LOGOS_INTAKE_API", "https://api.github.com")
TOKEN_ENV = "GITHUB_TOKEN"                      # the variable's name, never a value
BOARD = os.environ.get("LOGOS_INTAKE_BOARD", "logos")
REPO_ROOT = os.environ.get("LOGOS_INTAKE_REPO_ROOT", "/root/ai-language-program")
STATE_PATH = os.environ.get("LOGOS_INTAKE_STATE",
                            "~/.local/state/logos-issue-intake/state.json")
HERMES_BIN = os.environ.get("LOGOS_INTAKE_HERMES", "hermes")
MAX_PICKS = int(os.environ.get("LOGOS_INTAKE_MAX_PICKS", "2"))

PER_PAGE = 100
MAX_PAGES = 10
MAX_BODY_CHARS = 6000
MAX_TITLE_CHARS = 120
UMBRELLA_MAX_REFS = 8
HTTP_TIMEOUT = 30          # seconds; urllib has one socket timeout, not connect+read
FETCH_BUDGET_S = 90        # whole fetch phase, so a hung page set cannot hold the lock
CLI_TIMEOUT = 60
LOCK_STALE_S = 600

DEFAULT_ASSIGNEE = "backend-engineer"
LABEL_ASSIGNEE = {
    "docs": "oss-contributor",
    "documentation": "oss-contributor",
    "good first issue": "oss-contributor",
}
EXCLUDED_LABELS = {"question", "needs-info", "invalid", "wontfix",
                   "duplicate", "superseded", "in-progress"}
SUBSYSTEM_LABELS = {"compiler": "compiler", "runtime": "runtime", "docs": "docs",
                    "documentation": "docs", "target": "target",
                    "accessibility": "accessibility", "tooling": "tooling"}
SUBSYSTEM_PREFIX = {
    "docs": "docs", "documentation": "docs", "manual": "docs",
    "compiler": "compiler", "language": "compiler",
    "stdlib": "stdlib", "tooling": "tooling",
    "examples": "examples", "target": "target",
}
STRUCTURAL_PHRASES = ("blocked by", "depends on", "sequenced after", "part of",
                      "sub-issue of", "subissue of", "parent:", "follow-up to",
                      "followup to", "tracking issue for")
STRUCTURAL_RE = re.compile("|".join(re.escape(p) for p in STRUCTURAL_PHRASES),
                           re.IGNORECASE)
UMBRELLA_RE = re.compile(r"(?i)\b(tracking issue|index of|master list|umbrella)\b")
DONE_RE = re.compile(r"(?i)^\*\*done when")
ACCEPT_STOP_RE = re.compile(r"^(\*\*[A-Z]|## |---)")
TASK_ITEM_RE = re.compile(r"^\s*[-*] \[[ x]\]")
ACCEPT_HEAD_RE = re.compile(r"(?i)^(#+\s*|\*\*)(acceptance|definition of done|done\b)")
HEADING_RE = re.compile(r"^#{1,6}\s")

FALLBACK_DONE = (
    "No explicit definition of done in the issue. Derive it from the description\n"
    "above, state it in the first commit message, and verify it with\n"
    "`bash tools/pr_gate.sh`."
)


class Fatal(Exception):
    """A run-ending problem: ``code`` is the process exit status."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# --- small helpers -------------------------------------------------------------

def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value):
    """GitHub ISO-8601 (``...Z``) to an aware datetime; naive values are UTC."""
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def label_names(issue):
    names = []
    for label in issue.get("labels") or []:
        names.append(label["name"] if isinstance(label, dict) else label)
    return names


def max_picks():
    value = MAX_PICKS
    clamped = max(0, min(5, value))
    if clamped != value:
        print(f"WARN max-picks clamped value={value} used={clamped}")
    return clamped


# --- selection: 03-selection.md §3.1 ------------------------------------------

def refs(issue):
    text = (issue.get("title") or "") + "\n" + (issue.get("body") or "")
    return {int(n) for n in re.findall(r"#(\d+)", text)} - {issue["number"]}


def structural_refs(issue):
    found = set()
    for line in (issue.get("body") or "").splitlines():
        if STRUCTURAL_RE.search(line):
            found |= {int(n) for n in re.findall(r"#(\d+)", line)}
    return found - {issue["number"]}


def blocked(issue, open_numbers):
    return bool(structural_refs(issue) & open_numbers)


def umbrella(issue, open_numbers):
    if len(refs(issue) & open_numbers) >= UMBRELLA_MAX_REFS:
        return True
    heads = [issue.get("title") or ""]
    for line in (issue.get("body") or "").splitlines():
        if line.strip():
            heads.append(line)
            break
    return any(UMBRELLA_RE.search(head) for head in heads)


def subsystem(issue):
    title = issue.get("title") or ""
    prefix = title.split(":", 1)[0].strip().lower() if ":" in title else ""
    if prefix in SUBSYSTEM_PREFIX:
        return {SUBSYSTEM_PREFIX[prefix]}
    from_labels = {SUBSYSTEM_LABELS[name] for name in label_names(issue)
                   if name in SUBSYSTEM_LABELS}
    return from_labels or {"unclassified"}


def not_ready_reason(issue, open_numbers):
    """The ``skip_reason`` clause that keeps a new issue out of the candidate set."""
    if set(label_names(issue)) & EXCLUDED_LABELS:
        return "excluded-label"
    if blocked(issue, open_numbers):
        return "blocked"
    if umbrella(issue, open_numbers):
        return "umbrella"
    return None


def is_new(issue, state_issues, backlog_cutoff, include_backlog):
    if issue.get("state") != "open" or "pull_request" in issue:
        return False
    entry = state_issues.get(str(issue["number"])) or {}
    if entry.get("outcome") == "picked":
        return False
    # `seeded` is the bootstrap's audit record, not a permanent veto: the
    # operator's --include-backlog drain waives it (03-selection.md §3.1).
    if entry.get("outcome") == "seeded" and not include_backlog:
        return False
    if include_backlog or not backlog_cutoff:
        return True
    return parse_ts(issue["created_at"]) > parse_ts(backlog_cutoff)


def mutual_ref(a, b):
    return b["number"] in refs(a) or a["number"] in refs(b)


def independent(a, b):
    return not mutual_ref(a, b) and not (subsystem(a) & subsystem(b))


def select(issues, state_issues, backlog_cutoff, include_backlog=False,
           max_picks_value=2):
    """Apply 03-selection.md §3.4. Returns counters, picked objects, skip ledger."""
    open_numbers = {i["number"] for i in issues if "pull_request" not in i}
    prs = sum(1 for i in issues if "pull_request" in i)

    unseen = [i for i in issues
              if is_new(i, state_issues, backlog_cutoff, include_backlog)]
    candidates = [i for i in unseen if not_ready_reason(i, open_numbers) is None]
    candidates.sort(key=lambda i: (parse_ts(i["created_at"]), i["number"]))

    picked = []
    skipped = {}
    for issue in unseen:
        reason = not_ready_reason(issue, open_numbers)
        if reason:
            skipped[str(issue["number"])] = reason
    for issue in candidates:
        if len(picked) >= max_picks_value:
            skipped[str(issue["number"])] = "cap"
            continue
        conflict = next((p for p in picked if not independent(issue, p)), None)
        if conflict is None:
            picked.append(issue)
        else:
            skipped[str(issue["number"])] = (
                "cross-reference" if mutual_ref(issue, conflict) else "subsystem-collision")

    return {
        "fetched": len(issues),
        "prs_skipped": prs,
        "unseen": len(unseen),
        "ready": len(candidates),
        "picked": picked,
        "picked_numbers": [i["number"] for i in picked],
        "skipped": skipped,
        "unseen_issues": unseen,
        "open_numbers": open_numbers,
    }


# --- state: 02-state.md -------------------------------------------------------

def load_state(path):
    """``None`` for a first run; Fatal(65) for a file we must not silently reset."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        corrupt = f"{path}.corrupt-{int(time.time())}"
        os.replace(path, corrupt)
        raise Fatal(65, f"state-corrupt path={corrupt} error={exc.msg}")
    if state.get("version") != 1:
        raise Fatal(65, f"state-corrupt path={path} error=version-{state.get('version')}")
    state.setdefault("issues", {})
    state.setdefault("last_etag", None)
    state.setdefault("last_run_at", None)
    state.setdefault("last_run", {"fetched": 0, "prs_skipped": 0, "unseen": 0,
                                  "ready": 0, "picked": 0, "created": 0, "failed": 0})
    return state


def atomic_write(path, state):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    handle = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        json.dump(state, out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def new_state(run_start):
    return {
        "version": 1,
        "repo": REPO,
        "board": BOARD,
        "backlog_cutoff": iso(run_start),
        "last_run_at": None,
        "last_etag": None,
        "last_run": {"fetched": 0, "prs_skipped": 0, "unseen": 0, "ready": 0,
                     "picked": 0, "created": 0, "failed": 0},
        "issues": {},
    }


def take_lock(path):
    """``None`` when the lock is ours, ``"busy"`` when a live run holds it."""
    try:
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        age = max(0, int(time.time() - os.path.getmtime(path)))
        if age < LOCK_STALE_S:
            try:
                with open(path, "r", encoding="utf-8") as held:
                    pid = held.read().strip() or "?"
            except OSError:
                pid = "?"
            print(f"ERROR locked {pid} age={age}")
            return "busy"
        print("WARN stale-lock reclaimed")
        os.unlink(path)
        return take_lock(path)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(f"pid={os.getpid()} started={iso(now())}\n")
    return None


def release_lock(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


# --- polling: 01-polling.md ---------------------------------------------------

def next_link(headers):
    for part in (headers.get("Link") or "").split(","):
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            return match.group(1) if match else None
    return None


def http_get(url, headers):
    """One GET with the retry policy of 01-polling.md. Raises Fatal on failure."""
    failure = None
    for attempt in (1, 2):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as exc:
            status = exc.code
            if status == 304:
                return 304, b"", exc.headers
            remaining = exc.headers.get("x-ratelimit-remaining")
            retry_after = exc.headers.get("retry-after")
            if status in (403, 429) and remaining == "0":
                reset = exc.headers.get("x-ratelimit-reset")
                when = iso(datetime.fromtimestamp(int(reset), timezone.utc)) if reset and reset.isdigit() else "?"
                raise Fatal(75, f"rate-limited remaining=0 reset={when}")
            if status in (403, 429) and retry_after:
                raise Fatal(75, f"secondary-limit retry-after={retry_after}")
            if status in (401, 404):
                raise Fatal(65, f"auth/repo status={status} url={url}")
            if 500 <= status < 600:
                failure = Fatal(75, f"http={status} url={url}")
            elif status in (403, 429):
                failure = Fatal(75, f"http={status} url={url}")
            else:
                raise Fatal(65, f"http={status} url={url}")
        except (urllib.error.URLError, OSError) as exc:
            failure = Fatal(75, f"http-error {type(exc).__name__} url={url}")
        if attempt == 2:
            break
    raise failure


def fetch_issues(state):
    """Returns ``(issues, prs_skipped, etag, not_modified)``."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "logos-issue-intake/1",
    }
    token = os.environ.get(TOKEN_ENV)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    etag = (state or {}).get("last_etag")
    if etag:
        headers["If-None-Match"] = etag

    url = (f"{API_BASE}/repos/{REPO}/issues"
           f"?state=open&sort=created&direction=asc&per_page={PER_PAGE}")
    issues = []
    fetched_etag = None
    pages = 0
    deadline = time.monotonic() + FETCH_BUDGET_S
    while url:
        pages += 1
        if pages > MAX_PAGES:
            raise Fatal(65, f"pagination-cap pages={MAX_PAGES}")
        if time.monotonic() > deadline:
            raise Fatal(75, f"fetch-budget exceeded budget={FETCH_BUDGET_S}s")
        status, body, response_headers = http_get(url, headers)
        if status == 304:
            return [], 0, etag, True
        fetched_etag = response_headers.get("etag") or fetched_etag
        try:
            page = json.loads(body)
        except ValueError:
            raise Fatal(75, f"http=200 body-not-json url={url}")
        if not isinstance(page, list):
            raise Fatal(75, f"http=200 body-not-list url={url}")
        issues.extend(page)
        url = next_link(response_headers)

    prs = sum(1 for issue in issues if "pull_request" in issue)
    return issues, prs, fetched_etag, False


# --- task creation: 04-task-creation.md ---------------------------------------

def task_title(issue):
    prefix = f"[logos#{issue['number']}] "
    title = issue.get("title") or ""
    room = MAX_TITLE_CHARS - len(prefix)
    if len(title) > room:
        title = title[:room - 3] + "..."
    return prefix + title


def assignee_for(issue):
    for label in label_names(issue):
        if label in LABEL_ASSIGNEE:
            return LABEL_ASSIGNEE[label]
    return DEFAULT_ASSIGNEE


def truncate(text):
    if len(text) <= MAX_BODY_CHARS:
        return text
    cut = text[:MAX_BODY_CHARS]
    if "\n" in cut:
        cut = cut.rsplit("\n", 1)[0]
    return (cut + "\n\n…[truncated: "
            f"{len(text) - len(cut)} characters omitted; read the full issue at the URL above]")


def acceptance_criteria(body):
    """04-task-creation.md §4.4, first match wins."""
    lines = (body or "").splitlines()
    for index, line in enumerate(lines):
        if DONE_RE.match(line):
            block = [line]
            for following in lines[index + 1:]:
                if ACCEPT_STOP_RE.match(following):
                    break
                block.append(following)
            return "\n".join(block).strip()
    task_list = []
    for line in lines:
        if TASK_ITEM_RE.match(line):
            task_list.append(line)
        elif task_list:
            break
    if task_list:
        return "\n".join(task_list).strip()
    for index, line in enumerate(lines):
        if ACCEPT_HEAD_RE.match(line):
            block = [line]
            for following in lines[index + 1:]:
                if HEADING_RE.match(following):
                    break
                block.append(following)
            return "\n".join(block).strip()
    return FALLBACK_DONE


BODY_TEMPLATE = """Imported from {url} by `logos-issue-intake`.

- **Issue:** {url}
- **Title:** {title}
- **Labels:** {labels}
- **Opened by:** {user} at {created_at}
- **Updated on GitHub:** {updated_at}
- **Subsystem:** {subsystem}
- **Picked by run:** {picked_at}

## Acceptance criteria (inherited from the issue)

{acceptance}

## Repository gates

This repository's definition of done is not negotiable and is not restated from
the issue: `bash tools/pr_gate.sh` must pass, every commit carries a DCO
sign-off (`git commit --signoff`), and a compiler change also rebuilds
`bootstrap/logosc` in the same pull request. Read `AGENTS.md` before starting.

## Issue body (verbatim, truncated at 6000 characters)

{body}
"""


def build_body(issue, run_start):
    url = f"https://github.com/{REPO}/issues/{issue['number']}"
    labels = ", ".join(label_names(issue)) or "(none)"
    user = (issue.get("user") or {}).get("login") or "(unknown)"
    return BODY_TEMPLATE.format(
        url=url,
        title=issue.get("title") or "",
        labels=labels,
        user=user,
        created_at=issue.get("created_at") or "",
        updated_at=issue.get("updated_at") or "",
        subsystem=",".join(sorted(subsystem(issue))),
        picked_at=iso(run_start),
        acceptance=truncate(acceptance_criteria(issue.get("body"))),
        body=truncate(issue.get("body") or ""),
    )


def create_task(issue, body_path, run_start_ts):
    """Returns ``(task_id, task_existed)`` or raises Fatal(75)."""
    number = issue["number"]
    command = [HERMES_BIN, "kanban", "--board", BOARD, "create", task_title(issue),
               "--assignee", assignee_for(issue),
               "--workspace", f"worktree:{REPO_ROOT}/.worktrees/gh-{number}",
               "--branch", f"wt/gh-{number}",
               "--idempotency-key", f"logos-issue-{number}",
               "--created-by", "logos-issue-intake",
               "--body-file", body_path,
               "--json"]
    try:
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=CLI_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Fatal(75, f"create failed issue=#{number} rc=timeout")
    if proc.returncode != 0:
        # The CLI's first stderr line is the whole diagnosis; the rest may be a
        # traceback. Bound it so a runaway line cannot flood the log.
        diagnosis = (proc.stderr or "").strip().splitlines()[:1]
        raise Fatal(75, f"create failed issue=#{number} rc={proc.returncode}"
                        + (f" err={diagnosis[0][:200]}" if diagnosis else ""))
    try:
        payload = json.loads(proc.stdout)
        task_id = payload["id"]
    except (ValueError, KeyError, TypeError):
        raise Fatal(75, f"create failed issue=#{number} rc=0 no-task-id")
    created_at = payload.get("created_at")
    existed = isinstance(created_at, (int, float)) and created_at < run_start_ts
    return task_id, existed


# --- the run ------------------------------------------------------------------

def log_line(run_start, counts, picks, skipped, edited, existing):
    fields = (f"fetched={counts['fetched']} prs={counts['prs_skipped']} "
              f"unseen={counts['unseen']} ready={counts['ready']} "
              f"picked={counts['picked']} created={counts['created']} "
              f"failed={counts['failed']}")
    if picks:
        fields += " picks=" + ",".join(f"#{n}" for n in picks)
    if skipped:
        fields += " skipped=" + ",".join(f"#{n}:{reason}"
                                         for n, reason in skipped.items())
    if edited:
        fields += " edited=" + ",".join(f"#{n}" for n in edited)
    if existing:
        fields += " existing=" + ",".join(f"#{n}" for n in existing)
    print(f"logos-issue-intake {iso(run_start)} {fields}")


def skip_detail(issue, selection):
    """Why the dry-run table shows this issue skipping — spec 06-config.md §6.3."""
    number = str(issue["number"])
    reason = selection["skipped"].get(number, "skipped")
    if reason == "blocked":
        blockers = sorted(structural_refs(issue) & selection["open_numbers"])
        return "blocked by " + ",".join(f"#{b}" for b in blockers) if blockers else reason
    if reason == "cross-reference":
        for picked in selection["picked"]:
            if mutual_ref(issue, picked):
                return f"cites #{picked['number']}"
    if reason == "subsystem-collision":
        for picked in selection["picked"]:
            if subsystem(issue) & subsystem(picked):
                return f"subsystem-collision with #{picked['number']}"
    return reason


def dry_run(state, run_start, args):
    issues, prs, _, not_modified = fetch_issues(state)
    if not_modified:
        print(f"DRY RUN  repo={REPO} not-modified unseen=0 ready=0")
        print("  create 0 (dry run, state untouched)")
        return 0
    state_issues = (state or {}).get("issues") or {}
    cutoff = (state or {}).get("backlog_cutoff") or iso(run_start)
    selection = select(issues, state_issues, cutoff,
                       args.include_backlog, max_picks())
    if state is None:
        print(f"DRY RUN  repo={REPO} open={len(issues)} would-bootstrap "
              f"seeded={len(issues)} picked=0")
        print("  create 0 (dry run, state untouched)")
        return 0
    print(f"DRY RUN  repo={REPO} open={selection['fetched']} "
          f"unseen={selection['unseen']} ready={selection['ready']}")
    picked_numbers = set(selection["picked_numbers"])
    ordered = sorted(selection["unseen_issues"],
                     key=lambda i: (parse_ts(i["created_at"]), i["number"]))
    for issue in ordered:
        if issue["number"] in picked_numbers:
            print(f"  pick   #{issue['number']:<4} {','.join(sorted(subsystem(issue))):<12} "
                  f"{assignee_for(issue):<21} {task_title(issue)}")
        else:
            print(f"  skip   #{issue['number']:<4} {','.join(sorted(subsystem(issue))):<12} "
                  f"{'—':<21} {skip_detail(issue, selection)}")
    print("  create 0 (dry run, state untouched)")
    return 0


def run_locked(state, state_path, run_start, args):
    issues, prs, etag, not_modified = fetch_issues(state)

    if state is None:
        state = new_state(run_start)
        for issue in issues:
            if "pull_request" in issue:
                continue
            state["issues"][str(issue["number"])] = {
                "outcome": "seeded",
                "first_seen_at": iso(run_start),
                "github_created_at": issue.get("created_at"),
                "github_updated_at": issue.get("updated_at"),
            }
        state["last_etag"] = etag
        state["last_run_at"] = iso(run_start)
        state["last_run"] = {"fetched": len(issues) - prs, "prs_skipped": prs,
                             "unseen": 0, "ready": 0, "picked": 0,
                             "created": 0, "failed": 0}
        atomic_write(state_path, state)
        print(f"logos-issue-intake {iso(run_start)} bootstrap "
              f"seeded={len(state['issues'])} picked=0 "
              f"backlog_cutoff={state['backlog_cutoff']}")
        return 0

    if not_modified:
        state["last_run_at"] = iso(run_start)
        state["last_run"] = {"fetched": state["last_run"].get("fetched", 0),
                             "prs_skipped": 0, "unseen": 0, "ready": 0,
                             "picked": 0, "created": 0, "failed": 0}
        atomic_write(state_path, state)
        return 0

    entries = state["issues"]
    selection = select(issues, entries, state.get("backlog_cutoff"),
                       args.include_backlog, max_picks())
    picked = selection["picked"]

    edited = []
    for issue in issues:
        if "pull_request" in issue:
            continue
        entry = entries.get(str(issue["number"]))
        if not entry or entry.get("outcome") != "picked":
            continue
        if issue.get("updated_at") and entry.get("github_updated_at") != issue["updated_at"]:
            edited.append(issue["number"])
            entry["github_updated_at"] = issue["updated_at"]

    counts = {"fetched": selection["fetched"], "prs_skipped": selection["prs_skipped"],
              "unseen": selection["unseen"], "ready": selection["ready"],
              "picked": len(picked), "created": 0, "failed": 0}
    picks, existing = [], []
    exit_code = 0
    body_dir = os.path.dirname(state_path)

    try:
        for issue in picked:
            number = issue["number"]
            previous = entries.get(str(number)) or {}
            body_path = os.path.join(body_dir, f"body-{number}.tmp")
            handle = os.open(body_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(build_body(issue, run_start))
            try:
                task_id, existed = create_task(issue, body_path,
                                               int(run_start.timestamp()))
            except Fatal as failure:
                counts["failed"] = 1
                exit_code = failure.code
                print(f"ERROR {failure.message}")
                break
            finally:
                try:
                    os.unlink(body_path)
                except FileNotFoundError:
                    pass
            entries[str(number)] = {
                "outcome": "picked",
                "first_seen_at": previous.get("first_seen_at") or iso(run_start),
                "picked_at": iso(run_start),
                "task_id": task_id,
                "github_created_at": issue.get("created_at"),
                "github_updated_at": issue.get("updated_at"),
            }
            atomic_write(state_path, state)
            picks.append(number)
            if existed:
                existing.append(number)
            else:
                counts["created"] += 1

        for key, reason in selection["skipped"].items():
            entry = entries.get(key) or {}
            outcome = entry.get("outcome")
            # A drain run records why each seeded issue still waits; a normal run
            # must not overwrite the bootstrap's audit trail (03-selection §3.3).
            if outcome == "picked":
                continue
            if outcome == "seeded" and not args.include_backlog:
                continue
            entry.setdefault("first_seen_at", iso(run_start))
            entry["outcome"] = "skipped"
            entry["skip_reason"] = reason
            issue = next(i for i in issues if str(i["number"]) == key)
            entry["github_created_at"] = issue.get("created_at")
            entry["github_updated_at"] = issue.get("updated_at")
            entries[key] = entry
    finally:
        state["last_run_at"] = iso(run_start)
        state["last_run"] = counts
        state["last_etag"] = etag or state.get("last_etag")
        atomic_write(state_path, state)

    if picks or existing or selection["skipped"] or edited or counts["failed"]:
        log_line(run_start, counts, picks, selection["skipped"], edited, existing)
    return exit_code


def run(args):
    run_start = now()
    state_path = os.path.expanduser(STATE_PATH)

    if args.forget is not None:
        state = load_state(state_path)
        if state is None:
            print(f"ERROR no state file path={state_path}")
            return 65
        if state["issues"].pop(str(args.forget), None) is None:
            print(f"ERROR no state entry issue=#{args.forget}")
            return 65
        atomic_write(state_path, state)
        print(f"forgot issue=#{args.forget}")
        return 0

    if args.dry_run:
        try:
            return dry_run(load_state(state_path), run_start, args)
        except Fatal as failure:
            print(f"ERROR {failure.message}")
            return failure.code

    os.makedirs(os.path.dirname(state_path), mode=0o700, exist_ok=True)
    lock_path = state_path + ".lock"
    if take_lock(lock_path) == "busy":
        return 0
    try:
        return run_locked(load_state(state_path), state_path, run_start, args)
    except Fatal as failure:
        print(f"ERROR {failure.message}")
        return failure.code
    finally:
        release_lock(lock_path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create at most two Hermes Kanban tasks per hour from the "
                    "open issues of abaddon/logos.")
    parser.add_argument("--once", action="store_true",
                        help="run one cycle (the cron path; there is no daemon mode)")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and decide, print the table, write nothing")
    parser.add_argument("--include-backlog", action="store_true",
                        help="ignore backlog_cutoff for this run only")
    parser.add_argument("--forget", type=int, metavar="N",
                        help="drop the state entry for issue #N and exit")
    args = parser.parse_args(argv)
    if not args.once and args.forget is None:
        parser.error("--once is required (or --forget N)")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())

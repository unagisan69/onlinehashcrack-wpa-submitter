#!/usr/bin/env python3
"""
One-shot uploader for OnlineHashCrack (OHC) v2 API.

What it does:
- Finds ALL *.hc22000 files in the current directory
- Reads all hashes (one per line), combines, de-dupes (preserving order)

On normal run (no flags):
- FIRST lists current tasks on your OHC account (action=list_tasks)
- Filters out hashes that already exist on your account (prevents duplicates)
- If > 50 NEW hashes remain, it will NOT submit and writes overflow to:
  ohc_overflow_hashes.txt
- Otherwise submits EXACTLY ONE upload request with up to 50 hashes

Flags:
- -list : lists current tasks (raw JSON printed) and exits

Fixed settings:
- agree_terms = "yes" (ALWAYS)
- algo_mode = 22000 (WPA-PBKDF2-PMKID+EAPOL)
"""

import glob
import sys
import argparse
from typing import List, Dict, Any, Optional

import requests

# ==============================
# CONFIG
# ==============================
API_KEY = "sk_XXXXXX"  # <-- put your real key here
API_URL = "https://api.onlinehashcrack.com/v2"

AGREE_TERMS = "yes"   # MUST ALWAYS BE "yes"
ALGO_MODE = 22000     # WPA-PBKDF2-PMKID+EAPOL

MAX_HASHES_PER_REQUEST = 50
OVERFLOW_FILE = "ohc_overflow_hashes.txt"
# ==============================


def read_hashes_from_files(pattern: str = "*.hc22000") -> List[str]:
    files = sorted(glob.glob(pattern))
    if not files:
        return []

    all_hashes: List[str] = []
    for fp in files:
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                h = line.strip()
                if not h or h.startswith("#"):
                    continue
                all_hashes.append(h)

    # De-dupe while preserving order
    seen = set()
    deduped: List[str] = []
    for h in all_hashes:
        if h not in seen:
            seen.add(h)
            deduped.append(h)

    return deduped


def ohc_post(payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """
    Single OHC API POST. No retries (to avoid 429 escalations).
    Returns parsed JSON (or a dict with 'text' if JSON parse fails).
    Raises requests.RequestException for network errors.
    """
    resp = requests.post(
        API_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"success": False, "text": resp.text[:4000]}
    data["_http_status"] = resp.status_code
    return data


def fetch_tasks() -> Dict[str, Any]:
    """
    Calls action=list_tasks. agree_terms is ALWAYS sent.
    Returns response JSON with _http_status included.
    """
    payload = {
        "api_key": API_KEY,
        "agree_terms": AGREE_TERMS,
        "action": "list_tasks",
    }
    return ohc_post(payload, timeout=30)


def build_existing_hash_set(tasks_resp: Dict[str, Any]) -> set:
    """
    Extracts 'hash' from each task entry and returns a set of submitted hashes.
    """
    tasks = tasks_resp.get("tasks") or []
    existing = set()
    for t in tasks:
        h = t.get("hash")
        if h:
            existing.add(h)
    return existing


def list_tasks_mode() -> int:
    print("Fetching task list from OnlineHashCrack...")
    try:
        data = fetch_tasks()
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 4

    http = data.get("_http_status", 0)
    print(f"HTTP {http}")
    # print raw JSON so you can see exactly what the API returns
    print({k: v for k, v in data.items() if k != "_http_status"})

    if http >= 400 or not data.get("success", False):
        return 3
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OnlineHashCrack one-shot uploader (duplicate-safe)")
    parser.add_argument(
        "-list",
        action="store_true",
        help="List all current tasks on the OHC account and exit",
    )
    args = parser.parse_args()

    if not API_KEY or API_KEY.strip().startswith("sk_XXX"):
        print("ERROR: Set API_KEY at the top of the script.", file=sys.stderr)
        return 2

    if AGREE_TERMS != "yes":
        print('ERROR: AGREE_TERMS must always be "yes".', file=sys.stderr)
        return 2

    if args.list:
        return list_tasks_mode()

    # 1) Read local hashes
    hashes = read_hashes_from_files("*.hc22000")
    if not hashes:
        print("No hashes found (no *.hc22000 files or files were empty).")
        return 0

    print(f"Found {len(hashes)} total unique hashes across all *.hc22000 files.")

    # 2) Fetch existing tasks once, and filter duplicates
    print("Checking OHC for already-submitted hashes (list_tasks)...")
    try:
        tasks_resp = fetch_tasks()
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 4

    http = tasks_resp.get("_http_status", 0)
    if http >= 400 or not tasks_resp.get("success", False):
        # Don't proceed to upload if we can't reliably dedupe
        msg = tasks_resp.get("message") or tasks_resp.get("text") or "Unknown error"
        print(f"ERROR: list_tasks failed (HTTP {http}): {msg}", file=sys.stderr)
        return 3

    existing_hashes = build_existing_hash_set(tasks_resp)

    new_hashes: List[str] = [h for h in hashes if h not in existing_hashes]
    skipped = len(hashes) - len(new_hashes)

    print(f"Already on OHC: {skipped} hash(es) — will skip them.")
    print(f"New to submit: {len(new_hashes)} hash(es).")

    if not new_hashes:
        print("Nothing to do — all hashes in *.hc22000 files are already submitted on this OHC account.")
        return 0

    # 3) Enforce one-call upload limit (<= 50)
    if len(new_hashes) > MAX_HASHES_PER_REQUEST:
        overflow = new_hashes[MAX_HASHES_PER_REQUEST:]

        with open(OVERFLOW_FILE, "w", encoding="utf-8") as out:
            out.write("\n".join(overflow) + "\n")

        print(
            f"More than {MAX_HASHES_PER_REQUEST} NEW hashes remain.\n"
            f"- Will NOT submit (one-call-only rule)\n"
            f"- First {MAX_HASHES_PER_REQUEST} NEW hashes are ready to submit\n"
            f"- Wrote remaining {len(overflow)} NEW hashes to: {OVERFLOW_FILE}"
        )
        return 1

    # 4) Upload exactly one request
    payload = {
        "api_key": API_KEY,
        "agree_terms": AGREE_TERMS,
        "algo_mode": ALGO_MODE,
        "hashes": new_hashes,  # <= 50 strings
    }

    print(f"Submitting ONE request with {len(new_hashes)} new hashes...")

    try:
        resp_data = ohc_post(payload, timeout=60)
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 4

    http2 = resp_data.get("_http_status", 0)
    print(f"HTTP {http2}: { {k: v for k, v in resp_data.items() if k != '_http_status'} }")

    if http2 >= 400 or not resp_data.get("success", False):
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

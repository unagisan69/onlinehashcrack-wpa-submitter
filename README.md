# OnlineHashCrack One-Shot Uploader (Duplicate-Safe)

A minimal, rate-limit-safe Python client for the OnlineHashCrack (OHC) v2 API, designed specifically for WPA/WPA2 (hc22000) hashes.

This script intentionally avoids common mistakes that lead to HTTP 429 rate-limit bans, duplicate submissions, or excessive API usage.

---

##Features

- One-shot upload: submits exactly one API request per run
- Duplicate-safe: checks existing OHC tasks and skips hashes already submitted
- Strict rate-limit discipline: no retries, no loops, no batching
- Hard cap of 50 hashes per upload (per OHC API rules)
- Order-preserving de-duplication across multiple .hc22000 files
- Read-only task listing via -list
- Always sends agree_terms = "yes" (required by OHC for all actions)

---

##What this script does not do (by design)

- No retries on HTTP 429 responses
- No automatic batching across multiple API calls
- No polling or background task monitoring
- No cracking logic (this is an API client, not a cracker)

These omissions are intentional to ensure safety, predictability, and compliance.

---

##How it works

1. Reads all *.hc22000 files in the current directory
2. Combines hashes and removes duplicates while preserving order
3. Calls action: list_tasks to retrieve hashes already on the OHC account
4. Filters out hashes that have already been submitted
5. If zero new hashes remain, exits cleanly
6. If more than 50 new hashes remain, does not submit and writes overflow to a file
7. If 50 or fewer new hashes remain, submits exactly one upload request

---

##Requirements

- Python 3.8 or newer
- requests library

Install dependency:

pip install requests

---

Configuration

Edit the following values at the top of the script:

API_KEY = "sk_XXXXXXXXXXXXXXXXXXXXXXXX"

---

Usage

List existing tasks on your OHC account:

./online-hash-cracker-upload.py -list

Upload hashes (normal mode):

./online-hash-cracker-upload.py

Behavior:

- Skips hashes already submitted
- Uploads only new hashes
- Submits exactly one API request

---

Input format

- Place one or more .hc22000 files in the same directory as the script
- One hash per line
- Blank lines and lines starting with # are ignored

---

Overflow handling

If more than 50 new hashes remain after de-duplication:

- No upload is performed
- Remaining hashes are written to:

ohc_overflow_hashes.txt

You can trim inputs and rerun safely.

---

Disclaimer

Use this script only for hashes you own or have explicit authorization to test.
You are responsible for complying with OnlineHashCrack’s Terms of Service and all applicable laws.

---

License

MIT License. Use responsibly.

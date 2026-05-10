---
name: Simplify UX and README
overview: Replace the flag-heavy CLI experience with an interactive Rich menu (`python run.py`), ship a sample blocklist, and rewrite the README as a step-by-step beginner walkthrough where every feature has its own numbered section with exact commands, expected output, and an explanation of what happened.
todos:
  - id: create-run-py
    content: "Create run.py: interactive Rich menu launcher that auto-configures flags, picks a free port, prints dig commands, and handles all 10 menu options."
    status: pending
  - id: create-blocklist
    content: Create blocklist.txt with sample ad/tracker domains.
    status: pending
  - id: self-contained-benchmark
    content: "In run.py option 7: start server subprocess, run benchmark, print results, kill server -- no second terminal."
    status: pending
  - id: rewrite-readme
    content: Rewrite README.md as a linear beginner walkthrough with per-feature sections (What / How to test / Expected output / Explanation).
    status: pending
  - id: default-port-fix
    content: Change server.py default port from 5353 to 55353 to avoid macOS mDNS conflict out of the box.
    status: pending
  - id: verify-and-test
    content: Run pytest, run.py smoke test (offline demo option), verify README renders correctly.
    status: pending
isProject: false
---

# Simplify UX: interactive launcher, bundled blocklist, beginner README

## Problem summary

1. **Blocklist requires the user to create a file and pass a path** -- should ship a sample `blocklist.txt` and work out of the box.
2. **Every feature requires knowing the right combination of CLI flags** -- a newcomer has no idea what `--upstream-protocol doh --doh-url ...` means. Need an interactive script that presents a Rich menu of numbered choices.
3. **README is a wall of flags, not a walkthrough** -- each feature needs its own "Feature N: Title / Command / Expected Output / What just happened?" section that a total beginner can follow linearly.

## Changes

### 1. New `run.py` -- interactive Rich menu launcher (the single entry point)

Create [run.py](run.py) that uses `rich.prompt` to present a numbered menu. The user just runs `python run.py` and picks what to do. No flags to memorize.

Menu options:

```
=== Mini DNS Resolver ===

What would you like to do?

 [1] Start the resolver (basic, UDP upstream)
 [2] Start the resolver (DNS-over-TLS upstream)
 [3] Start the resolver (DNS-over-HTTPS upstream)
 [4] Start the resolver with blocklist enabled
 [5] Run the automated demo (cold/warm/TTL/TC tests)
 [6] Run the automated demo (offline, no internet needed)
 [7] Run the benchmark (latency stats)
 [8] Run tests (pytest)
 [9] Start the resolver with web dashboard
 [0] Exit

Enter your choice:
```

Each choice builds the right `server.py` / `demo.py` / `pytest` command internally and either `os.execvp`s it or runs it in a subprocess. For the server options, it auto-picks port **55353** (with a fallback to a random port if that fails), prints the exact `dig` command the user should copy-paste in a second terminal, and explains what to look for. For the benchmark option, it starts the server in a background subprocess, runs the benchmark, then kills the server -- fully self-contained, no second terminal needed.

Key behaviors:
- Port selection: try 55353, if `Address already in use`, try 55354, 55355... up to 5 attempts, or pick 0 for OS-assigned. Print the chosen port clearly.
- After starting the server, print a colored box with copy-paste `dig` commands.
- For blocklist mode: use the bundled [blocklist.txt](blocklist.txt) by default.
- For dashboard mode: auto-install FastAPI/uvicorn if missing (prompt user), then start server with `--dashboard 127.0.0.1:8080`.

### 2. Ship [blocklist.txt](blocklist.txt) in the repo root

A sample file with common ad/tracker domains so the user never needs to create one:

```
# Sample blocklist -- domains here return NXDOMAIN
ads.example.com
tracker.example.com
malware.example.net
```

The `run.py` option 4 automatically passes `--blocklist blocklist.txt`. The README explains the format and how to edit it.

### 3. Rewrite [README.md](README.md) as a linear beginner walkthrough

Structure:

```
# Mini DNS Resolver

## What is this?
  (3-sentence plain-English explanation, no jargon)

## Quick start (< 2 minutes)
  Step 1: install
  Step 2: python run.py
  Step 3: pick option 1
  Step 4: open second terminal, paste the dig command shown

## How it works (with diagram)
  Simple mermaid: laptop -> this program -> upstream (1.1.1.1)

## Feature walkthroughs
  ### Feature 1: Cache hit vs miss (cold/warm)
    What it does (2 sentences)
    Step-by-step commands
    What you should see (example server output pasted)
    What just happened (2 sentences)

  ### Feature 2: TTL expiry
    (same pattern)

  ### Feature 3: TCP fallback on truncation
    ...

  ### Feature 4: Negative caching (NXDOMAIN)
    ...

  ### Feature 5: DNS-over-TLS (DoT)
    ...

  ### Feature 6: DNS-over-HTTPS (DoH)
    ...

  ### Feature 7: Blocklist / domain blocking
    ...

  ### Feature 8: LRU cache eviction
    ...

  ### Feature 9: Live stats (SIGUSR1)
    ...

  ### Feature 10: JSON structured logs
    ...

  ### Feature 11: Trace mode
    ...

  ### Feature 12: Benchmark (latency distributions)
    ...

  ### Feature 13: Web dashboard
    ...

  ### Feature 14: Docker
    ...

## Running tests

## Project file map

## Theory (for the course report)
```

Each feature section follows the exact same template:
- **What it does** (plain English, 1-2 sentences)
- **How to test it** (numbered steps with exact commands -- either `python run.py` option N, or manual `dig` commands)
- **What you should see** (copy-pasted example terminal output)
- **What just happened** (plain English explanation of the behavior)

### 4. Self-contained benchmark in `run.py`

Option 7 in the menu should **not** require the user to know about PIDs, SIGUSR2, or two terminals. Instead, `run.py` will:
1. Start `server.py` as a background subprocess.
2. Wait 0.5s for it to bind.
3. Run the benchmark queries directly (warm loop + cold loop with SIGUSR2 to the known PID).
4. Print results.
5. Kill the server subprocess.

All in one step.

### 5. Minor code changes

- [server.py](server.py) `_async_main`: change default port from 5353 to **55353** so it works out of the box on macOS without the "Address already in use" error that confused the user earlier.
- [demo.py](demo.py): no changes needed (already self-contained).
- Keep all existing CLI flags for power users; `run.py` is the beginner layer on top.

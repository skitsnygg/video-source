# Find Video Source (Video + timestamps)

A python script that when given a snippet of text (book, paper, article, transcript) will find the original video and the relevant time range.

## Overview

Given a short snippet of text (from a book, paper, article, or transcript), this tool finds the most likely YouTube video where the line was spoken and returns tight start/end timestamps with evidence.

Supports two modes:
- **Video-first**: you provide a YouTube URL/ID (deterministic).
- **Search-first**: you provide only text; the tool searches candidates, ranks them, and returns the best match.

## Architecture

```text
snippet (+ optional youtube)
        |
        v
CLI (video-source)
  | search-first -> search providers -> candidate video_ids
  | video-first  -> single video_id
        |
        v
transcript fetcher (YT API -> yt-dlp fallback) + caching
        |
        v
matcher (exact -> n-gram anchors -> fuzzy window) -> timestamps
        |
        v
result JSON + evidence + alternatives
        |
        v
logs/traces (jsonl) + saved artifacts (vtt, ytdlp logs)

```
## Features

- Works even with noisy or approximate text.
- Returns a structured result indicating the most likely video and time range.
- Includes a brief explanation or confidence score.

## Input/Output

**Input:** Text snippet (plain text)


**Output format:**
```json
{
  "ok": true,
  "best": {
    "reference": {"platform":"youtube","id":"qp0HIF3SfI4","url":"https://www.youtube.com/watch?v=qp0HIF3SfI4"},
    "timestamp_start": "00:05:38",
    "timestamp_end": "00:05:40",
    "confidence": 98,
    "details": {"evidence":"youtube:exact_phrase", "coverage":1.0, "similarity":1.0}
  },
  "alternatives": [],
  "explanation": "Accepted: youtube:exact_phrase."
}


```

## Bonus Features

- **Ranked alternative candidates**  
  Returns up to 5 alternative videos, ordered by confidence score, when available.

- **Dual operation modes**
  - *Video-first*: deterministic evaluation when a YouTube URL or ID is provided.
  - *Search-first*: automatically searches for candidate videos when only text is given.

- **Tight timestamp extraction**
  - Exact full-phrase matching when possible (highest confidence).
  - Contiguous n-gram phrase anchoring (12 / 10 / 8 words).
  - Fuzzy sliding-window fallback with coverage and similarity scoring.
  - Additional timestamp tightening using the longest exact shared n-gram.

- **Robust transcript handling**
  - Supports both auto-generated and manually provided YouTube captions.
  - Gracefully handles YouTube bot/consent gating via browser cookies.
  - Caches downloaded transcripts to avoid repeated network calls.

- **Reproducibility and evidence**
  - Cached caption files stored in `cache/captions/`.
  - Full yt-dlp command output captured in `logs/ytdlp/`.
  - Per-run JSONL traces stored in `logs/`.
  - Final structured results saved in `data/results/`.

## Installation

### Prerequisites

- Python 3.10 or newer
- yt-dlp installed and available on your PATH

### Setup

Create and activate a virtual environment, then install the project in editable mode.


To install yt-dlp if needed:

    pip install -U yt-dlp

Create and activate a virtual environment, then install dependencies:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -U pip
    pip install -e .




## Configuration
This project is configurable via environment variables. All configuration is optional, but some settings improve reliability and reproducibility.

### YouTube access (recommended)

- `YTDLP_COOKIES_FROM_BROWSER`  
  Browser profile used by `yt-dlp` to bypass YouTube bot/consent gating.

  Example:

      export YTDLP_COOKIES_FROM_BROWSER=firefox

  This is strongly recommended, as many videos block subtitle access without cookies.

### Search providers (optional)

Used only in **search-first** mode (when no `--youtube` argument is provided).

- `SERPER_API_KEY`  
  Enables Google-based search via Serper.

- `TAVILY_API_KEY`  
  Enables Tavily search as an alternative provider.

If neither key is set, the tool still works in **video-first** mode.

### Matching thresholds and tuning

These parameters control match acceptance and scoring behavior:

- `MIN_CONFIDENCE`  
  Minimum confidence score for accepting fuzzy matches (default: 70).

- `MIN_COVERAGE`  
  Minimum token coverage ratio for accepting fuzzy matches (default: 0.55).

- `WINDOW_WORDS`  
  Size of the sliding window (in words) used for fuzzy matching (default: 80).

- `WINDOW_STRIDE`  
  Step size (in words) between windows during fuzzy matching (default: 12).

### Reproducibility and outputs

- `CW_CACHE_DIR`  
  Base directory for cached caption files (default: `./cache`).

- `CW_LOG_DIR`  
  Directory for per-run JSONL logs and yt-dlp outputs (default: `./logs`).

- `CW_RESULTS_DIR`  
  Directory for final structured result files (default: `./data/results`).

These directories allow runs to be inspected, replayed, and audited.


## Usage

The tool can be run in two primary modes: **video-first** and **search-first**.

## Demo Guide

### One-command demo (recommended for evaluation)

Video-first runs without any paid API keys. Search-first requires `SERPER_API_KEY` or `TAVILY_API_KEY`.

```bash
export YTDLP_COOKIES_FROM_BROWSER=firefox
./scripts/demo.sh
```

### Video-first mode (recommended)

Use this mode when you already know the video. It is deterministic and fastest.

    export YTDLP_COOKIES_FROM_BROWSER=firefox

    video-source \
      --youtube "https://www.youtube.com/watch?v=qp0HIF3SfI4" \
      --snippet "People don't buy what you do, they buy why you do it."

This evaluates only the provided video and returns the tightest matching timestamps.

### Search-first mode (optional)

Use this mode when you only have text and do not know the video source.

Requires at least one search API key.

    export SERPER_API_KEY=your_key_here
    export YTDLP_COOKIES_FROM_BROWSER=firefox

    video-source \
      --snippet "text here"

The system will:
1. Search for candidate YouTube videos.
2. Retrieve transcripts for each candidate.
3. Rank matches and return the best result.

### Diagnostic mode

Diagnostic mode prints short, human-readable status messages while running.
This is useful when debugging subtitle access, YouTube bot gating, or matching behavior.

    export YTDLP_COOKIES_FROM_BROWSER=firefox

    video-source --diagnose \
      --youtube "https://www.youtube.com/watch?v=qp0HIF3SfI4" \
      --snippet "People don't buy what you do, they buy why you do it."

Diagnostic output includes:
- Whether subtitles were accessible
- Number of caption segments parsed
- Whether an exact phrase or fuzzy match was used




## Observability (Logs & Traces)

- `--json` prints the final structured result to **stdout** only (safe for piping/UI parsing).
- `--diagnose` prints short run diagnostics to **stderr**.
- Per-run artifacts:
  - `logs/<run_id>.jsonl` (pipeline trace events)
  - `logs/ytdlp/*` (yt-dlp outputs)
  - `cache/captions/*` (cached VTT captions)
  - `data/results/<run_id>.json` (final result)

## Docker (Optional – Reproducible Setup)

This project includes optional **Docker** and **docker-compose** support for reproducible execution without requiring a local Python environment.

> **Important note on YouTube cookies**  
> Browser-based cookies (`YTDLP_COOKIES_FROM_BROWSER`) generally do **not** work inside Docker containers.  
> For reliable transcript access when running in Docker, it is recommended to export browser cookies to a `cookies.txt` file and mount it into the container.

---

### Build the Docker image

From the repository root:

```bash
docker compose build
```
## Run (Video-first mode – recommended)

### Prerequisites

```bash
export YTDLP_COOKIES_FROM_BROWSER=firefox
```
### Command
```
video-source --json --diagnose \
  --youtube "https://www.youtube.com/watch?v=qp0HIF3SfI4" \
  --snippet "People don't buy what you do, they buy why you do it."
```
### Optional: Save stdout/stderr separately
```
video-source --json --diagnose \
  --youtube "https://www.youtube.com/watch?v=qp0HIF3SfI4" \
  --snippet "People don't buy what you do, they buy why you do it." \
  1>out.json 2>debug.log
```
## Run (Search-first mode)

### Goal

Automatically search for candidate videos using the provided text snippet, evaluate transcripts, and return the best matching video with timestamps.

### Prerequisites

At least one search provider API key must be set:

```bash
export SERPER_API_KEY=YOUR_KEY_HERE
# or
export TAVILY_API_KEY=YOUR_KEY_HERE
```

Browser cookies are still strongly recommended for reliable transcript access:
```bash
export YTDLP_COOKIES_FROM_BROWSER=firefox
```

### Command
```bash
video-source --json --diagnose \
  --snippet "People don't buy what you do, they buy why you do it."
```
### Optional: Save stdout/stderr separately
```bash
video-source --json --diagnose \
  --snippet "People don't buy what you do, they buy why you do it." \
  1>out.json 2>debug.log
```

## Run via Docker (Video-first mode)

### Goal

Run the tool in **video-first mode** using Docker for reproducible execution, without requiring a local Python environment.

### Prerequisites

- Docker and Docker Compose installed
- You are in the repository root

> **Note on cookies:**  
> `YTDLP_COOKIES_FROM_BROWSER` generally does **not** work inside Docker containers.  
> For best results, use a `cookies.txt` file mounted into the container.

### Optional: Provide cookies to Docker (recommended)

1. Export browser cookies to a Netscape-format file named:
   ```text
   cookies.txt
Place the file in the repository root.

The file will be mounted automatically at /app/cookies.txt

### Command
```bash
docker compose run --rm video-source \
  video-source --json --diagnose \
  --youtube "https://www.youtube.com/watch?v=qp0HIF3SfI4" \
  --snippet "People don't buy what you do, they buy why you do it."
```
## Run via Docker (Search-first mode)

### Goal

Run the tool in **search-first mode** inside Docker, allowing the system to autonomously discover candidate videos from the provided text snippet.

### Prerequisites

- Docker and Docker Compose installed
- You are in the repository root
- At least one search provider API key set:

```bash
export SERPER_API_KEY=YOUR_KEY_HERE
# or
export TAVILY_API_KEY=YOUR_KEY_HERE
```
### Command
```bash
SERPER_API_KEY=YOUR_KEY_HERE docker compose run --rm video-source \
  video-source --json --diagnose \
  --snippet "People don't buy what you do, they buy why you do it."
```
## Observability & Debugging

### Overview

The system is designed to be fully observable. Each run produces structured outputs, human-readable diagnostics, and persistent artifacts that allow the full decision process to be inspected and audited.

### JSON Output Mode

When the `--json` flag is enabled:

- **stdout** contains exactly **one JSON object**
- **stderr** is reserved for diagnostics and logs

This guarantees that the tool is safe for:
- piping
- automation
- UI integration (e.g., Streamlit)

Example:

```bash
video-source --json --diagnose \
  --youtube "https://www.youtube.com/watch?v=qp0HIF3SfI4" \
  --snippet "People don't buy what you do, they buy why you do it."
```
#### The --diagnose flag enables short, human-readable diagnostics written to stderr, including:

subtitle availability checks\

caption segment counts

transcript download status

match acceptance / rejection reasoning

Diagnostics never pollute JSON output.

Persisted Artifacts

#### Each run generates the following artifacts on disk:

cache/captions/
Cached VTT subtitle files (avoids repeated downloads)

logs/<run_id>.jsonl
Structured per-step trace events (search, captions, matching)

logs/ytdlp/
Raw yt-dlp command outputs for subtitle listing and download

data/results/<run_id>.json
Final structured result saved to disk

#### These artifacts allow runs to be replayed, inspected, and audited end-to-end.


### Separating stdout and stderr (example)
```bash
video-source --json --diagnose \
  --snippet "People don't buy what you do, they buy why you do it." \
  1>result.json 2>debug.log
```
result.json → clean machine-readable output

debug.log → full diagnostic trace

## Architecture Summary

### High-level Flow

The system follows a simple, auditable pipeline from input text to timestamped video attribution:

```text
Text snippet
   |
   v
Candidate selection
  - Video-first: explicit YouTube URL or ID
  - Search-first: search providers (Serper / Tavily)
   |
   v
Transcript retrieval
  - yt-dlp subtitle discovery
  - caption download + caching
   |
   v
Matching engine
  - exact phrase match (highest confidence)
  - anchored n-gram matching
  - fuzzy sliding-window fallback
   |
   v
Scoring & ranking
  - confidence + coverage thresholds
  - deterministic acceptance rules
   |
   v
Structured result
  - best match
  - ranked alternatives
  - evidence + explanation
```

### Module Responsibilities

CLI (cli.py)
Orchestrates execution, handles modes, flags, logging, and output formatting.

Search (search.py)
Retrieves candidate video URLs in search-first mode using pluggable providers.

Transcripts (transcripts.py)
Handles subtitle discovery, download, parsing, and caching via yt-dlp.

Matching (match.py)
Performs exact, anchored, and fuzzy matching to locate tight timestamps.

Utilities (util.py)
Shared helpers for logging, paths, environment configuration, and persistence.

### Design Principles

Deterministic behavior when inputs are known

Conservative acceptance thresholds to avoid false positives

Clear separation of concerns between stages

Traceability at every step (logs, traces, artifacts)

Safe defaults for automation and UI integration

## Repository Structure

The repository is organized to clearly separate core logic, scripts, and generated artifacts.

```text
video-source/
├── README.md                 # Project overview and usage instructions
├── pyproject.toml            # Package metadata and dependencies
├── Dockerfile                # Optional Docker image for reproducibility
├── docker-compose.yml        # Optional docker-compose setup
├── .gitignore                # Ignore runtime and build artifacts
│
├── src/
│   └── video_source/
│       ├── cli.py            # Command-line interface
│       ├── search.py         # Candidate video search (search-first mode)
│       ├── transcripts.py    # Subtitle discovery, download, and parsing
│       ├── match.py          # Phrase anchoring and fuzzy matching logic
│       ├── types.py          # Shared data structures
│       └── util.py           # Utilities (logging, paths, helpers)
│
├── scripts/
│   └── demo.sh               # One-command demo for evaluation
│
├── cache/                    # Cached artifacts (ignored by git)
│   └── captions/             # Downloaded VTT subtitle files
│
├── logs/                     # Execution logs (ignored by git)
│   └── ytdlp/                # yt-dlp command outputs
│
└── data/
    └── results/              # Final structured JSON results (ignored by git)
```

### Notes

Core application code lives under src/video_source/.

Runtime artifacts (cache/, logs/, data/results/) are generated per run and excluded from version control.

The scripts/demo.sh script provides a single-command entry point for evaluators.

Docker support is optional and intended for reproducible execution.

This layout separates core logic from cached artifacts and ensures runs are reproducible end-to-end.


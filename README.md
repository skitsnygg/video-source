# Find Video Source (Video + timestamps)

A python script that when given a snippet of text (book, paper, article, transcript) will find the original video and the relevant time range.

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

``
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


## Repository Structure (Current)

The repository is organized as follows:

    video_source/
      README.md
      pyproject.toml
      src/video_source/
        cli.py            # Command-line interface
        match.py          # Phrase anchoring and fuzzy matching logic
        search.py         # Candidate retrieval (search-first)
        transcripts.py   # Caption download and parsing (yt-dlp)
        types.py         # Shared data structures
        util.py          # Utilities (logging, paths, helpers)
      cache/
        captions/         # Cached VTT subtitle files
      logs/
        ytdlp/            # yt-dlp command outputs per run
      data/
        results/          # Final structured JSON outputs

This layout separates core logic from cached artifacts and ensures runs are reproducible end-to-end.


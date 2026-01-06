#!/usr/bin/env bash
set -euo pipefail

SNIPPET=${1:-"People don't buy what you do, they buy why you do it."}

export YTDLP_COOKIES_FROM_BROWSER=${YTDLP_COOKIES_FROM_BROWSER:-firefox}

echo "=== Video-first (known-good) ==="
video-source --json --diagnose \
  --youtube "https://www.youtube.com/watch?v=qp0HIF3SfI4" \
  --snippet "$SNIPPET" \
  | tee data/results/demo_video_first.json

echo
echo "=== Search-first (requires SERPER_API_KEY or TAVILY_API_KEY) ==="
video-source --json --diagnose \
  --snippet "$SNIPPET" \
  | tee data/results/demo_search_first.json

echo
echo "Saved results to data/results/."

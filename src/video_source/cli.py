from __future__ import annotations

import argparse
import os
import time
from typing import Any, Dict, List, Optional

from .match import find_best_match
from .search import search_candidates
from .transcripts import download_best_captions_vtt, parse_vtt, yt_dlp_has_subs
from .util import append_jsonl, ensure_dirs, env_flag, extract_youtube_id, log, write_json


def _print_json(obj: Dict[str, Any]) -> None:
    import json
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(text or "")


def main() -> None:
    ap = argparse.ArgumentParser(prog="video-source")
    ap.add_argument("--snippet", required=False, help="Text snippet to locate (plain text)")
    ap.add_argument("--youtube", required=False, help="Optional: direct YouTube URL or ID (video-first)")
    ap.add_argument("--max-eval", type=int, default=int(os.getenv("MAX_EVAL", "30")))
    ap.add_argument("--diagnose", action="store_true", help="Print short diagnostics for failures")
    args = ap.parse_args()

    snippet = (args.snippet or "").strip()
    if not snippet:
        print("Paste snippet and press Enter:")
        snippet = input().strip()

    if not snippet:
        _print_json({"ok": False, "error": "Empty snippet"})
        return

    enable_web_fallback = env_flag("ENABLE_WEB_FALLBACK", True)
    min_conf = float(os.getenv("MIN_CONFIDENCE", "70"))
    min_cov = float(os.getenv("MIN_COVERAGE", "0.55"))
    window_words = int(os.getenv("WINDOW_WORDS", "80"))
    window_stride = int(os.getenv("WINDOW_STRIDE", "12"))

    cache_dir = os.getenv("CW_CACHE_DIR", "./cache")
    log_dir = os.getenv("CW_LOG_DIR", "./logs")
    results_dir = os.getenv("CW_RESULTS_DIR", "./data/results")
    captions_cache = os.path.join(cache_dir, "captions")
    ytdlp_out_dir = os.path.join(log_dir, "ytdlp")

    ensure_dirs(captions_cache, log_dir, results_dir, ytdlp_out_dir)

    run_id = f"run_{int(time.time())}"
    trace_path = os.path.join(log_dir, f"{run_id}.jsonl")
    out_path = os.path.join(results_dir, f"{run_id}.json")

    cookies_from_browser = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip() or None
    append_jsonl(
        trace_path,
        {"event": "start", "snippet": snippet, "youtube": args.youtube, "cookies_from_browser": cookies_from_browser},
    )

    if args.diagnose and not cookies_from_browser:
        print("[diagnose] No YTDLP_COOKIES_FROM_BROWSER set. YouTube may block transcript access.")

    # Candidates
    candidate_urls: List[str] = []
    if args.youtube:
        candidate_urls = [args.youtube.strip()]
    else:
        if not enable_web_fallback:
            res = {
                "ok": False,
                "error": "No --youtube provided and web fallback disabled",
                "best": None,
                "alternatives": [],
                "explanation": "Provide --youtube or set ENABLE_WEB_FALLBACK=1 and SERPER_API_KEY/TAVILY_API_KEY",
            }
            write_json(out_path, res)
            _print_json(res)
            return

        candidate_urls = search_candidates(snippet, max_urls=50)

    # canonicalize / dedupe watch urls
    seen = set()
    cleaned: List[str] = []
    for u in candidate_urls:
        vid = extract_youtube_id(u)
        if not vid:
            continue
        canon = f"https://www.youtube.com/watch?v={vid}"
        if canon in seen:
            continue
        seen.add(canon)
        cleaned.append(canon)
        if len(cleaned) >= 50:
            break

    candidate_urls = cleaned

    if not candidate_urls:
        res = {
            "ok": False,
            "error": "No YouTube candidates found",
            "best": None,
            "alternatives": [],
            "explanation": "Search returned no watch URLs. Provide --youtube to force a known video.",
        }
        write_json(out_path, res)
        _print_json(res)
        return

    # Evaluate
    scored: List[Dict[str, Any]] = []
    best_item: Optional[Dict[str, Any]] = None
    best_score = -1.0

    for url in candidate_urls[: args.max_eval]:
        vid = extract_youtube_id(url) or "unknown"

        has_subs, list_out, status = yt_dlp_has_subs(url, cookies_from_browser)
        list_path = os.path.join(ytdlp_out_dir, f"{run_id}__{vid}__list-subs.txt")
        _write_text(list_path, list_out)

        if not has_subs:
            if args.diagnose:
                print(f"[diagnose] {vid}: cannot list subtitles ({status}). saved: {list_path}")
            continue

        vtt_path, dl_out = download_best_captions_vtt(vid, url, captions_cache, cookies_from_browser)
        dl_path = os.path.join(ytdlp_out_dir, f"{run_id}__{vid}__download-subs.txt")
        _write_text(dl_path, dl_out)

        if not vtt_path:
            if args.diagnose:
                print(f"[diagnose] {vid}: subtitles download failed. saved: {dl_path}")
            continue

        segs = parse_vtt(vtt_path)
        if args.diagnose:
            print(f"[diagnose] {vid}: captions OK ({len(segs)} segments). vtt: {vtt_path}")

        if not segs:
            continue

        match = find_best_match(segs, snippet, window_words=window_words, window_stride=window_stride)
        if not match:
            if args.diagnose:
                print(f"[diagnose] {vid}: no match in transcript.")
            continue

        evidence = str(match.details.get("evidence", ""))
        conf = float(match.confidence)
        cov = float(match.details.get("coverage", 0.0))

        if evidence == "youtube:exact_phrase":
            score = 1_000_000 + conf
        elif evidence == "youtube:phrase_anchor":
            score = 900_000 + conf
        else:
            score = conf

        if evidence in ("youtube:exact_phrase", "youtube:phrase_anchor"):
            ok = True
            explanation = f"Accepted: {evidence}."
        else:
            ok = (conf >= min_conf) and (cov >= min_cov)
            if ok:
                explanation = f"Accepted: confidence={int(round(conf))}, coverage={cov:.3f}."
            else:
                explanation = (
                    f"Rejected: confidence={int(round(conf))}, coverage={cov:.3f} "
                    f"(thresholds MIN_CONFIDENCE={min_conf}, MIN_COVERAGE={min_cov})."
                )

        item = {
            "ok": ok,
            "reference": {"platform": "youtube", "id": vid, "url": url},
            "timestamp_start": match.timestamp_start,
            "timestamp_end": match.timestamp_end,
            "confidence": int(round(conf)),
            "details": match.details,
            "_score": float(score),
            "_explanation": explanation,
        }

        scored.append(item)

        if score > best_score:
            best_score = score
            best_item = item

        if evidence == "youtube:exact_phrase":
            break

    if not best_item:
        res = {
            "ok": False,
            "error": "No match found (no captions / blocked / no matching transcript content).",
            "best": None,
            "alternatives": [],
            "explanation": f"No evaluated candidate produced a usable timed transcript match. See logs: {trace_path}",
        }
        write_json(out_path, res)
        _print_json(res)
        return

    ranked = sorted(scored, key=lambda r: r["_score"], reverse=True)
    alternatives: List[Dict[str, Any]] = []
    for cand in ranked:
        if cand is best_item:
            continue
        alternatives.append(
            {
                "reference": cand["reference"],
                "timestamp_start": cand["timestamp_start"],
                "timestamp_end": cand["timestamp_end"],
                "confidence": cand["confidence"],
                "details": cand["details"],
            }
        )
        if len(alternatives) >= 5:
            break

    res = {
        "ok": bool(best_item["ok"]),
        "error": None if best_item["ok"] else "No confident match found",
        "best": {
            "reference": best_item["reference"],
            "timestamp_start": best_item["timestamp_start"],
            "timestamp_end": best_item["timestamp_end"],
            "confidence": best_item["confidence"],
            "details": best_item["details"],
        },
        "alternatives": alternatives,
        "explanation": best_item["_explanation"],
    }

    write_json(out_path, res)
    log(f"Wrote: {out_path}")
    _print_json(res)

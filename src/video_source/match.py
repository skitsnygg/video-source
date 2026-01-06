from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from .types import CaptionSeg
from .util import hms, normalize_text, tokenize

# Step 3: phrase anchors (longer n-grams get tighter + higher confidence)
ANCHOR_NGRAMS = (12, 10, 8)


@dataclass
class MatchResult:
    timestamp_start: str
    timestamp_end: str
    confidence: float
    details: Dict[str, Any]


# ---------------------------
# Step 3: Exact phrase anchor
# ---------------------------

def build_flat_transcript(segs: List[CaptionSeg]) -> Tuple[str, List[Tuple[int, int, float, float]]]:
    """
    Returns:
      flat_text: concatenated normalized transcript text with spaces between segments
      spans: list of (char_start, char_end, seg.start, seg.end) per segment within flat_text
    """
    parts: List[str] = []
    spans: List[Tuple[int, int, float, float]] = []
    cur = 0

    for s in segs:
        t = normalize_text(s.text)
        if not t:
            continue
        if parts:
            parts.append(" ")
            cur += 1

        a = cur
        parts.append(t)
        cur += len(t)
        b = cur

        spans.append((a, b, s.start, s.end))

    return "".join(parts), spans


def charpos_to_time(spans: List[Tuple[int, int, float, float]], pos0: int, pos1: int) -> Tuple[float, float]:
    """
    Map a match [pos0, pos1) in flat_text back to (start_time, end_time).

    We do a simple proportional interpolation within the first/last overlapped segment
    to tighten timestamps beyond whole-segment edges.
    """
    overlap: List[Tuple[int, int, float, float]] = []
    for a, b, st, et in spans:
        if b <= pos0:
            continue
        if a >= pos1:
            break
        overlap.append((a, b, st, et))

    if not overlap:
        return 0.0, 0.0

    # interpolate within first overlapped segment
    a0, b0, st0, et0 = overlap[0]
    dur0 = max(1e-6, et0 - st0)
    span0 = max(1, b0 - a0)
    frac0 = (pos0 - a0) / float(span0)
    frac0 = min(1.0, max(0.0, frac0))
    start_t = st0 + frac0 * dur0

    # interpolate within last overlapped segment
    a1, b1, st1, et1 = overlap[-1]
    dur1 = max(1e-6, et1 - st1)
    span1 = max(1, b1 - a1)
    frac1 = (pos1 - a1) / float(span1)
    frac1 = min(1.0, max(0.0, frac1))
    end_t = st1 + frac1 * dur1

    if end_t < start_t:
        end_t = start_t

    return float(start_t), float(end_t)


def exact_phrase_anchor(segs: List[CaptionSeg], snippet: str) -> Optional[MatchResult]:
    """
    Best case:
      - Find the entire normalized snippet as a contiguous substring in the flattened transcript.

    If not found:
      - Try contiguous n-gram chunks (12/10/8 words) from the snippet as an "anchor".
    """
    flat, spans = build_flat_transcript(segs)
    sn = normalize_text(snippet)
    if not sn or not flat:
        return None

    # Full snippet exact match (tightest)
    idx = flat.find(sn)
    if idx != -1:
        st, et = charpos_to_time(spans, idx, idx + len(sn))
        return MatchResult(
            timestamp_start=hms(st),
            timestamp_end=hms(et),
            confidence=98.0,
            details={
                "coverage": 1.0,
                "similarity": 1.0,
                "evidence": "youtube:exact_phrase",
                "preview": sn[:240],
            },
        )

    # Try best contiguous chunk
    toks = tokenize(snippet)
    if len(toks) >= min(ANCHOR_NGRAMS):
        best: Optional[MatchResult] = None
        for n in ANCHOR_NGRAMS:
            if len(toks) < n:
                continue
            for i in range(0, len(toks) - n + 1):
                chunk = " ".join(toks[i:i + n])
                chunk_n = normalize_text(chunk)
                j = flat.find(chunk_n)
                if j == -1:
                    continue

                st, et = charpos_to_time(spans, j, j + len(chunk_n))
                conf = 80.0 + min(18.0, float(n))  # longer => higher
                cand = MatchResult(
                    timestamp_start=hms(st),
                    timestamp_end=hms(et),
                    confidence=conf,
                    details={
                        "coverage": 1.0,
                        "similarity": 0.95,
                        "evidence": "youtube:phrase_anchor",
                        "preview": chunk_n[:240],
                        "ngram_n": n,
                    },
                )
                if best is None or cand.confidence > best.confidence:
                    best = cand

            if best:
                return best

    return None


# ---------------------------
# Step 4: Fuzzy window fallback
# ---------------------------

def jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def coverage_ratio(snippet_tokens: List[str], window_tokens: List[str]) -> float:
    """
    How many unique snippet tokens appear in the window.
    """
    if not snippet_tokens:
        return 0.0
    sw = set(window_tokens)
    hit = sum(1 for t in set(snippet_tokens) if t in sw)
    return hit / float(len(set(snippet_tokens)))


def tighten_with_ngram(
    window_tokens: List[str],
    window_word_times: List[Tuple[float, float]],
    snippet_tokens: List[str],
    min_n: int = 4,
    max_n: int = 12,
) -> Optional[Tuple[float, float, str, int]]:
    """
    Inside the winning fuzzy window, find the longest exact contiguous n-gram shared
    between snippet_tokens and window_tokens. Use it to tighten timestamps further.
    """
    if not window_tokens or not snippet_tokens:
        return None

    max_n = min(max_n, len(snippet_tokens), len(window_tokens))
    for n in range(max_n, min_n - 1, -1):
        # index window ngrams -> first position
        idx: Dict[str, int] = {}
        for i in range(0, len(window_tokens) - n + 1):
            key = " ".join(window_tokens[i:i + n])
            if key not in idx:
                idx[key] = i

        # scan snippet ngrams, look for first that appears
        for j in range(0, len(snippet_tokens) - n + 1):
            key = " ".join(snippet_tokens[j:j + n])
            if key in idx:
                i0 = idx[key]
                i1 = i0 + n - 1
                st = window_word_times[i0][0]
                et = window_word_times[i1][1]
                return st, et, key, n

    return None


def best_fuzzy_match(
    segs: List[CaptionSeg],
    snippet: str,
    window_words: int,
    window_stride: int,
) -> Optional[MatchResult]:
    snippet_tokens = tokenize(snippet)
    if not snippet_tokens:
        return None

    # Build a token stream with per-token (seg.start, seg.end) timestamps
    words: List[str] = []
    word_times: List[Tuple[float, float]] = []
    for s in segs:
        w = tokenize(s.text)
        for tok in w:
            words.append(tok)
            word_times.append((s.start, s.end))

    if not words:
        return None

    best: Optional[MatchResult] = None
    best_score = -1e18

    W = window_words
    stride = window_stride

    for i in range(0, max(1, len(words) - W + 1), stride):
        j = min(len(words), i + W)
        window_tokens = words[i:j]

        cov = coverage_ratio(snippet_tokens, window_tokens)
        if cov < 0.20:
            continue

        sim = jaccard(snippet_tokens, window_tokens)

        # scoring: coverage dominates, similarity nudges
        length_penalty = min(1.0, len(window_tokens) / max(1, len(snippet_tokens)))
        score = (cov * 100.0) + (sim * 40.0) - (length_penalty * 5.0)

        st = word_times[i][0]
        et = word_times[j - 1][1]

        # tighten timestamps using longest exact shared n-gram inside this window
        tightened = tighten_with_ngram(window_tokens, word_times[i:j], snippet_tokens, min_n=4, max_n=12)
        tight_note: Dict[str, Any] = {"tightened_by_ngram": False}
        if tightened:
            st, et, ngram_txt, n = tightened
            tight_note = {"tightened_by_ngram": True, "ngram_n": n, "ngram": ngram_txt[:240]}

        if score > best_score:
            best_score = score
            preview = " ".join(window_tokens[: min(len(window_tokens), 60)])
            best = MatchResult(
                timestamp_start=hms(st),
                timestamp_end=hms(et),
                confidence=float(score),
                details={
                    "coverage": round(cov, 3),
                    "similarity": round(sim, 3),
                    "evidence": "youtube:timed_transcript",
                    "preview": preview[:280],
                    **tight_note,
                },
            )

    return best


def find_best_match(segs: List[CaptionSeg], snippet: str, window_words: int, window_stride: int) -> Optional[MatchResult]:
    # Step 3 first: exact phrase anchor
    anchored = exact_phrase_anchor(segs, snippet)
    if anchored:
        return anchored
    # Step 4 fallback: fuzzy sliding window
    return best_fuzzy_match(segs, snippet, window_words=window_words, window_stride=window_stride)

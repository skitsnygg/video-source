from __future__ import annotations

import os
import re
import tempfile
from typing import List, Optional, Tuple

from .types import CaptionSeg
from .util import ensure_dirs, safe_run, which


BOT_GATE_HINT = "sign in to confirm you’re not a bot"
BOT_GATE_HINT_ASCII = "sign in to confirm you're not a bot"


def _cookie_args(cookies_from_browser: Optional[str], cookies_file: Optional[str]) -> List[str]:
    if cookies_file:
        return ["--cookies", cookies_file]
    if cookies_from_browser:
        return ["--cookies-from-browser", cookies_from_browser]
    return []


def yt_dlp_has_subs(
    video_url: str,
    cookies_from_browser: Optional[str],
    cookies_file: Optional[str] = None,
    ytdlp_path: Optional[str] = None,
) -> Tuple[bool, str, str]:
    """
    Returns:
      (has_any_subs, output_text, status)

    status:
      - "ok"
      - "bot_gate"
      - "no_subs"
      - "error"
      - "missing_ytdlp"
    """
    try:
        ytdlp = ytdlp_path or which("yt-dlp")
    except RuntimeError as exc:
        return False, str(exc), "missing_ytdlp"

    cmd = [ytdlp]
    cmd += _cookie_args(cookies_from_browser, cookies_file)
    cmd += ["--skip-download", "--list-subs", video_url]
    rc, out = safe_run(cmd, timeout=120)

    txt = (out or "").lower()
    if BOT_GATE_HINT in txt or BOT_GATE_HINT_ASCII in txt:
        return False, out, "bot_gate"
    if rc != 0:
        return False, out, "error"
    if "available subtitles" in txt or "available automatic captions" in txt:
        return True, out, "ok"
    if "has no subtitles" in txt or "no subtitles" in txt:
        return False, out, "no_subs"
    return True, out, "ok"


def _pick_best_vtt(td: str) -> Optional[str]:
    vtts = []
    for fn in os.listdir(td):
        if fn.startswith("__sub.") and fn.endswith(".vtt"):
            p = os.path.join(td, fn)
            if os.path.getsize(p) > 200:
                vtts.append(p)

    if not vtts:
        return None

    preferred_names = [
        "__sub.en.vtt",
        "__sub.en-US.vtt",
        "__sub.en-GB.vtt",
        "__sub.en-en.vtt",
    ]
    for name in preferred_names:
        p = os.path.join(td, name)
        if os.path.exists(p) and os.path.getsize(p) > 200:
            return p

    vtts.sort(key=lambda p: os.path.getsize(p), reverse=True)
    return vtts[0]


def download_best_captions_vtt(
    video_id: str,
    video_url: str,
    cache_dir: str,
    cookies_from_browser: Optional[str],
    cookies_file: Optional[str] = None,
    ytdlp_path: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """
    Tries:
      1) auto captions (--write-auto-subs)
      2) manual captions (--write-subs)

    Caches to: {cache_dir}/{video_id}__best.vtt
    """
    ensure_dirs(cache_dir)
    cache_path = os.path.join(cache_dir, f"{video_id}__best.vtt")
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 200:
        return cache_path, "cache_hit"

    try:
        ytdlp = ytdlp_path or which("yt-dlp")
    except RuntimeError as exc:
        return None, str(exc)

    def run_variant(write_flag: str) -> Tuple[Optional[str], str]:
        with tempfile.TemporaryDirectory(prefix="cw_caps_") as td:
            outtmpl = os.path.join(td, "__sub.%(ext)s")
            cmd = [ytdlp]
            cmd += _cookie_args(cookies_from_browser, cookies_file)
            cmd += [
                "--skip-download",
                write_flag,
                "--sub-lang",
                "en.*,en-orig,en",
                "--sub-format",
                "vtt",
                "-o",
                outtmpl,
                video_url,
                "-v",
            ]
            rc, out = safe_run(cmd, timeout=180)

            best = _pick_best_vtt(td)
            if not best:
                return None, out

            with open(best, "rb") as fsrc, open(cache_path, "wb") as fdst:
                fdst.write(fsrc.read())

            return cache_path, out

    p1, out1 = run_variant("--write-auto-subs")
    if p1:
        return p1, out1

    p2, out2 = run_variant("--write-subs")
    if p2:
        return p2, out2

    return None, (out1 or "") + "\n---\n" + (out2 or "")


def parse_vtt(path: str) -> List[CaptionSeg]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")

    segs: List[CaptionSeg] = []
    ts_re = re.compile(
        r"(?P<s>\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(?P<e>\d{2}:\d{2}:\d{2}\.\d{3})"
    )

    def to_sec(hmsms: str) -> float:
        hh, mm, rest = hmsms.split(":")
        ss, ms = rest.split(".")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if not line or line.upper() == "WEBVTT":
            continue

        m = ts_re.search(line)
        if not m:
            continue

        start = to_sec(m.group("s"))
        end = to_sec(m.group("e"))

        text_lines: List[str] = []
        while i < len(lines) and lines[i].strip():
            t = lines[i].strip()
            t = re.sub(r"<[^>]+>", "", t)
            text_lines.append(t)
            i += 1

        text = " ".join(text_lines).strip()
        if text:
            segs.append(CaptionSeg(start=start, end=end, text=text))

    return segs

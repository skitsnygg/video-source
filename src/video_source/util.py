from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple


def env_flag(name: str, default: bool = True) -> bool:
    v = os.getenv(name, "1" if default else "0").strip().lower()
    return v not in ("0", "false", "no")


DEBUG = env_flag("DEBUG", True)


def log(msg: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)


def hms(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    s = int(round(seconds))
    hh = s // 3600
    mm = (s % 3600) // 60
    ss = s % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = (
        s.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    s = re.sub(r"\s+", " ", s)
    # keep apostrophes inside words; remove other punctuation to stabilize matching
    s = re.sub(r"[^a-z0-9'\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(s: str) -> List[str]:
    s = normalize_text(s)
    return s.split() if s else []


def extract_youtube_id(url_or_id: str) -> Optional[str]:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s

    try:
        u = urllib.parse.urlparse(s)
    except Exception:
        return None

    host = (u.netloc or "").lower()

    if "youtube.com" in host:
        qs = urllib.parse.parse_qs(u.query)
        v = qs.get("v", [None])[0]
        if v and re.fullmatch(r"[A-Za-z0-9_-]{11}", v):
            return v
        m = re.search(r"/shorts/([A-Za-z0-9_-]{11})", u.path or "")
        if m:
            return m.group(1)

    if "youtu.be" in host:
        vid = (u.path or "").strip("/").split("/")[0]
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
            return vid

    return None


def which(cmd: str) -> str:
    p = shutil.which(cmd)
    if not p:
        raise RuntimeError(f"{cmd} not found on PATH")
    return p


def safe_run(cmd: List[str], timeout: int = 180) -> Tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, (p.stdout or "")
    except subprocess.TimeoutExpired as e:
        return 124, f"TIMEOUT: {e}"
    except Exception as e:
        return 127, f"ERROR running command: {e}"


def ensure_dirs(*paths: str) -> None:
    for p in paths:
        os.makedirs(p, exist_ok=True)


def write_json(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    obj = dict(obj)
    obj["_ts"] = time.time()
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

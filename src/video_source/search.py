from __future__ import annotations

import json
import os
import urllib.request
from typing import List

from .util import log


def serper_search_youtube(snippet: str, k: int = 20) -> List[str]:
    """
    Returns a list of YouTube watch URLs from Serper (Google).
    Requires SERPER_API_KEY.
    """
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if not api_key:
        return []

    query = f"\"{snippet.strip()}\" site:youtube.com"
    payload = json.dumps({"q": query, "num": k}).encode("utf-8")

    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log(f"Serper error: {e}")
        return []

    urls: List[str] = []
    for item in (data.get("organic") or []):
        link = item.get("link")
        if link and "youtube.com/watch" in link:
            urls.append(link)
    return urls


def tavily_search_youtube(snippet: str, k: int = 20) -> List[str]:
    """
    Returns a list of YouTube watch URLs from Tavily.
    Requires TAVILY_API_KEY.
    """
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []

    query = f"\"{snippet.strip()}\" site:youtube.com"
    payload = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "max_results": k,
            "include_answer": False,
            "include_raw_content": False,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log(f"Tavily error: {e}")
        return []

    urls: List[str] = []
    for item in (data.get("results") or []):
        link = item.get("url")
        if link and "youtube.com/watch" in link:
            urls.append(link)
    return urls


def search_candidates(snippet: str, max_urls: int = 50) -> List[str]:
    """
    Blends Serper + Tavily results, de-dupes, returns up to max_urls.
    """
    urls: List[str] = []
    urls.extend(serper_search_youtube(snippet, k=20))
    urls.extend(tavily_search_youtube(snippet, k=20))

    out: List[str] = []
    seen = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= max_urls:
            break

    return out

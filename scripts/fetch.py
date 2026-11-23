#!/usr/bin/env python3
"""Get the channel videos and keep one JSON record for each video in data/videos/.

Sources:
  rss    The public channel feed. It needs no key. It shows the 15 latest videos.
         Use it for the scheduled update.
  api    The YouTube Data API v3. Set the YT_API_KEY variable. It gets all
         videos, the statistics and the playlists.
  ytdlp  The yt-dlp tool. It gets all videos and playlists. Use it on your
         own computer for the first full fetch.
  auto   Use "api" if YT_API_KEY is set. Else use "rss".

The script adds new videos and updates the title, the description and the
statistics of the videos that are already in data/videos/. It does not
delete records. To remove a video from the site, add it to "hidden" in
data/overrides.json.
"""

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
VIDEOS = DATA / "videos"
CONFIG = json.loads((ROOT / "site.config.json").read_text("utf-8"))
CHANNEL_ID = CONFIG["channel"]["id"]
HANDLE = CONFIG["channel"]["handle"]
UA = "Mozilla/5.0 (compatible; channel-site-builder/1.0)"

FIELDS = ["id", "title", "description", "published", "duration", "views", "likes", "is_short"]


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_record(vid):
    p = VIDEOS / f"{vid}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def save_record(rec):
    """Write the record only when a field changed. This keeps the git history clean."""
    old = load_record(rec["id"])
    merged = dict(old or {})
    for k in FIELDS:
        v = rec.get(k)
        if v is not None and v != "":
            merged[k] = v
    merged.setdefault("is_short", False)
    if old and all(old.get(k) == merged.get(k) for k in FIELDS):
        return "same"
    merged["updated_at"] = now_iso()
    ordered = {k: merged.get(k) for k in FIELDS + ["updated_at"]}
    VIDEOS.mkdir(parents=True, exist_ok=True)
    (VIDEOS / f"{rec['id']}.json").write_text(
        json.dumps(ordered, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    return "updated" if old else "new"


def http_get(url, method="GET"):
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def probe_short(vid):
    """Return True if the video is a Short.

    YouTube serves /shorts/<id> with status 200 for a Short. It redirects a normal video.
    Return None if the check cannot be done.
    """
    opener = urllib.request.build_opener(NoRedirect)
    # The SOCS cookie stops the redirect to the EU consent page.
    headers = {"User-Agent": UA, "Cookie": "SOCS=CAI; CONSENT=PENDING+987"}
    req = urllib.request.Request(f"https://www.youtube.com/shorts/{vid}", headers=headers, method="HEAD")
    try:
        with opener.open(req, timeout=15) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return False if e.code in (301, 302, 303, 307, 308) else None
    except Exception:
        return None


# ---------------------------------------------------------------- RSS

def fetch_rss():
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
    _, body = http_get(url)
    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "m": "http://search.yahoo.com/mrss/",
    }
    root = ET.fromstring(body)
    out = []
    for e in root.findall("a:entry", ns):
        vid = e.findtext("yt:videoId", namespaces=ns)
        stats = e.find("m:group/m:community/m:statistics", ns)
        rating = e.find("m:group/m:community/m:starRating", ns)
        rec = {
            "id": vid,
            "title": e.findtext("a:title", namespaces=ns),
            "description": e.findtext("m:group/m:description", namespaces=ns) or "",
            "published": (e.findtext("a:published", namespaces=ns) or "")[:10],
            "views": int(stats.get("views")) if stats is not None else None,
            "likes": int(rating.get("count")) if rating is not None else None,
        }
        if load_record(vid) is None:
            rec["is_short"] = probe_short(vid)
        out.append(rec)
    return out, None


# ---------------------------------------------------------------- YouTube Data API

def api(path, **params):
    params["key"] = os.environ["YT_API_KEY"]
    url = f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(params)
    _, body = http_get(url)
    return json.loads(body)


def api_paged(path, **params):
    token = None
    while True:
        if token:
            params["pageToken"] = token
        page = api(path, **params)
        yield from page.get("items", [])
        token = page.get("nextPageToken")
        if not token:
            return


def iso_duration(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def fetch_api(with_playlists=True):
    ch = api("channels", part="contentDetails", id=CHANNEL_ID)["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [it["contentDetails"]["videoId"] for it in api_paged("playlistItems", part="contentDetails", playlistId=uploads, maxResults=50)]
    recs = []
    for i in range(0, len(ids), 50):
        batch = api("videos", part="snippet,contentDetails,statistics", id=",".join(ids[i:i + 50]), maxResults=50)
        for v in batch.get("items", []):
            s, st = v["snippet"], v.get("statistics", {})
            rec = {
                "id": v["id"],
                "title": s["title"],
                "description": s.get("description", ""),
                "published": s["publishedAt"][:10],
                "duration": iso_duration(v["contentDetails"].get("duration")),
                "views": int(st["viewCount"]) if "viewCount" in st else None,
                "likes": int(st["likeCount"]) if "likeCount" in st else None,
            }
            if load_record(v["id"]) is None:
                rec["is_short"] = probe_short(v["id"])
            recs.append(rec)
    playlists = None
    if with_playlists:
        playlists = []
        for p in api_paged("playlists", part="snippet", channelId=CHANNEL_ID, maxResults=50):
            vids = [it["contentDetails"]["videoId"] for it in api_paged("playlistItems", part="contentDetails", playlistId=p["id"], maxResults=50)]
            playlists.append({"id": p["id"], "title": p["snippet"]["title"], "videos": vids})
    return recs, playlists


# ---------------------------------------------------------------- yt-dlp

def ytdlp_json(url, flat=False):
    cmd = ["yt-dlp", "--no-update", "--no-warnings", "-J"]
    if flat:
        cmd.append("--flat-playlist")
    else:
        cmd.append("--skip-download")
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"yt-dlp failed for {url}: {r.stderr.strip()[-300:]}")
    return json.loads(r.stdout)


def from_ytdlp(info, is_short):
    d = info.get("upload_date") or ""
    return {
        "id": info["id"],
        "title": info.get("title"),
        "description": info.get("description") or "",
        "published": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None,
        "duration": info.get("duration"),
        "views": info.get("view_count"),
        "likes": info.get("like_count"),
        "is_short": is_short,
    }


def fetch_ytdlp(seed_dir=None, with_playlists=True, refresh_all=False):
    base = f"https://www.youtube.com/{HANDLE}"
    listing = {}
    for tab, short in (("videos", False), ("shorts", True)):
        try:
            for e in ytdlp_json(f"{base}/{tab}", flat=True).get("entries") or []:
                listing[e["id"]] = (e, short)
        except RuntimeError as err:
            print(f"warning: {err}", file=sys.stderr)

    def full(vid):
        seed = Path(seed_dir) / f"{vid}.json" if seed_dir else None
        if seed and seed.exists():
            return json.loads(seed.read_text("utf-8"))
        return ytdlp_json(f"https://www.youtube.com/watch?v={vid}")

    todo = [v for v in listing if refresh_all or load_record(v) is None]
    recs = []
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for vid, info in zip(todo, pool.map(full, todo)):
            recs.append(from_ytdlp(info, listing[vid][1]))
    # The flat listing has the current view count. Use it for the other videos.
    for vid, (e, short) in listing.items():
        if vid not in todo:
            recs.append({"id": vid, "views": e.get("view_count"), "duration": e.get("duration"), "is_short": short})

    playlists = None
    if with_playlists:
        playlists = []
        entries = ytdlp_json(f"{base}/playlists", flat=True).get("entries") or []

        def pl(e):
            d = ytdlp_json(f"https://www.youtube.com/playlist?list={e['id']}", flat=True)
            return {"id": e["id"], "title": d.get("title") or e.get("title"), "videos": [x["id"] for x in d.get("entries") or []]}

        with cf.ThreadPoolExecutor(max_workers=6) as pool:
            playlists = list(pool.map(pl, entries))
    return recs, playlists


# ---------------------------------------------------------------- main

def save_playlists(playlists):
    own = {p.stem for p in VIDEOS.glob("*.json")}
    keep = []
    for p in playlists:
        vids = [v for v in p["videos"] if v in own]
        if vids:
            keep.append({"id": p["id"], "title": p["title"].strip(), "videos": vids})
    keep.sort(key=lambda p: p["id"])
    path = DATA / "playlists.json"
    text = json.dumps(keep, ensure_ascii=False, indent=1) + "\n"
    if not path.exists() or path.read_text("utf-8") != text:
        path.write_text(text, "utf-8")
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["auto", "rss", "api", "ytdlp"], default="auto")
    ap.add_argument("--no-playlists", action="store_true", help="do not fetch the playlists")
    ap.add_argument("--refresh-all", action="store_true", help="ytdlp: fetch the full metadata of all videos again")
    ap.add_argument("--seed-dir", help="ytdlp: read the full metadata from this folder of yt-dlp JSON files when possible")
    ap.add_argument("--wait-for", default=os.environ.get("WAIT_FOR_VIDEO", ""),
                    help="fetch again until this video ID is in the data (the feed can be some minutes late)")
    ap.add_argument("--attempts", type=int, default=10)
    ap.add_argument("--interval", type=int, default=60, help="seconds between two attempts")
    a = ap.parse_args()

    source = a.source
    if source == "auto":
        source = "api" if os.environ.get("YT_API_KEY") else "rss"
    print(f"source: {source}")

    # The video ID comes from an outside event. Accept only the YouTube ID format.
    wait_for = a.wait_for.strip()
    if wait_for and not re.fullmatch(r"[A-Za-z0-9_-]{11}", wait_for):
        print(f"warning: ignore the invalid video ID {wait_for!r}", file=sys.stderr)
        wait_for = ""

    for attempt in range(1, (a.attempts if wait_for else 1) + 1):
        if source == "rss":
            recs, playlists = fetch_rss()
        elif source == "api":
            recs, playlists = fetch_api(not a.no_playlists)
        else:
            recs, playlists = fetch_ytdlp(a.seed_dir, not a.no_playlists, a.refresh_all)
        if not wait_for or load_record(wait_for) or any(r.get("id") == wait_for for r in recs):
            break
        print(f"video {wait_for} is not in the {source} data yet (attempt {attempt}/{a.attempts})")
        if attempt < a.attempts:
            time.sleep(a.interval)
    else:
        print(f"warning: video {wait_for} did not appear. The weekly job will add it.", file=sys.stderr)

    counts = {"new": 0, "updated": 0, "same": 0}
    new_ids = []
    for r in recs:
        if not r.get("id"):
            continue
        if load_record(r["id"]) is None and not r.get("title"):
            continue
        status = save_record(r)
        counts[status] += 1
        if status == "new":
            new_ids.append(r["id"])
    if playlists is not None and save_playlists(playlists):
        print("playlists: updated")
    print(f"videos: {counts['new']} new, {counts['updated']} updated, {counts['same']} unchanged")
    for v in new_ids:
        print(f"new video: {v}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Fetch ({source})\n\n- New videos: {counts['new']}\n- Updated: {counts['updated']}\n")
            for v in new_ids:
                f.write(f"- https://youtu.be/{v}\n")


if __name__ == "__main__":
    main()

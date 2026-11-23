#!/usr/bin/env python3
"""Stage 1: parse the raw video records into one content file.

Input:  data/videos/*.json, data/playlists.json, data/names.json, data/overrides.json
Output: build/content.json

The content file does not depend on a site framework. The renderer
(scripts/build.py) reads it. Another renderer (example: Astro) can read it too.
"""

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translit import fold, has_telugu, name_to_roman, transliterate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "build" / "content.json"

TYPES = ["padyam", "shloka", "stotram", "dandakam", "gadyam", "keerthana", "song", "bgm"]

# Words in a title or a marker line that tell the form of the piece.
TYPE_WORDS = [
    ("bgm", r"నేపధ్య సంగీతం|నేపథ్య సంగీతం|\bBGM\b"),
    ("dandakam", r"దండకం|దండకమ్"),
    ("gadyam", r"గద్యం"),
    ("stotram", r"స్తోత్రం|స్తోత్రము|స్తోత్రమ్|అష్టకం|స్తుతి|\bstotram\b|\bsthothram\b"),
    ("keerthana", r"కీర్తన"),
    ("shloka", r"శ్లోకం|\bslokam\b"),
    ("padyam", r"పద్యం|పద్యము|\bpadh?yam\b"),
    ("song", r"పాట\b|\bsong\b"),
]

PLAYLIST_TYPES = {
    "PLHkbY79dTSQXXV5zse_UfUULDyAn6d6Ep": "padyam",
    "PLHkbY79dTSQUXjn-nUue-siB-qnuPnV60": "shloka",
    "PLHkbY79dTSQX0khXLHNdE_iXkmL-m3YQB": "stotram",
    "PLHkbY79dTSQXAAPnqwYxVzVcN8nzL_DDx": "stotram",
    "PLHkbY79dTSQW4K6ZxJfEA_PtR8pTcREgG": "dandakam",
    "PLHkbY79dTSQVTNiDvpSpfaDq5I1_3l6yx": "keerthana",
}

CREDIT_KEYS = {
    "గానం": "singers", "గాయకులు": "singers",
    "రచన": "lyricists", "సాహిత్యం": "lyricists",
    "సంగీతం": "music",
    "చిత్రం": "film", "సినిమా": "film",
    "నాటకము": "drama", "నాటకం": "drama",
    "సంపుటి": "album",
    "మూలం": "source",
}

MARKER_WORDS = {"పద్యం", "పద్యము", "శ్లోకం", "పాట", "కీర్తన", "స్తోత్రం", "స్తోత్రము", "దండకం", "గద్యం", "గణేశ శ్లోకం"}
MEANING_WORDS = {"భావము", "భావం", "తెలుగు భావం", "తాత్పర్యం", "తాత్పర్యము", "అర్థం", "అర్ధం"}
PART_WORDS = {"పల్లవి", "అనుపల్లవి", "చరణం", "చరణము", "చరణము(లు)", "చరణాలు"}

LINE_RE = re.compile(r"^\s*([^:：]{1,24}?)\s*[:：]\s*(.*)$")
URL_RE = re.compile(r"https?://\S+")
HASHTAG_LINE_RE = re.compile(r"^\s*(#\S+\s*)+$")
SPLIT_NAMES_RE = re.compile(r"\s*(?:,|&|/| మరియు )\s*")


def clean(text):
    t = unicodedata.normalize("NFC", text or "")
    return t.replace(" ", " ").replace("\r", "").replace("​", "")


def key(text):
    """Make a match key: no spaces, dots, dashes or brackets."""
    t = clean(text).replace("‌", "").replace("‍", "")
    return re.sub(r"[\s.\-–()\[\]:,'\"]+", "", t).lower()


def slugify(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-") or "x"


class Registry:
    """Hold the people, the works or the source texts. Join the different spellings of one name."""

    def __init__(self, entries, kind):
        self.kind = kind
        self.by_key = {}
        self.items = {}
        self.unmapped = set()
        for e in entries:
            self._add(dict(e), curated=True)

    def _add(self, e, curated):
        base = e["en"] + (f" {e['year']}" if e.get("year") else "")
        slug = slugify(base)
        while slug in self.items and self.items[slug]["te"] != e["te"]:
            slug += "-x"
        e["slug"] = slug
        e["curated"] = curated
        self.items[slug] = e
        for name in [e["te"], e["en"], *e.get("aliases", [])]:
            self.by_key.setdefault(key(name), slug)
        return slug

    def find(self, name):
        name = clean(name).strip(" ,;")
        name = re.sub(r"^(రచన|గానం|సంగీతం)\s*[:：]\s*", "", name)
        if not name:
            return None
        k = key(name)
        if k in self.by_key:
            return self.by_key[k]
        # Try the name without a part in brackets. Example: "కాళిదాసు (శ్యామలా దండకం)".
        bare = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
        if bare and key(bare) in self.by_key:
            return self.by_key[key(bare)]
        self.unmapped.add(name)
        en = name_to_roman(bare or name) if has_telugu(name) else name
        return self._add({"te": name, "en": en}, curated=False)


def split_people(reg, value):
    value = clean(value).strip(" ,")
    if not value:
        return []
    whole = key(value)
    if whole in reg.by_key:
        return [reg.by_key[whole]]
    bare = re.sub(r"\s*\(.*?\)\s*", " ", value).strip()
    if key(bare) in reg.by_key:
        return [reg.by_key[key(bare)]]
    # Do not split at a comma inside brackets.
    parts, depth, buf = [], 0, ""
    for ch in value:
        depth += (ch == "(") - (ch == ")")
        buf += ch
        if depth == 0 and SPLIT_NAMES_RE.fullmatch(buf[-1:] if buf[-1:] in ",&/" else "x"):
            parts.append(buf[:-1])
            buf = ""
    parts.append(buf)
    parts = [q for p in parts for q in re.split(r" మరియు ", p)]
    out = []
    for part in parts:
        s = reg.find(part)
        if s and s not in out:
            out.append(s)
    return out


def parse_title(title):
    t = clean(title)
    t = re.sub(r"#\S+", "", t)
    parts = [p.strip() for p in re.split(r"\s*-\s*", t) if p.strip()]
    te = next((p for p in parts if has_telugu(p)), parts[0] if parts else t)
    en = next((p for p in parts if not has_telugu(p) and re.search(r"[A-Za-z]{3}", p)), None)
    te = re.sub(r"\s*(పద్యం|పద్యము|శ్లోకం|కీర్తన|స్తోత్రము|స్తోత్రం|దండకం)\s*$", "", te).strip()
    if en:
        en = re.sub(r"\(.*?\)", "", en)
        en = re.sub(r"\b(padh?yams?|padh?yaa?lu|slokam|sthothram|stotram|keerthana|song|telugu)\b", "", en, flags=re.I)
        en = re.sub(r"\s+", " ", en).strip(" -,")
        en = " ".join(w[:1].upper() + w[1:] for w in en.split()) if en else None
    roman = name_to_roman(te)
    if en:
        a, b = fold(en).split(), fold(roman).split()
        if not a or not b or a[0][:3] != b[0][:3] or len(a) < 0.7 * len(b):
            en = None
    return te, en or roman


def detect_type(text):
    for t, pat in TYPE_WORDS:
        if re.search(pat, text, flags=re.I):
            return t
    return None


def parse_description(desc, title):
    """Split a description into credits, lyric blocks, meaning blocks and links."""
    credits = defaultdict(str)
    blocks = []
    refs = []
    notes = []
    marker = None
    cur = None
    title_key = key(re.sub(r"#\S+", "", clean(title)))

    def new_block(kind, heading=None):
        nonlocal cur
        cur = {"kind": kind, "heading": heading, "lines": []}
        blocks.append(cur)

    last_credit = None
    for raw in clean(desc).split("\n"):
        line = raw.rstrip()
        s = line.strip()
        if last_credit and re.fullmatch(r"\(.*\)", s):
            credits[last_credit] = (credits[last_credit] + " " + s).strip()
            continue
        last_credit = None
        if not s:
            if cur and cur["lines"] and cur["lines"][-1] != "":
                cur["lines"].append("")
            continue
        if HASHTAG_LINE_RE.match(s) or re.fullmatch(r"[=\-_*~]{3,}", s):
            continue
        if key(re.sub(r"#\S+", "", s)) == title_key:
            continue
        urls = URL_RE.findall(s)
        if urls and len(URL_RE.sub("", s).strip()) < 3:
            refs.extend(urls)
            continue
        m = LINE_RE.match(s)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            if k in CREDIT_KEYS:
                field = CREDIT_KEYS[k]
                if field in ("film", "drama", "album"):
                    credits["work"] = v
                    credits["work_kind"] = field
                else:
                    credits[field] = v
                    last_credit = field
                continue
            if k.lower() == "source":
                notes.append(v)
                continue
            if k in MEANING_WORDS:
                new_block("meaning", k)
                if v:
                    cur["lines"].append(v)
                continue
            if k in PART_WORDS:
                new_block("lyrics", k)
                if v:
                    cur["lines"].append(v)
                continue
            if k in MARKER_WORDS:
                marker = marker or k
                if v:
                    if cur is None:
                        new_block("lyrics")
                    cur["lines"].append(v)
                continue
        if s in MARKER_WORDS:
            marker = marker or s
            continue
        if s in MEANING_WORDS:
            new_block("meaning", s)
            continue
        if s in PART_WORDS:
            new_block("lyrics", s)
            continue
        if cur is None:
            new_block("lyrics")
        # Keep the indent of the second half of a padyam line.
        indent = len(line) - len(line.lstrip(" \t"))
        cur["lines"].append(("\t" if indent >= 2 else "") + s)

    out_blocks = []
    for b in blocks:
        while b["lines"] and b["lines"][-1] == "":
            b["lines"].pop()
        while b["lines"] and b["lines"][0] == "":
            b["lines"].pop(0)
        if b["lines"]:
            out_blocks.append(b)
    return dict(credits), out_blocks, refs, notes, marker


def line_payload(line):
    """Return [indent flag, speaker, Telugu text, Roman text] for one lyric line."""
    if line == "":
        return None
    indent = line.startswith("\t")
    text = line.lstrip("\t")
    speaker = None
    m = re.match(r"^(\S{1,10})\s*[:：]\s*(.+)$", text)
    if m and has_telugu(m.group(1)) and m.group(1) not in CREDIT_KEYS:
        speaker, text = m.group(1), m.group(2)
    return {
        "in": indent,
        "sp": speaker,
        "sp_ro": name_to_roman(speaker) if speaker else None,
        "te": text,
        "ro": transliterate(text) if has_telugu(text) else text,
    }


def main():
    names = json.loads((DATA / "names.json").read_text("utf-8"))
    overrides = json.loads((DATA / "overrides.json").read_text("utf-8"))
    playlists = json.loads((DATA / "playlists.json").read_text("utf-8")) if (DATA / "playlists.json").exists() else []
    records = [json.loads(p.read_text("utf-8")) for p in sorted((DATA / "videos").glob("*.json"))]

    people = Registry(names["people"], "person")
    works = Registry(names["works"], "work")
    sources = Registry(names["sources"], "source")
    themes = names["themes"]
    theme_re = {t["key"]: re.compile(t["match"]) for t in themes if t.get("match")}

    in_playlists = defaultdict(list)
    for p in playlists:
        for v in p["videos"]:
            in_playlists[v].append(p["id"])

    hidden = set(overrides.get("hidden", []))
    ov_all = overrides.get("videos", {})
    songs = []

    for r in records:
        vid = r["id"]
        if vid in hidden:
            continue
        ov = ov_all.get(vid, {})
        title = clean(r.get("title") or "")
        credits, blocks, refs, notes, marker = parse_description(r.get("description") or "", title)
        te_title, en_title = parse_title(title)
        te_title = ov.get("title_te", te_title)
        en_title = ov.get("title_en", en_title if "title_te" not in ov else name_to_roman(te_title))

        # Form: the override, then the title, then the marker line, then the playlists.
        typ = ov.get("type") or detect_type(title) or (detect_type(marker) if marker else None)
        if not typ:
            typ = next((PLAYLIST_TYPES[p] for p in in_playlists[vid] if p in PLAYLIST_TYPES), "song")

        work_slug = None
        year = None
        work_text = ov.get("work") or credits.get("work") or ""
        if work_text:
            m = re.search(r"\((\d{4})\)", work_text)
            year = int(m.group(1)) if m else None
            name = re.sub(r"\s*\(?\d{4}\)?\s*", "", re.sub(r"చిత్రం\s*\(\d{4}\)", "", work_text)).strip()
            if name:
                work_slug = works.find(name)
                w = works.items[work_slug]
                if credits.get("work_kind") in ("drama", "album") and not w.get("kind"):
                    w["kind"] = credits["work_kind"]
                if year and not w.get("year"):
                    w["year"] = year
                year = year or w.get("year")
        year = ov.get("year", year)

        def role(field):
            if field in ov:
                return [people.find(n) for n in ov[field]]
            return split_people(people, credits.get(field, ""))

        singers, lyricists, music = role("singers"), role("lyricists"), role("music")
        src_text = ov.get("source") or credits.get("source") or ""
        src_slug = sources.find(src_text) if src_text and not re.search(r"\(\d{4}\)", src_text) else None

        # Themes: the override, the work and the source text, the playlists, and words in the title.
        th = set(ov.get("themes", []))
        if work_slug:
            th.update(works.items[work_slug].get("themes", []))
        if src_slug:
            th.update(sources.items[src_slug].get("themes", []))
        for t in themes:
            if set(t.get("playlists", [])) & set(in_playlists[vid]):
                th.add(t["key"])
            rx = theme_re.get(t["key"])
            if rx and rx.search(te_title + " " + (works.items[work_slug]["te"] if work_slug else "")):
                th.add(t["key"])

        lyric_blocks = []
        for b in blocks:
            lines = [line_payload(x) for x in b["lines"]]
            lyric_blocks.append({"kind": b["kind"], "heading": b["heading"], "lines": lines})

        lyric_text = " ".join(l["te"] for b in lyric_blocks if b["kind"] == "lyrics" for l in b["lines"] if l)
        songs.append({
            "id": vid,
            "title_raw": title,
            "te": te_title,
            "en": en_title,
            "type": typ,
            "year": year,
            "work": work_slug,
            "singers": [s for s in singers if s],
            "lyricists": [s for s in lyricists if s],
            "music": [s for s in music if s],
            "source": src_slug,
            "themes": sorted(th),
            "published": r.get("published"),
            "duration": r.get("duration"),
            "views": r.get("views"),
            "likes": r.get("likes"),
            "is_short": bool(r.get("is_short")),
            "blocks": lyric_blocks,
            "refs": list(dict.fromkeys(refs)),
            "notes": notes,
            "search_te": re.sub(r"\s+", " ", f"{te_title} {lyric_text}").strip(),
            "search_ro": fold(f"{en_title} {te_title} {lyric_text}"),
        })

    songs.sort(key=lambda s: (s["published"] or "", s["id"]), reverse=True)

    def used(reg, fields):
        counts = Counter()
        for s in songs:
            for f in fields:
                v = s[f]
                for x in (v if isinstance(v, list) else [v]):
                    if x:
                        counts[x] += 1
        return counts

    work_counts = used(works, ["work"])
    src_counts = used(sources, ["source"])
    role_counts = {f: used(people, [f]) for f in ("singers", "lyricists", "music")}

    def export(reg, counts, extra=None):
        out = {}
        for slug, e in reg.items.items():
            if counts[slug]:
                d = {"te": e["te"], "en": e["en"], "count": counts[slug], "curated": e["curated"]}
                for k in ("year", "kind"):
                    if e.get(k):
                        d[k] = e[k]
                if extra:
                    d.update(extra(slug))
                out[slug] = d
        return out

    content = {
        "types": TYPES,
        "themes": [{k: t[k] for k in ("key", "te", "en")} for t in themes],
        "works": export(works, work_counts),
        "sources": export(sources, src_counts),
        "people": export(people, Counter({k: sum(c[k] for c in role_counts.values()) for k in people.items}),
                         lambda slug: {"roles": {f: role_counts[f][slug] for f in role_counts if role_counts[f][slug]}}),
        "songs": songs,
        "unmapped": {
            "people": sorted(people.unmapped),
            "works": sorted(works.unmapped),
            "sources": sorted(sources.unmapped),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(content, ensure_ascii=False, indent=1), "utf-8")

    print(f"songs: {len(songs)}, works: {len(content['works'])}, people: {len(content['people'])}, sources: {len(content['sources'])}")
    for k, v in content["unmapped"].items():
        if v:
            print(f"names not in names.json ({k}): {', '.join(v)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Stage 2: render build/content.json into a static site in dist/.

Usage:
  python3 scripts/build.py              # run parse.py first, then render
  python3 scripts/build.py --base /repo/ # serve the site from a sub-path (GitHub project pages)

The output folder (dist/) has no server code. Any static host can serve it.
"""

import argparse
import datetime as dt
import html
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translit import fold  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ASSETS = ROOT / "site" / "assets"
CONFIG = json.loads((ROOT / "site.config.json").read_text("utf-8"))
LANGS = ("te", "en")

T = {
    "te": {
        "library": "సేకరణ", "films": "చిత్రాలు", "artists": "కళాకారులు", "about": "గురించి",
        "other_lang": "English", "other_lang_code": "en",
        "types": {"padyam": "పద్యం", "shloka": "శ్లోకం", "stotram": "స్తోత్రం", "dandakam": "దండకం", "gadyam": "గద్యం",
                  "keerthana": "కీర్తన", "song": "పాట", "bgm": "నేపథ్య సంగీతం"},
        "kinds": {"film": "చిత్రం", "drama": "నాటకం", "album": "సంపుటి"},
        "singers": "గానం", "lyricists": "రచన", "music": "సంగీతం", "source": "మూలం", "themes": "అంశం",
        "role_singers": "గాయకులు", "role_lyricists": "కవులు, గీత రచయితలు", "role_music": "సంగీత దర్శకులు",
        "f_type": "ప్రక్రియ", "f_decade": "దశాబ్దం", "f_year": "సంవత్సరం", "f_work": "చిత్రం", "f_singer": "గాయకులు",
        "f_lyricist": "కవి / రచయిత", "f_music": "సంగీతం", "f_source": "మూల గ్రంథం", "f_theme": "అంశం", "f_format": "రూపం",
        "shorts": "షార్ట్స్", "videos": "వీడియోలు",
        "sort": "క్రమం", "s_new": "కొత్త అప్‌లోడ్‌లు ముందు", "s_old_film": "పాత చిత్రాలు ముందు", "s_new_film": "కొత్త చిత్రాలు ముందు",
        "s_views": "ఎక్కువ వీక్షణలు", "s_title": "అక్షర క్రమం",
        "search": "పాట, పద్య పంక్తి, చిత్రం లేదా కళాకారుని పేరు…", "search_label": "వెతకండి",
        "results": "{n} అంశాలు", "result_one": "1 అంశం", "clear": "అన్నీ తీసివేయి", "filters": "వడపోత", "close": "మూసివేయి",
        "show": "{n} చూపించు", "none": "ఈ ఎంపికకు సరిపడేది ఏదీ లేదు.", "filter_more": "వెతకండి…",
        "script": "లిపి", "sc_te": "తెలుగు", "sc_ro": "రోమన్", "sc_both": "రెండూ",
        "watch": "యూట్యూబ్‌లో చూడండి", "play": "వీడియో ప్లే చేయండి", "uploaded": "అప్‌లోడ్", "views": "వీక్షణలు", "length": "నిడివి",
        "meaning_note": "", "refs": "ఆధారాలు", "notes": "గమనిక",
        "more_work": "{name} నుండి మరిన్ని", "more_by": "{name} — మరిన్ని", "prev": "మునుపటిది", "next": "తరువాతిది",
        "latest": "తాజా అప్‌లోడ్", "read_listen": "చదవండి, వినండి",
        "st_items": "వీడియోలు", "st_films": "చిత్రాలు", "st_voices": "గాయకులు", "st_poets": "కవులు, రచయితలు", "st_span": "చిత్రాల కాలం",
        "timeline": "కాలరేఖ", "timeline_sub": "చిత్రం విడుదలైన సంవత్సరం వారీగా. ఒక సంవత్సరాన్ని ఎంచుకుంటే సేకరణ వడపోస్తుంది.",
        "library_h": "పూర్తి సేకరణ", "items": "{n} వీడియోలు", "item_one": "1 వీడియో",
        "films_h": "చిత్రాలు, నాటకాలు, సంపుటాలు", "films_sub": "దశాబ్దాల వారీగా. ప్రతి చిత్రంలోని పద్యాలు, పాటలు.",
        "no_year": "సంవత్సరం తెలియనివి",
        "artists_h": "కళాకారులు", "artists_sub": "గాయకులు, కవులు, గీత రచయితలు, సంగీత దర్శకులు.",
        "years_active": "చిత్రాల కాలం", "as_role": "{role}",
        "footer_src": "పద్యాలు, సాహిత్యం, వీడియోలు: {channel} యూట్యూబ్ ఛానెల్.", "updated": "చివరి నవీకరణ",
        "about_h": "ఈ సైట్ గురించి",
        "kicker": "{channel} · యూట్యూబ్ ఛానెల్",
        "h1": "తెలుగు పద్యం,<br>పాట, శ్లోకం —<br><em>సాహిత్యంతో సహా.</em>",
        "lede": "{n} వీడియోలు. ప్రతిదానికీ పూర్తి సాహిత్యం, చిత్రం, కవి, గాయకులు, సంగీత దర్శకుల వివరాలు. సంవత్సరం, చిత్రం, కళాకారుల వారీగా వెతకండి.",
        "untitled_work": "ఇతరాలు",
        "not_found": "ఈ పేజీ దొరకలేదు.", "go_home": "సేకరణకు వెళ్ళండి",
        "theme_toggle": "రంగు మార్చు",
    },
    "en": {
        "library": "Library", "films": "Films", "artists": "Artists", "about": "About",
        "other_lang": "తెలుగు", "other_lang_code": "te",
        "types": {"padyam": "Padyam", "shloka": "Shloka", "stotram": "Stotram", "dandakam": "Dandakam", "gadyam": "Gadyam",
                  "keerthana": "Keerthana", "song": "Song", "bgm": "Background score"},
        "kinds": {"film": "Film", "drama": "Play", "album": "Album"},
        "singers": "Voice", "lyricists": "Words", "music": "Music", "source": "Source text", "themes": "Theme",
        "role_singers": "Singers", "role_lyricists": "Poets & lyricists", "role_music": "Composers",
        "f_type": "Form", "f_decade": "Decade", "f_year": "Year", "f_work": "Film", "f_singer": "Singer",
        "f_lyricist": "Poet / lyricist", "f_music": "Composer", "f_source": "Source text", "f_theme": "Theme", "f_format": "Format",
        "shorts": "Shorts", "videos": "Videos",
        "sort": "Sort", "s_new": "Newest uploads", "s_old_film": "Oldest films first", "s_new_film": "Newest films first",
        "s_views": "Most viewed", "s_title": "Title A–Z",
        "search": "A title, a line of verse, a film or an artist…", "search_label": "Search",
        "results": "{n} pieces", "result_one": "1 piece", "clear": "Clear all", "filters": "Filters", "close": "Close",
        "show": "Show {n}", "none": "Nothing matches these filters.", "filter_more": "Find…",
        "script": "Script", "sc_te": "Telugu", "sc_ro": "Roman", "sc_both": "Both",
        "watch": "Watch on YouTube", "play": "Play video", "uploaded": "Uploaded", "views": "Views", "length": "Length",
        "meaning_note": "in Telugu", "refs": "References", "notes": "Note",
        "more_work": "More from {name}", "more_by": "More with {name}", "prev": "Previous", "next": "Next",
        "latest": "Latest upload", "read_listen": "Read and listen",
        "st_items": "videos", "st_films": "films", "st_voices": "voices", "st_poets": "poets & lyricists", "st_span": "film years",
        "timeline": "Timeline", "timeline_sub": "By the year the film came out. Pick a year to filter the library.",
        "library_h": "The library", "items": "{n} videos", "item_one": "1 video",
        "films_h": "Films, plays and albums", "films_sub": "By decade, with every padyam and song from each one.",
        "no_year": "Year not known",
        "artists_h": "Artists", "artists_sub": "Singers, poets, lyricists and composers.",
        "years_active": "Film years", "as_role": "{role}",
        "footer_src": "Verses, words and videos from the {channel} YouTube channel.", "updated": "Last updated",
        "about_h": "About this site",
        "kicker": "From the {channel} YouTube channel",
        "h1": "Telugu verse<br>and song —<br><em>with the words.</em>",
        "lede": "{n} recordings of padyams, shlokas and film songs. Each one has the full text in Telugu and Roman script, with the film, poet, singers and composer. Browse by year, film or artist.",
        "untitled_work": "Other",
        "not_found": "This page does not exist.", "go_home": "Go to the library",
        "theme_toggle": "Change colour theme",
    },
}

MONTHS = {
    "te": ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జూలై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def fmt_date(iso, lang):
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MONTHS[lang][int(m) - 1]} {y}"


def fmt_dur(sec):
    if not sec:
        return ""
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def fmt_num(n):
    return f"{n:,}" if isinstance(n, int) else ""


class Site:
    def __init__(self, content, base):
        self.c = content
        self.base = base
        self.songs = content["songs"]
        self.by_id = {s["id"]: s for s in self.songs}
        self.works = content["works"]
        self.people = content["people"]
        self.sources = content["sources"]
        self.themes = {t["key"]: t for t in content["themes"]}
        self.built = dt.datetime.now(dt.timezone.utc)
        # The SITE_URL variable (set by the GitHub workflow) wins over the config file.
        self.site_url = (os.environ.get("SITE_URL") or CONFIG["site"]["base_url"]).rstrip("/")
        self.pages = []

    # ------------------------------------------------------------ helpers

    def u(self, path=""):
        return self.base + path.lstrip("/")

    def name(self, entity, lang):
        return entity["te"] if lang == "te" else entity["en"]

    def person_link(self, slug, lang):
        p = self.people[slug]
        return f'<a href="{self.u(f"{lang}/artist/{slug}/")}">{esc(self.name(p, lang))}</a>'

    def work_label(self, slug, lang, link=True):
        w = self.works[slug]
        nm = esc(self.name(w, lang))
        yr = f' <span class="yr">{w["year"]}</span>' if w.get("year") else ""
        if link:
            return f'<a href="{self.u(f"{lang}/film/{slug}/")}">{nm}</a>{yr}'
        return f"{nm}{yr}"

    def primary_title(self, s, lang):
        return (s["te"], "te") if lang == "te" else (s["en"], "en")

    def secondary_title(self, s, lang):
        return (s["en"], "en") if lang == "te" else (s["te"], "te")

    def write(self, rel, text):
        p = DIST / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")

    def page(self, lang, rel_path, title, body, *, desc="", alt_path=None, kind="page", image=None, head_extra="", noindex=False):
        """Wrap the body in the full HTML document and write it."""
        t = T[lang]
        alt_path = alt_path if alt_path is not None else rel_path.replace(f"{lang}/", f"{t['other_lang_code']}/", 1)
        site_name = CONFIG["site"][f"name_{lang}"]
        full_title = f"{title} · {site_name}" if title else f"{site_name} — {CONFIG['site'][f'tagline_{lang}']}"
        canonical = f"{self.site_url}/{rel_path}"
        nav = [("library", f"{lang}/"), ("films", f"{lang}/films/"), ("artists", f"{lang}/artists/"), ("about", f"{lang}/about/")]
        nav_html = "".join(
            f'<a href="{self.u(href)}"{" aria-current=page" if kind == k else ""}>{esc(t[k])}</a>' for k, href in nav
        )
        image = image or f"https://i.ytimg.com/vi/{self.songs[0]['id']}/hqdefault.jpg"
        alts = "".join(
            f'<link rel="alternate" hreflang="{l}" href="{self.site_url}/{rel_path.replace(f"{lang}/", f"{l}/", 1)}">' for l in LANGS
        )
        doc = f"""<!doctype html>
<html lang="{lang}" data-lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc or CONFIG['site'][f'tagline_{lang}'])}">
<link rel="canonical" href="{esc(canonical)}">
{alts}
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc or CONFIG['site'][f'tagline_{lang}'])}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(image)}">
<meta name="twitter:card" content="summary_large_image">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta name="theme-color" content="#f4efe6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14110e" media="(prefers-color-scheme: dark)">
<meta name="site-base" content="{esc(self.base)}">
<link rel="icon" href="{self.u('assets/mark.svg')}" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anek+Telugu:wdth,wght@75..100,300..700&family=Tiro+Telugu:ital@0;1&display=swap">
<link rel="stylesheet" href="{self.u('assets/style.css')}?v={self.built:%Y%m%d%H%M}">
<script>try{{var m=localStorage.getItem('theme');if(m)document.documentElement.dataset.theme=m}}catch(e){{}}</script>
{head_extra}
</head>
<body class="k-{kind}">
<a class="skip" href="#main">{'ప్రధాన భాగానికి వెళ్ళండి' if lang == 'te' else 'Skip to content'}</a>
<header class="mast">
 <div class="mast-in">
  <a class="brand" href="{self.u(f'{lang}/')}" aria-label="{esc(site_name)}">
   <svg class="brand-mark" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="7" width="4" height="14" rx="2"/><rect x="10" y="3" width="4" height="18" rx="2"/><rect x="17" y="7" width="4" height="14" rx="2"/></svg>
   <span class="brand-te" lang="te">{esc(CONFIG['site']['name_te'])}</span>
   <span class="brand-en" lang="en">{esc(CONFIG['site']['name_en'])}</span>
  </a>
  <nav class="nav" aria-label="{'ప్రధాన మెను' if lang == 'te' else 'Main'}">{nav_html}</nav>
  <div class="tools">
   <a class="lang-switch" href="{self.u(alt_path)}" hreflang="{t['other_lang_code']}" lang="{t['other_lang_code']}" data-set-lang="{t['other_lang_code']}">{esc(t['other_lang'])}</a>
   <button class="theme-btn" type="button" aria-label="{esc(t['theme_toggle'])}" title="{esc(t['theme_toggle'])}">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor"/></svg>
   </button>
  </div>
 </div>
</header>
<main id="main">
{body}
</main>
<footer class="foot">
 <div class="foot-in">
  <p class="foot-motto" lang="te">{esc(CONFIG['channel']['motto_te'])}</p>
  <p>{t['footer_src'].format(channel=f'<a href="{esc(CONFIG["channel"]["url"])}" rel="noopener">{esc(CONFIG["channel"]["name"])}</a>')}</p>
  <p class="foot-meta">{esc(t['updated'])}: <time datetime="{self.built.isoformat()}">{fmt_date(self.built.date().isoformat(), lang)}</time></p>
 </div>
</footer>
<script src="{self.u('assets/app.js')}?v={self.built:%Y%m%d%H%M}" defer></script>
</body>
</html>
"""
        self.write(rel_path + ("index.html" if rel_path.endswith("/") or rel_path == "" else ""), doc)
        if not noindex:
            self.pages.append(rel_path)

    # ------------------------------------------------------------ fragments

    def entry_row(self, s, lang, compact=False):
        t = T[lang]
        p_title, p_lang = self.primary_title(s, lang)
        s_title, s_lang = self.secondary_title(s, lang)
        meta = []
        if s["singers"]:
            meta.append(", ".join(esc(self.name(self.people[x], lang)) for x in s["singers"][:2]))
        if s["work"]:
            meta.append(esc(self.name(self.works[s["work"]], lang)))
        elif s["lyricists"]:
            meta.append(esc(self.name(self.people[s["lyricists"][0]], lang)))
        year = s["year"] or ""
        short = f'<span class="tag-short">{esc(t["shorts"][:-1] if lang == "en" else "షార్ట్")}</span>' if s["is_short"] else ""
        return f"""<li class="entry" data-id="{s['id']}">
<a class="entry-a" href="{self.u(f"{lang}/v/{s['id']}/")}">
<span class="thumb"><img src="https://i.ytimg.com/vi/{s['id']}/mqdefault.jpg" alt="" loading="lazy" decoding="async" width="320" height="180"><span class="dur">{fmt_dur(s['duration'])}</span></span>
<span class="entry-main">
<span class="entry-type">{esc(t['types'][s['type']])}{short}</span>
<span class="entry-title" lang="{p_lang}">{esc(p_title)}</span>
{'' if compact else f'<span class="entry-alt" lang="{s_lang}">{esc(s_title)}</span>'}
<span class="entry-meta">{' · '.join(meta)}</span>
</span>
<span class="entry-year">{year}</span>
</a>
</li>"""

    def entry_list(self, songs, lang, compact=False, cls=""):
        return f'<ol class="entries {cls}">' + "\n".join(self.entry_row(s, lang, compact) for s in songs) + "</ol>"

    def verse_html(self, s, lang, limit=None, preview=False):
        t = T[lang]
        out = []
        count = 0
        for b in s["blocks"]:
            if b["kind"] == "meaning" and preview:
                continue
            cls = "block meaning" if b["kind"] == "meaning" else "block lyrics"
            head = ""
            if b["heading"]:
                note = f' <span class="note">({esc(t["meaning_note"])})</span>' if b["kind"] == "meaning" and t["meaning_note"] else ""
                head = f'<h2 class="block-h"><span lang="te">{esc(b["heading"])}</span>{note}</h2>'
            lines = []
            for l in b["lines"]:
                if limit and count >= limit:
                    break
                if l is None:
                    lines.append('<span class="gap" aria-hidden="true"></span>')
                    continue
                count += 1
                sp = ""
                if l["sp"]:
                    sp = f'<span class="sp"><span class="te" lang="te">{esc(l["sp"])}</span><span class="ro">{esc(l["sp_ro"])}</span></span>'
                ro = "" if b["kind"] == "meaning" else f'<span class="ro" lang="te-Latn">{esc(l["ro"])}</span>'
                lines.append(f'<p class="l{" in" if l["in"] else ""}">{sp}<span class="te" lang="te">{esc(l["te"])}</span>{ro}</p>')
            if lines:
                out.append(f'<section class="{cls}">{head}{"".join(lines)}</section>')
            if limit and count >= limit:
                break
        return "".join(out)

    # ------------------------------------------------------------ catalog

    def catalog(self, lang):
        """The data that the library page uses for filters, counts and search."""
        items = []
        for s in self.songs:
            w = self.works.get(s["work"]) if s["work"] else None
            ppl = s["singers"] + s["lyricists"] + s["music"]
            items.append({
                "id": s["id"], "ty": s["type"], "y": s["year"], "w": s["work"], "s": s["singers"], "l": s["lyricists"],
                "m": s["music"], "src": s["source"], "th": s["themes"], "sh": s["is_short"], "p": s["published"],
                "v": s["views"] or 0, "t": s["te"] if lang == "te" else s["en"],
                # kt: Telugu text to match a Telugu query. kr: folded Roman text to match a Roman query.
                "kt": " ".join(filter(None, [s["te"], w and w["te"]] + [self.people[x]["te"] for x in ppl])),
                "kr": fold(" ".join(filter(None, [s["en"], s["te"], w and w["en"]] + [self.people[x]["en"] for x in ppl]))),
            })
        labels = {
            "ty": {k: T[lang]["types"][k] for k in self.c["types"]},
            "w": {k: self.name(v, lang) + (f" ({v['year']})" if v.get("year") else "") for k, v in self.works.items()},
            "p": {k: self.name(v, lang) for k, v in self.people.items()},
            "src": {k: self.name(v, lang) for k, v in self.sources.items()},
            "th": {k: self.name(v, lang) for k, v in self.themes.items()},
            "sh": {"1": T[lang]["shorts"], "0": T[lang]["videos"]},
        }
        return {"items": items, "labels": labels}

    def search_index(self):
        return {s["id"]: [s["search_te"], s["search_ro"]] for s in self.songs}

    # ------------------------------------------------------------ pages

    def home(self, lang):
        t = T[lang]
        ch = CONFIG["channel"]
        latest = next((s for s in self.songs if s["blocks"]), self.songs[0])
        years = [s["year"] for s in self.songs if s["year"]]
        voices = {x for s in self.songs for x in s["singers"]}
        poets = {x for s in self.songs for x in s["lyricists"]}
        films = {s["work"] for s in self.songs if s["work"] and not self.works[s["work"]].get("kind")}
        y0, y1 = min(years), max(years)

        lp, lpl = self.primary_title(latest, lang)
        credits = []
        if latest["work"]:
            credits.append(self.work_label(latest["work"], lang, link=False))
        if latest["singers"]:
            credits.append(", ".join(esc(self.name(self.people[x], lang)) for x in latest["singers"]))
        mission = ch["mission_te"] if lang == "te" else ch["mission_en"]

        # Timeline: one column for each year from the first decade to the last.
        by_year = defaultdict(int)
        for y in years:
            by_year[y] += 1
        start, end = (y0 // 10) * 10, (y1 // 10) * 10 + 9
        peak = max(by_year.values())
        cols = []
        for y in range(start, end + 1):
            n = by_year.get(y, 0)
            lab = f'<span class="tl-dec">{y}</span>' if y % 10 == 0 else ""
            if n:
                cols.append(f'<a class="tl-y on" href="?year={y}#library" data-year="{y}" style="--h:{n / peak:.3f}" title="{y} · {n}"><span class="tl-bar"></span><span class="tl-n">{n}</span>{lab}</a>')
            else:
                cols.append(f'<span class="tl-y" aria-hidden="true"><span class="tl-bar"></span>{lab}</span>')

        def sel_opts():
            return "".join(f'<option value="{k}">{esc(t[f"s_{k}"])}</option>' for k in ("new", "old_film", "new_film", "views", "title"))

        n_items = len(self.songs)
        body = f"""
<section class="opener wrap">
 <div class="op-text">
  <p class="kicker">{t['kicker'].format(channel=f'<a href="{esc(ch["url"])}" rel="noopener">{esc(ch["name"])}</a>')}</p>
  <h1 class="op-h">{t['h1']}</h1>
  <p class="op-lede">{esc(t['lede'].format(n=n_items))}</p>
  <figure class="mission">
   <blockquote lang="{lang}">{esc(mission)}</blockquote>
   <figcaption>— {esc(ch['name'])}</figcaption>
  </figure>
 </div>
 <a class="op-verse" href="{self.u(f"{lang}/v/{latest['id']}/")}">
  <span class="op-verse-k">{esc(t['latest'])} · {esc(t['types'][latest['type']])}</span>
  <span class="op-verse-body" lang="te">{''.join(f'<span class="{"in" if l["in"] else ""}">{esc(l["te"])}</span>' for b in latest['blocks'][:1] for l in b['lines'][:8] if l)}</span>
  <span class="op-verse-t" lang="{lpl}">{esc(lp)}</span>
  <span class="op-verse-c">{' · '.join(credits)}</span>
  <span class="op-verse-go">{esc(t['read_listen'])} <span aria-hidden="true">→</span></span>
 </a>
</section>

<section class="ledger wrap" aria-label="{'గణాంకాలు' if lang == 'te' else 'Numbers'}">
 <div><b>{n_items}</b><span>{esc(t['st_items'])}</span></div>
 <div><b>{len(films)}</b><span>{esc(t['st_films'])}</span></div>
 <div><b>{len(voices)}</b><span>{esc(t['st_voices'])}</span></div>
 <div><b>{len(poets)}</b><span>{esc(t['st_poets'])}</span></div>
 <div><b>{y0}–{y1}</b><span>{esc(t['st_span'])}</span></div>
</section>

<section class="timeline wrap" aria-labelledby="tl-h">
 <div class="sec-head">
  <h2 id="tl-h" class="sec-h">{esc(t['timeline'])}</h2>
  <p class="sec-sub">{esc(t['timeline_sub'])}</p>
 </div>
 <div class="tl" role="list">{''.join(cols)}</div>
</section>

<section class="library wrap" id="library" aria-labelledby="lib-h">
 <div class="sec-head">
  <h2 id="lib-h" class="sec-h">{esc(t['library_h'])}</h2>
 </div>
 <div class="lib-bar">
  <label class="search">
   <span class="vh">{esc(t['search_label'])}</span>
   <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m15.5 15.5 5 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
   <input type="search" id="q" placeholder="{esc(t['search'])}" autocomplete="off" spellcheck="false">
  </label>
  <label class="sort"><span>{esc(t['sort'])}</span><select id="sort">{sel_opts()}</select></label>
  <button class="filters-btn" type="button" id="filters-open" aria-controls="facets">{esc(t['filters'])}<span class="fcount" id="fcount"></span></button>
 </div>
 <div class="lib-status"><p id="count" aria-live="polite">{esc(t['items'].format(n=n_items))}</p><div class="chips" id="chips"></div></div>
 <div class="lib-grid">
  <aside class="facets" id="facets" aria-label="{esc(t['filters'])}">
   <div class="facets-head"><b>{esc(t['filters'])}</b><button type="button" class="facets-close" id="filters-close">{esc(t['close'])}</button></div>
   <div id="facet-groups"></div>
   <div class="facets-foot"><button type="button" class="btn-ghost" id="clear-all">{esc(t['clear'])}</button><button type="button" class="btn" id="filters-done"></button></div>
  </aside>
  <div class="results">
   {self.entry_list(self.songs, lang, cls="lib-list")}
   <p class="empty" id="empty" hidden>{esc(t['none'])}</p>
  </div>
 </div>
</section>
<script type="application/json" id="catalog">{json.dumps(self.catalog(lang), ensure_ascii=False, separators=(",", ":"))}</script>
<script type="application/json" id="i18n">{json.dumps({k: t[k] for k in ("results", "result_one", "clear", "show", "filter_more", "f_type", "f_decade", "f_year", "f_work", "f_singer", "f_lyricist", "f_music", "f_source", "f_theme", "f_format")}, ensure_ascii=False)}</script>
"""
        self.page(lang, f"{lang}/", "", body, kind="library", desc=t["lede"].format(n=n_items))

    def song_page(self, s, idx, lang):
        t = T[lang]
        p_title, p_lang = self.primary_title(s, lang)
        s_title, s_lang = self.secondary_title(s, lang)
        rows = []
        if s["work"]:
            w = self.works[s["work"]]
            rows.append((t["kinds"][w.get("kind", "film")], self.work_label(s["work"], lang)))
        if s["source"]:
            rows.append((t["source"], esc(self.name(self.sources[s["source"]], lang))))
        for role in ("lyricists", "music", "singers"):
            if s[role]:
                rows.append((t[role], ", ".join(self.person_link(x, lang) for x in s[role])))
        if s["themes"]:
            rows.append((t["themes"], " ".join(f'<a class="pill" href="{self.u(f"{lang}/?theme={k}#library")}">{esc(self.name(self.themes[k], lang))}</a>' for k in s["themes"] if k in self.themes)))
        stats = []
        if s["published"]:
            stats.append((t["uploaded"], fmt_date(s["published"], lang)))
        if s["duration"]:
            stats.append((t["length"], fmt_dur(s["duration"])))
        if s["views"]:
            stats.append((t["views"], fmt_num(s["views"])))
        colophon = "".join(f"<div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in rows)
        statline = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in stats)

        verse = self.verse_html(s, lang)
        has_lyrics = any(b["kind"] == "lyrics" for b in s["blocks"])
        toggle = ""
        if has_lyrics:
            toggle = f"""<div class="script" role="group" aria-label="{esc(t['script'])}">
<span class="script-l">{esc(t['script'])}</span>
<button type="button" data-script="te" lang="te">{esc(T['te']['sc_te'])}</button><button type="button" data-script="ro">{esc(t['sc_ro'])}</button><button type="button" data-script="both">{esc(t['sc_both'])}</button>
</div>"""
        extras = ""
        if s["notes"]:
            extras += f'<p class="src-note"><b>{esc(t["notes"])}:</b> {esc(" ".join(s["notes"]))}</p>'
        if s["refs"]:
            extras += f'<div class="refs"><h2 class="block-h">{esc(t["refs"])}</h2><ul>' + "".join(
                f'<li><a href="{esc(r)}" rel="noopener nofollow">{esc(urlparse(r).netloc.replace("www.", ""))}</a></li>' for r in s["refs"]
            ) + "</ul></div>"

        # Related: the same work first, then the first singer, then the first poet.
        related = []
        seen = {s["id"]}
        if s["work"]:
            same = [x for x in self.songs if x["work"] == s["work"] and x["id"] not in seen][:6]
            if same:
                seen.update(x["id"] for x in same)
                related.append((t["more_work"].format(name=self.name(self.works[s["work"]], lang)), same))
        for role in ("singers", "lyricists"):
            if s[role]:
                pid = s[role][0]
                same = [x for x in self.songs if pid in x[role] and x["id"] not in seen][:6]
                if same:
                    seen.update(x["id"] for x in same)
                    related.append((t["more_by"].format(name=self.name(self.people[pid], lang)), same))
                    break
        rel_html = "".join(
            f'<section class="rel"><h2 class="sec-h sm">{esc(h)}</h2>{self.entry_list(lst, lang, compact=True, cls="grid-list")}</section>' for h, lst in related
        )
        prev_s = self.songs[idx + 1] if idx + 1 < len(self.songs) else None
        next_s = self.songs[idx - 1] if idx > 0 else None

        def pn(x, label, cls):
            if not x:
                return "<span></span>"
            tt, tl = self.primary_title(x, lang)
            return f'<a class="pn {cls}" href="{self.u(f"{lang}/v/{x["id"]}/")}"><span class="pn-l">{esc(label)}</span><span class="pn-t" lang="{tl}">{esc(tt)}</span></a>'

        first_lines = " / ".join(l["te"] for b in s["blocks"][:1] for l in b["lines"][:2] if l)
        crumbs_type = f'<a href="{self.u(f"{lang}/?type={s["type"]}#library")}">{esc(t["types"][s["type"]])}</a>'
        year_bit = f' · <a href="{self.u(f"{lang}/?year={s["year"]}#library")}">{s["year"]}</a>' if s["year"] else ""
        ld = {
            "@context": "https://schema.org", "@type": "VideoObject", "name": s["title_raw"],
            "description": first_lines or s["title_raw"], "thumbnailUrl": f"https://i.ytimg.com/vi/{s['id']}/hqdefault.jpg",
            "uploadDate": s["published"], "embedUrl": f"https://www.youtube-nocookie.com/embed/{s['id']}", "inLanguage": "te",
        }
        if s["duration"]:
            ld["duration"] = f"PT{int(s['duration'])}S"

        body = f"""
<article class="song wrap" data-default-script="{'te' if lang == 'te' else 'both'}">
 <header class="song-head">
  <p class="kicker">{crumbs_type}{year_bit}</p>
  <h1 class="song-h" lang="{p_lang}">{esc(p_title)}</h1>
  <p class="song-alt" lang="{s_lang}">{esc(s_title)}</p>
 </header>
 <div class="song-grid">
  <aside class="song-aside">
   <div class="player{' is-short' if s['is_short'] else ''}">
    <button type="button" class="yt" data-id="{s['id']}" aria-label="{esc(t['play'])}: {esc(p_title)}">
     <img src="https://i.ytimg.com/vi/{s['id']}/hqdefault.jpg" alt="" decoding="async">
     <span class="yt-play" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z"/></svg></span>
    </button>
   </div>
   <dl class="colophon">{colophon}</dl>
   <dl class="statline">{statline}</dl>
   <a class="yt-link" href="https://www.youtube.com/watch?v={s['id']}" rel="noopener">{esc(t['watch'])} <span aria-hidden="true">↗</span></a>
  </aside>
  <div class="song-text">
   {toggle}
   <div class="verse" id="verse">{verse}</div>
   {'<p class="end-mark" aria-hidden="true">॥</p>' if has_lyrics else ''}
   {extras}
  </div>
 </div>
 <nav class="prevnext">{pn(prev_s, t['prev'], 'prev')}{pn(next_s, t['next'], 'next')}</nav>
 {rel_html}
</article>
"""
        desc = f"{s['te']} — {s['en']}. " + (first_lines[:140] if first_lines else "")
        self.page(lang, f"{lang}/v/{s['id']}/", p_title, body, kind="song", desc=desc,
                  image=f"https://i.ytimg.com/vi/{s['id']}/hqdefault.jpg",
                  head_extra=f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>')

    def films_index(self, lang):
        t = T[lang]
        groups = defaultdict(list)
        for slug, w in self.works.items():
            dec = (w["year"] // 10) * 10 if w.get("year") else None
            groups[dec].append((slug, w))
        out = []
        for dec in sorted(groups, key=lambda d: (d is None, d or 0)):
            items = sorted(groups[dec], key=lambda x: (x[1].get("year") or 0, self.name(x[1], lang)))
            rows = []
            for slug, w in items:
                songs = [s for s in self.songs if s["work"] == slug]
                singers = []
                for s in songs:
                    for p in s["singers"]:
                        if p not in singers:
                            singers.append(p)
                kind = f'<span class="kind">{esc(t["kinds"][w["kind"]])}</span>' if w.get("kind") else ""
                rows.append(f"""<li><a href="{self.u(f"{lang}/film/{slug}/")}">
<span class="fy">{w.get('year') or '—'}</span>
<span class="fn"><span class="fn-p" lang="{lang}">{esc(self.name(w, lang))}</span>{kind}<span class="fn-s" lang="{'en' if lang == 'te' else 'te'}">{esc(w['en'] if lang == 'te' else w['te'])}</span></span>
<span class="fv">{', '.join(esc(self.name(self.people[p], lang)) for p in singers[:3])}</span>
<span class="fc">{len(songs)}</span>
</a></li>""")
            label = f"{dec}s" if dec and lang == "en" else (f"{dec}లు" if dec else t["no_year"])
            out.append(f'<section class="dec"><h2 class="dec-h">{esc(label)}</h2><ol class="films">{"".join(rows)}</ol></section>')
        body = f"""
<section class="wrap page-head"><h1 class="page-h">{esc(t['films_h'])}</h1><p class="sec-sub">{esc(t['films_sub'])}</p></section>
<div class="wrap films-wrap">{''.join(out)}</div>"""
        self.page(lang, f"{lang}/films/", t["films"], body, kind="films", desc=t["films_sub"])

    def film_page(self, slug, lang):
        t = T[lang]
        w = self.works[slug]
        songs = [s for s in self.songs if s["work"] == slug]
        songs.sort(key=lambda s: s["published"] or "")
        crew = {}
        for role in ("music", "lyricists", "singers"):
            ids = []
            for s in songs:
                for p in s[role]:
                    if p not in ids:
                        ids.append(p)
            if ids:
                crew[role] = ids
        crew_html = "".join(f"<div><dt>{esc(t[r])}</dt><dd>{', '.join(self.person_link(p, lang) for p in ids)}</dd></div>" for r, ids in crew.items())
        kind = t["kinds"][w.get("kind", "film")]
        yr = f' · <a href="{self.u(f"{lang}/?year={w["year"]}#library")}">{w["year"]}</a>' if w.get("year") else ""
        count = t["item_one"] if len(songs) == 1 else t["items"].format(n=len(songs))
        body = f"""
<section class="wrap page-head entity-head">
 <p class="kicker"><a href="{self.u(f'{lang}/films/')}">{esc(kind)}</a>{yr}</p>
 <h1 class="page-h" lang="{lang}">{esc(self.name(w, lang))}</h1>
 <p class="song-alt" lang="{'en' if lang == 'te' else 'te'}">{esc(w['en'] if lang == 'te' else w['te'])}</p>
 <dl class="colophon wide">{crew_html}</dl>
</section>
<section class="wrap"><h2 class="sec-h sm">{esc(count)}</h2>{self.entry_list(songs, lang)}</section>"""
        name = self.name(w, lang) + (f" ({w['year']})" if w.get("year") else "")
        self.page(lang, f"{lang}/film/{slug}/", name, body, kind="films", desc=f"{name} — {count}")

    def artists_index(self, lang):
        t = T[lang]
        secs = []
        for role in ("singers", "lyricists", "music"):
            ppl = [(slug, p) for slug, p in self.people.items() if p["roles"].get(role)]
            ppl.sort(key=lambda x: self.name(x[1], lang).lower())
            top = sorted(ppl, key=lambda x: -x[1]["roles"][role])[:4]
            top_html = "".join(
                f'<li><a href="{self.u(f"{lang}/artist/{slug}/")}"><span class="an">{esc(self.name(p, lang))}</span><span class="ac">{p["roles"][role]}</span></a></li>' for slug, p in top
            )
            all_html = "".join(
                f'<li><a href="{self.u(f"{lang}/artist/{slug}/")}"><span class="an">{esc(self.name(p, lang))}</span><span class="ac">{p["roles"][role]}</span></a></li>' for slug, p in ppl
            )
            secs.append(f"""<section class="role" id="{role}">
<h2 class="sec-h">{esc(t[f'role_{role}'])} <span class="sec-n">{len(ppl)}</span></h2>
<ol class="top-artists">{top_html}</ol>
<ol class="artists">{all_html}</ol>
</section>""")
        jump = "".join(f'<a href="#{r}">{esc(t[f"role_{r}"])}</a>' for r in ("singers", "lyricists", "music"))
        body = f"""
<section class="wrap page-head"><h1 class="page-h">{esc(t['artists_h'])}</h1><p class="sec-sub">{esc(t['artists_sub'])}</p><nav class="jump">{jump}</nav></section>
<div class="wrap">{''.join(secs)}</div>"""
        self.page(lang, f"{lang}/artists/", t["artists"], body, kind="artists", desc=t["artists_sub"])

    def artist_page(self, slug, lang):
        t = T[lang]
        p = self.people[slug]
        sections = []
        all_songs = []
        for role in ("singers", "lyricists", "music"):
            songs = [s for s in self.songs if slug in s[role]]
            if songs:
                songs.sort(key=lambda s: (s["year"] or 9999, s["published"] or ""))
                all_songs += songs
                sections.append(f'<section class="wrap"><h2 class="sec-h sm">{esc(t[f"role_{role}"])} <span class="sec-n">{len(songs)}</span></h2>{self.entry_list(songs, lang)}</section>')
        years = sorted({s["year"] for s in all_songs if s["year"]})
        roles_txt = " · ".join(f'{esc(t[r])} {n}' for r, n in p["roles"].items())
        span = f"<div><dt>{esc(t['years_active'])}</dt><dd>{years[0]}–{years[-1]}</dd></div>" if len(years) > 1 else (f"<div><dt>{esc(t['years_active'])}</dt><dd>{years[0]}</dd></div>" if years else "")
        films = []
        for s in all_songs:
            if s["work"] and s["work"] not in films:
                films.append(s["work"])
        films_html = f"<div><dt>{esc(t['films'])}</dt><dd>{', '.join(self.work_label(w, lang) for w in films[:12])}</dd></div>" if films else ""
        body = f"""
<section class="wrap page-head entity-head">
 <p class="kicker"><a href="{self.u(f'{lang}/artists/')}">{esc(t['artists'])}</a> · {roles_txt}</p>
 <h1 class="page-h" lang="{lang}">{esc(self.name(p, lang))}</h1>
 <p class="song-alt" lang="{'en' if lang == 'te' else 'te'}">{esc(p['en'] if lang == 'te' else p['te'])}</p>
 <dl class="colophon wide">{span}{films_html}</dl>
</section>
{''.join(sections)}"""
        self.page(lang, f"{lang}/artist/{slug}/", self.name(p, lang), body, kind="artists", desc=f"{self.name(p, lang)} — {roles_txt}")

    def about(self, lang):
        t = T[lang]
        ch = CONFIG["channel"]
        if lang == "te":
            text = f"""
<p>ఈ సైట్‌లోని ప్రతి పద్యం, శ్లోకం, పాట <a href="{esc(ch['url'])}" rel="noopener">{esc(ch['name'])}</a> యూట్యూబ్ ఛానెల్ నుండి వచ్చినవి. ఛానెల్ ఆశయం: <q>{esc(ch['mission_te'])}</q>.</p>
<p>ప్రతి వీడియో వివరణలో చిత్రం, రచన, సంగీతం, గానం, పూర్తి సాహిత్యం ఉంటాయి. ఈ సైట్ ఆ వివరాలను చదివి, సంవత్సరం, చిత్రం, కవి, గాయకుల వారీగా అమర్చుతుంది.</p>
<p>తెలుగు లిపి చదవలేని వారి కోసం ప్రతి పంక్తిని రోమన్ లిపిలో కూడా చూపిస్తుంది. ప్రతి పాట పేజీలో „లిపి“ మీట నొక్కి మార్చుకోవచ్చు.</p>
<h2 class="sec-h sm">కొత్త వీడియోలు</h2>
<p>ఛానెల్‌లో కొత్త వీడియో వచ్చిన కొన్ని నిమిషాల్లోనే అది ఈ సైట్‌లో కనిపిస్తుంది.</p>
<h2 class="sec-h sm">తప్పులు</h2>
<p>ఏదైనా వివరం తప్పుగా ఉంటే, ఆ వీడియో కింద యూట్యూబ్‌లో వ్యాఖ్య రాయండి.</p>"""
        else:
            text = f"""
<p>Every padyam, shloka and song on this site comes from the <a href="{esc(ch['url'])}" rel="noopener">{esc(ch['name'])}</a> YouTube channel. In the channel's own words: <q>{esc(ch['mission_en'])}</q>.</p>
<p>Each video description lists the film, the poet or lyricist, the composer and the singers, followed by the full text. This site reads those details and arranges the collection by year, film, poet and singer.</p>
<p>Every line also appears in Roman script, for readers who do not read Telugu script. On each song page, use the <b>Script</b> switch to show Telugu, Roman or both.</p>
<h2 class="sec-h sm">New videos</h2>
<p>The site updates itself. A new video on the channel appears here within a few minutes.</p>
<h2 class="sec-h sm">Corrections</h2>
<p>If a detail is wrong, leave a comment under the video on YouTube.</p>"""
        body = f'<section class="wrap page-head"><h1 class="page-h">{esc(t["about_h"])}</h1></section><div class="wrap prose">{text}</div>'
        self.page(lang, f"{lang}/about/", t["about"], body, kind="about")

    def not_found(self):
        t = T["en"]
        body = f"""<section class="wrap page-head nf"><p class="nf-mark" lang="te">॥</p>
<h1 class="page-h"><span lang="te">{esc(T['te']['not_found'])}</span><br>{esc(t['not_found'])}</h1>
<p><a class="btn" href="{self.u('te/')}" lang="te">{esc(T['te']['go_home'])}</a> <a class="btn-ghost" href="{self.u('en/')}">{esc(t['go_home'])}</a></p></section>"""
        self.page("en", "404.html", "404", body, kind="nf", alt_path="te/", noindex=True)

    def root(self):
        dl = CONFIG["site"].get("default_lang", "te")
        doc = f"""<!doctype html>
<html lang="te"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(CONFIG['site']['name_te'])} · {esc(CONFIG['site']['name_en'])}</title>
<link rel="canonical" href="{self.site_url}/{dl}/">
<link rel="alternate" hreflang="te" href="{self.site_url}/te/"><link rel="alternate" hreflang="en" href="{self.site_url}/en/">
<script>(function(){{var l;try{{l=localStorage.getItem('lang')}}catch(e){{}}
if(!l){{var n=(navigator.languages||[navigator.language||'']).join(',').toLowerCase();l=/(^|,)te/.test(n)?'te':(/(^|,)en/.test(n)&&!/(^|,)te/.test(n)?'{dl}':'{dl}')}}
location.replace('{self.base}'+(l==='en'?'en':'te')+'/'+location.search+location.hash)}})()</script>
<style>body{{font:18px/1.6 system-ui;background:#f4efe6;color:#1d1915;display:grid;place-items:center;min-height:100vh;margin:0}}a{{color:#9e2f18;margin:0 .6em}}</style>
</head><body><p><a href="{self.u('te/')}" lang="te">తెలుగు</a><a href="{self.u('en/')}">English</a></p></body></html>"""
        self.write("index.html", doc)

    def sitemap(self):
        urls = "".join(f"<url><loc>{esc(self.site_url)}/{esc(p)}</loc></url>" for p in self.pages)
        self.write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
        self.write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {self.site_url}/sitemap.xml\n")

    def build(self):
        if DIST.exists():
            shutil.rmtree(DIST)
        shutil.copytree(ASSETS, DIST / "assets")
        for lang in LANGS:
            self.home(lang)
            for i, s in enumerate(self.songs):
                self.song_page(s, i, lang)
            self.films_index(lang)
            for slug in self.works:
                self.film_page(slug, lang)
            self.artists_index(lang)
            for slug in self.people:
                self.artist_page(slug, lang)
            self.about(lang)
        self.write("data/search.json", json.dumps(self.search_index(), ensure_ascii=False, separators=(",", ":")))
        self.not_found()
        self.root()
        self.sitemap()
        (DIST / ".nojekyll").write_text("")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("SITE_BASE"), help="URL path of the site root, example: /gjannu/")
    ap.add_argument("--skip-parse", action="store_true")
    a = ap.parse_args()
    if not a.skip_parse:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "parse.py")], check=True)
    base = a.base if a.base is not None else (urlparse(CONFIG["site"]["base_url"]).path or "/")
    base = "/" + base.strip("/") + "/" if base.strip("/") else "/"
    content = json.loads((ROOT / "build" / "content.json").read_text("utf-8"))
    site = Site(content, base)
    site.build()
    n = sum(1 for _ in DIST.rglob("*.html"))
    print(f"built {n} pages into dist/ (base path {base})")
    unmapped = content.get("unmapped", {})
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and any(unmapped.values()):
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### Names to add to data/names.json\n\n")
            for k, v in unmapped.items():
                for name in v:
                    f.write(f"- {k}: {name}\n")


if __name__ == "__main__":
    main()

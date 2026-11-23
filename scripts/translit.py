"""Telugu to Roman transliteration.

The scheme is the popular, readable ASCII style (example: "Ghantasala",
"Seetharama"). It is not ISO 15919. It does not use diacritics, so that
a reader without Telugu script can read it easily.
"""

import re
import unicodedata

VIRAMA = "్"
ANUSVARA = "ం"
VISARGA = "ః"
CANDRABINDU = "ఁ"
SILENT = {CANDRABINDU, "‌", "‍", "​", "఼", "ౕ", "ౖ"}

VOWELS = {
    "అ": "a", "ఆ": "aa", "ఇ": "i", "ఈ": "ee", "ఉ": "u", "ఊ": "oo",
    "ఋ": "ru", "ౠ": "roo", "ఌ": "lu", "ఎ": "e", "ఏ": "e", "ఐ": "ai",
    "ఒ": "o", "ఓ": "o", "ఔ": "au",
}

SIGNS = {
    "ా": "aa", "ి": "i", "ీ": "ee", "ు": "u",
    "ూ": "oo", "ృ": "ru", "ౄ": "roo", "ె": "e",
    "ే": "e", "ై": "ai", "ొ": "o", "ో": "o",
    "ౌ": "au",
}

CONSONANTS = {
    "క": "k", "ఖ": "kh", "గ": "g", "ఘ": "gh", "ఙ": "n",
    "చ": "ch", "ఛ": "chh", "జ": "j", "ఝ": "jh", "ఞ": "n",
    "ట": "t", "ఠ": "th", "డ": "d", "ఢ": "dh", "ణ": "n",
    "త": "th", "థ": "th", "ద": "d", "ధ": "dh", "న": "n",
    "ప": "p", "ఫ": "ph", "బ": "b", "భ": "bh", "మ": "m",
    "య": "y", "ర": "r", "ఱ": "r", "ల": "l", "ళ": "l", "ఴ": "zh",
    "వ": "v", "శ": "sh", "ష": "sh", "స": "s", "హ": "h",
    "ౘ": "ts", "ౙ": "dz",
}

# The anusvara is "m" before labials and at the end of a word. It is "n" before other stops.
NASAL_N = set("కఖగఘచఛజఝటఠడఢతథదధనఙఞణ")

DIGITS = {chr(0x0C66 + i): str(i) for i in range(10)}

TELUGU_RE = re.compile(r"[ఀ-౿]")


def has_telugu(text):
    return bool(TELUGU_RE.search(text or ""))


def transliterate(text):
    """Return the Roman form of the Telugu text. Other characters stay as they are."""
    s = unicodedata.normalize("NFC", text or "")
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in CONSONANTS:
            r = CONSONANTS[c]
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt == VIRAMA:
                after = s[i + 2] if i + 2 < n else ""
                # A doubled consonant (example: త్త) gives "tth", not "thth".
                out.append(r[0] if after == c else r)
                i += 2
                continue
            if nxt in SIGNS:
                out.append(r + SIGNS[nxt])
                i += 2
                continue
            out.append(r + "a")
            i += 1
            continue
        if c in VOWELS:
            out.append(VOWELS[c])
        elif c == ANUSVARA:
            nxt = s[i + 1] if i + 1 < n else ""
            out.append("n" if nxt in NASAL_N else "m")
        elif c == VISARGA:
            out.append("h")
        elif c in SILENT:
            pass
        elif c in DIGITS:
            out.append(DIGITS[c])
        elif c in ("।", "॥"):
            out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out)


def title_case(text):
    """Make the first letter of each word a capital letter."""
    return " ".join(w[:1].upper() + w[1:] for w in text.split(" "))


def name_to_roman(text):
    return title_case(transliterate(text)).strip()


_FOLD = [
    ("aa", "a"), ("ee", "i"), ("oo", "u"), ("th", "t"), ("dh", "d"),
    ("sh", "s"), ("bh", "b"), ("kh", "k"), ("gh", "g"), ("ph", "p"),
    ("jh", "j"), ("chh", "ch"), ("w", "v"), ("z", "j"), ("q", "k"),
    ("x", "ks"), ("f", "p"), ("ou", "au"), ("y", "i"),
]


def fold(text):
    """Make a search key. Different Roman spellings of one word give the same key.

    Example: "dhorakadu", "dorakadu" and "doraakadu" give the same key.
    """
    t = text or ""
    if has_telugu(t):
        t = transliterate(t)
    t = unicodedata.normalize("NFKD", t.lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    for a, b in _FOLD:
        t = t.replace(a, b)
    t = re.sub(r"(.)\1+", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


if __name__ == "__main__":
    import sys

    for line in sys.stdin:
        print(transliterate(line.rstrip("\n")))

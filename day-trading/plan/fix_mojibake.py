"""Repair a file whose UTF-8 bytes were decoded as CP1252 and re-encoded.

Usage:  python plan/fix_mojibake.py FILE [FILE ...]         (in place)
        python plan/fix_mojibake.py --check FILE [FILE ...] (report only)

CAUSE (hit 2026-09-01, Day 20). PowerShell's
`Get-Content file | Set-Content file -Encoding utf8` round-trip reads a UTF-8
file as the system ANSI codepage and writes it back as UTF-8, so every
non-ASCII character becomes its CP1252 mis-reading. It also prepends a BOM.
An em dash (E2 80 94) comes out as C3 A2 E2 82 AC E2 80 9D.

REVERSAL: decode the file as UTF-8 to recover the mangled string, encode THAT
string as CP1252 to recover the original bytes, write them back with no BOM.
Applied ONLY if the reversal round-trips (recovered bytes must be valid UTF-8),
so an unusual-but-intact file is left alone.

DETECTION IS ON RAW BYTES, deliberately. A character-level marker list is
unreliable because the marker literals would themselves be non-ASCII and would
depend on how THIS source file is decoded -- which is the very failure being
diagnosed. This source is pure ASCII for that reason.
"""
import sys
from pathlib import Path

# UTF-8 encodings of the CP1252 mis-readings of common UTF-8 lead bytes:
#   E2 (dashes, arrows, minus) -> "a-circumflex" + euro-sign  -> C3 A2 E2 82 AC
#   C2 (nbsp, degree)          -> "A-circumflex" + C2 xx      -> C3 82
#   C3 (accented latin)        -> "A-tilde" + C2 xx           -> C3 83 C2
MARKER_BYTES = (b"\xc3\xa2\xe2\x82\xac", b"\xc3\x82\xc2", b"\xc3\x83\xc2")

BOM = b"\xef\xbb\xbf"


def repair(raw):
    body = raw[len(BOM):] if raw.startswith(BOM) else raw
    if not any(m in body for m in MARKER_BYTES):
        return None, "clean (no mojibake byte signature)"
    text = raw.decode("utf-8-sig")
    try:
        recovered = text.encode("cp1252")
        recovered.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        return None, "REFUSED -- reversal does not round-trip (%s)" % e
    return recovered, "repaired"


def main():
    args = sys.argv[1:]
    check = bool(args) and args[0] == "--check"
    if check:
        args = args[1:]
    rc = 0
    for f in args:
        p = Path(f)
        raw = p.read_bytes()
        had_bom = raw.startswith(BOM)
        fixed, status = repair(raw)
        note = "%s: %s%s" % (p.name, status, " (had BOM)" if had_bom else "")
        if fixed is None:
            if status.startswith("REFUSED"):
                rc = 1
            print(note)
            continue
        if check:
            print(note + "  [--check, not written]")
        else:
            p.write_bytes(fixed)
            print(note + " -> wrote %d bytes, BOM removed" % len(fixed))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

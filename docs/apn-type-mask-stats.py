#!/usr/bin/env python3
"""Reproduce the numbers quoted in docs/apn-type-mask.md.

Usage: python3 docs/apn-type-mask-stats.py [PROFILES_DIR]   (default: ../profiles next to this file)

Needs PyYAML. Read-only. "Entry" = one item of an `apns` list in common, plmn_overrides or
selector_overrides. "Combination" = one supported PLMN of one profile, using common unless
plmn_overrides[plmn] replaces `apns` (selector_overrides are per-SIM refinements and are not
expanded here; the vohive runtime does expand them).
"""
import collections
import glob
import os
import sys

import yaml

DEFAULT_DATA, VOICEMAIL, MMS, TETHER_A, TETHER_B, IMS, EMERGENCY, XCAP = 0x1, 0x2, 0x4, 0x10, 0x20, 0x20000, 0x40000, 0x100000


def is_valid_data_apn(apn):
    """Same rule as vohive_card_policy::is_valid_data_apn (empty is valid = network default)."""
    if apn == "":
        return True
    if len(apn.encode()) > 100 or not apn.isascii():
        return False
    for label in apn.split("."):
        if not label or len(label) > 63 or label.startswith("-") or label.endswith("-"):
            return False
        if not all(c.isalnum() or c == "-" for c in label):
            return False
    return True


def has_credentials(entry):
    for key in ("username", "password", "auth_type"):
        value = entry.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return True
        else:
            return True
    return False


def mask(entry):
    value = entry.get("type_mask")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def bits(value):
    return [f"0x{1 << b:x}" for b in range(32) if value >> b & 1]


def load(directory):
    entries, combos = [], []
    for path in sorted(glob.glob(os.path.join(directory, "*.yaml"))):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        slug = os.path.basename(path)[:-5]
        common = (doc.get("common") or {}).get("apns")
        plmn_overrides = doc.get("plmn_overrides") or {}
        for lst in [common] + [o.get("apns") for o in plmn_overrides.values() if isinstance(o, dict)] \
                + [o.get("apns") for o in (doc.get("selector_overrides") or {}).values() if isinstance(o, dict)]:
            for e in lst or []:
                if isinstance(e, dict):
                    entries.append((slug, e))
        for plmn in doc.get("supported_plmns") or []:
            override = plmn_overrides.get(plmn)
            apns = override["apns"] if isinstance(override, dict) and "apns" in override else common
            combos.append((slug, str(plmn), [e for e in apns or [] if isinstance(e, dict)], apns is not None))
    return entries, combos


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    directory = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "profiles")
    entries, combos = load(directory)
    print(f"entries={len(entries)} combinations={len(combos)}\n")

    print("== most common type_mask values (value, hex, bits, entries)")
    counts = collections.Counter(mask(e) for _, e in entries)
    for value, n in counts.most_common(16):
        print(f"  {value!s:>8} {hex(value) if value is not None else '-':>9} {bits(value) if value else []} {n}")
    print(f"  distinct values: {len([v for v in counts if v is not None])}; missing type_mask: {counts.get(None, 0)}\n")

    print("== per bit: entries containing it / entries that are exactly that bit / names of the exact ones")
    for b in range(32):
        bit = 1 << b
        having = sum(1 for _, e in entries if (mask(e) or 0) & bit)
        if not having:
            continue
        exact = collections.Counter((e.get("apn") or "") for _, e in entries if mask(e) == bit)
        print(f"  0x{bit:<8x} having={having:<5} exact={sum(exact.values()):<4} {exact.most_common(4)}")
    print()

    print("== name -> mask (what do APNs called X carry?)")
    groups = {
        "ims*": lambda n: n.startswith("ims"), "sos/emergency": lambda n: n.startswith("sos") or "emergency" in n,
        "mms": lambda n: "mms" in n, "vvm": lambda n: "vvm" in n, "hotspot": lambda n: "hotspot" in n,
        "xcap/hos": lambda n: "xcap" in n or n.startswith("hos"), "internet": lambda n: n == "internet",
    }
    for label, test in groups.items():
        c = collections.Counter(mask(e) for _, e in entries if test((e.get("apn") or "").lower()))
        print(f"  {label:<14} {sum(c.values()):>4} " + ", ".join(f"{v}x{n}" for v, n in c.most_common(4)))
    print()

    print("== entries without type_mask (apn names)")
    missing = collections.Counter((e.get("apn") if e.get("apn") is not None else "<no apn>") for _, e in entries if mask(e) is None)
    print(f"  {sum(missing.values())}: {sorted(missing.items())}\n")

    print("== combinations: which entry would the data-APN rule pick")
    none_apns = first = later = no_data = 0
    selected_cred = selected_empty = selected_invalid = alt_after_cred = 0
    for slug, plmn, apns, present in combos:
        if not apns:
            none_apns += 1
            continue
        data = [e for e in apns if (mask(e) or 0) & DEFAULT_DATA]
        if not data:
            no_data += 1
            print(f"  NO DATA ENTRY: {slug} {plmn} {[(e.get('apn'), mask(e)) for e in apns]}")
            continue
        first, later = (first + 1, later) if apns[0] is data[0] else (first, later + 1)
        chosen = data[0]
        apn = (chosen.get("apn") or "").strip()
        if has_credentials(chosen):
            selected_cred += 1
            alt_after_cred += any(not has_credentials(e) and is_valid_data_apn((e.get("apn") or "").strip()) for e in data[1:])
        elif not is_valid_data_apn(apn):
            selected_invalid += 1
        elif apn == "":
            selected_empty += 1
    print(f"  no apns list: {none_apns}; first entry is the data entry: {first}; data entry later in the list: {later}; no data entry: {no_data}")
    print(f"  chosen entry has credentials (-> empty APN): {selected_cred} (a later credential-free data entry exists in {alt_after_cred}); "
          f"invalid syntax: {selected_invalid}; apn is the empty string: {selected_empty}\n")

    print("== why the data APN's value differs (per combination that has a data entry)")
    rows = []
    for slug, plmn, apns, present in combos:
        data = [e for e in apns if (mask(e) or 0) & DEFAULT_DATA]
        if not data:
            continue
        chosen, name = data[0], (data[0].get("apn") or "")
        other = [e for e in apns if not (mask(e) or 0) & DEFAULT_DATA]
        rows.append({
            "mask": mask(chosen) or 0,
            "separate_hotspot": any((mask(e) or 0) & TETHER_A and e.get("apn") != name for e in other),
            "separate_mms": any((mask(e) or 0) & MMS for e in other),
            "ims": any((mask(e) or 0) & IMS for e in apns),
        })

    def rate(pred, base):
        sel = [r for r in rows if base(r)]
        return f"{sum(1 for r in sel if pred(r))}/{len(sel)}"

    print(f"  data APN carries the tether bits | carrier has no separate hotspot APN: {rate(lambda r: r['mask'] & TETHER_A, lambda r: not r['separate_hotspot'])}")
    print(f"  data APN carries the tether bits | carrier has a separate hotspot APN : {rate(lambda r: r['mask'] & TETHER_A, lambda r: r['separate_hotspot'])}")
    print(f"  data APN carries the MMS bit     | no separate MMS APN : {rate(lambda r: r['mask'] & MMS, lambda r: not r['separate_mms'])}")
    print(f"  data APN carries the MMS bit     | has separate MMS APN: {rate(lambda r: r['mask'] & MMS, lambda r: r['separate_mms'])}")
    print(f"  carrier lists an IMS entry       | data APN has bit 0x8000   : {rate(lambda r: r['ims'], lambda r: r['mask'] & 0x8000)}")
    print(f"  carrier lists an IMS entry       | data APN lacks bit 0x8000 : {rate(lambda r: r['ims'], lambda r: not r['mask'] & 0x8000)}")


if __name__ == "__main__":
    main()

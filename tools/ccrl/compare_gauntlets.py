#!/usr/bin/env python3
"""Pair-by-pair comparison of two gauntlets played with the same openings.

  compare_gauntlets.py base.pgn BASE_NAME new.pgn NEW_NAME

Both gauntlets must come from tools/ccrl/gauntlet.sh with the same -srand,
so that opponent + Round identify the same opening pair in both files. For
every opening pair played completely in both, the difference of Farzin's
pair score (new - base) is taken; the mean difference and its standard
error give the Elo gain with a 95% interval. Pairing removes the opening
variance that dominates two independent gauntlets of this size. Games lost
on time by either side are reported but kept (they are part of the result).
"""
import argparse
import collections
import math

import chess.pgn


def elo(s):
    s = min(max(s, 1e-6), 1 - 1e-6)
    return -400 * math.log10(1 / s - 1)


def load(path, me):
    pairs = collections.defaultdict(list)
    forfeits = collections.Counter()
    with open(path, encoding="utf-8", errors="replace") as fh:
        while True:
            h = chess.pgn.read_headers(fh)
            if h is None:
                break
            r = h.get("Result")
            if r not in ("1-0", "0-1", "1/2-1/2"):
                continue
            white = h.get("White") == me
            if not white and h.get("Black") != me:
                continue
            opp = h["Black"] if white else h["White"]
            s = 0.5 if r == "1/2-1/2" else float((r == "1-0") == white)
            pairs[(opp, h.get("Round", "").split(".")[0])].append(s)
            if h.get("Termination") == "time forfeit":
                forfeits[opp] += 1
    return {k: sum(v) / 2 for k, v in pairs.items() if len(v) == 2}, forfeits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("base_name")
    ap.add_argument("new")
    ap.add_argument("new_name")
    args = ap.parse_args()
    base, fb = load(args.base, args.base_name)
    new, fn = load(args.new, args.new_name)
    keys = sorted(set(base) & set(new))
    by_opp = collections.defaultdict(list)
    for k in keys:
        by_opp[k[0]].append((base[k], new[k]))
    print("| opponent | pairs | base score | new score | diff (Elo) | time forfeits base/new |")
    print("|---|---|---|---|---|---|")
    allb, alln, diffs = [], [], []
    for opp in sorted(by_opp):
        rows = by_opp[opp]
        b = sum(x for x, _ in rows) / len(rows)
        n = sum(y for _, y in rows) / len(rows)
        allb += [x for x, _ in rows]
        alln += [y for _, y in rows]
        diffs += [y - x for x, y in rows]
        print(f"| {opp} | {len(rows)} | {100 * b:.1f}% | {100 * n:.1f}% | "
              f"{elo(n) - elo(b):+.0f} | {fb[opp]}/{fn[opp]} |")
    m = len(diffs)
    b = sum(allb) / m
    n = sum(alln) / m
    md = sum(diffs) / m
    sd = math.sqrt(sum((d - md) ** 2 for d in diffs) / (m - 1)) if m > 1 else 0
    se = sd / math.sqrt(m) if m else 0
    lo, hi = n - 1.96 * se, n + 1.96 * se
    print(f"| **total** | {m} | {100 * b:.1f}% | {100 * n:.1f}% | "
          f"{elo(n) - elo(b):+.1f} [{elo(lo) - elo(b):+.1f}, {elo(hi) - elo(b):+.1f}] | "
          f"{sum(fb.values())}/{sum(fn.values())} |")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Pentanomial SPRT status of a two-engine match from its PGN.

Games are paired by Round tag and opening (FEN), as fastchess writes them
with `-repeat`; incomplete pairs are ignored. Prints W/D/L, the pentanomial
counts, the Elo estimate with a 95% interval, and the GSPRT log-likelihood
ratio (normal approximation, logistic Elo bounds) against the bounds.

  pgn_sprt.py match.pgn NEW_NAME [--elo0 0 --elo1 10 --alpha 0.05 --beta 0.05]
"""
import argparse
import collections
import math

import chess.pgn


def score_to_elo(s):
    s = min(max(s, 1e-6), 1 - 1e-6)
    return -400 * math.log10(1 / s - 1)


def elo_to_score(e):
    return 1 / (1 + 10 ** (-e / 400))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("name")
    ap.add_argument("--elo0", type=float, default=0)
    ap.add_argument("--elo1", type=float, default=10)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--beta", type=float, default=0.05)
    args = ap.parse_args()
    pairs = collections.defaultdict(list)
    wdl = [0, 0, 0]
    with open(args.pgn, encoding="utf-8", errors="replace") as fh:
        while True:
            h = chess.pgn.read_headers(fh)
            if h is None:
                break
            r = h.get("Result")
            if r not in ("1-0", "0-1", "1/2-1/2"):
                continue
            white = h.get("White") == args.name
            s = 0.5 if r == "1/2-1/2" else float((r == "1-0") == white)
            wdl[0 if s == 1 else 1 if s == 0.5 else 2] += 1
            pairs[(h.get("Round"), h.get("FEN"))].append(s)
    penta = [0] * 5
    for v in pairs.values():
        if len(v) == 2:
            penta[int(round(2 * sum(v)))] += 1
    n = sum(penta)
    print(f"games W/D/L {wdl[0]}/{wdl[1]}/{wdl[2]}  pairs {n}  pentanomial {penta}")
    if n < 2:
        return
    probs = [c / n for c in penta]
    scores = [0, 0.25, 0.5, 0.75, 1]
    mean = sum(p * s for p, s in zip(probs, scores))
    var = sum(p * (s - mean) ** 2 for p, s in zip(probs, scores))
    se = math.sqrt(var / n) if var > 0 else 1e-9
    lo, hi = mean - 1.96 * se, mean + 1.96 * se
    print(f"score {100 * mean:.2f}%  Elo {score_to_elo(mean):+.1f} "
          f"[{score_to_elo(lo):+.1f}, {score_to_elo(hi):+.1f}]")
    s0, s1 = elo_to_score(args.elo0), elo_to_score(args.elo1)
    llr = (s1 - s0) * (2 * mean - s0 - s1) / (2 * var / n) if var > 0 else 0.0
    lower = math.log(args.beta / (1 - args.alpha))
    upper = math.log((1 - args.beta) / args.alpha)
    verdict = "H1 accepted" if llr >= upper else "H0 accepted" if llr <= lower else "continue"
    print(f"LLR {llr:.2f} [{lower:.2f}, {upper:.2f}]  (elo0={args.elo0}, elo1={args.elo1})  {verdict}")


if __name__ == "__main__":
    main()

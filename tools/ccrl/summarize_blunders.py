#!/usr/bin/env python3
"""Summarise find_blunders.py output and write an `am`-only EPD suite.

  summarize_blunders.py blunders.json --epd tests/regression/ccrl-mistakes.epd

The suite keeps positions whose decisive mistake lost at least --min-drop
centipawns (reference engine, Farzin's point of view). Only the move that was
actually played is recorded, as `am` (avoid move): the reference engine's
preferred move need not be unique, but the played move is known to be bad.
"""
import argparse
import collections
import json

import chess


def phase_bucket(ply):
    move = ply // 2 + 1
    if move <= 20:
        return "moves 1-20"
    if move <= 40:
        return "moves 21-40"
    if move <= 60:
        return "moves 41-60"
    return "moves 61+"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--epd")
    ap.add_argument("--min-drop", type=int, default=100)
    args = ap.parse_args()
    games = json.load(open(args.json))
    phase = collections.Counter()
    pieces = []
    drops = []
    move_no = []
    per_opp = collections.Counter()
    rows = []
    for g in games:
        w = g.get("worst")
        if not w:
            continue
        opp = g["black"] if g["color"] == "white" else g["white"]
        # Same move as the reference engine: the "drop" is search noise.
        if w["drop"] >= args.min_drop and w["played_uci"] != w["best_uci"]:
            phase[w["phase"]] += 1
            pieces.append(w["pieces"])
            drops.append(w["drop"])
            move_no.append(w["move_number"])
            per_opp[opp] += 1
            rows.append((g, w, opp))
    n = len(rows)
    print(f"games analysed: {len(games)}; decisive mistakes >= {args.min_drop} cp: {n}")
    if n:
        print("phase of the decisive mistake:", dict(phase))
        print(f"pieces on board: median {sorted(pieces)[n // 2]}, "
              f"<= 12 pieces: {sum(p <= 12 for p in pieces)}")
        print(f"move number: median {sorted(move_no)[n // 2]}")
        print(f"eval drop (cp): median {sorted(drops)[n // 2]}")
        print(f"games without a single decisive mistake (gradual losses): {len(games) - n}")
    # Where does a lost game turn bad? First position (Farzin's view) below -100.
    turn = collections.Counter()
    plies = []
    for g in games:
        curve = g.get("curve") or []
        for ply, v in enumerate(curve):
            if v is not None and v < -100:
                turn[phase_bucket(ply)] += 1
                plies.append(ply)
                break
    if plies:
        print(f"first eval below -100 cp: median move {sorted(plies)[len(plies) // 2] // 2 + 1}; "
              f"by move range {dict(sorted(turn.items()))}")
    if args.epd:
        with open(args.epd, "w") as fh:
            for g, w, opp in rows:
                board = chess.Board(w["fen"])
                fh.write(board.epd(
                    am=chess.Move.from_uci(w["played_uci"]),
                    id=f"ccrl-blitz {g['round']} {g['white']} - {g['black']}",
                    c0=f"ref {w['best']} {w['eval_before']}->{w['eval_after']}cp {w['phase']}",
                ) + "\n")
        print(f"wrote {n} positions to {args.epd}")


if __name__ == "__main__":
    main()

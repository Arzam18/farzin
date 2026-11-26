#!/usr/bin/env python3
"""Summarise an engine's games from a CCRL PGN download.

Reports per-opponent W/D/L, results by colour, game length and the material
situation at the end of lost and won games, so that weaknesses (endgames,
long games, colour, openings) can be located before changing the engine.

Usage:
  analyze_ccrl_games.py GAMES.pgn --engine "Farzin 0.5.2 64-bit" [--json out.json]

Requires python-chess.
"""
import argparse
import collections
import json

import chess
import chess.pgn

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def material(board, color):
    return sum(len(board.pieces(p, color)) * v for p, v in VALUES.items())


def phase_of(board):
    """Rough phase from non-pawn material of both sides (max 62)."""
    npm = sum(
        len(board.pieces(p, c)) * VALUES[p]
        for p in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        for c in (chess.WHITE, chess.BLACK)
    )
    if npm >= 44:
        return "middlegame"
    if npm >= 20:
        return "late-middlegame"
    return "endgame"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--json")
    args = ap.parse_args()

    per_opp = collections.defaultdict(lambda: [0, 0, 0])
    by_color = {"white": [0, 0, 0], "black": [0, 0, 0]}
    length = {"win": [], "draw": [], "loss": []}
    end_phase = {"win": collections.Counter(), "loss": collections.Counter(), "draw": collections.Counter()}
    loss_eco = collections.Counter()
    losses = []
    with open(args.pgn, encoding="utf-8", errors="replace") as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            h = game.headers
            white = h.get("White") == args.engine
            if not white and h.get("Black") != args.engine:
                continue
            opp = h["Black"] if white else h["White"]
            res = h.get("Result")
            if res == "1/2-1/2":
                outcome = "draw"
            elif (res == "1-0") == white:
                outcome = "win"
            else:
                outcome = "loss"
            idx = {"win": 0, "draw": 1, "loss": 2}[outcome]
            per_opp[opp][idx] += 1
            by_color["white" if white else "black"][idx] += 1
            board = game.end().board()
            plies = board.ply()
            length[outcome].append(plies)
            end_phase[outcome][phase_of(board)] += 1
            if outcome == "loss":
                loss_eco[h.get("ECO", "?")[:1]] += 1
                me = chess.WHITE if white else chess.BLACK
                losses.append({
                    "opponent": opp,
                    "color": "white" if white else "black",
                    "round": h.get("Round"),
                    "eco": h.get("ECO"),
                    "plies": plies,
                    "final_fen": board.fen(),
                    "material_diff": material(board, me) - material(board, not me),
                    "end_phase": phase_of(board),
                })

    def wdl(t):
        w, d, l = t
        n = max(1, w + d + l)
        return f"+{w} ={d} -{l} ({100 * (w + d / 2) / n:.1f}%)"

    print("Per opponent (sorted by score):")
    for opp, t in sorted(per_opp.items(), key=lambda kv: (kv[1][0] + kv[1][1] / 2) / max(1, sum(kv[1]))):
        print(f"  {opp:32s} {wdl(t)}")
    print("By colour:")
    for c, t in by_color.items():
        print(f"  {c:6s} {wdl(t)}")
    print("Average game length (plies):")
    for k, v in length.items():
        if v:
            print(f"  {k:5s} n={len(v):3d} mean={sum(v) / len(v):.1f} median={sorted(v)[len(v) // 2]}")
    print("Phase at game end:")
    for k, v in end_phase.items():
        print(f"  {k:5s} {dict(v)}")
    print("Loss ECO groups:", dict(loss_eco))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump({
                "per_opponent": per_opp,
                "by_color": by_color,
                "length": length,
                "end_phase": {k: dict(v) for k, v in end_phase.items()},
                "losses": losses,
            }, fh, indent=1)


if __name__ == "__main__":
    main()

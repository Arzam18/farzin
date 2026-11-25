#!/usr/bin/env python3
"""Locate the decisive mistakes of an engine in its lost (or drawn) games.

Every position of each selected game is evaluated once by a reference
engine at a fixed node count. For every move of the tested engine the
evaluation drop (from that engine's point of view) is computed; the
largest drop is the game's "decisive mistake". The positions before those
mistakes, together with the reference engine's preferred move, form a
regression suite (EPD with `bm` and the move actually played as `am`).

Usage:
  find_blunders.py GAMES.pgn --engine "Farzin 0.5.2 64-bit" \
      --reference /path/to/stockfish --nodes 200000 \
      --results loss --json out.json --epd out.epd

Requires python-chess. Scores are clamped to +-2000 cp; mates count as 2000.
"""
import argparse
import json

import chess
import chess.engine
import chess.pgn

CLAMP = 2000


def white_cp(info):
    score = info["score"].white()
    if score.is_mate():
        return CLAMP if score.mate() > 0 else -CLAMP
    return max(-CLAMP, min(CLAMP, score.score()))


def phase_of(board):
    npm = 0
    for p, v in ((chess.KNIGHT, 3), (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9)):
        npm += v * (len(board.pieces(p, chess.WHITE)) + len(board.pieces(p, chess.BLACK)))
    if npm >= 44:
        return "middlegame"
    if npm >= 20:
        return "late-middlegame"
    return "endgame"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--nodes", type=int, default=200_000)
    ap.add_argument("--hash", type=int, default=64)
    ap.add_argument("--min-ply", type=int, default=16, help="skip book plies")
    ap.add_argument("--lost-cp", type=int, default=150,
                    help="ignore moves made when already worse than this (cp)")
    ap.add_argument("--results", default="loss", help="comma list of loss,draw,win")
    ap.add_argument("--json", required=True)
    ap.add_argument("--epd")
    args = ap.parse_args()
    wanted = set(args.results.split(","))

    ref = chess.engine.SimpleEngine.popen_uci(args.reference)
    ref.configure({"Hash": args.hash, "Threads": 1})
    limit = chess.engine.Limit(nodes=args.nodes)
    out = []
    with open(args.pgn, encoding="utf-8", errors="replace") as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            h = game.headers
            white = h.get("White") == args.engine
            if not white and h.get("Black") != args.engine:
                continue
            res = h.get("Result")
            outcome = "draw" if res == "1/2-1/2" else ("win" if (res == "1-0") == white else "loss")
            if outcome not in wanted:
                continue
            me = chess.WHITE if white else chess.BLACK
            board = game.board()
            evals = []  # white-relative eval of each position (index = ply)
            moves = list(game.mainline_moves())
            boards = [board.copy()]
            for mv in moves:
                board.push(mv)
                boards.append(board.copy())
            for ply, b in enumerate(boards):
                if ply < args.min_ply or b.is_game_over():
                    evals.append(None)
                    continue
                info = ref.analyse(b, limit)
                evals.append((white_cp(info), info.get("pv", [None])[0]))
            sign = 1 if me == chess.WHITE else -1
            worst = None
            for ply in range(args.min_ply, len(moves)):
                b = boards[ply]
                if b.turn != me or evals[ply] is None:
                    continue
                before = sign * evals[ply][0]
                if evals[ply + 1] is not None:
                    after = sign * evals[ply + 1][0]
                else:
                    # game over after our move: we mated (win) or a draw
                    after = CLAMP if boards[ply + 1].is_checkmate() else 0
                # Only moves played while the game was not yet lost count:
                # once the reference sees a lost position, later "drops" are
                # noise between losing scores.
                if before < -args.lost_cp:
                    continue
                drop = before - after
                if worst is None or drop > worst["drop"]:
                    worst = {
                        "ply": ply,
                        "move_number": ply // 2 + 1,
                        "fen": b.fen(),
                        "played": b.san(moves[ply]),
                        "played_uci": moves[ply].uci(),
                        "best_uci": evals[ply][1].uci() if evals[ply][1] else None,
                        "best": b.san(evals[ply][1]) if evals[ply][1] else None,
                        "eval_before": before,
                        "eval_after": after,
                        "drop": drop,
                        "phase": phase_of(b),
                        "pieces": chess.popcount(b.occupied),
                    }
            curve = [None if e is None else (e[0] if me == chess.WHITE else -e[0]) for e in evals]
            rec = {
                "white": h.get("White"), "black": h.get("Black"), "result": res,
                "round": h.get("Round"), "eco": h.get("ECO"), "outcome": outcome,
                "color": "white" if white else "black", "plies": len(moves),
                "worst": worst, "curve": curve,
            }
            out.append(rec)
            w = worst or {}
            print(f"{rec['round']:>14s} {outcome:4s} {rec['color']:5s} vs "
                  f"{(h['Black'] if white else h['White'])[:22]:22s} move {w.get('move_number')} "
                  f"{w.get('played')} (best {w.get('best')}) {w.get('eval_before')} -> "
                  f"{w.get('eval_after')} [{w.get('phase')}, {w.get('pieces')} pcs]", flush=True)
    ref.quit()
    with open(args.json, "w") as fh:
        json.dump(out, fh, indent=1)
    if args.epd:
        with open(args.epd, "w") as fh:
            for rec in out:
                w = rec["worst"]
                if not w or not w["best_uci"] or w["drop"] < 100:
                    continue
                board = chess.Board(w["fen"])
                epd = board.epd(bm=chess.Move.from_uci(w["best_uci"]),
                                am=chess.Move.from_uci(w["played_uci"]),
                                id=f"ccrl {rec['round']} {rec['white']} - {rec['black']}")
                fh.write(epd + "\n")


if __name__ == "__main__":
    main()

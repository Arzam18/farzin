#!/usr/bin/env python3
"""Extract endgame starting positions from PGN games.

For every game, the first position with at most --max-pieces men (and more
than --min-pieces), not in check and with no capture available that would
immediately simplify further, is written as EPD. Used to measure endgame
skill (e.g. tablebase support) with colour-reversed game pairs, which cancel
the imbalance of each position.

  endgame_starts.py games.pgn --max-pieces 8 --min-pieces 6 > endgames.epd
"""
import argparse
import random

import chess
import chess.pgn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("--max-pieces", type=int, default=8)
    ap.add_argument("--min-pieces", type=int, default=6)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    seen = set()
    out = []
    with open(args.pgn, encoding="utf-8", errors="replace") as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            board = game.board()
            for mv in game.mainline_moves():
                board.push(mv)
                n = chess.popcount(board.occupied)
                if n < args.min_pieces:
                    break
                if n > args.max_pieces or board.is_check() or board.is_game_over():
                    continue
                if any(board.is_capture(m) for m in board.legal_moves):
                    continue
                key = board.epd()
                if key not in seen:
                    seen.add(key)
                    out.append(key)
                break
    random.Random(args.seed).shuffle(out)
    for epd in out:
        print(epd)


if __name__ == "__main__":
    main()

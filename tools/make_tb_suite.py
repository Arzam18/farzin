#!/usr/bin/env python3
"""Generate a tablebase-verified endgame regression suite.

Picks random legal positions with 4-5 pieces (at least one pawn or a rook /
minor ending, i.e. practical material) in which the side to move wins and
exactly one legal move keeps the win (all others draw or lose). The EPD gets
`bm` = that move, so the suite is objectively correct; engines are tested on
it *without* tablebases to measure endgame search quality.

  make_tb_suite.py /path/to/syzygy --count 60 --seed 1 > tb-only-moves.epd

Requires python-chess.
"""
import argparse
import random

import chess
import chess.syzygy

MATERIAL = [
    # (white extra pieces, black extra pieces): practical endings.
    ("RP", "R"), ("P", ""), ("PP", "P"), ("RP", "B"), ("RP", "N"), ("QP", "Q"),
    ("BP", "B"), ("NP", "N"), ("BP", "N"), ("RB", "R"), ("RN", "R"), ("Q", "R"),
    ("R", "B"), ("Q", "PP"), ("R", "PP"), ("BN", ""), ("P", "P"), ("PP", ""),
]
LETTER = {"Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT, "P": chess.PAWN}


def random_position(rng):
    w, b = rng.choice(MATERIAL)
    if rng.random() < 0.5:
        w, b = b, w
        white_strong = False
    else:
        white_strong = True
    board = chess.Board(None)
    squares = list(chess.SQUARES)
    rng.shuffle(squares)
    board.set_piece_at(squares.pop(), chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(squares.pop(), chess.Piece(chess.KING, chess.BLACK))
    for color, letters in ((chess.WHITE, w), (chess.BLACK, b)):
        for ch in letters:
            pt = LETTER[ch]
            while True:
                sq = squares.pop()
                if pt != chess.PAWN or chess.square_rank(sq) not in (0, 7):
                    break
            board.set_piece_at(sq, chess.Piece(pt, color))
    board.turn = chess.WHITE if (rng.random() < 0.5) == white_strong else chess.BLACK
    return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tb")
    ap.add_argument("--count", type=int, default=60)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    tb = chess.syzygy.open_tablebase(args.tb)
    found = 0
    while found < args.count:
        board = random_position(rng)
        if not board.is_valid() or board.is_game_over() or board.is_check():
            continue
        if tb.probe_wdl(board) != 2:
            continue
        winners = []
        for mv in board.legal_moves:
            board.push(mv)
            v = 2 if board.is_checkmate() else -tb.probe_wdl(board)
            board.pop()
            if v == 2:
                winners.append(mv)
                if len(winners) > 1:
                    break
        # Exactly one winning move, and not a trivial capture/mate-in-1.
        if len(winners) != 1 or board.is_capture(winners[0]):
            continue
        board.push(winners[0])
        trivial = board.is_checkmate()
        board.pop()
        if trivial:
            continue
        found += 1
        dtz = tb.probe_dtz(board)
        print(board.epd(bm=winners[0], id=f"tb-only-move {found}", c0=f"dtz {dtz}"))


if __name__ == "__main__":
    main()

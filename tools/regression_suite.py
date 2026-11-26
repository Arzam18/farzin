#!/usr/bin/env python3
"""Position regression suite: does an engine find the right move?

Runs a UCI engine on EPD positions with `bm` (best move(s)) and/or `am`
(avoid move(s)) operations under a fixed node or time budget and reports
how many are solved, per suite file. Compare two engines (old/new) to catch
regressions in tactics, endgames or special positions before merging.

  regression_suite.py --engine ./farzin --engine ./farzin-new \\
      --nodes 2000000 tests/regression/*.epd [--option SyzygyPath=/tb]
      [--json out.json]

A position counts as solved if the chosen move is one of `bm` (when given)
and none of `am`. Requires python-chess.
"""
import argparse
import json
import os
import sys

import chess
import chess.engine


def load(path):
    items = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            board, ops = chess.Board.from_epd(line)
            items.append((board, ops))
    return items


def solved(ops, move):
    bm = ops.get("bm") or []
    am = ops.get("am") or []
    if bm and move not in bm:
        return False
    return move not in am


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("epd", nargs="+")
    ap.add_argument("--engine", action="append", required=True)
    ap.add_argument("--nodes", type=int)
    ap.add_argument("--movetime", type=float, help="seconds per position")
    ap.add_argument("--hash", type=int, default=64)
    ap.add_argument("--option", action="append", default=[], help="NAME=VALUE for every engine")
    ap.add_argument("--json")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if not args.nodes and not args.movetime:
        args.nodes = 1_000_000
    limit = chess.engine.Limit(nodes=args.nodes, time=args.movetime)
    suites = {os.path.basename(p): load(p) for p in args.epd}
    report = {}
    for path in args.engine:
        eng = chess.engine.SimpleEngine.popen_uci(path)
        opts = {"Hash": args.hash, "Threads": 1}
        for o in args.option:
            k, _, v = o.partition("=")
            if k in eng.options:
                opts[k] = v
        eng.configure(opts)
        name = os.path.basename(path)
        report[name] = {}
        total = good = 0
        for suite, items in suites.items():
            ok = 0
            failed = []
            for board, ops in items:
                eng.configure({"Clear Hash": None}) if "Clear Hash" in eng.options else None
                move = eng.play(board, limit).move
                if solved(ops, move):
                    ok += 1
                else:
                    failed.append({"id": ops.get("id"), "fen": board.fen(), "played": board.san(move)})
            report[name][suite] = {"solved": ok, "total": len(items), "failed": failed}
            total += len(items)
            good += ok
            print(f"{name:28s} {suite:28s} {ok:3d}/{len(items):3d}", flush=True)
            if args.verbose:
                for f in failed:
                    print(f"    miss {f['id']}: played {f['played']}")
        report[name]["_total"] = {"solved": good, "total": total}
        print(f"{name:28s} {'TOTAL':28s} {good:3d}/{total:3d}", flush=True)
        eng.quit()
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(report, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())

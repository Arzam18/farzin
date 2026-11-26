#!/usr/bin/env python3
"""Compare two OwnNet releases at fixed depth, ignoring wall-clock speed.

Used to show that a release without new search code (or with features that
are off by default, such as Syzygy probing without SyzygyPath) searches
exactly like the previous one: same bench node count and the same depth-12
score, node count and PV on 11 positions.
"""
import argparse
import json
import re
import subprocess

import chess
import chess.engine

from release_check import PERFT, SPECIAL


def snapshot(path, name, bench):
    version = subprocess.check_output([path, "--version"], text=True)
    assert f"{name} edition OwnNet" in version, version
    assert "3ec5aa7e6c16b1ea6bd366ad873f4b649da310c91204915000bfd5f1e90ebfc0" in version
    benches = []
    for _ in range(3):
        out = subprocess.check_output([path, "bench"], text=True, timeout=180)
        benches.append(int(re.search(r"^(\d+) nodes", out, re.M)[1]))
    assert benches == [bench] * 3, benches
    positions = []
    with chess.engine.SimpleEngine.popen_uci(path) as engine:
        engine.configure({"Hash": 16, "Threads": 1})
        for position in PERFT + SPECIAL[:5]:
            fen = position[0]
            board = chess.Board(fen)
            info = engine.analyse(board, chess.engine.Limit(depth=12), game=object())
            positions.append({"fen": fen, "depth": info["depth"],
                              "score": str(info["score"].relative),
                              "nodes": info["nodes"],
                              "pv": [m.uci() for m in info["pv"]]})
    return {"version": version.strip(), "bench": benches, "positions": positions}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("baseline")
    ap.add_argument("candidate")
    ap.add_argument("--json", required=True)
    ap.add_argument("--baseline-name", default="Farzin 0.5.2")
    ap.add_argument("--candidate-name", default="Farzin 0.6.0")
    ap.add_argument("--bench", type=int, default=992681,
                    help="expected bench node count of both builds")
    args = ap.parse_args()
    before = snapshot(args.baseline, args.baseline_name, args.bench)
    after = snapshot(args.candidate, args.candidate_name, args.bench)
    result = {"baseline": before, "candidate": after,
              "equivalent": before["positions"] == after["positions"]}
    with open(args.json, "w") as f:
        json.dump(result, f, indent=2)
    assert result["equivalent"], "fixed-depth scores/nodes/PVs differ; inspect JSON"
    print("PASS: 3 benchmark repetitions and 11 fixed-depth positions agree")


if __name__ == "__main__":
    main()

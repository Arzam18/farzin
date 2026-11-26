#!/bin/sh
# The same Farzin binary with and without Syzygy tables, from endgame start
# positions taken from Farzin's CCRL games (tools/ccrl/endgame_starts.py), as
# in docs/ccrl-improvement-2026-11-fa.md.
#
#   tools/ccrl/tb_match.sh FASTCHESS FARZIN SYZYGY_DIR STARTS.epd OUT.pgn
#
# Every start is played twice with colours reversed. Only the tablebases
# differ between the two engines, so the score measures what they add.
# Environment: TC [10+0.1], CONC [4].
set -eu
FASTCHESS=${1:?usage: tb_match.sh FASTCHESS FARZIN SYZYGY_DIR STARTS.epd OUT.pgn}
FARZIN=$2
TB=$3
STARTS=$4
OUT=$5
rounds=$(grep -c . "$STARTS")
exec "$FASTCHESS" \
    -engine cmd="$FARZIN" name=farzin-tb option.SyzygyPath="$TB" \
    -engine cmd="$FARZIN" name=farzin-notb \
    -each tc="${TC:-10+0.1}" option.Hash=16 option.Threads=1 \
    -openings file="$STARTS" format=epd order=sequential \
    -rounds "$rounds" -games 2 -repeat -concurrency "${CONC:-4}" \
    -resign movecount=4 score=1000 twosided=true \
    -ratinginterval 50 -report penta=true -pgnout file="$OUT" -recover

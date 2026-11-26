#!/bin/sh
# Gauntlet of one Farzin build against the CCRL Blitz opponents rebuilt by
# tools/opponents/build_opponents.sh, as in docs/ccrl-improvement-2026-11-fa.md.
#
#   tools/ccrl/gauntlet.sh WORKDIR FARZIN_BINARY NAME OUT.pgn [farzin option.X=Y ...]
#
# WORKDIR is the build_opponents.sh directory (engines/ inside it, fastchess
# included). BOOK points at 8moves_v3.pgn. The same -srand gives the same
# opening pairs to every build, so two gauntlets can be compared pair by pair.
# Environment: BOOK, TC [10+0.1], ROUNDS [50 pairs per opponent],
# CONC [4], SEED [20261125].
set -eu
W=${1:?usage: gauntlet.sh WORKDIR FARZIN NAME OUT.pgn [option.X=Y ...]}
FARZIN=$2
NAME=$3
OUT=$4
shift 4
E=$W/engines
# shellcheck disable=SC2086
exec "$E/fastchess" \
    -engine cmd="$FARZIN" name="$NAME" "$@" \
    -engine cmd="$E/thrawn" name=Thrawn-3.2 \
    -engine cmd="$E/eleanor" name=Eleanor-4.1 \
    -engine cmd="$E/blackmarlin" name=BlackMarlin-9.0 \
    -engine cmd="$E/altair" name=Altair-7.0.0 \
    -engine cmd="$E/akimbo" name=akimbo-1.0.0 \
    -engine cmd="$E/texel" name=Texel-1.12 \
    -each tc="${TC:-10+0.1}" option.Hash=16 option.Threads=1 \
    -tournament gauntlet -rounds "${ROUNDS:-50}" -games 2 -repeat \
    -concurrency "${CONC:-4}" \
    -openings file="${BOOK:?set BOOK to 8moves_v3.pgn}" format=pgn order=random \
    -srand "${SEED:-20261125}" \
    -draw movenumber=40 movecount=8 score=10 \
    -resign movecount=4 score=1000 twosided=true \
    -ratinginterval 50 -report penta=true \
    -pgnout file="$OUT" -recover

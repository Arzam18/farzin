#!/bin/sh
# SPRT a candidate Farzin build against a base build with fastchess.
#
#   tools/sprt_fastchess.sh NAME NEW_CMD BASE_CMD [extra fastchess args...]
#
# Environment (defaults in brackets):
#   FASTCHESS  fastchess binary            [fastchess]
#   BOOK       EPD opening suite           [UHO_Lichess_4852_v1.epd]
#   TC         time control                [8+0.08]
#   ELO0/ELO1  logistic SPRT bounds        [0 / 10]
#   ALPHA/BETA error rates                 [0.05 / 0.05]
#   CONC       concurrent games            [nproc]
#   ROUNDS     maximum game pairs          [3000]
#   OUT        output directory            [sprt-results]
#   NEW_OPTS / BASE_OPTS  extra "option.X=Y" words for each side
#
# Unbalanced (UHO) openings with pentanomial statistics resolve small
# differences with far fewer games than balanced books; every opening is
# played twice with colours reversed. To pass hidden tune_* options to the
# OwnNet edition, wrap the binary in a script that exports FARZIN_TUNE=1.
set -eu
NAME=$1
NEW=$2
BASE=$3
shift 3
FC=${FASTCHESS:-fastchess}
BOOK=${BOOK:-UHO_Lichess_4852_v1.epd}
TC=${TC:-8+0.08}
OUT=${OUT:-sprt-results}
mkdir -p "$OUT"
# shellcheck disable=SC2086
exec "$FC" \
    -engine cmd="$NEW" name="$NAME" ${NEW_OPTS:-} \
    -engine cmd="$BASE" name=base ${BASE_OPTS:-} \
    -each tc="$TC" option.Hash=16 option.Threads=1 \
    -openings file="$BOOK" format=epd order=random \
    -srand "${SEED:-$(date +%s)}" \
    -rounds "${ROUNDS:-3000}" -games 2 -repeat \
    -concurrency "${CONC:-$(nproc)}" \
    -sprt elo0="${ELO0:-0}" elo1="${ELO1:-10}" alpha="${ALPHA:-0.05}" beta="${BETA:-0.05}" model=logistic \
    -draw movenumber=40 movecount=8 score=10 \
    -resign movecount=4 score=1000 twosided=true \
    -ratinginterval 20 -report penta=true \
    -pgnout file="$OUT/$NAME.pgn" \
    -recover "$@"

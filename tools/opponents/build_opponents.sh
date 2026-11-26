#!/bin/sh
# Rebuild the CCRL Blitz opponents used in docs/ccrl-improvement-2026-11-fa.md
# (the engines that scored >= 50% against Farzin 0.5.2 on CCRL, or are rated
# above it), from their public sources at the tested versions.
#
#   tools/opponents/build_opponents.sh WORKDIR
#
# Binaries land in WORKDIR/engines. All builds target x86-64-v3 (AVX2/BMI2),
# the instruction set of Farzin's CCRL executable. Needs git, make, g++,
# clang++ (+lld), cmake, cargo and curl. Nothing here is redistributed by
# Farzin; each engine keeps its own licence.
set -eu
W=${1:?usage: build_opponents.sh WORKDIR}
mkdir -p "$W/src" "$W/engines" "$W/nets"
W=$(cd "$W" && pwd)

clone() { # repo tag dir commit
    [ -d "$W/src/$3" ] || git clone -q --depth 1 --branch "$2" "https://github.com/$1" "$W/src/$3"
    test "$(git -C "$W/src/$3" rev-parse HEAD)" = "$4"
}

# Thrawn 3.2 (CCRL Blitz 3592) - network from the thrawn-nnue release.
clone feftywacky/thrawn v3.2 thrawn e814f72db8090cb6b1c53c038702b378b1606f6d
curl -sSL -o "$W/nets/thrawn-nn-2.nnue" \
    https://github.com/feftywacky/thrawn-nnue/releases/download/thrawn-nn-2/thrawn-nn-2.nnue
echo "abb8dd8fb6756d76a097fca62431f9e2694c0d2e54d7fea03a397446552dfa05  $W/nets/thrawn-nn-2.nnue" | sha256sum -c
make -C "$W/src/thrawn" -j"$(nproc)" ARCH=x86-64-avx2 NNUE_FILE="$W/nets/thrawn-nn-2.nnue"
cp "$W/src/thrawn/build/thrawn-v3.2-linux-x64-avx2" "$W/engines/thrawn"

# Eleanor 4.1 (3588) - network in the repository.
clone rektdie/Eleanor v4.1 eleanor 390ee23e75eae25ca3f37c9ea32f1dc583af3882
make -C "$W/src/eleanor" ARCH_FLAGS="-march=x86-64-v3"
cp "$W/src/eleanor/Eleanor" "$W/engines/eleanor"

# Black Marlin 9.0 (3589) - network stored with git LFS.
clone jnlt3/blackmarlin 9.0 blackmarlin 83826c1ec45d7698b33de151fe0d6c642e9ff4f5
curl -sSL -o "$W/src/blackmarlin/nn/default.bin" \
    https://media.githubusercontent.com/media/jnlt3/blackmarlin/9.0/nn/default.bin
echo "d3d48148b7c64478d97afcb2348ab9372da9cf049a8ed08c0a4513f5e3adf8ff  $W/src/blackmarlin/nn/default.bin" | sha256sum -c
(cd "$W/src/blackmarlin" && RUSTFLAGS="-C target-cpu=x86-64-v3" cargo build --release --target-dir "$W/target/bm")
cp "$W/target/bm/release/blackmarlin" "$W/engines/blackmarlin"

# Altair 7.0.0 (3579) - network in the repository (incbin, relative path).
clone Alex2262/AltairChessEngine v7.0.0 altair 9b52e0e14963acf6409cc183fda01455d8059b7b
(cd "$W/src/altair" && clang++ -O3 -std=c++20 -march=x86-64-v3 -DNDEBUG -flto -fuse-ld=lld \
    -pthread src/*.cpp -o "$W/engines/altair")

# akimbo 1.0.0 (3567) - network in the repository.
clone jw1912/akimbo v1.0.0 akimbo 3bfea08c8c56c462a28cb1f3b76a442938e8085f
(cd "$W/src/akimbo" && EVALFILE=resources/net.bin RUSTFLAGS="-C target-cpu=x86-64-v3" \
    cargo build --release --target-dir "$W/target/akimbo")
cp "$W/target/akimbo/release/akimbo" "$W/engines/akimbo"

# Texel 1.12 (3562) - network in the repository.
clone peterosterlund2/texel 1.12 texel bd5698c67f3c1841db623296cfd49d4a37abd5a3
cmake -S "$W/src/texel" -B "$W/target/texel" -DCMAKE_BUILD_TYPE=Release -DUSE_SSSE3=ON \
    -DUSE_AVX2=ON -DUSE_BMI2=ON -DUSE_POPCNT=ON -DUSE_CTZ=ON -DUSE_PREFETCH=ON
cmake --build "$W/target/texel" -j"$(nproc)" --target texel
cp "$W/target/texel/texel" "$W/engines/texel"

# Match runner.
[ -d "$W/src/fastchess" ] || git clone -q https://github.com/Disservin/fastchess "$W/src/fastchess"
git -C "$W/src/fastchess" checkout -q 07fc150ac666f0c4e590810d63bce4d280ef8d2e
make -C "$W/src/fastchess" -j"$(nproc)"
cp "$W/src/fastchess/fastchess" "$W/engines/fastchess"
ls -l "$W/engines"

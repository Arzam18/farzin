# Farzin 0.6.0 — OwnNet competition edition

Farzin is a UCI chess engine written in Rust. **Farzin 0.6.0** is the edition
for rating lists such as CCRL. It embeds only Farzin's own network,
`fzn2-b1.nnue`. It contains no Stockfish network weights and no Stockfish
source code.

0.6.0 adds **Syzygy endgame tablebase support** through the vendored Fathom
prober (MIT). CCRL Blitz tests engines with 4–6-piece tables. The search,
evaluation, time management and FZN2-b1 weights are unchanged from 0.5.2:
without `SyzygyPath` the engine searches exactly like 0.5.2 (same bench node
count, 992681 at depth 12, and the same depth-12 scores, node counts and PVs;
CI checks this against the v0.5.2 source). The UCI identity is
`Farzin 0.6.0`.

How the change was chosen and measured (CCRL game analysis, gauntlets
against the engines Farzin lost to, SPRT tests, tablebase match, regression
suites) is described in `docs/ccrl-improvement-2026-11-fa.md` (Persian).

## Tablebases

| option | default | notes |
|---|---|---|
| `SyzygyPath` | `<empty>` | directory of `.rtbw`/`.rtbz` files; several directories separated by `:` (Linux) or `;` (Windows) |
| `SyzygyProbeDepth` | 1 | minimum remaining depth for probes in the search |
| `Syzygy50MoveRule` | true | cursed wins and blessed losses count as draws |

* In the search, the WDL tables are probed after captures and pawn moves
  (the positions where a WDL probe is exact). Wins and losses get a score
  below the mate range and are stored in the transposition table.
* At the root, the DTZ tables rank the legal moves and the search chooses
  among the best-ranked moves only, so a won position is converted (the
  fifty-move counter keeps being reset) and a drawn position is held. The
  reported score is then the tablebase result.
* `info ... tbhits N` reports the number of probes.
* Tables are not included; download them from any Syzygy mirror.

## License and source

Farzin is licensed under **GPL-3.0-only**. The archive includes the complete
`LICENSE` and `THIRD_PARTY_NOTICES.md` (now also with Fathom's MIT licence).
Corresponding source, including the network and build scripts, is available
at: https://github.com/ar-karkon/farzin/tree/v0.6.0

## Hardware requirements (files)

| file | target CPU | use |
|---|---|---|
| `farzin-0.6.0-windows-x64-avx2-bmi2.exe` | x86-64-v3: AVX2, BMI1, **BMI2 (PEXT)**, FMA, LZCNT, MOVBE, POPCNT | **Main build.** Intel Haswell (2013) or newer, AMD Zen 3 or newer |
| `farzin-0.6.0-windows-x64-avx2.exe` | x86-64-v3 without BMI2 (magic bitboards) | AMD Zen 1/Zen 2, where PEXT is microcoded and slow |
| `farzin-0.6.0-windows-x64-popcnt.exe` | x86-64-v2: SSE4.2, POPCNT | older CPUs without AVX2 (slower network code) |
| `farzin-0.6.0-linux-x64-avx2-bmi2` | as the main build | Linux |
| `SHA256SUMS` | | checksums |

All builds play identical moves at a fixed depth (same `bench` node count,
992681 at depth 12). Only their speed differs. Each build checks the CPU at
start-up, before any other code runs. On an unsupported CPU it prints a
clear message (also as a UCI `info string`) and exits with status 1 instead
of crashing.

The Windows executables are self-contained. They link the C runtime
statically and import only Windows system DLLs. No Rust, Python or other
runtime is needed. Windows 10 or 11 (x64) is required.

## Usage

Add the `.exe` to any UCI GUI (Cute Chess, Arena, Banksia, Fritz/ChessBase,
Shredder, and others). Options:

| option | default | notes |
|---|---|---|
| `Hash` | 16 | MB, 1–65536 |
| `Threads` | 1 | 1–256, Lazy SMP |
| `Move Overhead` | 50 | ms kept in reserve per move for GUI/OS latency |
| `Ponder` | false | `go ponder` / `ponderhit` are supported |
| `Clear Hash` | button | |
| `EvalFile` | `<default>` | `<default>` = embedded FZN2 net |
| `SyzygyPath`, `SyzygyProbeDepth`, `Syzygy50MoveRule` | | see above |

Command-line checks:

```
farzin-0.6.0-windows-x64-avx2-bmi2.exe --version
farzin-0.6.0-windows-x64-avx2-bmi2.exe bench
```

`--version` prints the edition, the compiled CPU features, the slider method
and the embedded network's name, architecture and SHA-256. For example:

```
Farzin 0.6.0 edition OwnNet target x86_64 features [popcnt,avx2,bmi2] sliders pext net fzn2-b1.nnue FZN2 4x768x768 buckets 8 mirrored sha256 3ec5aa7e6c16b1ea6bd366ad873f4b649da310c91204915000bfd5f1e90ebfc0
```

## Network provenance

Unchanged from 0.5.1/0.5.2: `fzn2-b1.nnue` (sha256
`3ec5aa7e6c16b1ea6bd366ad873f4b649da310c91204915000bfd5f1e90ebfc0`). It was
trained by Farzin's own trainer on positions from Farzin self-play, with
labels from the CC0 Stockfish-project network `nn-ad9b42354671.nnue`
(distillation; no Stockfish weights are embedded or used at run time). Full
details: `nets/README.md` (packaged as `NETWORK-PROVENANCE.md`) and
`docs/RELEASE-0.5.md`.

A candidate successor network (`fzn2-c1`, trained further from b1 on 59.3M
positions) was tested against b1 by SPRT and not adopted; see the CCRL
improvement report.

## Reproducible build

The release is built on Linux (Ubuntu 24.04) by cross-compiling with rustc
**1.97.0**, the Ubuntu 24.04 `gcc` (Fathom, Linux build) and mingw-w64
(Windows builds):

```bash
rustup toolchain install 1.97.0 --target x86_64-pc-windows-gnu
sudo apt-get install mingw-w64
git checkout <release commit>
RUSTUP_TOOLCHAIN=1.97.0 tools/build_release.sh dist
cat dist/SHA256SUMS
```

Paths are remapped, timestamps are suppressed and symbols are stripped. Two
builds from different directories produce bit-identical files. The CI job
`release-build` repeats the build on a fresh GitHub runner, compares it with
`benchmarks/release-0.6.0/SHA256SUMS` and uploads `dist/` as the artifact
`farzin-release-candidate`.

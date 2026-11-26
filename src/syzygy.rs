//! Syzygy endgame tablebase support through the vendored Fathom prober
//! (`third_party/fathom`, MIT licence).
//!
//! * In the search, WDL tables are probed after zeroing moves (captures and
//!   pawn moves, i.e. when the fifty-move counter is zero), as Fathom's WDL
//!   probe is only exact there.
//! * At the root, the DTZ tables rank the legal moves (preserving the
//!   theoretical result under the fifty-move rule, and making progress
//!   when winning); the search is then restricted to the best-ranked moves.
//!
//! Fathom keeps global state: [`init`] must not run while a search is in
//! progress. WDL probes are thread safe; the root probe is not, so it is
//! done once by the UCI layer before helper threads start.
use crate::board::Board;
use crate::movegen::legal_moves;
use crate::types::*;
use std::ffi::CString;
use std::os::raw::{c_char, c_int, c_uint};
use std::sync::atomic::{AtomicBool, AtomicI32, AtomicUsize, Ordering};
use std::sync::Mutex;

const TB_MAX_MOVES: usize = 192 + 1;
const TB_MAX_PLY: usize = 256;
const TB_RESULT_FAILED: c_uint = 0xFFFF_FFFF;

#[repr(C)]
struct TbRootMove {
    mv: u16,
    pv: [u16; TB_MAX_PLY],
    pv_size: c_uint,
    tb_score: i32,
    tb_rank: i32,
}

#[repr(C)]
struct TbRootMoves {
    size: c_uint,
    moves: [TbRootMove; TB_MAX_MOVES],
}

#[cfg(not(farzin_no_fathom))]
extern "C" {
    fn tb_init(path: *const c_char) -> bool;
    fn tb_free();
    static TB_LARGEST: c_uint;
    fn tb_probe_wdl_impl(
        white: u64,
        black: u64,
        kings: u64,
        queens: u64,
        rooks: u64,
        bishops: u64,
        knights: u64,
        pawns: u64,
        ep: c_uint,
        turn: bool,
    ) -> c_uint;
    fn tb_probe_root_dtz(
        white: u64,
        black: u64,
        kings: u64,
        queens: u64,
        rooks: u64,
        bishops: u64,
        knights: u64,
        pawns: u64,
        rule50: c_uint,
        castling: c_uint,
        ep: c_uint,
        turn: bool,
        has_repeated: bool,
        use_rule50: bool,
        results: *mut TbRootMoves,
    ) -> c_int;
    fn tb_probe_root_wdl(
        white: u64,
        black: u64,
        kings: u64,
        queens: u64,
        rooks: u64,
        bishops: u64,
        knights: u64,
        pawns: u64,
        rule50: c_uint,
        castling: c_uint,
        ep: c_uint,
        turn: bool,
        use_rule50: bool,
        results: *mut TbRootMoves,
    ) -> c_int;
}

// Stand-ins when build.rs could not compile Fathom (MSVC without C11
// atomics): nothing ever loads, so the probes below are never reached.
#[cfg(farzin_no_fathom)]
static TB_LARGEST: c_uint = 0;
#[cfg(farzin_no_fathom)]
unsafe fn tb_init(_path: *const c_char) -> bool {
    false
}
#[cfg(farzin_no_fathom)]
unsafe fn tb_free() {}
#[cfg(farzin_no_fathom)]
#[allow(clippy::too_many_arguments)]
#[rustfmt::skip]
unsafe fn tb_probe_wdl_impl(
    _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: c_uint, _: bool,
) -> c_uint {
    TB_RESULT_FAILED
}
#[cfg(farzin_no_fathom)]
#[allow(clippy::too_many_arguments)]
#[rustfmt::skip]
unsafe fn tb_probe_root_dtz(
    _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: c_uint, _: c_uint,
    _: c_uint, _: bool, _: bool, _: bool, _: *mut TbRootMoves,
) -> c_int {
    0
}
#[cfg(farzin_no_fathom)]
#[allow(clippy::too_many_arguments)]
#[rustfmt::skip]
unsafe fn tb_probe_root_wdl(
    _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: u64, _: c_uint, _: c_uint,
    _: c_uint, _: bool, _: bool, _: *mut TbRootMoves,
) -> c_int {
    0
}

/// Largest number of pieces covered by the loaded tables (0 = none).
static LARGEST: AtomicUsize = AtomicUsize::new(0);
/// Probe in the search only from this remaining depth (unless the position
/// has fewer pieces than the largest tables).
pub static PROBE_DEPTH: AtomicI32 = AtomicI32::new(1);
/// Treat cursed wins / blessed losses as draws (the fifty-move rule).
pub static RULE50: AtomicBool = AtomicBool::new(true);
/// Fathom's init/free are not reentrant.
static INIT_LOCK: Mutex<()> = Mutex::new(());

/// Win/draw/loss from the side to move's point of view, Fathom order:
/// loss, blessed loss, draw, cursed win, win as -2..=2.
pub type Wdl = i32;

/// Load tables from `path` (separate several directories with ':' on Unix,
/// ';' on Windows). An empty path or `<empty>` unloads them. Returns the
/// largest piece count available.
pub fn init(path: &str) -> usize {
    let _guard = INIT_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    let path = path.trim();
    if path.is_empty() || path == "<empty>" {
        unsafe { tb_free() };
        LARGEST.store(0, Ordering::Relaxed);
        return 0;
    }
    let Ok(c) = CString::new(path) else {
        return 0;
    };
    let ok = unsafe { tb_init(c.as_ptr()) };
    let n = if ok {
        unsafe { std::ptr::addr_of!(TB_LARGEST).read() as usize }
    } else {
        0
    };
    LARGEST.store(n, Ordering::Relaxed);
    n
}

#[inline]
pub fn largest() -> usize {
    LARGEST.load(Ordering::Relaxed)
}

struct Bbs {
    white: u64,
    black: u64,
    kings: u64,
    queens: u64,
    rooks: u64,
    bishops: u64,
    knights: u64,
    pawns: u64,
    ep: c_uint,
    turn: bool,
}

fn bbs(board: &Board) -> Bbs {
    Bbs {
        white: board.colors[WHITE],
        black: board.colors[BLACK],
        kings: board.pieces[KING],
        queens: board.pieces[QUEEN],
        rooks: board.pieces[ROOK],
        bishops: board.pieces[BISHOP],
        knights: board.pieces[KNIGHT],
        pawns: board.pieces[PAWN],
        ep: if board.ep < 64 {
            c_uint::from(board.ep)
        } else {
            0
        },
        turn: board.stm == WHITE,
    }
}

/// Can `board` be probed at all (enough tables, no castling rights)?
#[inline]
pub fn probeable(board: &Board) -> bool {
    let n = largest();
    n > 0 && board.castling == 0 && (board.occupied().count_ones() as usize) <= n
}

/// WDL probe for use inside the search. Exact only when the fifty-move
/// counter is zero (Fathom refuses other positions), so callers probe after
/// zeroing moves only.
pub fn probe_wdl(board: &Board) -> Option<Wdl> {
    if !probeable(board) || board.halfmove != 0 {
        return None;
    }
    let b = bbs(board);
    let r = unsafe {
        tb_probe_wdl_impl(
            b.white, b.black, b.kings, b.queens, b.rooks, b.bishops, b.knights, b.pawns, b.ep,
            b.turn,
        )
    };
    if r == TB_RESULT_FAILED {
        None
    } else {
        Some(r as i32 - 2)
    }
}

/// Fathom move encoding: to (6 bits) | from (6 bits) << 6 | promotion << 12,
/// promotion 1..=4 = queen, rook, bishop, knight.
fn decode(board: &Board, tb_move: u16) -> Option<Move> {
    let to = usize::from(tb_move & 63);
    let from = usize::from((tb_move >> 6) & 63);
    let promo = match (tb_move >> 12) & 7 {
        1 => Some(QUEEN),
        2 => Some(ROOK),
        3 => Some(BISHOP),
        4 => Some(KNIGHT),
        _ => None,
    };
    legal_moves(board).into_iter().find(|m| {
        m.from() == from
            && m.to() == to
            && match promo {
                Some(p) => m.is_promotion() && m.promotion() == p,
                None => !m.is_promotion(),
            }
    })
}

/// Result of ranking the root moves with the tables.
#[derive(Clone, Debug, Default)]
pub struct RootProbe {
    /// The legal moves that keep the best achievable result, best DTZ rank
    /// first. The search is restricted to these.
    pub moves: Vec<Move>,
    /// WDL of the position for the side to move (-2..=2).
    pub wdl: Wdl,
    /// Whether DTZ tables were used (otherwise WDL-only ranking).
    pub dtz: bool,
}

/// Rank the root moves with DTZ tables (falling back to WDL). `has_repeated`
/// tells whether a position has repeated since the last zeroing move.
/// Returns `None` if the root is not covered by the tables.
pub fn probe_root(board: &Board, has_repeated: bool) -> Option<RootProbe> {
    if !probeable(board) {
        return None;
    }
    let b = bbs(board);
    let rule50 = RULE50.load(Ordering::Relaxed);
    // ~100 KiB: keep it off the (helper thread) stack.
    let mut results: Box<TbRootMoves> = unsafe { Box::new(std::mem::zeroed()) };
    let mut dtz = true;
    let ok = unsafe {
        tb_probe_root_dtz(
            b.white,
            b.black,
            b.kings,
            b.queens,
            b.rooks,
            b.bishops,
            b.knights,
            b.pawns,
            c_uint::from(board.halfmove),
            0,
            b.ep,
            b.turn,
            has_repeated,
            rule50,
            &mut *results,
        )
    };
    if ok == 0 {
        dtz = false;
        results.size = 0;
        let ok = unsafe {
            tb_probe_root_wdl(
                b.white,
                b.black,
                b.kings,
                b.queens,
                b.rooks,
                b.bishops,
                b.knights,
                b.pawns,
                c_uint::from(board.halfmove),
                0,
                b.ep,
                b.turn,
                rule50,
                &mut *results,
            )
        };
        if ok == 0 {
            return None;
        }
    }
    let n = (results.size as usize).min(TB_MAX_MOVES);
    if n == 0 {
        return None;
    }
    let best_rank = results.moves[..n].iter().map(|m| m.tb_rank).max()?;
    let mut ranked: Vec<(i32, Move)> = Vec::new();
    for rm in &results.moves[..n] {
        if rm.tb_rank == best_rank {
            ranked.push((rm.tb_score, decode(board, rm.mv)?));
        }
    }
    ranked.sort_by_key(|(score, _)| -score);
    // Fathom ranks: certain win 1000 (900 = needs exactly 100 plies), draw 0,
    // loss -1000; with the fifty-move rule, ranks strictly between -900 and
    // 900 are cursed wins / blessed losses (without it the bound is 1).
    let bound = if rule50 { 900 } else { 1 };
    let wdl = if best_rank >= bound {
        2
    } else if best_rank > 0 {
        1
    } else if best_rank == 0 {
        0
    } else if best_rank > -bound {
        -1
    } else {
        -2
    };
    Some(RootProbe {
        moves: ranked.into_iter().map(|(_, m)| m).collect(),
        wdl,
        dtz,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_matches_legal_moves() {
        let board = Board::from_fen("8/4P3/8/8/8/8/k7/4K3 w - - 0 1").unwrap();
        // e7e8 = from 52, to 60, queen promotion.
        let mv = decode(&board, 60 | (52 << 6) | (1 << 12)).unwrap();
        assert_eq!(mv.to_uci(), "e7e8q");
        let mv = decode(&board, 60 | (52 << 6) | (4 << 12)).unwrap();
        assert_eq!(mv.to_uci(), "e7e8n");
        assert!(decode(&board, 60 | (52 << 6)).is_none());
    }

    /// Needs real tables: set FARZIN_SYZYGY_PATH to a directory holding at
    /// least the 3- and 4-piece files.
    #[test]
    fn probes_known_endgames() {
        let Ok(path) = std::env::var("FARZIN_SYZYGY_PATH") else {
            return;
        };
        assert!(init(&path) >= 4);
        let kqk = Board::from_fen("8/8/8/4k3/8/8/8/KQ6 w - - 0 1").unwrap();
        assert_eq!(probe_wdl(&kqk), Some(2));
        let kqk_b = Board::from_fen("8/8/8/4k3/8/8/8/KQ6 b - - 0 1").unwrap();
        assert_eq!(probe_wdl(&kqk_b), Some(-2));
        let knk = Board::from_fen("8/8/8/4k3/8/8/8/KN6 w - - 0 1").unwrap();
        assert_eq!(probe_wdl(&knk), Some(0));
        let krk = Board::from_fen("8/8/8/4k3/8/8/8/KR6 w - - 0 1").unwrap();
        assert_eq!(probe_wdl(&krk), Some(2));
        let kbk = Board::from_fen("8/8/8/4k3/8/8/8/KB6 b - - 0 1").unwrap();
        assert_eq!(probe_wdl(&kbk), Some(0));
        let root = probe_root(&kqk, false).unwrap();
        assert_eq!(root.wdl, 2);
        assert!(!root.moves.is_empty());
        init("");
        assert_eq!(largest(), 0);
    }
}

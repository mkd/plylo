// @ts-nocheck
import { useState, useEffect, useRef, useCallback } from 'react';
import { Chess } from 'chess.js';
import { Chessboard } from 'react-chessboard';
import axios from 'axios';
import './App.css';

axios.defaults.withCredentials = true;
const API = import.meta.env.PROD ? '/plylo/api' : '/api';

/* ── Types ──────────────────────────────────── */

interface ServerStatus {
  status: string;
  n_accepted: number;
  t_trained: number;
}

interface GameState {
  id: string;
  visitor_color: string;
  pinned_age: number;
  state: 'active' | 'completed' | 'aborted';
  result: number | null;
  moves: string[];   // UCI strings from server
}

/* ── Root ───────────────────────────────────── */

export default function App() {
  const [tab, setTab] = useState<'play' | 'explorer' | 'archive'>('play');
  const [status, setStatus] = useState<ServerStatus | null>(null);

  useEffect(() => {
    const poll = () => axios.get(`${API}/status`).then(r => setStatus(r.data)).catch(() => {});
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="app-container">
      <header className="header">
        <h1 onClick={() => window.location.reload()} style={{cursor: 'pointer'}} title="Reset to initial state">Plylo</h1>
        <div className="tabs">
          {(['play', 'explorer', 'archive'] as const).map(t => (
            <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <div className="stats">
          <p>Experience: <span>{status?.n_accepted ?? '–'}</span> games</p>
        </div>
      </header>

      <main className="main-content">
        {tab === 'play'     && <PlayTab status={status} />}
        {tab === 'explorer' && <ExplorerTab status={status} />}
        {tab === 'archive'  && <ArchiveTab />}
      </main>
    </div>
  );
}

/* ══════════════════════════════════════════════
   Play Tab
   ══════════════════════════════════════════════ */

function PlayTab({ status }: { status: ServerStatus | null }) {
  const [game, setGame]             = useState<GameState | null>(null);
  const [chess, setChess]           = useState(() => new Chess());
  const [orientation, setOrientation] = useState<'white' | 'black'>('white');
  const [color, setColor]           = useState<'white' | 'black' | 'random'>('white');
  const [pinAge, setPinAge]         = useState(false);
  const [age, setAge]               = useState(0);
  const [reviewPly, setReviewPly]   = useState<number | null>(null);
  const movesGridRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (movesGridRef.current) {
      movesGridRef.current.scrollTop = movesGridRef.current.scrollHeight;
    }
  }, [game?.moves?.length]);

  const [waiting, setWaiting]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const pollRef                     = useRef<number | null>(null);

  // If "Latest", track server age
  useEffect(() => {
    if (!pinAge && status) setAge(status.t_trained);
  }, [status?.t_trained, pinAge]);

  // Restore active game from localStorage
  useEffect(() => {
    const gid = localStorage.getItem('plylo_game_id');
    if (gid) startPolling(gid);
    return () => stopPolling();
  }, []);

  const startPolling = useCallback((gid: string) => {
    stopPolling();
    // Fetch once immediately
    axios.get(`${API}/games/${gid}`).then(r => applyState(r.data)).catch(() => {
      localStorage.removeItem('plylo_game_id');
    });
    pollRef.current = window.setInterval(() => {
      axios.get(`${API}/games/${gid}`).then(r => applyState(r.data)).catch(() => {});
    }, 1200);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const applyState = useCallback((data: GameState) => {
    setGame(data);
    const c = new Chess();
    // Server sends UCI moves; replay them via UCI
    for (const uci of data.moves) {
      const from = uci.slice(0, 2);
      const to   = uci.slice(2, 4);
      const promo = uci.length > 4 ? uci[4] : undefined;
      c.move({ from, to, promotion: promo });
    }
    setChess(c);
    setWaiting(false);

    if (data.state !== 'active') {
      stopPolling();
    } else {
      // Is it bot's turn? show waiting indicator
      const botColor = data.visitor_color === 'white' ? 'b' : 'w';
      if (c.turn() === botColor) setWaiting(true);
    }
  }, [stopPolling]);

  /* ── Start Game ── */
  const handleStart = async () => {
    setError(null);
    let c = color;
    if (c === 'random') c = Math.random() > 0.5 ? 'white' : 'black';
    setOrientation(c as 'white' | 'black');
    setReviewPly(null);
    try {
      const r = await axios.post(`${API}/games`, {
        visitor_color: c,
        target_age: pinAge ? age : null,
      });
      localStorage.setItem('plylo_game_id', r.data.id);
      applyState(r.data);
      startPolling(r.data.id);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to start game');
    }
  };

  const [moveFrom, setMoveFrom] = useState<string | null>(null);
  const [moveTo, setMoveTo] = useState<string | null>(null);
  const [showPromo, setShowPromo] = useState(false);

  /* ── Piece Drop (react-chessboard v5 API) ── */
  const handleDrop = useCallback(({ piece, sourceSquare, targetSquare }: any) => {
    if (!targetSquare) return false;           // dropped off board
    if (reviewPly !== null) return false;       // in review mode

    // If there's an active game, check turn. If no game, let them drag to start!
    if (game && game.state === 'active') {
      const visitorTurn =
        (chess.turn() === 'w' && game.visitor_color === 'white') ||
        (chess.turn() === 'b' && game.visitor_color === 'black');
      if (!visitorTurn) return false;
    } else if (game && game.state !== 'active') {
      return false; // completed game, no dragging
    }

    // Detect promotion
    const isPawn = piece?.pieceType?.toLowerCase?.() === 'p'
                || (typeof piece === 'string' && piece[1] === 'P')
                || (typeof piece === 'string' && piece[1] === 'p');
    const promoRank = chess.turn() === 'w' ? '8' : '1';
    const isPromo = isPawn && targetSquare[1] === promoRank;

    if (isPromo) {
      setMoveFrom(sourceSquare);
      setMoveTo(targetSquare);
      setShowPromo(true);
      return false; // Wait for dialog
    }

    return executeMove(sourceSquare, targetSquare, undefined);
  }, [chess, game, reviewPly, pinAge, age]);

  const executeMove = (sourceSquare: string, targetSquare: string, promo?: string) => {
    const uci = sourceSquare + targetSquare + (promo || '');

    try {
      const m = chess.move({ from: sourceSquare, to: targetSquare, promotion: promo });
      if (!m) return false;
    } catch { return false; }

    setChess(new Chess(chess.fen()));
    setWaiting(true);

    if (!game) {
      // Implicitly start a new game
      const visitorColor = chess.turn() === 'b' ? 'white' : 'black';
      setOrientation(visitorColor);
      axios.post(`${API}/games`, {
        visitor_color: visitorColor,
        target_age: pinAge ? age : null,
      }).then(r => {
        localStorage.setItem('plylo_game_id', r.data.id);
        // Immediately post the move
        axios.post(`${API}/games/${r.data.id}/move`, { uci }).then(() => {
          startPolling(r.data.id);
        }).catch(() => {
          // If move fails, still poll the created game
          startPolling(r.data.id);
        });
      }).catch(e => {
        setError(e?.response?.data?.detail || 'Failed to start game');
        chess.undo();
        setChess(new Chess(chess.fen()));
        setWaiting(false);
      });
      return true;
    }

    // Existing game move
    axios.post(`${API}/games/${game.id}/move`, { uci }).catch(() => {
      chess.undo();
      setChess(new Chess(chess.fen()));
      setWaiting(false);
    });
    return true;
  };

  const onPromotionPieceSelect = (piece?: string) => {
    if (piece && moveFrom && moveTo) {
      const promo = piece[1].toLowerCase(); // e.g. "wQ" -> "q"
      executeMove(moveFrom, moveTo, promo);
    }
    setShowPromo(false);
    setMoveFrom(null);
    setMoveTo(null);
    return true;
  };

  /* ── Resign ── */
  const handleResign = async () => {
    if (!game) return;
    await axios.post(`${API}/games/${game.id}/resign`).catch(() => {});
  };

  /* ── Abort ── */
  const handleAbort = async () => {
    if (!game) return;
    await axios.post(`${API}/games/${game.id}/abort`).catch(() => {});
  };

  /* ── New Game (reset) ── */
  const handleNew = () => {
    stopPolling();
    setGame(null);
    setChess(new Chess());
    setReviewPly(null);
    setWaiting(false);
    localStorage.removeItem('plylo_game_id');
  };

  /* ── Review Board ── */
  const displayFen = (() => {
    if (reviewPly === null) return chess.fen();
    const t = new Chess();
    for (let i = 0; i < reviewPly && game; i++) {
      const u = game.moves[i];
      t.move({ from: u.slice(0,2), to: u.slice(2,4), promotion: u.length > 4 ? u[4] : undefined });
    }
    return t.fen();
  })();

  /* ── Result label ── */
  const resultLabel = game?.termination === 'abort' ? 'Game Aborted'
    : game?.result === 1.0 ? 'White wins'
    : game?.result === -1.0 ? 'Black wins'
    : game?.result === 0.0  ? 'Draw' : '';

  /* ── Move list with move-number grid ── */
  const renderMoves = () => {
    if (!game || game.moves.length === 0) return null;
    const rows: React.ReactNode[] = [];
    const c = new Chess();
    for (let i = 0; i < game.moves.length; i++) {
      const u = game.moves[i];
      const san = c.move({ from: u.slice(0,2), to: u.slice(2,4), promotion: u.length>4?u[4]:undefined })?.san || u;
      if (i % 2 === 0) {
        rows.push(<span key={`n${i}`} className="move-number">{Math.floor(i/2)+1}.</span>);
      }
      rows.push(
        <span key={i}
              className={`move-cell${reviewPly === i+1 ? ' active' : ''}`}
              onClick={() => setReviewPly(i+1)}>
          {san}
        </span>
      );
      if (i % 2 === 0 && i === game.moves.length - 1) {
        rows.push(<span key="empty" className="move-cell empty" />);
      }
    }
    return rows;
  };

  const isSetup = !game || game.state !== 'active';

  return (
    <>
      <div className="sidebar">
        {isSetup ? (
          <div className="setup-panel">
            <h2>New Game</h2>
            <div className="control-group">
              <label>Play as</label>
              <select value={color} onChange={e => setColor(e.target.value as any)}>
                <option value="white">White</option>
                <option value="black">Black</option>
                <option value="random">Random</option>
              </select>
            </div>

            <div className="control-group">
              <label className="checkbox-label">
                <input type="checkbox" checked={pinAge} onChange={e => setPinAge(e.target.checked)} />
                Pin exact age
              </label>
              {pinAge && (
                <div className="age-slider">
                  <input type="range" min={0} max={status?.t_trained || 0} value={age}
                         onChange={e => setAge(+e.target.value)} />
                  <input type="number" min={0} max={status?.t_trained || 0} value={age}
                         onChange={e => setAge(+e.target.value)} />
                </div>
              )}
              {!pinAge && <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                Using latest age ({status?.t_trained ?? 0})
              </span>}
            </div>

            <button className="btn btn-primary" onClick={handleStart}>Play</button>

            {error && <p style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>{error}</p>}

            {game?.state === 'completed' && (
              <button className="btn btn-secondary" onClick={handleNew}>New Game</button>
            )}
          </div>
        ) : (
          <div className="active-panel">
            <h2>Playing vs Age {game.pinned_age}</h2>
            {waiting && (
              <div className="waiting-indicator">
                <div className="waiting-dot" />
                Bot is thinking…
              </div>
            )}
            <div className="btn-row">
              <button className="btn btn-danger btn-small" onClick={handleResign} title="Surrender the game (Bot learns from win)">Resign</button>
              <button className="btn btn-secondary btn-small" onClick={handleAbort} title="Cancel the game (No learning)">Abort</button>
            </div>
          </div>
        )}

        <button className="flip-btn" onClick={() => setOrientation(o => o === 'white' ? 'black' : 'white')}>
          ⇅ Flip board
        </button>

        {game && game.moves.length > 0 && (
          <div className="move-list">
            <h3>Moves</h3>
            <div className="moves-grid" ref={movesGridRef}>{renderMoves()}</div>
            {reviewPly !== null && (
              <button className="btn btn-secondary btn-small" onClick={() => setReviewPly(null)}>
                ↻ Return to live
              </button>
            )}
          </div>
        )}
      </div>

      <div className="board-wrapper" style={{ position: 'relative' }}>
        <Chessboard options={{
          position: displayFen,
          boardOrientation: orientation,
          onPieceDrop: handleDrop,
          allowDragging: reviewPly === null && (!game || game.state === 'active'),
          showNotation: true,
          animationDurationInMs: 200,
          darkSquareStyle:  { backgroundColor: '#b58863' },
          lightSquareStyle: { backgroundColor: '#f0d9b5' }
        }} />
        
        {showPromo && (
          <div className="promotion-dialog">
            <p>Promote to:</p>
            <div className="promotion-pieces">
              {['q', 'r', 'b', 'n'].map(p => (
                <button key={p} onClick={() => onPromotionPieceSelect(p)}>
                  {p.toUpperCase()}
                </button>
              ))}
            </div>
            <button className="btn btn-secondary btn-small" onClick={() => onPromotionPieceSelect()}>Cancel</button>
          </div>
        )}

        {game?.state === 'completed' && (
          <div className="game-over-banner">
            <div className="game-over-inner">
              <h3>{resultLabel}</h3>
              <p>Opponent was Age {game.pinned_age}</p>
              <button className="btn btn-primary" onClick={handleNew}>New Game</button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

/* ══════════════════════════════════════════════
   Explorer Tab
   ══════════════════════════════════════════════ */

function ExplorerTab({ status }: { status: ServerStatus | null }) {
  const [cutoff, setCutoff]   = useState(0);
  const [prefix, setPrefix]   = useState<string[]>([]);
  const [data, setData]       = useState<any>(null);

  // Track latest age
  useEffect(() => {
    if (status) setCutoff(status.t_trained);
  }, [status?.t_trained]);

  useEffect(() => {
    axios.get(`${API}/explorer`, { params: { prefix: prefix.join(','), cutoff } })
      .then(r => setData(r.data))
      .catch(() => {});
  }, [prefix, cutoff]);

  // Build FEN for display
  const boardChess = new Chess();
  for (const uci of prefix) {
    try {
      boardChess.move({ from: uci.slice(0,2), to: uci.slice(2,4), promotion: uci.length>4?uci[4]:undefined });
    } catch { break; }
  }

  return (
    <>
      <div className="sidebar explorer-sidebar">
        <h2>Explorer</h2>
        <div className="control-group">
          <label>Experience cutoff: {cutoff}</label>
          <input type="range" min={0} max={status?.t_trained || 0} value={cutoff}
                 onChange={e => setCutoff(+e.target.value)} />
        </div>

        <div className="explorer-stats">
          <p>Games reaching this node: <strong>{data?.total ?? 0}</strong></p>
          <p>Games ending here: <strong>{data?.ended_here ?? 0}</strong></p>
        </div>

        <div className="btn-row">
          <button className="btn btn-secondary btn-small" disabled={!prefix.length}
                  onClick={() => setPrefix([])}>Reset</button>
          <button className="btn btn-secondary btn-small" disabled={!prefix.length}
                  onClick={() => setPrefix(p => p.slice(0,-1))}>← Back</button>
        </div>

        <div className="next-moves">
          <h3>Next moves</h3>
          {data?.moves?.length > 0 ? (
            <table>
              <thead><tr><th>Move</th><th>Games</th><th style={{color:'var(--win)'}}>W</th><th style={{color:'var(--draw)'}}>D</th><th style={{color:'var(--loss)'}}>L</th></tr></thead>
              <tbody>
                {data.moves.map((m: any) => (
                  <tr key={m.uci} className="explorer-move-row" onClick={() => setPrefix([...prefix, m.uci])}>
                    <td>{m.san}</td>
                    <td>{m.count}</td>
                    <td className="win-count">{m.wins}</td>
                    <td className="draw-count">{m.draws}</td>
                    <td className="loss-count">{m.losses}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="empty-state">
              {cutoff === 0
                ? 'Age 0 has no learned games yet.'
                : 'No recorded moves from this position.'}
            </p>
          )}
        </div>
      </div>

      <div className="board-wrapper">
        <Chessboard
          position={boardChess.fen()}
          arePiecesDraggable={false}
          showBoardNotation={true}
          customDarkSquareStyle={{ backgroundColor: '#b58863' }}
          customLightSquareStyle={{ backgroundColor: '#f0d9b5' }}
        />
      </div>
    </>
  );
}

/* ══════════════════════════════════════════════
   Archive Tab
   ══════════════════════════════════════════════ */

function ArchiveTab() {
  const [games, setGames] = useState<any[]>([]);
  const [page, setPage]   = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    axios.get(`${API}/archive`, { params: { page } }).then(r => {
      setGames(r.data.games);
      setTotal(r.data.total);
    });
  }, [page]);

  const resultStr = (g: any) =>
    g.termination === 'abort' ? 'Aborted' :
    g.result === 1 ? '1-0' : g.result === -1 ? '0-1' : g.result === 0 ? '½-½' : '?';

  return (
    <div className="archive-container">
      <h2>Game Archive</h2>
      <p>Total accepted games: {total}</p>
      <table className="archive-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Opp. Age</th>
            <th>Color</th>
            <th>Result</th>
            <th>Moves</th>
            <th>PGN</th>
          </tr>
        </thead>
        <tbody>
          {games.map(g => (
            <tr key={g.id}>
              <td>{g.sequence}</td>
              <td>{g.pinned_age}</td>
              <td>{g.visitor_color}</td>
              <td>{resultStr(g)}</td>
              <td>{g.moves.length}</td>
              <td><a href={`${API}/games/${g.id}/pgn`} target="_blank" rel="noreferrer">↓ PGN</a></td>
            </tr>
          ))}
          {games.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '2rem' }}>
              No completed games yet.
            </td></tr>
          )}
        </tbody>
      </table>
      <div className="pagination">
        <button className="btn btn-secondary btn-small" disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}>← Prev</button>
        <span>Page {page}</span>
        <button className="btn btn-secondary btn-small" disabled={games.length < 20}
                onClick={() => setPage(p => p + 1)}>Next →</button>
      </div>
    </div>
  );
}

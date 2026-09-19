import uuid
import chess
from fastapi import FastAPI, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime

from server.storage.database import get_db
from server.storage import models
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Plylo API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def get_status(db: Session = Depends(get_db)):
    timeline = db.query(models.Timeline).order_by(desc(models.Timeline.created_at)).first()
    if not timeline:
        return {"status": "no_timeline", "n_accepted": 0, "t_trained": 0}
    return {
        "status": "ok",
        "active_timeline": timeline.id,
        "n_accepted": timeline.n_accepted,
        "t_trained": timeline.t_trained,
    }

@app.on_event("startup")
def ensure_timeline():
    """Create the initial timeline (S0) if no timeline exists. Non-destructive."""
    from server.storage.database import SessionLocal
    db = SessionLocal()
    try:
        existing = db.query(models.Timeline).first()
        if not existing:
            import hashlib, json
            tl = models.Timeline(
                id="main",
                initialization_ref="s0_random_init",
                active_runtime="local",
            )
            db.add(tl)
            db.commit()
            print("[startup] Created initial timeline 'main' at age 0")
        else:
            print(f"[startup] Using existing timeline '{existing.id}' (N={existing.n_accepted}, T={existing.t_trained})")
    finally:
        db.close()

class GameCreateReq(BaseModel):
    visitor_color: str
    target_age: Optional[int] = None

class GameResp(BaseModel):
    id: str
    visitor_color: str
    pinned_age: int
    state: str
    result: Optional[float]
    moves: List[str] = []
    session_token: Optional[str] = None

class MoveReq(BaseModel):
    uci: str

def verify_session(game: models.Game, request: Request):
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization")
        if auth:
            token = auth.replace("Bearer ", "")
    if not token or token != game.session_token:
        raise HTTPException(status_code=403, detail="Invalid session token")

def mark_game_completed(db: Session, game: models.Game, result: float, termination: str):
    game.state = "completed"
    game.result = result
    game.termination = termination
    game.completed_at = datetime.utcnow()
    
    # Only assign sequence if it's a qualifying game (aborts don't count)
    if termination != "abort":
        # Atomically increment N and assign event
        timeline = db.query(models.Timeline).with_for_update().filter(models.Timeline.id == game.timeline_id).first()
        timeline.n_accepted += 1
        seq = timeline.n_accepted
        ev = models.ExperienceEvent(
            timeline_id=timeline.id,
            sequence=seq,
            game_id=game.id,
            trajectory_digest=f"traj_{game.id}_{seq}"
        )
        db.add(ev)
        
        # Enqueue trainer job (optional, trainer can also poll)
        # We rely on trainer polling ExperienceEvent where sequence > t_trained.

from fastapi import Response

@app.post("/api/games", response_model=GameResp)
def create_game(req: GameCreateReq, response: Response, db: Session = Depends(get_db)):
    timeline = db.query(models.Timeline).order_by(desc(models.Timeline.created_at)).first()
    if not timeline:
        raise HTTPException(status_code=400, detail="No active timeline")
        
    pinned_age = req.target_age if req.target_age is not None else timeline.t_trained
    session_token = uuid.uuid4().hex
    
    game = models.Game(
        id=str(uuid.uuid4()),
        timeline_id=timeline.id,
        visitor_color=req.visitor_color,
        pinned_age=pinned_age,
        runtime_digest="active", 
        seed=1337,
        session_token=session_token,
        state="active"
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    
    if game.visitor_color == "black":
        _enqueue_bot_move(db, game.id)
        
    response.set_cookie(key="session_token", value=session_token, httponly=True, samesite="lax")
    # Do not return session_token in JSON to avoid leaking to JS
    return {
        "id": game.id,
        "visitor_color": game.visitor_color,
        "pinned_age": game.pinned_age,
        "state": game.state,
        "result": game.result,
        "moves": [],
        "session_token": None
    }

@app.post("/api/games/{game_id}/migrate_session")
def migrate_session(game_id: str, request: Request, response: Response, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(status_code=400, detail="No token provided")
    
    old_token = auth.replace("Bearer ", "")
    if old_token != game.session_token:
        raise HTTPException(status_code=403, detail="Invalid token")
        
    # Rotate token
    new_token = uuid.uuid4().hex
    game.session_token = new_token
    db.commit()
    
    response.set_cookie(key="session_token", value=new_token, httponly=True, samesite="lax")
    return {"status": "migrated"}

from sqlalchemy import func, case

@app.get("/api/explorer")
def explore(prefix: str = "", cutoff: Optional[int] = None, db: Session = Depends(get_db)):
    timeline = db.query(models.Timeline).order_by(desc(models.Timeline.created_at)).first()
    if not timeline:
        return {"moves": [], "ended_here": 0}
        
    cutoff_seq = cutoff if cutoff is not None else timeline.t_trained
    prefix_moves = prefix.split(",") if prefix else []
    
    # Base query for games in timeline up to cutoff
    g_query = db.query(models.Game.id, models.Game.result).join(
        models.ExperienceEvent, models.ExperienceEvent.game_id == models.Game.id
    ).filter(
        models.Game.timeline_id == timeline.id,
        models.ExperienceEvent.sequence <= cutoff_seq
    )
    
    # Filter by exact prefix matches
    for i, m_uci in enumerate(prefix_moves):
        g_query = g_query.filter(
            db.query(models.Move).filter(
                models.Move.game_id == models.Game.id,
                models.Move.ply == i + 1,
                models.Move.uci == m_uci
            ).exists()
        )
        
    g_subq = g_query.subquery()
    
    # 1. Total games reaching this node
    total_reaching = db.query(func.count(g_subq.c.id)).scalar() or 0
    if total_reaching == 0:
        return {"moves": [], "ended_here": 0, "total": 0}
        
    # 2. Games ending exactly here (no move at ply = len+1)
    target_ply = len(prefix_moves) + 1
    games_continuing = db.query(models.Move.game_id).filter(
        models.Move.game_id.in_(db.query(g_subq.c.id)),
        models.Move.ply == target_ply
    ).subquery()
    
    ended_here = db.query(func.count(g_subq.c.id)).filter(
        ~g_subq.c.id.in_(db.query(games_continuing.c.game_id))
    ).scalar() or 0
    
    # 3. Next moves distribution
    next_moves = db.query(
        models.Move.uci,
        models.Move.san,
        func.count(models.Move.id).label("count"),
        func.sum(case((g_subq.c.result == 1.0, 1), else_=0)).label("wins"),
        func.sum(case((g_subq.c.result == 0.0, 1), else_=0)).label("draws"),
        func.sum(case((g_subq.c.result == -1.0, 1), else_=0)).label("losses")
    ).join(g_subq, g_subq.c.id == models.Move.game_id).filter(
        models.Move.ply == target_ply
    ).group_by(models.Move.uci, models.Move.san).order_by(desc("count")).all()
    
    results = []
    for m in next_moves:
        results.append({
            "uci": m.uci,
            "san": m.san,
            "count": m.count,
            "wins": m.wins,
            "draws": m.draws,
            "losses": m.losses
        })
        
    return {
        "moves": results,
        "ended_here": ended_here,
        "total": total_reaching
    }

@app.get("/api/archive")
def archive(page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    timeline = db.query(models.Timeline).order_by(desc(models.Timeline.created_at)).first()
    if not timeline:
        return {"games": [], "total": 0}
        
    base_q = db.query(models.Game, models.ExperienceEvent.sequence).join(
        models.ExperienceEvent, models.ExperienceEvent.game_id == models.Game.id
    ).filter(models.Game.timeline_id == timeline.id)
    
    total = base_q.count()
    games = base_q.order_by(desc(models.ExperienceEvent.sequence)).offset((page-1)*limit).limit(limit).all()
    
    res = []
    for g, seq in games:
        res.append({
            "id": g.id,
            "sequence": seq,
            "pinned_age": g.pinned_age,
            "visitor_color": g.visitor_color,
            "result": g.result,
            "termination": g.termination,
            "completed_at": g.completed_at,
            "moves": [m.uci for m in g.moves]
        })
        
    return {"games": res, "total": total}

from fastapi.responses import PlainTextResponse

@app.get("/api/games/{game_id}/pgn", response_class=PlainTextResponse)
def get_game_pgn(game_id: str, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    board = chess.Board()
    pgn_moves = []
    for i, m in enumerate(game.moves):
        # We stored SAN, but let's recalculate to be safe and build standard PGN
        try:
            move = chess.Move.from_uci(m.uci)
            san = board.san(move)
            board.push(move)
            if i % 2 == 0:
                pgn_moves.append(f"{i//2 + 1}. {san}")
            else:
                pgn_moves.append(san)
        except:
            break
            
    res_str = "*"
    if game.result == 1.0: res_str = "1-0"
    elif game.result == -1.0: res_str = "0-1"
    elif game.result == 0.0: res_str = "1/2-1/2"
    
    date_str = game.completed_at.strftime("%Y.%m.%d") if game.completed_at else datetime.utcnow().strftime("%Y.%m.%d")
    
    headers = [
        '[Event "Plylo API Game"]',
        f'[Site "plylo"]',
        f'[Date "{date_str}"]',
        f'[White "{game.visitor_color == "white" and "Anonymous Visitor" or f"Plylo Age {game.pinned_age}"}"]',
        f'[Black "{game.visitor_color == "black" and "Anonymous Visitor" or f"Plylo Age {game.pinned_age}"}"]',
        f'[Result "{res_str}"]'
    ]
    
    pgn = "\n".join(headers) + "\n\n" + " ".join(pgn_moves) + f" {res_str}"
    return pgn

def _enqueue_bot_move(db: Session, game_id: str):
    # Enqueue bot move using a unique deduplication key for this state
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    ply = len(game.moves) + 1
    dedup_key = f"bot_move_{game_id}_{ply}"
    
    # Insert if not exists
    existing = db.query(models.Job).filter(models.Job.deduplication_key == dedup_key).first()
    if not existing:
        job = models.Job(
            kind="bot_move",
            deduplication_key=dedup_key,
            payload={"game_id": game_id}
        )
        db.add(job)
        db.commit()

@app.get("/api/games/{game_id}")
def get_game(game_id: str, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    return {
        "id": game.id,
        "state": game.state,
        "visitor_color": game.visitor_color,
        "pinned_age": game.pinned_age,
        "result": game.result,
        "moves": [m.uci for m in game.moves]
    }

@app.post("/api/games/{game_id}/move")
def make_move(game_id: str, req: MoveReq, request: Request, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.state != "active":
        raise HTTPException(status_code=400, detail="Game is not active")
        
    verify_session(game, request)
        
    board = chess.Board()
    for m in game.moves:
        board.push_uci(m.uci)
        
    is_visitor_turn = (board.turn == chess.WHITE and game.visitor_color == "white") or \
                      (board.turn == chess.BLACK and game.visitor_color == "black")
                      
    if not is_visitor_turn:
        raise HTTPException(status_code=400, detail="Not your turn")
        
    try:
        move = chess.Move.from_uci(req.uci)
        if move not in board.legal_moves:
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Illegal move")
        
    ply = len(game.moves) + 1
    san_str = board.san(move)
    board.push(move)
    
    new_move = models.Move(
        game_id=game.id,
        ply=ply,
        uci=req.uci,
        san=san_str,
        state_hash=board.fen(),
        prefix_key=f"{game.id}_{ply}",
        actor="visitor"
    )
    db.add(new_move)
    
    if board.is_checkmate():
        res = 1.0 if board.turn == chess.BLACK else -1.0
        mark_game_completed(db, game, result=res, termination="mate")
    elif board.is_game_over(claim_draw=True):
        mark_game_completed(db, game, result=0.0, termination="draw")
    else:
        _enqueue_bot_move(db, game.id)
        
    db.commit()
    return {"status": "ok"}

@app.post("/api/games/{game_id}/resign")
def resign(game_id: str, request: Request, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game or game.state != "active":
        raise HTTPException(status_code=400, detail="Game not active")
        
    verify_session(game, request)
    res = -1.0 if game.visitor_color == "white" else 1.0
    mark_game_completed(db, game, result=res, termination="resign")
    db.commit()
    return {"status": "ok"}

@app.post("/api/games/{game_id}/abort")
def abort(game_id: str, request: Request, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game or game.state != "active":
        raise HTTPException(status_code=400, detail="Game not active")
        
    verify_session(game, request)
        
    mark_game_completed(db, game, result=0.0, termination="abort")
    db.commit()
    return {"status": "ok"}

import time
import uuid
import chess
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from server.storage.database import SessionLocal
from server.storage import models
from server.engine.model import PlyloNet
from server.engine.search import select_move

# Mock registry for cached models
model_cache = {} # age -> PlyloNet

import os
import torch
CHECKPOINT_DIR = "/app/checkpoints"

def _load_model(db: Session, timeline_id: str, age: int) -> PlyloNet:
    if age in model_cache:
        return model_cache[age]
        
    model = PlyloNet(seed=1337)
    
    if age > 0:
        path = os.path.join(CHECKPOINT_DIR, f"{timeline_id}_{age}.pt")
        if os.path.exists(path):
            state = torch.load(path, map_location='cpu', weights_only=True)
            model.load_state_dict(state['net'])
            
    model.eval()
    model_cache[age] = model
    return model

def process_bot_move(db: Session, job: models.Job):
    game_id = job.payload["game_id"]
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    
    if not game or game.state != "active":
        job.status = "completed"
        return
        
    board = chess.Board()
    for m in game.moves:
        board.push_uci(m.uci)
        
    # Is it bot's turn?
    is_bot_turn = (board.turn == chess.WHITE and game.visitor_color == "black") or \
                  (board.turn == chess.BLACK and game.visitor_color == "white")
                  
    if not is_bot_turn:
        job.status = "completed"
        return
        
    # Check termination before move
    if board.is_game_over(claim_draw=True):
        game.state = "completed"
        game.termination = "draw" if board.is_draw() else "mate"
        db.commit()
        job.status = "completed"
        return
        
    bot_model = _load_model(db, game.timeline_id, game.pinned_age)
    move = select_move(board, bot_model, seed=game.seed + len(game.moves))
    
    if not move:
        game.state = "completed"
        game.termination = "mate"
        game.result = 1.0 if board.turn == chess.BLACK else -1.0
    else:
        ply = len(game.moves) + 1
        san_str = board.san(move)
        board.push(move)
        new_move = models.Move(
            game_id=game.id,
            ply=ply,
            uci=move.uci(),
            san=san_str,
            state_hash=board.fen(),
            prefix_key=f"{game.id}_{ply}",
            actor="bot"
        )
        db.add(new_move)
        
        # Check termination after move
        if board.is_checkmate():
            game.state = "completed"
            game.termination = "mate"
            game.result = 1.0 if board.turn == chess.BLACK else -1.0
        elif board.is_game_over(claim_draw=True):
            game.state = "completed"
            game.termination = "draw"
            game.result = 0.0
            
    job.status = "completed"
    db.commit()

def process_jobs_loop():
    while True:
        with SessionLocal() as db:
            # Lease a pending job
            now = datetime.utcnow()
            job = db.query(models.Job).filter(
                models.Job.status.in_(["pending", "leased"]),
                or_(models.Job.lease_expires_at == None, models.Job.lease_expires_at < now)
            ).with_for_update(skip_locked=True).first()
            
            if not job:
                time.sleep(1)
                continue
                
            job.status = "leased"
            job.lease_expires_at = now + timedelta(minutes=5)
            db.commit()
            
            try:
                if job.kind == "bot_move":
                    process_bot_move(db, job)
                else:
                    job.status = "failed"
                    job.failure_details = f"Unknown job kind: {job.kind}"
                    db.commit()
            except Exception as e:
                db.rollback()
                job.status = "failed"
                job.failure_details = str(e)
                db.add(job)
                db.commit()

if __name__ == "__main__":
    process_jobs_loop()

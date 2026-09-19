import os
import sys
import chess
import random
import torch
from sqlalchemy import desc

# Ensure we can import server modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from server.storage.database import SessionLocal
from server.storage import models
from server.engine.model import PlyloNet
from server.engine.search import select_move

CHECKPOINT_DIR = "/app/checkpoints"

def load_latest_model(db, timeline):
    model = PlyloNet(seed=1337)
    age = timeline.t_trained
    if age > 0:
        path = os.path.join(CHECKPOINT_DIR, f"{timeline.id}_{age}.pt")
        if os.path.exists(path):
            state = torch.load(path, map_location='cpu', weights_only=True)
            model.load_state_dict(state['net'])
    model.eval()
    return model, age

def play_self_game():
    with SessionLocal() as db:
        timeline = db.query(models.Timeline).order_by(desc(models.Timeline.created_at)).first()
        if not timeline:
            print("No timeline found.")
            return
            
        model, age = load_latest_model(db, timeline)
        
        # Create game
        game = models.Game(
            timeline_id=timeline.id,
            visitor_color="white", # Arbitrary for self-play
            pinned_age=age,
            runtime_digest="self_play",
            seed=random.randint(0, 1000000),
            session_token="self_play_token"
        )
        db.add(game)
        db.commit()
        
        board = chess.Board()
        ply = 0
        
        # Play until game over or 200 ply (100 moves)
        while not board.is_game_over(claim_draw=True) and ply < 200:
            move = select_move(board, model, seed=game.seed + ply, explore=True)
            if not move:
                break
                
            san_str = board.san(move)
            board.push(move)
            
            db_move = models.Move(
                game_id=game.id,
                ply=ply + 1,
                uci=move.uci(),
                san=san_str,
                state_hash=board.fen(),
                prefix_key=board.fen(),
                actor="bot"
            )
            db.add(db_move)
            ply += 1
            
        # Game over
        result = 0.0
        term = "draw_claim"
        if board.is_checkmate():
            result = 1.0 if board.turn == chess.BLACK else -1.0
            term = "mate"
            
        game.state = "completed"
        game.result = result
        game.termination = term
        
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
        db.commit()
        print(f"Self-play game {seq} finished. Result: {result}, Age: {age}, Plies: {ply}", flush=True)

if __name__ == "__main__":
    print("Starting self-play loop...", flush=True)
    while True:
        play_self_game()

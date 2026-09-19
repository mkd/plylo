import time
import os
import uuid
import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
import torch

from server.storage.database import SessionLocal
from server.storage import models
from server.learning.timeline import Timeline, GameRecord

CHECKPOINT_DIR = "/app/checkpoints"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

def process_training_loop():
    while True:
        with SessionLocal() as db:
            timeline = db.query(models.Timeline).order_by(desc(models.Timeline.created_at)).first()
            if not timeline:
                time.sleep(1)
                continue
                
            while timeline.t_trained < timeline.n_accepted:
                target_t = timeline.t_trained + 1
                ev = db.query(models.ExperienceEvent).filter(
                    models.ExperienceEvent.timeline_id == timeline.id,
                    models.ExperienceEvent.sequence == target_t
                ).first()
                
                if not ev:
                    break
                    
                game = db.query(models.Game).filter(models.Game.id == ev.game_id).first()
                moves = [m.uci for m in game.moves]
                
                tl = Timeline(seed=1337)
                
                # Fetch past games for replay
                past_evs = db.query(models.ExperienceEvent).filter(
                    models.ExperienceEvent.timeline_id == timeline.id,
                    models.ExperienceEvent.sequence < target_t
                ).order_by(models.ExperienceEvent.sequence).all()
                for p_ev in past_evs:
                    p_game = db.query(models.Game).filter(models.Game.id == p_ev.game_id).first()
                    tl.games.append(GameRecord(p_ev.sequence, [m.uci for m in p_game.moves], p_game.result or 0.0))
                
                # Load T from disk
                if timeline.t_trained > 0:
                    path_t = os.path.join(CHECKPOINT_DIR, f"{timeline.id}_{timeline.t_trained}.pt")
                    if os.path.exists(path_t):
                        state = torch.load(path_t, map_location='cpu', weights_only=True)
                        tl.net.load_state_dict(state['net'])
                        tl.optimizer.load_state_dict(state['opt'])
                
                # Train
                gr = GameRecord(seq=target_t, moves=moves, result=game.result or 0.0)
                tl.update_for_game(gr)
                tl.games.append(gr)
                
                # Save checkpoint T+1 to disk
                path_t1 = os.path.join(CHECKPOINT_DIR, f"{timeline.id}_{target_t}.pt")
                torch.save({
                    'net': tl.net.state_dict(),
                    'opt': tl.optimizer.state_dict()
                }, path_t1)
                
                chk = models.Checkpoint(
                    timeline_id=timeline.id,
                    age=target_t,
                    file_manifest={"weights": path_t1},
                    logical_digest=f"digest_{target_t}",
                    artifact_checksums={},
                    runtime_reference=path_t1,
                    retention_role="transient"
                )
                db.add(chk)
                
                timeline.t_trained = target_t
                db.commit()
                
        time.sleep(1)

if __name__ == "__main__":
    process_training_loop()

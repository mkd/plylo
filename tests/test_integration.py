import os
import copy
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from server.storage.models import Base
from server.storage.database import engine, get_db
from server.storage import models
from server.api.main import app

def check_postgres_available():
    url = str(engine.url)
    if "sqlite" in url:
        return False
    try:
        with engine.connect() as conn:
            pass
        return True
    except Exception:
        return False

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def setup_test_timeline(db):
    db.query(models.Move).delete()
    db.query(models.Job).delete()
    db.query(models.ExperienceEvent).delete()
    db.query(models.Game).delete()
    # Delete dependent tables before timeline
    db.query(models.Checkpoint).delete()
    db.query(models.TrainingStep).delete()
    db.query(models.Timeline).delete()
    
    tl = models.Timeline(id="tl_test", initialization_ref="test_init", active_runtime="test_runtime")
    db.add(tl)
    db.commit()
    return tl

def test_milestone_b_and_d_persistent_workflow():
    if not check_postgres_available():
        print("\n[UNVERIFIED] Integration check cannot run: Missing PostgreSQL prerequisite.")
        return
        
    print("\n[STARTING] PostgreSQL Integration Tests...")
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    tl = setup_test_timeline(db)
    
    # 1. Anonymous session ownership & Cookies
    resp = client.post("/api/games", json={"visitor_color": "white", "target_age": 0})
    assert resp.status_code == 200
    game_data = resp.json()
    game_id = game_data["id"]
    
    # Extract HttpOnly cookie
    cookies = resp.cookies
    assert "session_token" in cookies
    
    # Try move without cookie
    client.cookies.clear()
    move_resp = client.post(f"/api/games/{game_id}/move", json={"uci": "e2e4"})
    assert move_resp.status_code == 403
    
    # Valid move with cookie
    move_resp = client.post(f"/api/games/{game_id}/move", json={"uci": "e2e4"}, cookies=cookies)
    assert move_resp.status_code == 200
    
    # Resign using cookie
    res_resp = client.post(f"/api/games/{game_id}/resign", cookies=cookies)
    assert res_resp.status_code == 200
    
    db.refresh(tl)
    assert tl.n_accepted == 1
    
    # Test session migration endpoint
    resp2 = client.post("/api/games", json={"visitor_color": "white", "target_age": 0})
    old_token_simulated = resp2.cookies.get("session_token")
    mig_resp = client.post(f"/api/games/{resp2.json()['id']}/migrate_session", headers={"Authorization": f"Bearer {old_token_simulated}"})
    assert mig_resp.status_code == 200
    assert mig_resp.cookies.get("session_token") != old_token_simulated
    
    # 2. Explorer Cutoffs (G31 / Age 20)
    setup_test_timeline(db)
    
    # Insert Game 30 (sequence 30, completed)
    g30 = models.Game(id="game_30", timeline_id="tl_test", visitor_color="white", pinned_age=0, runtime_digest="active", seed=42, session_token="mock", state="completed", result=1.0, termination="mate", completed_at=datetime.utcnow())
    db.add(g30)
    db.add(models.ExperienceEvent(timeline_id="tl_test", sequence=30, game_id="game_30", trajectory_digest="mock"))
    # Moves: e2e4, e7e5
    db.add(models.Move(game_id="game_30", ply=1, uci="e2e4", san="e4", state_hash="hash1", prefix_key="game_30_1", actor="visitor"))
    db.add(models.Move(game_id="game_30", ply=2, uci="e7e5", san="e5", state_hash="hash2", prefix_key="game_30_2", actor="bot"))
    
    db.query(models.Timeline).update({"n_accepted": 30, "t_trained": 30})
    db.commit()
    
    # Start Game 31 at pinned age 20
    resp31 = client.post("/api/games", json={"visitor_color": "white", "target_age": 20})
    g31_id = resp31.json()["id"]
    cookies31 = resp31.cookies
    assert resp31.json()["pinned_age"] == 20
    
    # Visitor plays e2e4
    client.post(f"/api/games/{g31_id}/move", json={"uci": "e2e4"}, cookies=cookies31)
    
    # Explore at cutoff 30. G31 should NOT be visible.
    expl_30 = client.get("/api/explorer?prefix=e2e4&cutoff=30")
    assert expl_30.json()["total"] == 1 # Only Game 30
    assert any(m["uci"] == "e7e5" for m in expl_30.json()["moves"])
    
    # Resign Game 31 -> assigns sequence 31
    client.post(f"/api/games/{g31_id}/resign", cookies=cookies31)
    
    # Explore at cutoff 31. G31 should be visible and ended exactly at e2e4.
    expl_31 = client.get("/api/explorer?prefix=e2e4&cutoff=31")
    assert expl_31.json()["total"] == 2
    assert expl_31.json()["ended_here"] == 1 # Game 31
    
    # 3. PGN Export
    pgn_resp = client.get(f"/api/games/{g31_id}/pgn")
    assert pgn_resp.status_code == 200
    assert '1. e4' in pgn_resp.text
    assert 'Anonymous Visitor' in pgn_resp.text
    assert 'Plylo Age 20' in pgn_resp.text
    
    print("\n[PASS] Integration tests completed successfully.")

if __name__ == "__main__":
    test_milestone_b_and_d_persistent_workflow()

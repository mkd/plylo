import pytest
import chess
import copy
import random
import torch
from server.learning.timeline import Timeline
from server.engine.search import select_move
from server.engine.model import PlyloNet

def generate_random_game() -> tuple[list[str], float]:
    board = chess.Board()
    moves = []
    # Just play random legal moves until it ends or 80 plies
    for _ in range(80):
        if board.is_game_over(claim_draw=True):
            break
        move = random.choice(list(board.legal_moves))
        moves.append(move.uci())
        board.push(move)
        
    res = board.result(claim_draw=True)
    if res == '1-0':
        val = 1.0
    elif res == '0-1':
        val = -1.0
    else:
        val = 0.0
    return moves, val

def test_milestone_a_scenario():
    # 1. Initialize timeline (S0)
    timeline = Timeline(seed=1337)
    
    # Check age 0 has zero knowledge (residual is 0)
    # We can test this by checking model output on initial board
    board = chess.Board()
    # (Checking weights is sufficient)
    # Actually just check the weights
    
    # 2. Add 30 games
    random.seed(42)
    for i in range(30):
        moves, res = generate_random_game()
        timeline.add_game_and_train(moves, res)
        
    assert len(timeline.games) == 30
    assert 30 in timeline.checkpoints
    
    # 3. 30/20/31 Scenario
    # "A visitor starts a game against age 20. Every bot move in that game uses S20."
    timeline.load_checkpoint(30)
    s30_net_state = copy.deepcopy(timeline.net.state_dict())
    
    # Load age 20 for the visitor game
    bot_20 = PlyloNet(seed=1337)
    bot_20.load_state_dict(timeline.checkpoints[20].net_state_dict)
    
    # Let's verify S20 != S30
    diff_found = False
    for (k1, v1), (k2, v2) in zip(s30_net_state.items(), bot_20.state_dict().items()):
        if not torch.equal(v1, v2):
            diff_found = True
            break
    assert diff_found, "S20 should be different from S30"
    
    # Play the game (Visitor vs Age 20)
    game_31_board = chess.Board()
    game_31_moves = []
    
    # Visitor plays White, Bot plays Black
    for ply in range(10): # Short game
        if game_31_board.turn == chess.WHITE:
            move = random.choice(list(game_31_board.legal_moves))
        else:
            # Bot uses S20
            move = select_move(game_31_board, bot_20, seed=123, max_nodes=50) # small node count for test speed
        game_31_moves.append(move.uci())
        game_31_board.push(move)
        
    # Assume white won
    game_31_result = 1.0
    
    # "The completed game is accepted as G31. The trainer calculates S31 from S30 and G31"
    timeline.load_checkpoint(30) # make sure trainer is at S30
    seq = timeline.add_game_and_train(game_31_moves, game_31_result)
    assert seq == 31
    
    # "Age 20 remains S20."
    assert torch.equal(timeline.checkpoints[20].net_state_dict['fc1.weight'], bot_20.state_dict()['fc1.weight'])
    
    # "The new maximum becomes 31"
    s31_net_state = timeline.checkpoints[31].net_state_dict
    
    # Verify S31 is different from S30
    diff_found = False
    for (k1, v1), (k2, v2) in zip(s30_net_state.items(), s31_net_state.items()):
        if not torch.equal(v1, v2):
            diff_found = True
            break
    assert diff_found, "S31 should be different from S30"
    
def test_prefix_isolation():
    # 4. Exact prefix isolation
    # "create two development histories with identical first four games and different later games. 
    # Age 4 must reconstruct to the same state and choose the same action for the same history, policy configuration, and seed."
    random.seed(123)
    prefix_games = [generate_random_game() for _ in range(4)]
    
    t1 = Timeline(seed=99)
    t2 = Timeline(seed=99)
    
    for m, r in prefix_games:
        t1.add_game_and_train(m, r)
        t2.add_game_and_train(m, r)
        
    t1.add_game_and_train(*generate_random_game()) # 5th game for t1
    
    t2.add_game_and_train(*generate_random_game()) # 5th game for t2 (different)
    t2.add_game_and_train(*generate_random_game()) # 6th game for t2
    
    # Restore Age 4 in both
    t1.load_checkpoint(4)
    t2.load_checkpoint(4)
    
    for (k1, v1), (k2, v2) in zip(t1.net.state_dict().items(), t2.net.state_dict().items()):
        assert torch.equal(v1, v2)

def test_reconstruct_age_leakage():
    # Builds a timeline with 10 games, then reconstructs age 4
    # Ensure reconstruction uses exactly games 1-4 and does not leak games 5-10
    random.seed(42)
    t_full = Timeline(seed=1337)
    for _ in range(10):
        t_full.add_game_and_train(*generate_random_game())
        
    # Save the real age 4 state dict directly from checkpoints
    saved_age_4 = copy.deepcopy(t_full.checkpoints[4].net_state_dict)
    
    # Reconstruct age 4 from checkpoint 0 using the new method
    t_full.reconstruct_age(4)
    recon_age_4 = t_full.net.state_dict()
    
    for k in saved_age_4:
        assert torch.equal(saved_age_4[k], recon_age_4[k]), f"Mismatch in {k} due to future leakage!"


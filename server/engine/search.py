import chess
import random
from typing import Tuple, List, Optional
from server.engine.model import PlyloNet, get_value

def count_repetitions(board: chess.Board) -> int:
    """Counts how many times the current position has occurred in the game."""
    # This is a simple O(N) check through history
    # For a real implementation, you might maintain a history dictionary
    count = 1
    current_hash = board._transposition_key()
    
    # We must traverse the move stack and apply/unapply to get the state stack precisely if not available
    # Actually python-chess board keeps track of this internally with `board._state_stack`?
    # No, it's easier to just use `board.is_repetition()` but we need the count.
    # We can iterate through `board.move_stack` by copying and popping:
    b = board.copy()
    while b.move_stack:
        b.pop()
        if b._transposition_key() == current_hash:
            count += 1
    return count

def evaluate_moves(board: chess.Board, net: PlyloNet, depth: int, max_nodes: int) -> Tuple[List[Tuple[chess.Move, float]], int]:
    """
    Evaluates legal moves using minimax. Returns a list of (move, score) and nodes visited.
    Always evaluates from White's perspective (positive = good for White).
    """
    legal_moves = list(board.legal_moves)
    # Fixed stable UCI move ordering
    legal_moves.sort(key=lambda m: m.uci())
    
    if not legal_moves:
        return [], 0
        
    nodes = 0
    
    def minimax(b: chess.Board, d: int, alpha: float, beta: float) -> float:
        nonlocal nodes
        nodes += 1
        
        rep_count = count_repetitions(b)
        
        if d == 0 or b.is_game_over(claim_draw=True) or rep_count >= 3:
            return get_value(b, net, rep_count)
            
        moves = list(b.legal_moves)
        moves.sort(key=lambda m: m.uci())
        
        if b.turn == chess.WHITE:
            max_eval = -float('inf')
            for move in moves:
                b.push(move)
                eval_val = minimax(b, d - 1, alpha, beta)
                b.pop()
                max_eval = max(max_eval, eval_val)
                alpha = max(alpha, eval_val)
                if beta <= alpha or nodes >= max_nodes:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for move in moves:
                b.push(move)
                eval_val = minimax(b, d - 1, alpha, beta)
                b.pop()
                min_eval = min(min_eval, eval_val)
                beta = min(beta, eval_val)
                if beta <= alpha or nodes >= max_nodes:
                    break
            return min_eval

    # One-ply iteration
    scored_moves_1 = []
    for move in legal_moves:
        board.push(move)
        score = minimax(board, 0, -float('inf'), float('inf'))
        board.pop()
        scored_moves_1.append((move, score))
        if nodes >= max_nodes:
            break
            
    if nodes >= max_nodes or depth == 1:
        return scored_moves_1, nodes
        
    # Two-ply iteration
    scored_moves_2 = []
    nodes_before_2 = nodes
    alpha = -float('inf')
    beta = float('inf')
    
    for move in legal_moves:
        board.push(move)
        score = minimax(board, 1, alpha, beta)
        board.pop()
        scored_moves_2.append((move, score))
        
        if board.turn == chess.WHITE:
            alpha = max(alpha, score)
        else:
            beta = min(beta, score)
            
        if nodes >= max_nodes:
            break
            
    # If we hit the node limit during ply 2, fall back to ply 1 results completely
    if nodes >= max_nodes and len(scored_moves_2) < len(legal_moves):
        return scored_moves_1, nodes_before_2
        
    return scored_moves_2, nodes

def select_move(board: chess.Board, net: PlyloNet, seed: int, max_nodes: int = 5000, explore: bool = True) -> Optional[chess.Move]:
    """
    Selects a move based on minimax evaluation and exploration strategy.
    seed + current ply is used for deterministic exploration.
    """
    if board.is_game_over(claim_draw=True):
        return None
        
    scored_moves, nodes = evaluate_moves(board, net, depth=2, max_nodes=max_nodes)
    if not scored_moves:
        return None
        
    is_white = board.turn == chess.WHITE
    
    # Sort moves best to worst for the current player
    scored_moves.sort(key=lambda x: x[1], reverse=is_white)
    
    best_score = scored_moves[0][1]
    
    # Check if we have a proven mate available
    proven_mate_score = 10.0 if is_white else -10.0
    if best_score == proven_mate_score:
        return scored_moves[0][0] # Force the proven mate
        
    # Find moves within 0.10 of the best score
    candidates = []
    for move, score in scored_moves:
        diff = best_score - score if is_white else score - best_score
        if diff <= 0.10:
            # Exclude proven losses if an alternative without a proven loss exists
            proven_loss_score = -10.0 if is_white else 10.0
            if score == proven_loss_score and best_score != proven_loss_score:
                continue
            candidates.append(move)
            
    rng = random.Random(seed + len(board.move_stack))
    
    # 5% probability of sampling among candidates, otherwise pick best (which is candidates[0])
    if explore and rng.random() < 0.05 and len(candidates) > 1:
        return rng.choice(candidates)
    else:
        return candidates[0]

import chess
import torch
import random
import copy
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from server.engine.model import PlyloNet, get_value
from server.engine.encoder import encode_board

@dataclass
class GameRecord:
    seq: int
    moves: List[str] # uci moves
    result: float # 1.0 for White win, 0.0 for Draw, -1.0 for Black win
    
@dataclass
class TimelineState:
    age: int
    net_state_dict: dict
    opt_state_dict: dict

class Timeline:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.games: List[GameRecord] = []
        self.checkpoints: Dict[int, TimelineState] = {}
        
        # S0
        self.net = PlyloNet(seed=seed)
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=0.001)
        self.save_checkpoint(0)
        
    def save_checkpoint(self, age: int):
        self.checkpoints[age] = TimelineState(
            age=age,
            net_state_dict=copy.deepcopy(self.net.state_dict()),
            opt_state_dict=copy.deepcopy(self.optimizer.state_dict())
        )
        
    def load_checkpoint(self, age: int):
        if age not in self.checkpoints:
            raise ValueError(f"No checkpoint for age {age}")
        state = self.checkpoints[age]
        self.net.load_state_dict(copy.deepcopy(state.net_state_dict))
        self.optimizer.load_state_dict(copy.deepcopy(state.opt_state_dict))
        
    def add_game_and_train(self, moves: List[str], result: float) -> int:
        seq = len(self.games) + 1
        game = GameRecord(seq=seq, moves=moves, result=result)
        self.games.append(game)
        
        self.update_for_game(game)
        self.save_checkpoint(seq) # For Milestone A, save every age
        return seq
        
    def update_for_game(self, new_game: GameRecord):
        self.net.train()
        # Seed based on timeline seed and seq k
        rng = random.Random(self.seed + new_game.seq)
        
        # 1. Sample positions from the new game
        new_positions = self._extract_positions(new_game)
        if len(new_positions) > 64:
            new_positions = rng.sample(new_positions, 64)
            
        # 2. Sample replay games
        replay_positions = []
        if new_game.seq > 1:
            # up to 8 earlier games
            num_replay_games = min(8, new_game.seq - 1)
            past_games = rng.sample(self.games[:new_game.seq - 1], num_replay_games)
            for g in past_games:
                g_pos = self._extract_positions(g)
                if len(g_pos) > 8:
                    g_pos = rng.sample(g_pos, 8)
                replay_positions.extend(g_pos)
                
        # 3. Two optimizer steps
        # We need to construct tensors
        for step in range(2):
            self.optimizer.zero_grad()
            
            loss = torch.tensor(0.0)
            
            # Loss for new game
            if new_positions:
                new_loss = self._compute_group_loss(new_positions)
                if replay_positions:
                    replay_loss = self._compute_group_loss(replay_positions)
                    loss = 0.5 * new_loss + 0.5 * replay_loss
                else:
                    loss = new_loss
            elif replay_positions:
                loss = self._compute_group_loss(replay_positions)
            
            if loss.requires_grad:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
                self.optimizer.step()
                
    def _extract_positions(self, game: GameRecord) -> List[Tuple[torch.Tensor, int, float]]:
        from server.engine.model import calculate_material
        board = chess.Board()
        positions = []
        rep_counts = {}
        for move_uci in game.moves:
            board.push_uci(move_uci)
            if board.is_game_over(claim_draw=True):
                break # Exclude terminal positions
                
            hash_val = board._transposition_key()
            rep_counts[hash_val] = rep_counts.get(hash_val, 0) + 1
            count = rep_counts[hash_val]
            
            features = encode_board(board, count)
            m_s = calculate_material(board)
            positions.append((features, m_s, game.result))
        return positions
        
    def _compute_group_loss(self, positions: List[Tuple[torch.Tensor, int, float]]) -> torch.Tensor:
        if not positions:
            return torch.tensor(0.0, requires_grad=True)
            
        features_stack = torch.stack([p[0] for p in positions])
        m_s_tensor = torch.tensor([p[1] for p in positions], dtype=torch.float32).unsqueeze(1)
        targets = torch.tensor([p[2] for p in positions], dtype=torch.float32).unsqueeze(1)
        
        f_theta = self.net(features_stack)
        v_theta = torch.tanh(m_s_tensor / 10.0 + f_theta)
        
        loss = torch.mean((v_theta - targets) ** 2)
        return loss

    def reconstruct_age(self, target_age: int) -> TimelineState:
        # Find highest checkpoint <= target_age
        c = max(age for age in self.checkpoints.keys() if age <= target_age)
        
        # Load the checkpoint
        self.load_checkpoint(c)
        
        # Replay updates c+1 through target_age in isolation
        for seq in range(c + 1, target_age + 1):
            # In our mocked timeline, self.games is 0-indexed, so game seq is at seq-1
            game = self.games[seq - 1]
            self.update_for_game(game)
            
        return TimelineState(
            age=target_age,
            net_state_dict=copy.deepcopy(self.net.state_dict()),
            opt_state_dict=copy.deepcopy(self.optimizer.state_dict())
        )

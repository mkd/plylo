import chess
import torch
import torch.nn as nn
import math
from server.engine.encoder import encode_board

class PlyloNet(nn.Module):
    def __init__(self, seed: int = 42):
        super().__init__()
        # Provide the generator to random initialization
        self.fc1 = nn.Linear(784, 128)
        self.relu1 = nn.ReLU()
        self.fc2 = nn.Linear(128, 32)
        self.relu2 = nn.ReLU()
        self.fc3 = nn.Linear(32, 1)
        
        # Reset parameters with seed manually for exact reproducibility if needed
        # Just setting torch.manual_seed is usually enough, but we should do it locally:
        with torch.random.fork_rng():
            torch.manual_seed(seed)
            self._init_weights(self.fc1)
            self._init_weights(self.fc2)

        # Initialize final layer weights and bias to zero
        nn.init.zeros_(self.fc3.weight)
        nn.init.zeros_(self.fc3.bias)

    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            nn.init.kaiming_uniform_(m.weight, a=math.sqrt(5))
            if m.bias is not None:
                fan_in, _ = nn.init._calculate_fan_in_and_fan_out(m.weight)
                bound = 1 / math.sqrt(fan_in) if fan_in > 0 else 0
                nn.init.uniform_(m.bias, -bound, bound)

    def forward(self, x):
        x = self.relu1(self.fc1(x))
        x = self.relu2(self.fc2(x))
        return self.fc3(x)

def calculate_material(board: chess.Board) -> int:
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    score = 0
    for piece_type, val in values.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * val
        score -= len(board.pieces(piece_type, chess.BLACK)) * val
    return score

def get_value(board: chess.Board, net: PlyloNet, repetition_count: int, scale: float = 10.0) -> float:
    """
    Returns the evaluation of the position from White's perspective.
    V_theta(s) = tanh(M(s) / 10 + f_theta(s))
    """
    # Check terminal conditions
    if board.is_checkmate():
        # Negative if it's White's turn and they are checkmated, positive if Black's turn
        return -10.0 if board.turn == chess.WHITE else 10.0
    if board.is_game_over(claim_draw=True) or repetition_count >= 3:
        return 0.0

    M_s = calculate_material(board)
    features = encode_board(board, repetition_count).unsqueeze(0)
    net.eval() # Ensure evaluation mode
    with torch.no_grad():
        f_theta = net(features).item()
        
    v = math.tanh(M_s / scale + f_theta)
    return v

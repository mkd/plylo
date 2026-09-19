import chess
import torch

def encode_board(board: chess.Board, repetition_count: int) -> torch.Tensor:
    """
    Encodes the board state into a 784-dimensional float32 tensor.
    """
    features = torch.zeros(784, dtype=torch.float32)
    
    # 1. 12 piece/color occupancy planes (12 * 64 = 768)
    # Order: P, N, B, R, Q, K, p, n, b, r, q, k
    # (White then Black)
    pieces = [
        (chess.WHITE, chess.PAWN), (chess.WHITE, chess.KNIGHT), (chess.WHITE, chess.BISHOP),
        (chess.WHITE, chess.ROOK), (chess.WHITE, chess.QUEEN), (chess.WHITE, chess.KING),
        (chess.BLACK, chess.PAWN), (chess.BLACK, chess.KNIGHT), (chess.BLACK, chess.BISHOP),
        (chess.BLACK, chess.ROOK), (chess.BLACK, chess.QUEEN), (chess.BLACK, chess.KING)
    ]
    idx = 0
    for color, piece_type in pieces:
        mask = board.pieces_mask(piece_type, color)
        for sq in range(64):
            if (mask >> sq) & 1:
                features[idx + sq] = 1.0
        idx += 64
        
    # 2. Side to move (1)
    features[768] = 1.0 if board.turn == chess.WHITE else 0.0
    
    # 3. 4 castling-right flags (4)
    features[769] = 1.0 if board.has_kingside_castling_rights(chess.WHITE) else 0.0
    features[770] = 1.0 if board.has_queenside_castling_rights(chess.WHITE) else 0.0
    features[771] = 1.0 if board.has_kingside_castling_rights(chess.BLACK) else 0.0
    features[772] = 1.0 if board.has_queenside_castling_rights(chess.BLACK) else 0.0
    
    # 4. En-passant file a-h or none, one-hot (9)
    # 773-780 for a-h, 781 for none
    if board.ep_square is not None and board.has_legal_en_passant():
        file_idx = chess.square_file(board.ep_square)
        features[773 + file_idx] = 1.0
    else:
        features[781] = 1.0
        
    # 5. Halfmove clock (1)
    # Bounded by 100, scaled by 1/100
    features[782] = min(board.halfmove_clock, 100.0) / 100.0
    
    # 6. Current position repetition count (1)
    # Bounded by 3, scaled by 1/3
    features[783] = min(repetition_count, 3.0) / 3.0
    
    return features

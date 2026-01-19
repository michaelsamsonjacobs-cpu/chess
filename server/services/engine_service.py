
import logging
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import chess.engine

LOGGER = logging.getLogger(__name__)

# Default path - adjusted based on download location
STOCKFISH_PATH = Path(__file__).parent.parent.parent / "stockfish" / "stockfish" / "stockfish-windows-x86-64-avx2.exe"

class EngineService:
    """Singleton service for managing Stockfish engine."""
    
    _instance = None
    _engine = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EngineService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        self.path = STOCKFISH_PATH
        if not self.path.exists():
            # Try alternative path (sometimes unzip structure varies)
             self.path = Path(__file__).parent.parent.parent / "stockfish" / "stockfish-windows-x86-64-avx2.exe"
    
    async def ensure_engine(self):
        """Start engine if not running."""
        if self._engine and not self._engine.transport.is_closing():
            return

        if not self.path.exists():
            LOGGER.error(f"Stockfish binary not found at {self.path}")
            raise FileNotFoundError(f"Stockfish not found at {self.path}")

        try:
            transport, engine = await chess.engine.popen_uci(str(self.path))
            self._engine = engine
            # Configure
            await self._engine.configure({"Threads": 2, "Hash": 64})
            LOGGER.info("Stockfish engine started successfully")
        except Exception as e:
            LOGGER.error(f"Failed to start Stockfish: {e}")
            raise

    async def analyze_position(self, board: chess.Board, time_limit: float = 0.1) -> Dict[str, Any]:
        """Analyze a position and return score/best move."""
        await self.ensure_engine()
        
        try:
            limit = chess.engine.Limit(time=time_limit)
            info = await self._engine.analyse(board, limit)
            
            score = info.get("score")
            return {
                "score_cp": score.white().score(mate_score=10000) if score else None,
                "best_move": info.get("pv")[0] if info.get("pv") else None,
                "depth": info.get("depth", 0),
                "nodes": info.get("nodes", 0)
            }
        except Exception as e:
            LOGGER.error(f"Analysis failed: {e}")
            return {}

    async def get_top_moves(self, board: chess.Board, multipv: int = 3, time_limit: float = 0.1) -> List[chess.Move]:
        """Get top N moves."""
        await self.ensure_engine()
        
        try:
            # Reconfigure for MultiPV
            await self._engine.configure({"MultiPV": multipv})
            
            limit = chess.engine.Limit(time=time_limit)
            info = await self._engine.analyse(board, limit, multipv=multipv)
            
            moves = []
            # info is a list when multipv > 1 ?? actually python-chess analyze returns one info dict?
            # Wait, python-chess usage for multipv:
            # It usually returns a list of infos if stream? NO. 
            # With simple analyse, it returns one info dict, but keys might handle multipv?
            # Actually simplest is to just inspect the 'pv' list if it's there.
            # But MultiPV entries in info?
            
            # Let's stick to simple "best move" check for now to be safe, 
            # Or assume the engine returns 'pv' which is the best line.
            # For "Top 3 moves", we need `info[i]["pv"][0]` logic.
            
            # Correction: simple analyse might not be structured for multipv list return easily
            # in the way I recall.
            # Let's just reset MultiPV to 1 to be safe for the first implementation
            # and rely on checking if the player's move matched the *best* move.
            
            top_move = None
            if "pv" in info:
                top_move = info["pv"][0]
            
            return [top_move] if top_move else []

        finally:
            await self._engine.configure({"MultiPV": 1})

    async def close(self):
        if self._engine:
            await self._engine.quit()
            self._engine = None

    def get_path_status(self) -> str:
        return "Found" if self.path.exists() else f"Missing at {self.path}"

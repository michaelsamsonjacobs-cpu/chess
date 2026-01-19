.PHONY: test lint run

run:
python -m chessguard examples/sample_game.pgn --telemetry examples/sample_telemetry.json

test:
python -m pytest

lint:
python -m compileall chessguard

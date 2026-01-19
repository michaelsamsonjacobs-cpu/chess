"""Interactive experiment play endpoints for human vs engine sessions."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..dependencies import get_experiment_session_manager
from ..schemas.experiment import (
    ExperimentMoveResponse,
    ExperimentSessionRequest,
    ExperimentSessionState,
)
from ..services.experiment_session import ExperimentSessionManager


router = APIRouter(prefix="/experiment/play", tags=["experiment-play"])


class MoveSubmission(BaseModel):
    """Payload for submitting a UCI move to the session."""

    move: str


@router.post("/session", response_model=ExperimentSessionState)
async def start_play_session(
    payload: ExperimentSessionRequest,
    manager: ExperimentSessionManager = Depends(get_experiment_session_manager),
) -> ExperimentSessionState:
    try:
        return await asyncio.to_thread(manager.start_session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/session/{session_id}", response_model=ExperimentSessionState)
async def get_play_session_state(
    session_id: UUID,
    manager: ExperimentSessionManager = Depends(get_experiment_session_manager),
) -> ExperimentSessionState:
    try:
        return await asyncio.to_thread(manager.get_state, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/session/{session_id}/move",
    response_model=ExperimentMoveResponse,
)
async def submit_move(
    session_id: UUID,
    payload: MoveSubmission,
    manager: ExperimentSessionManager = Depends(get_experiment_session_manager),
) -> ExperimentMoveResponse:
    try:
        player_move, engine_move, state = await asyncio.to_thread(
            manager.apply_player_move, session_id, payload.move
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ExperimentMoveResponse(player=player_move, engine=engine_move, state=state)


@router.post(
    "/session/{session_id}/complete",
    response_model=ExperimentMoveResponse,
)
async def complete_play_session(
    session_id: UUID,
    manager: ExperimentSessionManager = Depends(get_experiment_session_manager),
) -> ExperimentMoveResponse:
    try:
        state, export = await asyncio.to_thread(manager.finish_session, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Surface the final state and export artefact in a consistent envelope.
    return ExperimentMoveResponse(state=state, export=export)


@router.websocket("/session/{session_id}/stream")
async def play_session_stream(
    websocket: WebSocket,
    session_id: UUID,
    manager: ExperimentSessionManager = Depends(get_experiment_session_manager),
) -> None:
    await websocket.accept()

    try:
        state = await asyncio.to_thread(manager.get_state, session_id)
    except KeyError:
        await websocket.close(code=4404)
        return

    await websocket.send_json({"type": "state", "payload": state.model_dump()})

    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("type")

            if action == "move":
                move = message.get("move")
                if not isinstance(move, str):
                    await websocket.send_json(
                        {"type": "error", "detail": "Move must be provided as a string."}
                    )
                    continue

                try:
                    player_move, engine_move, state = await asyncio.to_thread(
                        manager.apply_player_move, session_id, move
                    )
                except ValueError as exc:
                    await websocket.send_json(
                        {"type": "error", "detail": str(exc)}
                    )
                    continue
                except KeyError:
                    await websocket.close(code=4404)
                    return

                await websocket.send_json(
                    {
                        "type": "update",
                        "player": player_move.model_dump(),
                        "engine": engine_move.model_dump() if engine_move else None,
                        "state": state.model_dump(),
                    }
                )

            elif action == "complete":
                try:
                    state, export = await asyncio.to_thread(manager.finish_session, session_id)
                except KeyError:
                    await websocket.close(code=4404)
                    return

                await websocket.send_json(
                    {
                        "type": "complete",
                        "state": state.model_dump(),
                        "export": export.model_dump(),
                    }
                )
                await websocket.close()
                return

            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": f"Unsupported message type: {action}",
                    }
                )
    except WebSocketDisconnect:
        return

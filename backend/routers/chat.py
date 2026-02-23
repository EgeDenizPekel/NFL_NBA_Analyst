import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from models.chat import ChatRequest
from services.llm_service import stream_chat
from services.sports_context import SportsContextService

router = APIRouter()
context_service = SportsContextService()


@router.post("/api/chat")
async def chat(request: ChatRequest):
    # Extract last user message to build sports context
    last_user_msg = next(
        (m.content for m in reversed(request.messages) if m.role == "user"), ""
    )
    context = await context_service.build_context(last_user_msg, request.sport)

    async def event_stream():
        try:
            async for token in stream_chat(
                messages=[m.model_dump() for m in request.messages],
                context=context,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

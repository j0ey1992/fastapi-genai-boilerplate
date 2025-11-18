"""Route for chat streaming and summary task."""

from fastapi import Depends, Query, Request
from fastapi.routing import APIRouter
from fastapi_limiter.depends import RateLimiter
from fastapi_utils.cbv import cbv

from app.core.responses import AppJSONResponse, AppStreamingResponse

from .models import ChatRequest, PolicyChatRequest, PolicyChatResponse, SummaryRequest, WebSearchChatRequest
from .rag_service import RAGChatService
from .service import ChatService

router = APIRouter()


def common_dependency() -> dict[str, str]:
    """Common dependency."""
    return {"msg": "This is a dependency"}


@cbv(router)
class ChatRoute:
    """Chat-related routes."""

    def __init__(self, common_dep=Depends(common_dependency)) -> None:
        self.common_dep = common_dep
        self.service = ChatService()

    @router.get(
        "/chat",
        response_class=AppStreamingResponse,
        dependencies=[Depends(RateLimiter(times=5, seconds=60))],
    )
    async def chat(
        self,
        request: Request,
        sleep: float = Query(
            1, description="Sleep duration (in seconds) between streamed tokens."
        ),
        number: int = Query(10, description="Total number of tokens to stream."),
    ) -> AppStreamingResponse:
        """Stream chat tokens based on query parameters."""
        chat_request = ChatRequest(sleep=sleep, number=number)
        data = await self.service.chat_service(request_params=chat_request)

        return AppStreamingResponse(data_stream=data)

    @router.get(
        "/chat/websearch",
        response_class=AppStreamingResponse,
        dependencies=[Depends(RateLimiter(times=5, seconds=60))],
    )
    async def chat_websearch(
        self,
        request: Request,
        question: str = Query(
            description="The user's input question to be processed for web search and answer generation."
        ),
        thread_id: str = Query(
            description="Unique identifier for the chat thread to maintain context across requests."
        ),
    ) -> AppStreamingResponse:
        """Stream chat tokens based on query parameters."""
        chat_request = WebSearchChatRequest(question=question, thread_id=thread_id)
        data = await self.service.chat_websearch_service(request_params=chat_request)

        return AppStreamingResponse(data_stream=data)

    @router.post(
        "/chat/policy",
        response_model=PolicyChatResponse,
        dependencies=[Depends(RateLimiter(times=10, seconds=60))],
    )
    async def chat_policy(
        self,
        request: Request,
        request_params: PolicyChatRequest,
    ) -> AppJSONResponse | AppStreamingResponse:
        """
        Answer policy questions using RAG.

        This endpoint retrieves relevant policy chunks from Qdrant
        and generates answers using Google Gemini.

        Rate limit: 10 requests per 60 seconds
        """
        # Get database session (placeholder dependency)
        # TODO: Implement proper database session management
        from sqlalchemy.ext.asyncio import AsyncSession
        async def get_db() -> AsyncSession:
            raise NotImplementedError("Database session not configured")

        try:
            from app.services.llm.gemini_service import get_gemini_service
            from app.services.vector.qdrant_service import get_qdrant_service

            # Get services
            gemini_service = get_gemini_service()
            qdrant_service = await get_qdrant_service()
            db_session = await get_db()

            # Create RAG service
            rag_service = RAGChatService(
                gemini_service=gemini_service,
                qdrant_service=qdrant_service,
                db_session=db_session,
            )

            # Stream or return JSON
            if request_params.stream:
                async def stream_generator():
                    async for chunk in rag_service.answer_question_stream(
                        question=request_params.question,
                        top_k=5,
                        score_threshold=0.7,
                    ):
                        yield chunk

                return AppStreamingResponse(data_stream=stream_generator)
            else:
                result = await rag_service.answer_question(
                    question=request_params.question,
                    user_id=request_params.user_id,
                    user_role=request_params.user_role,
                    service_id=request_params.service_id,
                    top_k=5,
                    score_threshold=0.7,
                )

                return AppJSONResponse(
                    content=PolicyChatResponse(**result).model_dump()
                )

        except NotImplementedError:
            # Temporary response until DB is configured
            return AppJSONResponse(
                content={
                    "answer": "Database not yet configured. Please set up PostgreSQL first.",
                    "sources": [],
                    "confidence": "error",
                    "chunks_retrieved": 0,
                }
            )
        except Exception as e:
            from loguru import logger
            logger.error(f"Policy chat failed: {e}")
            return AppJSONResponse(
                content={
                    "answer": "An error occurred. Please contact your manager or on-call coordinator.",
                    "sources": [],
                    "confidence": "error",
                    "chunks_retrieved": 0,
                }
            )

    @router.post("/celery/summary")
    async def celery_summary(
        self, request: Request, request_params: SummaryRequest
    ) -> AppJSONResponse:
        """Submit text for summary task."""
        data, message, status_code = await self.service.submit_summary_task(
            text=request_params.text
        )

        return AppJSONResponse(data=data, message=message, status_code=status_code)

    @router.get("/celery/summary/status")
    async def celery_summary_status(
        self,
        request: Request,
        task_id: str = Query(..., description="Celery task ID to check status"),
    ) -> AppJSONResponse:
        """Get status and result of a Celery summary task."""
        data, message, status_code = await self.service.summary_status(task_id=task_id)

        return AppJSONResponse(data=data, message=message, status_code=status_code)

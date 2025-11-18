"""Request module for chat streaming API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for configuring chat token streaming."""

    sleep: float = Field(
        1,
        json_schema_extra={
            "description": "Sleep duration (in seconds) between streamed tokens."
        },
    )
    number: int = Field(
        10, json_schema_extra={"description": "Total number of tokens to stream."}
    )


class WebSearchChatRequest(BaseModel):
    """Request model for initiating a web search-based chat response."""

    question: str = Field(
        description="The user's input question to be processed for web search and answer generation."
    )
    thread_id: str = Field(
        description="Unique identifier for the chat thread to maintain context across requests."
    )


class SummaryRequest(BaseModel):
    """Request model for submitting text to the summary task."""

    text: str = Field(
        ..., json_schema_extra={"description": "The text content to summarize."}
    )


class PolicyChatRequest(BaseModel):
    """Request model for policy-based RAG chat."""

    question: str = Field(
        ...,
        description="User's question about Voyage Care policies",
        min_length=5,
        max_length=500,
    )
    user_id: str = Field(
        ...,
        description="ID of the user asking the question (for audit logging)",
    )
    user_role: str = Field(
        ...,
        description="Role of the user (support_worker, team_leader, manager, ops)",
    )
    service_id: str | None = Field(
        None,
        description="Optional service/location identifier",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response",
    )


class PolicyChatResponse(BaseModel):
    """Response model for policy chat."""

    answer: str = Field(..., description="Generated answer based on policies")
    sources: list[dict[str, str | float]] = Field(
        ..., description="Policy sources used for the answer"
    )
    confidence: str = Field(
        ..., description="Confidence level: high, medium, low, none, error"
    )
    chunks_retrieved: int = Field(..., description="Number of policy chunks retrieved")

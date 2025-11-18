"""Google Gemini service for embeddings and RAG chat generation."""

from typing import Any, AsyncGenerator

from google import genai
from google.genai import types
from loguru import logger

from app.core.config import settings


class GeminiService:
    """Service for Google Gemini embeddings and chat generation."""

    def __init__(self) -> None:
        """Initialize Gemini client."""
        self.client: genai.Client | None = None
        self.chat_model = settings.GEMINI_CHAT_MODEL
        self.embedding_model = settings.GEMINI_EMBEDDING_MODEL

    def initialize(self) -> None:
        """Initialize Gemini client with API key."""
        try:
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY not set in environment")

            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info(
                f"Gemini client initialized (chat: {self.chat_model}, "
                f"embedding: {self.embedding_model})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as list of floats
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        try:
            response = self.client.models.embed_content(
                model=self.embedding_model,
                contents=text,
            )

            if not response.embeddings:
                raise ValueError("No embeddings returned from Gemini")

            embedding = response.embeddings[0].values
            logger.debug(f"Generated embedding (dim={len(embedding)}) for text")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def generate_embeddings_batch(
        self, texts: list[str], batch_size: int = 100
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of input texts
            batch_size: Number of texts to embed per API call

        Returns:
            List of embedding vectors
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        try:
            all_embeddings: list[list[float]] = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]

                # Gemini can handle batch embedding
                response = self.client.models.embed_content(
                    model=self.embedding_model,
                    contents=batch,
                )

                if not response.embeddings:
                    raise ValueError(f"No embeddings returned for batch {i}")

                batch_embeddings = [emb.values for emb.values in response.embeddings]
                all_embeddings.extend(batch_embeddings)

                logger.debug(
                    f"Generated {len(batch_embeddings)} embeddings "
                    f"(batch {i // batch_size + 1})"
                )

            logger.info(f"Generated {len(all_embeddings)} embeddings total")
            return all_embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    async def generate_chat_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate chat completion for RAG responses.

        Args:
            system_prompt: System instructions with context
            user_prompt: User question
            temperature: Sampling temperature (0-2, lower is more deterministic)
            max_tokens: Maximum response tokens

        Returns:
            Generated response text
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        try:
            # Combine system and user prompts for Gemini
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            response = self.client.models.generate_content(
                model=self.chat_model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    # Safety settings for healthcare context
                    safety_settings=[
                        types.SafetySetting(
                            category="HARM_CATEGORY_HARASSMENT",
                            threshold="BLOCK_NONE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_HATE_SPEECH",
                            threshold="BLOCK_NONE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            threshold="BLOCK_MEDIUM_AND_ABOVE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_DANGEROUS_CONTENT",
                            threshold="BLOCK_NONE",  # Medical advice isn't "dangerous"
                        ),
                    ],
                ),
            )

            if not response.text:
                logger.warning("Empty response from Gemini")
                return "I couldn't generate a response. Please try again or contact your manager."

            logger.info(f"Generated chat response ({len(response.text)} chars)")
            return response.text

        except Exception as e:
            logger.error(f"Failed to generate chat response: {e}")
            # Return safe fallback instead of raising
            return (
                "I encountered an error processing your question. "
                "Please contact your manager or on-call coordinator for assistance."
            )

    async def generate_chat_response_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming chat completion for RAG responses.

        Args:
            system_prompt: System instructions with context
            user_prompt: User question
            temperature: Sampling temperature
            max_tokens: Maximum response tokens

        Yields:
            Response text chunks
        """
        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            response = self.client.models.generate_content_stream(
                model=self.chat_model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    safety_settings=[
                        types.SafetySetting(
                            category="HARM_CATEGORY_HARASSMENT",
                            threshold="BLOCK_NONE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_HATE_SPEECH",
                            threshold="BLOCK_NONE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            threshold="BLOCK_MEDIUM_AND_ABOVE",
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_DANGEROUS_CONTENT",
                            threshold="BLOCK_NONE",
                        ),
                    ],
                ),
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

            logger.info("Completed streaming chat response")

        except Exception as e:
            logger.error(f"Failed to generate streaming response: {e}")
            yield (
                "I encountered an error processing your question. "
                "Please contact your manager or on-call coordinator for assistance."
            )


# Global singleton instance
_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    """Get or create singleton Gemini service instance."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
        _gemini_service.initialize()
    return _gemini_service

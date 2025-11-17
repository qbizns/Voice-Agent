"""AI Agent service for generating responses using LLMs."""

import time
from abc import ABC, abstractmethod
from typing import Optional, AsyncGenerator

import httpx
from loguru import logger

from app.core.config import get_settings
from app.services.knowledge_base import KnowledgeBase
from app.services.structured_knowledge import StructuredKnowledgeService


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate response from LLM.

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated response text
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> AsyncGenerator[str, None]:
        """Generate response from LLM as a stream.

        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        pass


class OllamaProvider(LLMProvider):
    """Ollama LLM provider for local model inference."""

    def __init__(self, base_url: str, model: str):
        """Initialize Ollama provider.

        Args:
            base_url: Ollama server base URL
            model: Model name to use
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        # Increased timeout for Ollama (can take 30-120 seconds for first response)
        self.client = httpx.AsyncClient(timeout=180.0)
        logger.info(f"Ollama provider initialized: {base_url} / {model}")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate response using Ollama."""
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Call Ollama API
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            )

            response.raise_for_status()
            result = response.json()

            return result.get("message", {}).get("content", "")

        except httpx.TimeoutException as e:
            logger.error(f"Ollama API timeout: {e}")
            raise RuntimeError(f"Ollama request timed out. The model may be loading or taking too long. Please try again.")
        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            logger.error(f"Error details: {str(e)}")
            raise RuntimeError(f"Failed to generate response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Ollama generation: {e}")
            raise RuntimeError(f"Unexpected error: {str(e)}")

    async def generate_with_history(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate response with conversation history.

        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated response text
        """
        try:
            # Call Ollama API with full message history
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            )

            response.raise_for_status()
            result = response.json()

            return result.get("message", {}).get("content", "")

        except httpx.TimeoutException as e:
            logger.error(f"Ollama API timeout: {e}")
            raise RuntimeError(f"Ollama request timed out. The model may be loading or taking too long. Please try again.")
        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {e}")
            logger.error(f"Error details: {str(e)}")
            raise RuntimeError(f"Failed to generate response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Ollama generation: {e}")
            raise RuntimeError(f"Unexpected error: {str(e)}")

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response using Ollama."""
        try:
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Call Ollama API with streaming enabled
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            ) as response:
                response.raise_for_status()

                # Stream chunks
                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json
                            chunk = json.loads(line)
                            if "message" in chunk and "content" in chunk["message"]:
                                content = chunk["message"]["content"]
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException as e:
            logger.error(f"Ollama streaming API timeout: {e}")
            raise RuntimeError(f"Ollama request timed out. The model may be loading or taking too long.")
        except httpx.HTTPError as e:
            logger.error(f"Ollama streaming API error: {e}")
            logger.error(f"Error details: {str(e)}")
            raise RuntimeError(f"Failed to generate streaming response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Ollama streaming: {e}")
            raise RuntimeError(f"Unexpected error: {str(e)}")

    async def generate_stream_with_history(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response with conversation history.

        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            Text chunks as they are generated
        """
        try:
            # Call Ollama API with streaming enabled
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                }
            ) as response:
                response.raise_for_status()

                # Stream chunks
                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json
                            chunk = json.loads(line)
                            if "message" in chunk and "content" in chunk["message"]:
                                content = chunk["message"]["content"]
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException as e:
            logger.error(f"Ollama streaming API timeout: {e}")
            raise RuntimeError(f"Ollama request timed out. The model may be loading or taking too long.")
        except httpx.HTTPError as e:
            logger.error(f"Ollama streaming API error: {e}")
            logger.error(f"Error details: {str(e)}")
            raise RuntimeError(f"Failed to generate streaming response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Ollama streaming: {e}")
            raise RuntimeError(f"Unexpected error: {str(e)}")

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


class LocalLLMProvider(LLMProvider):
    """Local LLM provider using transformers (for smaller models)."""

    def __init__(self, model_name: str = "bigscience/bloomz-560m"):
        """Initialize local LLM provider.

        Args:
            model_name: HuggingFace model name
        """
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading local model: {model_name} on {device}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForCausalLM.from_pretrained(model_name).to(device)
            self.device = device
            logger.info("Local LLM provider initialized")

        except ImportError:
            raise ImportError("Transformers not installed. Install with: pip install transformers")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate response using local model."""
        # Combine system prompt and user prompt
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        # Tokenize
        inputs = self.tokenizer(full_prompt, return_tensors="pt").to(self.device)

        # Generate
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )

        # Decode
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Remove prompt from response
        response = response[len(full_prompt):].strip()

        return response

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response (not supported for local model).

        Falls back to non-streaming generation.
        """
        # For local models, we don't have streaming support yet
        # Fall back to generating the full response
        response = await self.generate(prompt, system_prompt, temperature, max_tokens)
        yield response


class AIAgent:
    """AI Agent for generating contextual responses using RAG."""

    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        use_structured_knowledge: bool = True
    ):
        """Initialize AI agent.

        Args:
            knowledge_base: Optional knowledge base for RAG
            use_structured_knowledge: Enable structured knowledge for precise answers
        """
        settings = get_settings()
        self.settings = settings
        self.knowledge_base = knowledge_base

        # Initialize structured knowledge (optional)
        self.structured_knowledge = None
        if use_structured_knowledge:
            try:
                self.structured_knowledge = StructuredKnowledgeService()
                logger.info("Structured knowledge enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize structured knowledge: {e}")

        # Initialize LLM provider
        if settings.llm_provider == "ollama":
            self.llm = OllamaProvider(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model
            )
        elif settings.llm_provider == "local":
            self.llm = LocalLLMProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")

        logger.info(f"AI Agent initialized with {settings.llm_provider} provider")

    async def generate_response(
        self,
        message: str,
        use_knowledge_base: bool = True,
        conversation_history: Optional[list[dict]] = None
    ) -> tuple[str, Optional[list[str]], float]:
        """Generate response to user message.

        Args:
            message: User message
            use_knowledge_base: Whether to use knowledge base for context
            conversation_history: Optional conversation history (list of {"role": "...", "content": "..."})

        Returns:
            Tuple of (response, sources, processing_time_ms)
        """
        start_time = time.perf_counter()

        # Try structured knowledge first for precise answers
        if self.structured_knowledge:
            structured_answer = self.structured_knowledge.query_all(message)
            if structured_answer:
                processing_time = (time.perf_counter() - start_time) * 1000
                logger.info(f"Answered from structured knowledge in {processing_time:.2f}ms")
                return structured_answer, ["structured_knowledge"], processing_time

        # Get context from knowledge base if enabled
        context = ""
        sources = []

        if use_knowledge_base and self.knowledge_base:
            try:
                context = self.knowledge_base.get_context(message)
                # Extract sources
                results = self.knowledge_base.search(message)
                sources = [meta.get("source", "") for _, _, meta in results]
                logger.debug(f"Retrieved context from {len(sources)} sources")
            except Exception as e:
                logger.warning(f"Failed to retrieve from knowledge base: {e}")

        # Build prompt with conversation history
        if conversation_history and hasattr(self.llm, 'generate_with_history'):
            # Use conversation history with LLM
            messages = []

            # Add system prompt
            if self.settings.system_prompt:
                messages.append({"role": "system", "content": self.settings.system_prompt})

            # Add conversation history
            messages.extend(conversation_history)

            # Add knowledge base context if available
            if context:
                current_message = f"""السياق من قاعدة المعرفة:
{context}

السؤال: {message}

الرجاء الإجابة بناءً على السياق المقدم والمحادثة السابقة."""
            else:
                current_message = message

            messages.append({"role": "user", "content": current_message})

            # Generate with history
            try:
                response = await self.llm.generate_with_history(
                    messages=messages,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens
                )
            except Exception as e:
                logger.error(f"Failed to generate with history: {e}")
                raise
        else:
            # Fallback to simple generation
            if context:
                prompt = f"""السياق من قاعدة المعرفة:
{context}

السؤال: {message}

الرجاء الإجابة بناءً على السياق المقدم. إذا لم تكن المعلومات متوفرة في السياق، قل ذلك بوضوح."""
            else:
                prompt = message

            # Generate response
            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    system_prompt=self.settings.system_prompt,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens
                )
            except Exception as e:
                logger.error(f"Failed to generate response: {e}")
                logger.error(f"Error type: {type(e).__name__}, Details: {str(e)}")
                error_msg = str(e)
                if "timeout" in error_msg.lower():
                    response = "عذراً، استغرق الرد وقتاً طويلاً. يرجى المحاولة مرة أخرى."
                else:
                    response = f"عذراً، حدث خطأ أثناء معالجة طلبك: {error_msg[:100]}"

        processing_time = (time.perf_counter() - start_time) * 1000

        logger.info(f"Generated response in {processing_time:.2f}ms")
        return response, sources if sources else None, processing_time

    async def generate_response_stream(
        self,
        message: str,
        use_knowledge_base: bool = True,
        conversation_history: Optional[list[dict]] = None
    ) -> AsyncGenerator[tuple[str, Optional[list[str]]], None]:
        """Generate streaming response to user message.

        Args:
            message: User message
            use_knowledge_base: Whether to use knowledge base for context
            conversation_history: Optional conversation history

        Yields:
            Tuples of (text_chunk, sources)
        """
        # Try structured knowledge first for precise answers
        if self.structured_knowledge:
            structured_answer = self.structured_knowledge.query_all(message)
            if structured_answer:
                logger.info("Answered from structured knowledge (streaming)")
                yield structured_answer, ["structured_knowledge"]
                return

        # Get context from knowledge base if enabled
        context = ""
        sources = []

        if use_knowledge_base and self.knowledge_base:
            try:
                context = self.knowledge_base.get_context(message)
                results = self.knowledge_base.search(message)
                sources = [meta.get("source", "") for _, _, meta in results]
                logger.debug(f"Retrieved context from {len(sources)} sources")
            except Exception as e:
                logger.warning(f"Failed to retrieve from knowledge base: {e}")

        # Build prompt with conversation history
        if conversation_history and hasattr(self.llm, 'generate_stream_with_history'):
            # Use conversation history with LLM streaming
            messages = []

            # Add system prompt
            if self.settings.system_prompt:
                messages.append({"role": "system", "content": self.settings.system_prompt})

            # Add conversation history
            messages.extend(conversation_history)

            # Add knowledge base context if available
            if context:
                current_message = f"""السياق من قاعدة المعرفة:
{context}

السؤال: {message}

الرجاء الإجابة بناءً على السياق المقدم والمحادثة السابقة."""
            else:
                current_message = message

            messages.append({"role": "user", "content": current_message})

            # Generate with history (streaming)
            try:
                logger.info("Starting streaming generation with history")
                async for chunk in self.llm.generate_stream_with_history(
                    messages=messages,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens
                ):
                    yield chunk, sources if sources else None
            except Exception as e:
                logger.error(f"Failed to generate streaming response: {e}")
                raise
        else:
            # Fallback to simple streaming generation
            if context:
                prompt = f"""السياق من قاعدة المعرفة:
{context}

السؤال: {message}

الرجاء الإجابة بناءً على السياق المقدم. إذا لم تكن المعلومات متوفرة في السياق، قل ذلك بوضوح."""
            else:
                prompt = message

            # Generate streaming response
            try:
                logger.info("Starting streaming generation")
                async for chunk in self.llm.generate_stream(
                    prompt=prompt,
                    system_prompt=self.settings.system_prompt,
                    temperature=self.settings.temperature,
                    max_tokens=self.settings.max_tokens
                ):
                    yield chunk, sources if sources else None
            except Exception as e:
                logger.error(f"Failed to generate streaming response: {e}")
                logger.error(f"Error type: {type(e).__name__}, Details: {str(e)}")
                error_msg = str(e)
                if "timeout" in error_msg.lower():
                    yield "عذراً، استغرق الرد وقتاً طويلاً. يرجى المحاولة مرة أخرى.", None
                else:
                    yield f"عذراً، حدث خطأ أثناء معالجة طلبك: {error_msg[:100]}", None

    async def close(self) -> None:
        """Clean up resources."""
        if hasattr(self.llm, "close"):
            await self.llm.close()

"""Conversation context management service.

Manages conversation history and context for multi-turn dialogues.
"""

import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class Message:
    """Represents a single message in conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class ConversationContext:
    """Manages conversation context for a single session."""

    session_id: str
    max_history: int = 10  # Maximum number of message pairs to keep
    max_tokens: int = 4000  # Approximate max tokens (for LLM context window)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    messages: List[Message] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> None:
        """Add a user message to the conversation.

        Args:
            content: Message content
            metadata: Optional metadata (e.g., confidence, language)
        """
        message = Message(
            role="user",
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.last_accessed = time.time()
        self._trim_history()

        logger.debug(f"Session {self.session_id}: Added user message ({len(self.messages)} total)")

    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> None:
        """Add an assistant response to the conversation.

        Args:
            content: Message content
            metadata: Optional metadata (e.g., sources, processing_time)
        """
        message = Message(
            role="assistant",
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.last_accessed = time.time()
        self._trim_history()

        logger.debug(f"Session {self.session_id}: Added assistant message ({len(self.messages)} total)")

    def add_exchange(self, user_msg: str, assistant_msg: str,
                    user_metadata: Optional[Dict] = None,
                    assistant_metadata: Optional[Dict] = None) -> None:
        """Add a complete exchange (user message + assistant response).

        Args:
            user_msg: User message
            assistant_msg: Assistant response
            user_metadata: Optional user message metadata
            assistant_metadata: Optional assistant message metadata
        """
        self.add_user_message(user_msg, user_metadata)
        self.add_assistant_message(assistant_msg, assistant_metadata)

    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """Get conversation messages.

        Args:
            limit: Maximum number of messages to return (from end)

        Returns:
            List of messages
        """
        self.last_accessed = time.time()
        if limit:
            return self.messages[-limit:]
        return self.messages.copy()

    def get_messages_for_llm(self, system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """Get messages formatted for LLM input.

        Args:
            system_prompt: Optional system prompt to prepend

        Returns:
            List of message dicts in LLM format
        """
        self.last_accessed = time.time()

        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        for msg in self.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        return messages

    def get_context_summary(self) -> str:
        """Get a summary of the current conversation context.

        Returns:
            Summary string
        """
        if not self.messages:
            return "No conversation history"

        user_msgs = sum(1 for m in self.messages if m.role == "user")
        assistant_msgs = sum(1 for m in self.messages if m.role == "assistant")

        return (f"Session {self.session_id}: {len(self.messages)} messages "
                f"({user_msgs} user, {assistant_msgs} assistant)")

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()
        logger.info(f"Session {self.session_id}: Cleared conversation history")

    def _trim_history(self) -> None:
        """Trim history to stay within limits."""
        # Keep only last N messages
        if len(self.messages) > self.max_history * 2:  # *2 for user+assistant pairs
            removed = len(self.messages) - (self.max_history * 2)
            self.messages = self.messages[removed:]
            logger.debug(f"Session {self.session_id}: Trimmed {removed} old messages")

        # Estimate tokens (rough: ~1.3 tokens per word in Arabic/English)
        total_chars = sum(len(m.content) for m in self.messages)
        estimated_tokens = total_chars // 4  # Rough estimate

        if estimated_tokens > self.max_tokens:
            # Remove oldest messages until under limit
            while estimated_tokens > self.max_tokens and len(self.messages) > 2:
                removed_msg = self.messages.pop(0)
                estimated_tokens -= len(removed_msg.content) // 4
                logger.debug(f"Session {self.session_id}: Removed message to stay under token limit")

    def to_dict(self) -> Dict:
        """Convert to dictionary format."""
        return {
            "session_id": self.session_id,
            "max_history": self.max_history,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
            "summary": self.get_context_summary()
        }


class ContextService:
    """Service for managing multiple conversation contexts."""

    def __init__(
        self,
        max_history_per_session: int = 10,
        max_tokens_per_session: int = 4000,
        session_timeout_seconds: int = 1800  # 30 minutes
    ):
        """Initialize context service.

        Args:
            max_history_per_session: Max message pairs per session
            max_tokens_per_session: Max tokens per session
            session_timeout_seconds: Session timeout in seconds
        """
        self.max_history = max_history_per_session
        self.max_tokens = max_tokens_per_session
        self.session_timeout = session_timeout_seconds

        self.contexts: Dict[str, ConversationContext] = {}

        logger.info(f"Context service initialized (max_history={max_history_per_session}, "
                   f"session_timeout={session_timeout_seconds}s)")

    def get_or_create_context(self, session_id: str) -> ConversationContext:
        """Get existing context or create new one.

        Args:
            session_id: Session identifier

        Returns:
            ConversationContext instance
        """
        # Clean up expired sessions first
        self._cleanup_expired_sessions()

        if session_id not in self.contexts:
            self.contexts[session_id] = ConversationContext(
                session_id=session_id,
                max_history=self.max_history,
                max_tokens=self.max_tokens
            )
            logger.info(f"Created new conversation context for session: {session_id}")

        return self.contexts[session_id]

    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """Get existing context.

        Args:
            session_id: Session identifier

        Returns:
            ConversationContext or None if not found
        """
        return self.contexts.get(session_id)

    def delete_context(self, session_id: str) -> bool:
        """Delete a conversation context.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        if session_id in self.contexts:
            del self.contexts[session_id]
            logger.info(f"Deleted conversation context: {session_id}")
            return True
        return False

    def clear_context(self, session_id: str) -> bool:
        """Clear messages in a context without deleting it.

        Args:
            session_id: Session identifier

        Returns:
            True if cleared, False if not found
        """
        context = self.get_context(session_id)
        if context:
            context.clear()
            return True
        return False

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs.

        Returns:
            List of session IDs
        """
        self._cleanup_expired_sessions()
        return list(self.contexts.keys())

    def get_stats(self) -> Dict:
        """Get service statistics.

        Returns:
            Statistics dictionary
        """
        total_sessions = len(self.contexts)
        total_messages = sum(len(ctx.messages) for ctx in self.contexts.values())

        return {
            "active_sessions": total_sessions,
            "total_messages": total_messages,
            "avg_messages_per_session": total_messages / total_sessions if total_sessions > 0 else 0,
            "sessions": [ctx.to_dict() for ctx in self.contexts.values()]
        }

    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions based on timeout."""
        current_time = time.time()
        expired = []

        for session_id, context in self.contexts.items():
            if current_time - context.last_accessed > self.session_timeout:
                expired.append(session_id)

        for session_id in expired:
            del self.contexts[session_id]
            logger.info(f"Removed expired session: {session_id}")

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

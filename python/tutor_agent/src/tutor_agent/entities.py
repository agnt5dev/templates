"""
Tutor Entities for State Management

Provides entities for maintaining conversation history and learning progress.
"""

import time
from agnt5 import Entity


class TutorConversation(Entity):
    """
    Entity for storing tutor conversation history.

    Manages persistent conversation state across multiple interactions.
    Each session has its own entity instance identified by session_id.
    """

    _state_schema = {
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "description": "Conversation message history",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {
                            "type": "string",
                            "enum": ["user", "assistant"],
                            "description": "Message sender role"
                        },
                        "content": {
                            "type": "string",
                            "description": "Message content"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Subject area (history, math, general)"
                        },
                        "timestamp": {
                            "type": "number",
                            "description": "Message timestamp"
                        }
                    },
                    "required": ["role", "content", "timestamp"]
                },
                "default": []
            },
            "primary_subject": {
                "type": "string",
                "description": "Primary subject being discussed (history, math, general)",
                "default": "general"
            },
            "message_count": {
                "type": "integer",
                "description": "Total number of messages in conversation",
                "default": 0
            }
        },
        "description": "Tutor conversation state with message history and subject tracking"
    }

    async def add_message(self, role: str, content: str, subject: str = "general") -> None:
        """Add a message to the conversation history."""
        messages = self.state.get("messages", [])
        messages.append({
            "role": role,
            "content": content,
            "subject": subject,
            "timestamp": time.time()
        })
        self.state.set("messages", messages)

        # Update message count
        message_count = self.state.get("message_count", 0)
        self.state.set("message_count", message_count + 1)

    async def get_messages(self) -> list:
        """Get conversation message history."""
        return self.state.get("messages", [])

    async def get_primary_subject(self) -> str:
        """Get primary conversation subject."""
        return self.state.get("primary_subject", "general")

    async def set_primary_subject(self, subject: str) -> None:
        """Set primary conversation subject."""
        self.state.set("primary_subject", subject)

    async def get_message_count(self) -> int:
        """Get total message count."""
        return self.state.get("message_count", 0)

    async def get_recent_messages(self, count: int = 5) -> list:
        """Get the most recent messages."""
        messages = self.state.get("messages", [])
        return messages[-count:] if len(messages) > count else messages


__all__ = ["TutorConversation"]
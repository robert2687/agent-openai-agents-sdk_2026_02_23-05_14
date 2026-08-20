"""Enhanced memory store with session management and multiple backends.

This module provides:
- In-memory store for development
- Cosmos DB store for production
- Session management
- Message history with TTL
- Thread-safe operations
"""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from agent_server.config import get_config
from agent_server.monitoring import logger


# ============================================================================
# Type Definitions
# ============================================================================

class MemoryStore(Protocol):
    """Protocol for memory store implementations."""

    async def add_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a message to the store. Returns message ID."""
        ...

    async def get_recent_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
        session_id: str | None = None,
    ) -> list[dict]:
        """Get recent messages for tenant/user."""
        ...

    async def get_session_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """Get messages for a specific session."""
        ...

    async def get_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get list of sessions for tenant/user."""
        ...

    async def delete_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> bool:
        """Delete a session. Returns True if session existed."""
        ...

    async def delete_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        message_id: str,
    ) -> bool:
        """Delete a message. Returns True if message existed."""
        ...

    async def clear_user_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> int:
        """Clear all messages for a user. Returns count of deleted messages."""
        ...

    async def cleanup_old_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        older_than: timedelta | None = None,
    ) -> int:
        """Clean up old messages. Returns count of deleted messages."""
        ...


# ============================================================================
# Message Model
# ============================================================================

@dataclass
class Message:
    """Represents a stored message."""

    id: str
    tenant_id: str
    user_id: str
    session_id: str | None
    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ttl: timedelta | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "tenantId": self.tenant_id,
            "userId": self.user_id,
            "sessionId": self.session_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            id=data.get("id", ""),
            tenant_id=data.get("tenantId", ""),
            user_id=data.get("userId", ""),
            session_id=data.get("sessionId"),
            role=data.get("role", ""),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data.get("createdAt", datetime.now(UTC).isoformat())),
            updated_at=datetime.fromisoformat(data.get("updatedAt", datetime.now(UTC).isoformat())),
        )


# ============================================================================
# In-Memory Store Implementation
# ============================================================================

class InMemoryStore:
    """In-memory implementation of MemoryStore.

    Suitable for development and single-instance deployments.
    """

    def __init__(self):
        self._messages: dict[str, Message] = {}  # message_id -> Message
        self._user_sessions: dict[str, set[str]] = {}  # user_key -> set of session_ids
        self._session_messages: dict[str, list[str]] = {}  # session_id -> list of message_ids
        self._lock = asyncio.Lock()
        self._message_counter = 0

    @staticmethod
    def _make_user_key(tenant_id: str, user_id: str) -> str:
        return f"{tenant_id}#{user_id}"

    @staticmethod
    def _make_session_key(tenant_id: str, user_id: str, session_id: str) -> str:
        return f"{tenant_id}#{user_id}#{session_id}"

    @staticmethod
    def _generate_id() -> str:
        import uuid
        return str(uuid.uuid4())

    async def add_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a message to the store."""
        async with self._lock:
            message_id = self._generate_id()
            user_key = self._make_user_key(tenant_id, user_id)

            message = Message(
                id=message_id,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                metadata=metadata or {},
            )

            self._messages[message_id] = message

            # Track user sessions
            if user_key not in self._user_sessions:
                self._user_sessions[user_key] = set()
            if session_id:
                self._user_sessions[user_key].add(session_id)

            # Track session messages
            if session_id:
                session_key = self._make_session_key(tenant_id, user_id, session_id)
                if session_key not in self._session_messages:
                    self._session_messages[session_key] = []
                self._session_messages[session_key].append(message_id)

            self._message_counter += 1
            logger.debug(
                "Message added",
                message_id=message_id,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                role=role,
                content_length=len(content),
            )

            return message_id

    async def get_recent_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
        session_id: str | None = None,
    ) -> list[dict]:
        """Get recent messages for tenant/user."""
        async with self._lock:
            user_key = self._make_user_key(tenant_id, user_id)
            messages = []

            if session_id:
                # Get messages for specific session
                session_key = self._make_session_key(tenant_id, user_id, session_id)
                message_ids = self._session_messages.get(session_key, [])
                messages = [self._messages[mid] for mid in message_ids if mid in self._messages]
            else:
                # Get all messages for user
                for message in self._messages.values():
                    if message.tenant_id == tenant_id and message.user_id == user_id:
                        messages.append(message)

            # Sort by created_at descending and limit
            messages.sort(key=lambda m: m.created_at, reverse=True)
            return [m.to_dict() for m in messages[:max(1, limit)]]

    async def get_session_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """Get messages for a specific session."""
        async with self._lock:
            session_key = self._make_session_key(tenant_id, user_id, session_id)
            message_ids = self._session_messages.get(session_key, [])
            messages = [self._messages[mid] for mid in message_ids if mid in self._messages]

            messages.sort(key=lambda m: m.created_at, reverse=False)  # Chronological order
            return [m.to_dict() for m in messages[-max(1, limit):]]

    async def get_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get list of sessions for tenant/user."""
        async with self._lock:
            user_key = self._make_user_key(tenant_id, user_id)
            session_ids = self._user_sessions.get(user_key, set())

            sessions = []
            for session_id in session_ids:
                session_key = self._make_session_key(tenant_id, user_id, session_id)
                message_ids = self._session_messages.get(session_key, [])
                messages = [self._messages[mid] for mid in message_ids if mid in self._messages]

                if messages:
                    # Use first message timestamp as session start
                    first_message = min(messages, key=lambda m: m.created_at)
                    sessions.append({
                        "id": session_id,
                        "createdAt": first_message.created_at.isoformat(),
                        "messageCount": len(messages),
                    })

            # Sort by created_at descending
            sessions.sort(key=lambda s: s["createdAt"], reverse=True)
            return sessions[:max(1, limit)]

    async def delete_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> bool:
        """Delete a session and all its messages."""
        async with self._lock:
            session_key = self._make_session_key(tenant_id, user_id, session_id)
            message_ids = self._session_messages.pop(session_key, [])

            deleted_count = 0
            for message_id in message_ids:
                if message_id in self._messages:
                    del self._messages[message_id]
                    deleted_count += 1

            # Remove from user sessions
            user_key = self._make_user_key(tenant_id, user_id)
            if user_key in self._user_sessions:
                self._user_sessions[user_key].discard(session_id)

            logger.info(
                "Session deleted",
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                deleted_messages=deleted_count,
            )

            return deleted_count > 0

    async def delete_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        message_id: str,
    ) -> bool:
        """Delete a specific message."""
        async with self._lock:
            if message_id not in self._messages:
                return False

            message = self._messages[message_id]
            if message.tenant_id != tenant_id or message.user_id != user_id:
                return False

            # Remove from session tracking
            if message.session_id:
                session_key = self._make_session_key(
                    tenant_id, user_id, message.session_id
                )
                if session_key in self._session_messages:
                    if message_id in self._session_messages[session_key]:
                        self._session_messages[session_key].remove(message_id)

            del self._messages[message_id]
            logger.info(
                "Message deleted",
                message_id=message_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return True

    async def clear_user_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> int:
        """Clear all messages for a user."""
        async with self._lock:
            user_key = self._make_user_key(tenant_id, user_id)
            deleted_count = 0

            # Delete all messages for user
            message_ids_to_delete = [
                mid for mid, msg in self._messages.items()
                if msg.tenant_id == tenant_id and msg.user_id == user_id
            ]

            for message_id in message_ids_to_delete:
                message = self._messages[message_id]
                if message.session_id:
                    session_key = self._make_session_key(
                        tenant_id, user_id, message.session_id
                    )
                    if session_key in self._session_messages:
                        if message_id in self._session_messages[session_key]:
                            self._session_messages[session_key].remove(message_id)
                del self._messages[message_id]
                deleted_count += 1

            # Clear user sessions
            if user_key in self._user_sessions:
                del self._user_sessions[user_key]

            logger.info(
                "User messages cleared",
                tenant_id=tenant_id,
                user_id=user_id,
                deleted_count=deleted_count,
            )

            return deleted_count

    async def cleanup_old_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        older_than: timedelta | None = None,
    ) -> int:
        """Clean up old messages."""
        if older_than is None:
            older_than = timedelta(days=30)  # Default: 30 days

        async with self._lock:
            cutoff = datetime.now(UTC) - older_than
            deleted_count = 0

            message_ids_to_delete = [
                mid for mid, msg in self._messages.items()
                if (msg.tenant_id == tenant_id and msg.user_id == user_id and
                    msg.created_at < cutoff)
            ]

            for message_id in message_ids_to_delete:
                message = self._messages[message_id]
                if message.session_id:
                    session_key = self._make_session_key(
                        tenant_id, user_id, message.session_id
                    )
                    if session_key in self._session_messages:
                        if message_id in self._session_messages[session_key]:
                            self._session_messages[session_key].remove(message_id)
                del self._messages[message_id]
                deleted_count += 1

            logger.info(
                "Old messages cleaned up",
                tenant_id=tenant_id,
                user_id=user_id,
                older_than=str(older_than),
                deleted_count=deleted_count,
            )

            return deleted_count

    def get_stats(self) -> dict[str, Any]:
        """Get store statistics."""
        return {
            "total_messages": len(self._messages),
            "total_sessions": sum(len(s) for s in self._user_sessions.values()),
            "total_users": len(self._user_sessions),
        }


# ============================================================================
# Cosmos DB Store Implementation
# ============================================================================

class CosmosMemoryStore:
    """Cosmos DB-backed memory store.

    Requires:
    - azure-cosmos package installed
    - COSMOS_ENDPOINT, COSMOS_KEY, COSMOS_DATABASE, COSMOS_CONTAINER env vars
    """

    def __init__(self, endpoint: str, key: str, database: str, container: str):
        try:
            from azure.cosmos.aio import CosmosClient
        except ImportError as e:
            logger.error("azure-cosmos package not installed: %s", e)
            raise

        self._endpoint = endpoint
        self._key = key
        self._database = database
        self._container_name = container
        self._client = CosmosClient(endpoint, credential=key)
        self._database_client = self._client.get_database_client(database)
        self._container_client = self._database_client.get_container_client(container)

    @staticmethod
    def _make_partition_key(tenant_id: str, user_id: str) -> str:
        return f"{tenant_id}#{user_id}"

    @staticmethod
    def _make_session_key(tenant_id: str, user_id: str, session_id: str) -> str:
        return f"{tenant_id}#{user_id}#{session_id}"

    async def _get_container(self):
        """Get container client."""
        return self._container_client

    async def add_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a message to Cosmos DB."""
        import uuid

        message_id = str(uuid.uuid4())
        pk = self._make_partition_key(tenant_id, user_id)
        now = datetime.now(UTC)

        item = {
            "id": message_id,
            "pk": pk,
            "tenantId": tenant_id,
            "userId": user_id,
            "sessionId": session_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
            "type": "message",
        }

        container = await self._get_container()
        await container.upsert_item(item)

        logger.debug(
            "Message added to Cosmos DB",
            message_id=message_id,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
        )

        return message_id

    async def get_recent_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 20,
        session_id: str | None = None,
    ) -> list[dict]:
        """Get recent messages from Cosmos DB."""
        pk = self._make_partition_key(tenant_id, user_id)
        container = await self._get_container()

        query = "SELECT * FROM c WHERE c.pk = @pk AND c.type = 'message'"
        parameters = [{"name": "@pk", "value": pk}]

        if session_id:
            query += " AND c.sessionId = @sessionId"
            parameters.append({"name": "@sessionId", "value": session_id})

        query += " ORDER BY c.createdAt DESC"

        iterator = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=pk,
            max_item_count=max(1, limit),
        )

        items = [item async for item in iterator]
        return items

    async def get_session_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """Get messages for a specific session from Cosmos DB."""
        pk = self._make_partition_key(tenant_id, user_id)
        container = await self._get_container()

        query = (
            "SELECT * FROM c WHERE c.pk = @pk AND c.sessionId = @sessionId "
            "AND c.type = 'message' ORDER BY c.createdAt ASC"
        )
        parameters = [
            {"name": "@pk", "value": pk},
            {"name": "@sessionId", "value": session_id},
        ]

        iterator = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=pk,
            max_item_count=max(1, limit),
        )

        items = [item async for item in iterator]
        return items

    async def get_sessions(
        self,
        *,
        tenant_id: str,
        user_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get list of sessions from Cosmos DB."""
        pk = self._make_partition_key(tenant_id, user_id)
        container = await self._get_container()

        # Get distinct session IDs
        query = (
            "SELECT DISTINCT c.sessionId, MIN(c.createdAt) as createdAt, "
            "COUNT(1) as messageCount FROM c WHERE c.pk = @pk AND c.type = 'message' "
            "AND c.sessionId IS NOT NULL GROUP BY c.sessionId ORDER BY createdAt DESC"
        )
        parameters = [{"name": "@pk", "value": pk}]

        iterator = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=pk,
            max_item_count=max(1, limit),
        )

        items = [item async for item in iterator]
        sessions = []
        for item in items:
            sessions.append({
                "id": item.get("sessionId"),
                "createdAt": item.get("createdAt"),
                "messageCount": item.get("messageCount", 0),
            })

        return sessions

    async def delete_session(
        self,
        *,
        tenant_id: str,
        user_id: str,
        session_id: str,
    ) -> bool:
        """Delete a session from Cosmos DB."""
        pk = self._make_partition_key(tenant_id, user_id)
        container = await self._get_container()

        # Delete all messages in the session
        query = "SELECT c.id FROM c WHERE c.pk = @pk AND c.sessionId = @sessionId AND c.type = 'message'"
        parameters = [
            {"name": "@pk", "value": pk},
            {"name": "@sessionId", "value": session_id},
        ]

        iterator = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=pk,
        )

        deleted_count = 0
        async for item in iterator:
            message_id = item.get("id")
            if message_id:
                try:
                    await container.delete_item(message_id, partition_key=pk)
                    deleted_count += 1
                except Exception:
                    pass

        logger.info(
            "Session deleted from Cosmos DB",
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            deleted_messages=deleted_count,
        )

        return deleted_count > 0

    async def delete_message(
        self,
        *,
        tenant_id: str,
        user_id: str,
        message_id: str,
    ) -> bool:
        """Delete a specific message from Cosmos DB."""
        pk = self._make_partition_key(tenant_id, user_id)
        container = await self._get_container()

        try:
            await container.delete_item(message_id, partition_key=pk)
            logger.info(
                "Message deleted from Cosmos DB",
                message_id=message_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            return True
        except Exception:
            return False

    async def clear_user_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> int:
        """Clear all messages for a user from Cosmos DB."""
        pk = self._make_partition_key(tenant_id, user_id)
        container = await self._get_container()

        # Get all message IDs
        query = "SELECT c.id FROM c WHERE c.pk = @pk AND c.type = 'message'"
        parameters = [{"name": "@pk", "value": pk}]

        iterator = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=pk,
        )

        deleted_count = 0
        async for item in iterator:
            message_id = item.get("id")
            if message_id:
                try:
                    await container.delete_item(message_id, partition_key=pk)
                    deleted_count += 1
                except Exception:
                    pass

        logger.info(
            "User messages cleared from Cosmos DB",
            tenant_id=tenant_id,
            user_id=user_id,
            deleted_count=deleted_count,
        )

        return deleted_count

    async def cleanup_old_messages(
        self,
        *,
        tenant_id: str,
        user_id: str,
        older_than: timedelta | None = None,
    ) -> int:
        """Clean up old messages from Cosmos DB."""
        if older_than is None:
            older_than = timedelta(days=30)

        pk = self._make_partition_key(tenant_id, user_id)
        container = await self._get_container()

        cutoff = (datetime.now(UTC) - older_than).isoformat()

        # Get old message IDs
        query = (
            "SELECT c.id FROM c WHERE c.pk = @pk AND c.type = 'message' "
            "AND c.createdAt < @cutoff"
        )
        parameters = [
            {"name": "@pk", "value": pk},
            {"name": "@cutoff", "value": cutoff},
        ]

        iterator = container.query_items(
            query=query,
            parameters=parameters,
            partition_key=pk,
        )

        deleted_count = 0
        async for item in iterator:
            message_id = item.get("id")
            if message_id:
                try:
                    await container.delete_item(message_id, partition_key=pk)
                    deleted_count += 1
                except Exception:
                    pass

        logger.info(
            "Old messages cleaned up from Cosmos DB",
            tenant_id=tenant_id,
            user_id=user_id,
            older_than=str(older_than),
            deleted_count=deleted_count,
        )

        return deleted_count


# ============================================================================
# Store Factory
# ============================================================================

def build_memory_store() -> MemoryStore:
    """Factory function to create appropriate memory store."""
    config = get_config()
    backend = (config.memory_backend or "inmemory").strip().lower()

    if backend == "cosmos":
        endpoint = config.cosmos_endpoint
        key = config.cosmos_key
        database = config.cosmos_database
        container = config.cosmos_container

        if not all([endpoint, key, database, container]):
            logger.warning(
                "Cosmos DB configuration incomplete. Falling back to in-memory store. "
                "Missing: %s",
                [k for k, v in [
                    ("COSMOS_ENDPOINT", endpoint),
                    ("COSMOS_KEY", key),
                    ("COSMOS_DATABASE", database),
                    ("COSMOS_CONTAINER", container),
                ] if not v]
            )
            return InMemoryStore()

        try:
            logger.info("Using Cosmos DB memory store")
            return CosmosMemoryStore(
                endpoint=endpoint,
                key=key,
                database=database,
                container=container,
            )
        except Exception as e:
            logger.error("Failed to initialize Cosmos DB store: %s. Falling back to in-memory.", e)
            return InMemoryStore()

    logger.info("Using in-memory store")
    return InMemoryStore()

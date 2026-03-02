import logging
import time
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)


class SessionStore:
    """Thread-safe in-memory session store with TTL and cache."""

    def __init__(self, max_sessions: int = 1000, ttl_minutes: int = 30):
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._ttl = timedelta(minutes=ttl_minutes)

    def create(self, session_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._cleanup_expired()
            if len(self._store) >= self._max_sessions:
                # Remove oldest
                self._store.popitem(last=False)
            data["created_at"] = datetime.now()
            data["updated_at"] = datetime.now()
            self._store[session_id] = data
            return data

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            session = self._store.get(session_id)
            if session:
                # Check if expired
                if datetime.now() - session["updated_at"] > self._ttl:
                    del self._store[session_id]
                    return None
                # Move to end (LRU)
                self._store.move_to_end(session_id)
            return session

    def update(self, session_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self._lock:
            if session_id in self._store:
                self._store[session_id].update(data)
                self._store[session_id]["updated_at"] = datetime.now()
                self._store.move_to_end(session_id)
                return self._store[session_id]
            return None

    def delete(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                return True
            return False

    def _cleanup_expired(self):
        """Remove expired sessions."""
        now = datetime.now()
        expired = [
            sid for sid, data in self._store.items()
            if now - data.get("updated_at", now) > self._ttl
        ]
        for sid in expired:
            del self._store[sid]


class QueryCache:
    """Simple LRU cache for repeated queries."""

    def __init__(self, max_entries: int = 500, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._ttl = ttl_seconds

    @staticmethod
    def _make_key(text: str, language: str) -> str:
        content = f"{text[:500]}:{language}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, text: str, language: str) -> Optional[Dict[str, Any]]:
        key = self._make_key(text, language)
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                if time.time() - entry["timestamp"] > self._ttl:
                    del self._cache[key]
                    return None
                self._cache.move_to_end(key)
                return entry["data"]
            return None

    def set(self, text: str, language: str, data: Dict[str, Any]):
        key = self._make_key(text, language)
        with self._lock:
            if len(self._cache) >= self._max_entries:
                self._cache.popitem(last=False)
            self._cache[key] = {
                "data": data,
                "timestamp": time.time(),
            }

    def invalidate(self, text: str, language: str):
        key = self._make_key(text, language)
        with self._lock:
            self._cache.pop(key, None)


# Global instances
sessions_store = SessionStore()
analysis_cache = QueryCache(max_entries=200, ttl_seconds=1800)
audio_cache = QueryCache(max_entries=100, ttl_seconds=3600)

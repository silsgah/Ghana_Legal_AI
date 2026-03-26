"""Caching system for the Ghana Legal AI to improve response times."""

import hashlib
import json
import time
from typing import Any, Optional, Dict
from functools import wraps
from loguru import logger
import pickle
import os


class SimpleCache:
    """Simple in-memory cache with TTL (Time To Live) for legal queries."""
    
    def __init__(self, default_ttl: int = 3600):  # 1 hour default TTL
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, float] = {}
        self.default_ttl = default_ttl
        self.max_size = 1000  # Maximum number of cached items
    
    def _get_key(self, query: str, expert_id: str) -> str:
        """Generate a unique key for the query and expert combination."""
        key_string = f"{query}:{expert_id}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, query: str, expert_id: str) -> Optional[Any]:
        """Get value from cache if it exists and hasn't expired."""
        key = self._get_key(query, expert_id)
        
        if key in self.cache:
            # Check if expired
            if time.time() - self.timestamps[key] > self.default_ttl:
                # Remove expired entry
                del self.cache[key]
                del self.timestamps[key]
                return None
            
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return self.cache[key]
        
        logger.debug(f"Cache miss for query: {query[:50]}...")
        return None
    
    def set(self, query: str, expert_id: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        if ttl is None:
            ttl = self.default_ttl
            
        key = self._get_key(query, expert_id)
        
        # Check if we need to evict old items
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self.timestamps, key=self.timestamps.get)
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]
            logger.debug("Cache eviction: removed oldest entry")
        
        self.cache[key] = value
        self.timestamps[key] = time.time() + ttl - self.default_ttl  # Store as future timestamp
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self.cache.clear()
        self.timestamps.clear()


# Global cache instance
cache = SimpleCache()


def cache_response(ttl: int = 3600):
    """Decorator to cache function responses."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Assume first two arguments are query and expert_id
            query = args[0] if len(args) > 0 else kwargs.get('query', '')
            expert_id = args[1] if len(args) > 1 else kwargs.get('expert_id', '')
            
            # Try to get from cache first
            cached_result = cache.get(query, expert_id)
            if cached_result is not None:
                return cached_result
            
            # Call the original function
            result = func(*args, **kwargs)
            
            # Cache the result
            cache.set(query, expert_id, result, ttl)
            
            return result
        return wrapper
    return decorator


def get_cache() -> SimpleCache:
    """Get the singleton cache instance."""
    return cache
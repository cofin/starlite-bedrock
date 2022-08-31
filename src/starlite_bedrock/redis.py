from redis.asyncio import Redis

from starlite_bedrock.config import cache_settings

__all__ = ["redis"]

redis = Redis.from_url(cache_settings.URL)
"""
Async [`Redis`][redis.Redis] instance.
Configure via [CacheSettings][starlite.contrib.bedrock.config.CacheSettings].
"""

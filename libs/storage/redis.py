"""Redis client for caching and streaming."""

import json
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio import Redis
from ..common.log import get_logger
from ..common.config import settings


class RedisClient:
    """Redis client with async operations."""
    
    def __init__(self, url: str):
        self.url = url
        self.logger = get_logger(__name__)
        self.redis: Optional[Redis] = None
        self.pubsub = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis = redis.from_url(self.url, decode_responses=True)
            await self.redis.ping()
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
        self.logger.info("Disconnected from Redis")
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set key-value pair."""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            return await self.redis.set(key, value, ex=expire)
        except Exception as e:
            self.logger.error(f"Redis SET failed: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            self.logger.error(f"Redis GET failed: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete key."""
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            self.logger.error(f"Redis DELETE failed: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            result = await self.redis.exists(key)
            return result > 0
        except Exception as e:
            self.logger.error(f"Redis EXISTS failed: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration."""
        try:
            result = await self.redis.expire(key, seconds)
            return result
        except Exception as e:
            self.logger.error(f"Redis EXPIRE failed: {e}")
            return False
    
    # Hash operations
    async def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields."""
        try:
            # Convert values to JSON strings
            json_mapping = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                          for k, v in mapping.items()}
            return await self.redis.hset(name, mapping=json_mapping)
        except Exception as e:
            self.logger.error(f"Redis HSET failed: {e}")
            return 0
    
    async def hget(self, name: str, key: str) -> Optional[Any]:
        """Get hash field value."""
        try:
            value = await self.redis.hget(name, key)
            if value is None:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            self.logger.error(f"Redis HGET failed: {e}")
            return None
    
    async def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all hash fields."""
        try:
            data = await self.redis.hgetall(name)
            result = {}
            for k, v in data.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            return result
        except Exception as e:
            self.logger.error(f"Redis HGETALL failed: {e}")
            return {}
    
    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        try:
            return await self.redis.hdel(name, *keys)
        except Exception as e:
            self.logger.error(f"Redis HDEL failed: {e}")
            return 0
    
    # List operations
    async def lpush(self, name: str, *values: Any) -> int:
        """Push values to list."""
        try:
            json_values = [json.dumps(v) if isinstance(v, (dict, list)) else str(v) for v in values]
            return await self.redis.lpush(name, *json_values)
        except Exception as e:
            self.logger.error(f"Redis LPUSH failed: {e}")
            return 0
    
    async def rpop(self, name: str) -> Optional[Any]:
        """Pop value from list."""
        try:
            value = await self.redis.rpop(name)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            self.logger.error(f"Redis RPOP failed: {e}")
            return None
    
    async def lrange(self, name: str, start: int, end: int) -> List[Any]:
        """Get list range."""
        try:
            values = await self.redis.lrange(name, start, end)
            result = []
            for v in values:
                try:
                    result.append(json.loads(v))
                except (json.JSONDecodeError, TypeError):
                    result.append(v)
            return result
        except Exception as e:
            self.logger.error(f"Redis LRANGE failed: {e}")
            return []
    
    # Stream operations
    async def xadd(self, stream: str, fields: Dict[str, Any], maxlen: Optional[int] = None) -> str:
        """Add entry to stream."""
        try:
            # Convert values to strings
            str_fields = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                         for k, v in fields.items()}
            
            if maxlen:
                return await self.redis.xadd(stream, str_fields, maxlen=maxlen)
            else:
                return await self.redis.xadd(stream, str_fields)
        except Exception as e:
            self.logger.error(f"Redis XADD failed: {e}")
            return ""
    
    async def xread(self, streams: Dict[str, str], count: Optional[int] = None, block: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Read from streams."""
        try:
            result = await self.redis.xread(streams, count=count, block=block)
            
            parsed_result = {}
            for stream, messages in result.items():
                parsed_messages = []
                for message_id, fields in messages:
                    parsed_fields = {}
                    for k, v in fields.items():
                        try:
                            parsed_fields[k] = json.loads(v)
                        except (json.JSONDecodeError, TypeError):
                            parsed_fields[k] = v
                    parsed_messages.append({"id": message_id, "fields": parsed_fields})
                parsed_result[stream] = parsed_messages
            
            return parsed_result
        except Exception as e:
            self.logger.error(f"Redis XREAD failed: {e}")
            return {}
    
    async def xgroup_create(self, stream: str, group: str, id: str = "0") -> bool:
        """Create consumer group."""
        try:
            await self.redis.xgroup_create(stream, group, id)
            return True
        except Exception as e:
            if "BUSYGROUP" in str(e):
                return True  # Group already exists
            self.logger.error(f"Redis XGROUP CREATE failed: {e}")
            return False
    
    async def xreadgroup(self, group: str, consumer: str, streams: Dict[str, str], 
                        count: Optional[int] = None, block: Optional[int] = None) -> Dict[str, List[Dict]]:
        """Read from consumer group."""
        try:
            result = await self.redis.xreadgroup(group, consumer, streams, count=count, block=block)
            
            parsed_result = {}
            for stream, messages in result.items():
                parsed_messages = []
                for message_id, fields in messages:
                    parsed_fields = {}
                    for k, v in fields.items():
                        try:
                            parsed_fields[k] = json.loads(v)
                        except (json.JSONDecodeError, TypeError):
                            parsed_fields[k] = v
                    parsed_messages.append({"id": message_id, "fields": parsed_fields})
                parsed_result[stream] = parsed_messages
            
            return parsed_result
        except Exception as e:
            self.logger.error(f"Redis XREADGROUP failed: {e}")
            return {}
    
    async def xack(self, stream: str, group: str, *ids: str) -> int:
        """Acknowledge stream messages."""
        try:
            return await self.redis.xack(stream, group, *ids)
        except Exception as e:
            self.logger.error(f"Redis XACK failed: {e}")
            return 0
    
    # Pub/Sub operations
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel."""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            return await self.redis.publish(channel, message)
        except Exception as e:
            self.logger.error(f"Redis PUBLISH failed: {e}")
            return 0
    
    async def subscribe(self, *channels: str):
        """Subscribe to channels."""
        try:
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe(*channels)
            return self.pubsub
        except Exception as e:
            self.logger.error(f"Redis SUBSCRIBE failed: {e}")
            return None
    
    async def unsubscribe(self, *channels: str) -> None:
        """Unsubscribe from channels."""
        if self.pubsub:
            await self.pubsub.unsubscribe(*channels)
    
    async def get_message(self, timeout: float = 0.0) -> Optional[Dict]:
        """Get message from pubsub."""
        if not self.pubsub:
            return None
        
        try:
            message = await self.pubsub.get_message(timeout=timeout)
            if message and message['type'] == 'message':
                # Try to parse message data as JSON
                try:
                    message['data'] = json.loads(message['data'])
                except (json.JSONDecodeError, TypeError):
                    pass
            return message
        except Exception as e:
            self.logger.error(f"Redis GET_MESSAGE failed: {e}")
            return None
    
    # Trading-specific operations
    async def cache_market_data(self, symbol: str, data: Dict[str, Any], ttl: int = 60) -> bool:
        """Cache market data with TTL."""
        key = f"md:{symbol}"
        return await self.set(key, data, expire=ttl)
    
    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached market data."""
        key = f"md:{symbol}"
        return await self.get(key)
    
    async def cache_order(self, order_id: str, order_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Cache order data."""
        key = f"order:{order_id}"
        return await self.set(key, order_data, expire=ttl)
    
    async def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get cached order data."""
        key = f"order:{order_id}"
        return await self.get(key)
    
    async def stream_tick(self, symbol: str, tick_data: Dict[str, Any]) -> str:
        """Stream tick data."""
        stream = f"ticks:{symbol}"
        return await self.xadd(stream, tick_data)
    
    async def stream_signal(self, signal_data: Dict[str, Any]) -> str:
        """Stream trading signal."""
        stream = "signals"
        return await self.xadd(stream, signal_data)
    
    async def stream_order(self, order_data: Dict[str, Any]) -> str:
        """Stream order data."""
        stream = "orders"
        return await self.xadd(stream, order_data)
    
    async def stream_fill(self, fill_data: Dict[str, Any]) -> str:
        """Stream fill data."""
        stream = "fills"
        return await self.xadd(stream, fill_data)
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get Redis connection information."""
        try:
            info = await self.redis.info()
            return {
                "connected": True,
                "version": info.get("redis_version"),
                "memory_used": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed")
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }

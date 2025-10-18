"""Kafka client for message streaming."""

import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError
from ..common.log import get_logger
from ..common.config import settings


class KafkaClient:
    """Kafka client for async message streaming."""
    
    def __init__(self, brokers: str):
        self.brokers = brokers.split(',')
        self.logger = get_logger(__name__)
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.running = False
    
    async def connect(self) -> None:
        """Connect to Kafka brokers."""
        try:
            # Create producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.brokers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                retry_backoff_ms=100,
                request_timeout_ms=30000
            )
            
            await self.producer.start()
            self.running = True
            self.logger.info(f"Connected to Kafka brokers: {self.brokers}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        self.running = False
        
        # Stop producer
        if self.producer:
            await self.producer.stop()
        
        # Stop all consumers
        for consumer in self.consumers.values():
            await consumer.stop()
        
        self.consumers.clear()
        self.logger.info("Disconnected from Kafka")
    
    async def send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> None:
        """Send message to Kafka topic."""
        if not self.producer:
            raise RuntimeError("Producer not connected")
        
        try:
            await self.producer.send(topic, value=message, key=key)
            self.logger.debug(f"Sent message to topic {topic}")
        except KafkaError as e:
            self.logger.error(f"Failed to send message to {topic}: {e}")
            raise
    
    async def send_batch(self, topic: str, messages: List[Dict[str, Any]], keys: Optional[List[str]] = None) -> None:
        """Send batch of messages to Kafka topic."""
        if not self.producer:
            raise RuntimeError("Producer not connected")
        
        try:
            for i, message in enumerate(messages):
                key = keys[i] if keys and i < len(keys) else None
                await self.producer.send(topic, value=message, key=key)
            
            await self.producer.flush()
            self.logger.debug(f"Sent {len(messages)} messages to topic {topic}")
        except KafkaError as e:
            self.logger.error(f"Failed to send batch to {topic}: {e}")
            raise
    
    async def create_consumer(self, topic: str, group_id: str, auto_offset_reset: str = 'latest') -> AIOKafkaConsumer:
        """Create Kafka consumer for topic."""
        try:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.brokers,
                group_id=group_id,
                auto_offset_reset=auto_offset_reset,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
                max_poll_records=100,
                fetch_min_bytes=1,
                fetch_max_wait_ms=500
            )
            
            await consumer.start()
            self.consumers[topic] = consumer
            self.logger.info(f"Created consumer for topic {topic} with group {group_id}")
            return consumer
            
        except Exception as e:
            self.logger.error(f"Failed to create consumer for {topic}: {e}")
            raise
    
    async def consume_messages(self, topic: str, group_id: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Consume messages from topic with callback."""
        consumer = await self.create_consumer(topic, group_id)
        
        try:
            async for message in consumer:
                try:
                    callback(message.value)
                except Exception as e:
                    self.logger.error(f"Error processing message from {topic}: {e}")
        except Exception as e:
            self.logger.error(f"Error consuming from {topic}: {e}")
        finally:
            await consumer.stop()
            if topic in self.consumers:
                del self.consumers[topic]
    
    async def consume_messages_batch(self, topic: str, group_id: str, 
                                   callback: Callable[[List[Dict[str, Any]]], None],
                                   batch_size: int = 100, timeout_ms: int = 1000) -> None:
        """Consume messages in batches."""
        consumer = await self.create_consumer(topic, group_id)
        
        try:
            while self.running:
                try:
                    # Poll for messages
                    msg_pack = await consumer.getmany(timeout_ms=timeout_ms, max_records=batch_size)
                    
                    if msg_pack:
                        batch = []
                        for topic_partition, messages in msg_pack.items():
                            for message in messages:
                                batch.append(message.value)
                        
                        if batch:
                            callback(batch)
                
                except Exception as e:
                    self.logger.error(f"Error in batch consumption from {topic}: {e}")
                    await asyncio.sleep(1)
        
        finally:
            await consumer.stop()
            if topic in self.consumers:
                del self.consumers[topic]
    
    # Trading-specific methods
    async def send_tick(self, symbol: str, tick_data: Dict[str, Any]) -> None:
        """Send tick data to Kafka."""
        message = {
            "type": "tick",
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "data": tick_data
        }
        await self.send_message(f"ticks.{symbol}", message, key=symbol)
    
    async def send_bar(self, symbol: str, bar_data: Dict[str, Any]) -> None:
        """Send bar data to Kafka."""
        message = {
            "type": "bar",
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "data": bar_data
        }
        await self.send_message(f"bars.{symbol}", message, key=symbol)
    
    async def send_signal(self, signal_data: Dict[str, Any]) -> None:
        """Send trading signal to Kafka."""
        message = {
            "type": "signal",
            "timestamp": datetime.utcnow().isoformat(),
            "data": signal_data
        }
        await self.send_message("signals", message, key=signal_data.get("symbol"))
    
    async def send_order(self, order_data: Dict[str, Any]) -> None:
        """Send order to Kafka."""
        message = {
            "type": "order",
            "timestamp": datetime.utcnow().isoformat(),
            "data": order_data
        }
        await self.send_message("orders", message, key=order_data.get("id"))
    
    async def send_fill(self, fill_data: Dict[str, Any]) -> None:
        """Send fill to Kafka."""
        message = {
            "type": "fill",
            "timestamp": datetime.utcnow().isoformat(),
            "data": fill_data
        }
        await self.send_message("fills", message, key=fill_data.get("order_id"))
    
    async def send_risk_event(self, risk_data: Dict[str, Any]) -> None:
        """Send risk event to Kafka."""
        message = {
            "type": "risk_event",
            "timestamp": datetime.utcnow().isoformat(),
            "data": risk_data
        }
        await self.send_message("risk_events", message, key=risk_data.get("symbol"))
    
    async def send_metric(self, metric_data: Dict[str, Any]) -> None:
        """Send metric to Kafka."""
        message = {
            "type": "metric",
            "timestamp": datetime.utcnow().isoformat(),
            "data": metric_data
        }
        await self.send_message("metrics", message, key=metric_data.get("name"))
    
    async def consume_ticks(self, symbols: List[str], callback: Callable[[Dict[str, Any]], None]) -> None:
        """Consume tick data for symbols."""
        topics = [f"ticks.{symbol}" for symbol in symbols]
        
        for topic in topics:
            asyncio.create_task(
                self.consume_messages(topic, "tick_consumer", callback)
            )
    
    async def consume_signals(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Consume trading signals."""
        await self.consume_messages("signals", "signal_consumer", callback)
    
    async def consume_orders(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Consume orders."""
        await self.consume_messages("orders", "order_consumer", callback)
    
    async def consume_fills(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Consume fills."""
        await self.consume_messages("fills", "fill_consumer", callback)
    
    async def consume_risk_events(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Consume risk events."""
        await self.consume_messages("risk_events", "risk_consumer", callback)
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get Kafka connection information."""
        try:
            if self.producer:
                metadata = await self.producer.client.cluster
                return {
                    "connected": True,
                    "brokers": [broker.host + ":" + str(broker.port) for broker in metadata.brokers()],
                    "topics": list(metadata.topics()),
                    "consumers": list(self.consumers.keys())
                }
            else:
                return {"connected": False, "error": "Producer not connected"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

"""Market data collector metrics."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry
from ..common.log import get_logger


@dataclass
class MDMetric:
    """Market data metric data point."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    symbol: Optional[str] = None


class MDCollectorMetrics:
    """Collect and expose market data collector metrics."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self.logger = get_logger(__name__)
        
        # Prometheus metrics
        self._setup_prometheus_metrics()
        
        # Internal metrics storage
        self.metrics_history: List[MDMetric] = []
        self.max_history = 10000
    
    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics."""
        # Data reception metrics
        self.ticks_received = Counter(
            'md_ticks_received_total',
            'Total number of ticks received',
            ['symbol'],
            registry=self.registry
        )
        
        self.bars_received = Counter(
            'md_bars_received_total',
            'Total number of bars received',
            ['symbol'],
            registry=self.registry
        )
        
        self.data_errors = Counter(
            'md_data_errors_total',
            'Total number of data processing errors',
            ['symbol', 'error_type'],
            registry=self.registry
        )
        
        # Data processing metrics
        self.processing_duration = Histogram(
            'md_processing_duration_seconds',
            'Data processing duration',
            ['symbol', 'data_type'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        self.cache_size = Gauge(
            'md_cache_size',
            'Current cache size',
            ['symbol', 'data_type'],
            registry=self.registry
        )
        
        self.cache_hit_rate = Gauge(
            'md_cache_hit_rate',
            'Cache hit rate',
            ['symbol'],
            registry=self.registry
        )
        
        # Database write metrics
        self.ticks_written = Counter(
            'md_ticks_written_total',
            'Total number of ticks written to database',
            ['symbol'],
            registry=self.registry
        )
        
        self.bars_written = Counter(
            'md_bars_written_total',
            'Total number of bars written to database',
            ['symbol'],
            registry=self.registry
        )
        
        self.write_duration = Histogram(
            'md_write_duration_seconds',
            'Database write duration',
            ['symbol', 'data_type'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        self.write_errors = Counter(
            'md_write_errors_total',
            'Total number of write errors',
            ['symbol', 'error_type'],
            registry=self.registry
        )
        
        # Kafka metrics
        self.kafka_messages_sent = Counter(
            'md_kafka_messages_sent_total',
            'Total number of Kafka messages sent',
            ['symbol', 'message_type'],
            registry=self.registry
        )
        
        self.kafka_send_duration = Histogram(
            'md_kafka_send_duration_seconds',
            'Kafka send duration',
            ['symbol', 'message_type'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        self.kafka_send_errors = Counter(
            'md_kafka_send_errors_total',
            'Total number of Kafka send errors',
            ['symbol', 'error_type'],
            registry=self.registry
        )
        
        # Redis metrics
        self.redis_cache_operations = Counter(
            'md_redis_cache_operations_total',
            'Total number of Redis cache operations',
            ['symbol', 'operation'],
            registry=self.registry
        )
        
        self.redis_operation_duration = Histogram(
            'md_redis_operation_duration_seconds',
            'Redis operation duration',
            ['symbol', 'operation'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        # Subscription metrics
        self.active_subscriptions = Gauge(
            'md_active_subscriptions',
            'Number of active market data subscriptions',
            registry=self.registry
        )
        
        self.subscription_errors = Counter(
            'md_subscription_errors_total',
            'Total number of subscription errors',
            ['symbol', 'error_type'],
            registry=self.registry
        )
        
        # Data quality metrics
        self.stale_data_count = Gauge(
            'md_stale_data_count',
            'Number of symbols with stale data',
            registry=self.registry
        )
        
        self.data_gaps = Counter(
            'md_data_gaps_total',
            'Total number of data gaps detected',
            ['symbol'],
            registry=self.registry
        )
        
        # System metrics
        self.memory_usage = Gauge(
            'md_memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )
        
        self.cpu_usage = Gauge(
            'md_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
    
    def record_tick_received(self, symbol: str) -> None:
        """Record tick received."""
        self.ticks_received.labels(symbol=symbol).inc()
        self._add_metric('tick_received', 1.0, {'symbol': symbol}, symbol)
    
    def record_bar_received(self, symbol: str) -> None:
        """Record bar received."""
        self.bars_received.labels(symbol=symbol).inc()
        self._add_metric('bar_received', 1.0, {'symbol': symbol}, symbol)
    
    def record_data_error(self, symbol: str, error_type: str) -> None:
        """Record data processing error."""
        self.data_errors.labels(symbol=symbol, error_type=error_type).inc()
        self._add_metric('data_error', 1.0, {'symbol': symbol, 'error_type': error_type}, symbol)
    
    def record_processing_duration(self, symbol: str, data_type: str, duration: float) -> None:
        """Record data processing duration."""
        self.processing_duration.labels(symbol=symbol, data_type=data_type).observe(duration)
        self._add_metric('processing_duration', duration, {'symbol': symbol, 'data_type': data_type}, symbol)
    
    def record_cache_size(self, symbol: str, data_type: str, size: int) -> None:
        """Record cache size."""
        self.cache_size.labels(symbol=symbol, data_type=data_type).set(size)
        self._add_metric('cache_size', size, {'symbol': symbol, 'data_type': data_type}, symbol)
    
    def record_cache_hit_rate(self, symbol: str, hit_rate: float) -> None:
        """Record cache hit rate."""
        self.cache_hit_rate.labels(symbol=symbol).set(hit_rate)
        self._add_metric('cache_hit_rate', hit_rate, {'symbol': symbol}, symbol)
    
    def record_ticks_written(self, symbol: str, count: int) -> None:
        """Record ticks written to database."""
        self.ticks_written.labels(symbol=symbol).inc(count)
        self._add_metric('ticks_written', count, {'symbol': symbol}, symbol)
    
    def record_bars_written(self, symbol: str, count: int) -> None:
        """Record bars written to database."""
        self.bars_written.labels(symbol=symbol).inc(count)
        self._add_metric('bars_written', count, {'symbol': symbol}, symbol)
    
    def record_write_duration(self, symbol: str, data_type: str, duration: float) -> None:
        """Record database write duration."""
        self.write_duration.labels(symbol=symbol, data_type=data_type).observe(duration)
        self._add_metric('write_duration', duration, {'symbol': symbol, 'data_type': data_type}, symbol)
    
    def record_write_error(self, symbol: str, error_type: str) -> None:
        """Record database write error."""
        self.write_errors.labels(symbol=symbol, error_type=error_type).inc()
        self._add_metric('write_error', 1.0, {'symbol': symbol, 'error_type': error_type}, symbol)
    
    def record_kafka_message_sent(self, symbol: str, message_type: str) -> None:
        """Record Kafka message sent."""
        self.kafka_messages_sent.labels(symbol=symbol, message_type=message_type).inc()
        self._add_metric('kafka_message_sent', 1.0, {'symbol': symbol, 'message_type': message_type}, symbol)
    
    def record_kafka_send_duration(self, symbol: str, message_type: str, duration: float) -> None:
        """Record Kafka send duration."""
        self.kafka_send_duration.labels(symbol=symbol, message_type=message_type).observe(duration)
        self._add_metric('kafka_send_duration', duration, {'symbol': symbol, 'message_type': message_type}, symbol)
    
    def record_kafka_send_error(self, symbol: str, error_type: str) -> None:
        """Record Kafka send error."""
        self.kafka_send_errors.labels(symbol=symbol, error_type=error_type).inc()
        self._add_metric('kafka_send_error', 1.0, {'symbol': symbol, 'error_type': error_type}, symbol)
    
    def record_redis_operation(self, symbol: str, operation: str) -> None:
        """Record Redis operation."""
        self.redis_cache_operations.labels(symbol=symbol, operation=operation).inc()
        self._add_metric('redis_operation', 1.0, {'symbol': symbol, 'operation': operation}, symbol)
    
    def record_redis_operation_duration(self, symbol: str, operation: str, duration: float) -> None:
        """Record Redis operation duration."""
        self.redis_operation_duration.labels(symbol=symbol, operation=operation).observe(duration)
        self._add_metric('redis_operation_duration', duration, {'symbol': symbol, 'operation': operation}, symbol)
    
    def record_subscription_status(self, active: int, total: int) -> None:
        """Record subscription status."""
        self.active_subscriptions.set(active)
        self._add_metric('active_subscriptions', active, {'total': str(total)})
    
    def record_subscription_error(self, symbol: str, error_type: str) -> None:
        """Record subscription error."""
        self.subscription_errors.labels(symbol=symbol, error_type=error_type).inc()
        self._add_metric('subscription_error', 1.0, {'symbol': symbol, 'error_type': error_type}, symbol)
    
    def record_stale_data_count(self, count: int) -> None:
        """Record stale data count."""
        self.stale_data_count.set(count)
        self._add_metric('stale_data_count', count, {})
    
    def record_data_gap(self, symbol: str) -> None:
        """Record data gap."""
        self.data_gaps.labels(symbol=symbol).inc()
        self._add_metric('data_gap', 1.0, {'symbol': symbol}, symbol)
    
    def record_system_metrics(self, memory_bytes: int, cpu_percent: float) -> None:
        """Record system metrics."""
        self.memory_usage.set(memory_bytes)
        self.cpu_usage.set(cpu_percent)
        
        self._add_metric('memory_usage_bytes', memory_bytes, {})
        self._add_metric('cpu_usage_percent', cpu_percent, {})
    
    def record_cache_status(self, cache_status: Dict[str, Any]) -> None:
        """Record cache status metrics."""
        # Update cache sizes
        for symbol, size in cache_status.get('tick_buffers', {}).items():
            self.record_cache_size(symbol, 'ticks', size)
        
        for symbol, size in cache_status.get('bar_buffers', {}).items():
            self.record_cache_size(symbol, 'bars', size)
        
        # Update cache hit rates
        stats = cache_status.get('stats', {})
        cache_hits = stats.get('cache_hits', 0)
        cache_misses = stats.get('cache_misses', 0)
        
        if cache_hits + cache_misses > 0:
            hit_rate = cache_hits / (cache_hits + cache_misses)
            # Record for all symbols (this is a simplification)
            for symbol in cache_status.get('tick_buffers', {}).keys():
                self.record_cache_hit_rate(symbol, hit_rate)
    
    def record_writer_stats(self, writer_stats: Dict[str, Any]) -> None:
        """Record writer statistics."""
        stats = writer_stats.get('stats', {})
        
        # Record write counts
        ticks_written = stats.get('ticks_written', 0)
        bars_written = stats.get('bars_written', 0)
        
        if ticks_written > 0:
            # Record for all symbols (simplification)
            for symbol in ['SPY', 'QQQ', 'IWM']:  # Default symbols
                self.record_ticks_written(symbol, ticks_written)
        
        if bars_written > 0:
            for symbol in ['SPY', 'QQQ', 'IWM']:  # Default symbols
                self.record_bars_written(symbol, bars_written)
    
    def _add_metric(self, name: str, value: float, tags: Dict[str, str], symbol: Optional[str] = None) -> None:
        """Add metric to history."""
        metric = MDMetric(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags,
            symbol=symbol
        )
        
        self.metrics_history.append(metric)
        
        # Keep only recent metrics
        if len(self.metrics_history) > self.max_history:
            self.metrics_history = self.metrics_history[-self.max_history:]
    
    def get_metrics_summary(self, symbol: Optional[str] = None, 
                           start_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get metrics summary."""
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=1)
        
        # Filter metrics
        filtered_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= start_time and (symbol is None or m.symbol == symbol)
        ]
        
        if not filtered_metrics:
            return {}
        
        # Group by metric name
        metrics_by_name = {}
        for metric in filtered_metrics:
            if metric.name not in metrics_by_name:
                metrics_by_name[metric.name] = []
            metrics_by_name[metric.name].append(metric.value)
        
        # Calculate summary statistics
        summary = {}
        for name, values in metrics_by_name.items():
            if values:
                summary[name] = {
                    'count': len(values),
                    'sum': sum(values),
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'latest': values[-1]
                }
        
        return summary
    
    def get_symbol_metrics(self, symbol: str) -> Dict[str, Any]:
        """Get metrics for specific symbol."""
        symbol_metrics = [m for m in self.metrics_history if m.symbol == symbol]
        
        if not symbol_metrics:
            return {}
        
        # Calculate symbol-specific metrics
        ticks_received = [m for m in symbol_metrics if m.name == 'tick_received']
        bars_received = [m for m in symbol_metrics if m.name == 'bar_received']
        ticks_written = [m for m in symbol_metrics if m.name == 'ticks_written']
        bars_written = [m for m in symbol_metrics if m.name == 'bars_written']
        
        return {
            'ticks_received': len(ticks_received),
            'bars_received': len(bars_received),
            'ticks_written': sum(m.value for m in ticks_written),
            'bars_written': sum(m.value for m in bars_written),
            'avg_processing_duration': self._get_avg_metric(symbol_metrics, 'processing_duration'),
            'avg_write_duration': self._get_avg_metric(symbol_metrics, 'write_duration'),
            'avg_kafka_send_duration': self._get_avg_metric(symbol_metrics, 'kafka_send_duration'),
            'cache_hit_rate': self._get_latest_metric(symbol_metrics, 'cache_hit_rate')
        }
    
    def _get_avg_metric(self, metrics: List[MDMetric], name: str) -> float:
        """Get average value for metric."""
        values = [m.value for m in metrics if m.name == name]
        return sum(values) / len(values) if values else 0.0
    
    def _get_latest_metric(self, metrics: List[MDMetric], name: str) -> float:
        """Get latest value for metric."""
        values = [m.value for m in metrics if m.name == name]
        return values[-1] if values else 0.0
    
    def clear_old_metrics(self, cutoff_time: datetime) -> None:
        """Clear old metrics from history."""
        self.metrics_history = [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]

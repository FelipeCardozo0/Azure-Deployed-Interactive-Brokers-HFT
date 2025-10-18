"""Strategy metrics collection."""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry
from ..common.log import get_logger


@dataclass
class MetricPoint:
    """Metric data point."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    symbol: Optional[str] = None


class StrategyMetrics:
    """Collect and expose strategy metrics."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self.logger = get_logger(__name__)
        
        # Prometheus metrics
        self._setup_prometheus_metrics()
        
        # Internal metrics storage
        self.metrics_history: List[MetricPoint] = []
        self.max_history = 10000
    
    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics."""
        # Signal metrics
        self.signals_generated = Counter(
            'strategy_signals_generated_total',
            'Total number of signals generated',
            ['symbol', 'signal_type'],
            registry=self.registry
        )
        
        self.signal_strength = Histogram(
            'strategy_signal_strength',
            'Signal strength distribution',
            ['symbol'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry
        )
        
        self.signal_confidence = Histogram(
            'strategy_signal_confidence',
            'Signal confidence distribution',
            ['symbol'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry
        )
        
        # Order metrics
        self.orders_placed = Counter(
            'strategy_orders_placed_total',
            'Total number of orders placed',
            ['symbol', 'side', 'status'],
            registry=self.registry
        )
        
        self.order_latency = Histogram(
            'strategy_order_latency_seconds',
            'Order placement latency',
            ['symbol'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        self.order_size = Histogram(
            'strategy_order_size',
            'Order size distribution',
            ['symbol'],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
            registry=self.registry
        )
        
        # Fill metrics
        self.fills_received = Counter(
            'strategy_fills_received_total',
            'Total number of fills received',
            ['symbol', 'side'],
            registry=self.registry
        )
        
        self.fill_latency = Histogram(
            'strategy_fill_latency_seconds',
            'Fill latency from order placement',
            ['symbol'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry
        )
        
        self.slippage = Histogram(
            'strategy_slippage_bps',
            'Slippage in basis points',
            ['symbol'],
            buckets=[0, 1, 2, 5, 10, 20, 50, 100, 200, 500],
            registry=self.registry
        )
        
        # PnL metrics
        self.total_pnl = Gauge(
            'strategy_total_pnl',
            'Total PnL',
            ['symbol'],
            registry=self.registry
        )
        
        self.daily_pnl = Gauge(
            'strategy_daily_pnl',
            'Daily PnL',
            ['symbol'],
            registry=self.registry
        )
        
        self.unrealized_pnl = Gauge(
            'strategy_unrealized_pnl',
            'Unrealized PnL',
            ['symbol'],
            registry=self.registry
        )
        
        self.realized_pnl = Gauge(
            'strategy_realized_pnl',
            'Realized PnL',
            ['symbol'],
            registry=self.registry
        )
        
        # Risk metrics
        self.risk_events = Counter(
            'strategy_risk_events_total',
            'Total number of risk events',
            ['symbol', 'event_type'],
            registry=self.registry
        )
        
        self.position_size = Gauge(
            'strategy_position_size',
            'Current position size',
            ['symbol'],
            registry=self.registry
        )
        
        self.exposure_pct = Gauge(
            'strategy_exposure_percentage',
            'Portfolio exposure percentage',
            registry=self.registry
        )
        
        # Performance metrics
        self.feature_calculation_time = Histogram(
            'strategy_feature_calculation_seconds',
            'Feature calculation time',
            ['symbol'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        self.signal_generation_time = Histogram(
            'strategy_signal_generation_seconds',
            'Signal generation time',
            ['symbol'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        self.throttle_violations = Counter(
            'strategy_throttle_violations_total',
            'Total throttle violations',
            ['symbol'],
            registry=self.registry
        )
        
        # System metrics
        self.active_connections = Gauge(
            'strategy_active_connections',
            'Number of active connections',
            registry=self.registry
        )
        
        self.memory_usage = Gauge(
            'strategy_memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )
        
        self.cpu_usage = Gauge(
            'strategy_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
    
    def record_signal(self, symbol: str, signal_type: str, strength: float, confidence: float) -> None:
        """Record signal generation."""
        self.signals_generated.labels(symbol=symbol, signal_type=signal_type).inc()
        self.signal_strength.labels(symbol=symbol).observe(strength)
        self.signal_confidence.labels(symbol=symbol).observe(confidence)
        
        self._add_metric('signal_generated', 1.0, {'symbol': symbol, 'signal_type': signal_type})
        self._add_metric('signal_strength', strength, {'symbol': symbol})
        self._add_metric('signal_confidence', confidence, {'symbol': symbol})
    
    def record_order(self, symbol: str, side: str, quantity: float, status: str, latency: float) -> None:
        """Record order placement."""
        self.orders_placed.labels(symbol=symbol, side=side, status=status).inc()
        self.order_latency.labels(symbol=symbol).observe(latency)
        self.order_size.labels(symbol=symbol).observe(quantity)
        
        self._add_metric('order_placed', 1.0, {'symbol': symbol, 'side': side, 'status': status})
        self._add_metric('order_latency', latency, {'symbol': symbol})
        self._add_metric('order_size', quantity, {'symbol': symbol})
    
    def record_fill(self, symbol: str, side: str, quantity: float, price: float, 
                   order_price: float, latency: float) -> None:
        """Record fill."""
        self.fills_received.labels(symbol=symbol, side=side).inc()
        self.fill_latency.labels(symbol=symbol).observe(latency)
        
        # Calculate slippage in basis points
        if order_price > 0:
            slippage_bps = abs(price - order_price) / order_price * 10000
            self.slippage.labels(symbol=symbol).observe(slippage_bps)
            self._add_metric('slippage_bps', slippage_bps, {'symbol': symbol})
        
        self._add_metric('fill_received', 1.0, {'symbol': symbol, 'side': side})
        self._add_metric('fill_latency', latency, {'symbol': symbol})
    
    def record_pnl(self, symbol: str, total_pnl: float, daily_pnl: float, 
                  unrealized_pnl: float, realized_pnl: float) -> None:
        """Record PnL metrics."""
        self.total_pnl.labels(symbol=symbol).set(total_pnl)
        self.daily_pnl.labels(symbol=symbol).set(daily_pnl)
        self.unrealized_pnl.labels(symbol=symbol).set(unrealized_pnl)
        self.realized_pnl.labels(symbol=symbol).set(realized_pnl)
        
        self._add_metric('total_pnl', total_pnl, {'symbol': symbol})
        self._add_metric('daily_pnl', daily_pnl, {'symbol': symbol})
        self._add_metric('unrealized_pnl', unrealized_pnl, {'symbol': symbol})
        self._add_metric('realized_pnl', realized_pnl, {'symbol': symbol})
    
    def record_risk_event(self, symbol: str, event_type: str) -> None:
        """Record risk event."""
        self.risk_events.labels(symbol=symbol, event_type=event_type).inc()
        self._add_metric('risk_event', 1.0, {'symbol': symbol, 'event_type': event_type})
    
    def record_position(self, symbol: str, quantity: float, exposure_pct: float) -> None:
        """Record position metrics."""
        self.position_size.labels(symbol=symbol).set(quantity)
        self.exposure_pct.set(exposure_pct)
        
        self._add_metric('position_size', quantity, {'symbol': symbol})
        self._add_metric('exposure_pct', exposure_pct, {})
    
    def record_performance(self, symbol: str, feature_time: float, signal_time: float) -> None:
        """Record performance metrics."""
        self.feature_calculation_time.labels(symbol=symbol).observe(feature_time)
        self.signal_generation_time.labels(symbol=symbol).observe(signal_time)
        
        self._add_metric('feature_calculation_time', feature_time, {'symbol': symbol})
        self._add_metric('signal_generation_time', signal_time, {'symbol': symbol})
    
    def record_throttle_violation(self, symbol: str) -> None:
        """Record throttle violation."""
        self.throttle_violations.labels(symbol=symbol).inc()
        self._add_metric('throttle_violation', 1.0, {'symbol': symbol})
    
    def record_system_metrics(self, connections: int, memory_bytes: int, cpu_percent: float) -> None:
        """Record system metrics."""
        self.active_connections.set(connections)
        self.memory_usage.set(memory_bytes)
        self.cpu_usage.set(cpu_percent)
        
        self._add_metric('active_connections', connections, {})
        self._add_metric('memory_usage_bytes', memory_bytes, {})
        self._add_metric('cpu_usage_percent', cpu_percent, {})
    
    def _add_metric(self, name: str, value: float, tags: Dict[str, str], symbol: Optional[str] = None) -> None:
        """Add metric to history."""
        metric = MetricPoint(
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
        signals = [m for m in symbol_metrics if m.name == 'signal_generated']
        orders = [m for m in symbol_metrics if m.name == 'order_placed']
        fills = [m for m in symbol_metrics if m.name == 'fill_received']
        
        return {
            'signals_generated': len(signals),
            'orders_placed': len(orders),
            'fills_received': len(fills),
            'fill_rate': len(fills) / len(orders) if orders else 0.0,
            'avg_signal_strength': self._get_avg_metric(symbol_metrics, 'signal_strength'),
            'avg_signal_confidence': self._get_avg_metric(symbol_metrics, 'signal_confidence'),
            'avg_order_latency': self._get_avg_metric(symbol_metrics, 'order_latency'),
            'avg_fill_latency': self._get_avg_metric(symbol_metrics, 'fill_latency'),
            'avg_slippage': self._get_avg_metric(symbol_metrics, 'slippage_bps'),
            'total_pnl': self._get_latest_metric(symbol_metrics, 'total_pnl'),
            'daily_pnl': self._get_latest_metric(symbol_metrics, 'daily_pnl')
        }
    
    def _get_avg_metric(self, metrics: List[MetricPoint], name: str) -> float:
        """Get average value for metric."""
        values = [m.value for m in metrics if m.name == name]
        return sum(values) / len(values) if values else 0.0
    
    def _get_latest_metric(self, metrics: List[MetricPoint], name: str) -> float:
        """Get latest value for metric."""
        values = [m.value for m in metrics if m.name == name]
        return values[-1] if values else 0.0
    
    def clear_old_metrics(self, cutoff_time: datetime) -> None:
        """Clear old metrics from history."""
        self.metrics_history = [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]

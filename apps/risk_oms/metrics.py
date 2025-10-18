"""Risk and OMS metrics collection."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry
from ..common.log import get_logger


@dataclass
class RiskMetric:
    """Risk metric data point."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    symbol: Optional[str] = None


class RiskMetrics:
    """Collect and expose risk and OMS metrics."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self.logger = get_logger(__name__)
        
        # Prometheus metrics
        self._setup_prometheus_metrics()
        
        # Internal metrics storage
        self.metrics_history: List[RiskMetric] = []
        self.max_history = 10000
    
    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics."""
        # Risk metrics
        self.risk_checks_total = Counter(
            'risk_checks_total',
            'Total number of risk checks performed',
            ['symbol', 'decision', 'level'],
            registry=self.registry
        )
        
        self.risk_check_duration = Histogram(
            'risk_check_duration_seconds',
            'Risk check duration',
            ['symbol'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
            registry=self.registry
        )
        
        self.risk_rejections = Counter(
            'risk_rejections_total',
            'Total number of risk rejections',
            ['symbol', 'reason'],
            registry=self.registry
        )
        
        self.kill_switch_activations = Counter(
            'kill_switch_activations_total',
            'Total number of kill switch activations',
            registry=self.registry
        )
        
        # Order metrics
        self.orders_submitted = Counter(
            'oms_orders_submitted_total',
            'Total number of orders submitted',
            ['symbol', 'side', 'order_type'],
            registry=self.registry
        )
        
        self.orders_filled = Counter(
            'oms_orders_filled_total',
            'Total number of orders filled',
            ['symbol', 'side'],
            registry=self.registry
        )
        
        self.orders_cancelled = Counter(
            'oms_orders_cancelled_total',
            'Total number of orders cancelled',
            ['symbol'],
            registry=self.registry
        )
        
        self.orders_rejected = Counter(
            'oms_orders_rejected_total',
            'Total number of orders rejected',
            ['symbol', 'reason'],
            registry=self.registry
        )
        
        self.order_latency = Histogram(
            'oms_order_latency_seconds',
            'Order processing latency',
            ['symbol'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        self.fill_latency = Histogram(
            'oms_fill_latency_seconds',
            'Fill processing latency',
            ['symbol'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        # Position metrics
        self.position_size = Gauge(
            'oms_position_size',
            'Current position size',
            ['symbol'],
            registry=self.registry
        )
        
        self.position_value = Gauge(
            'oms_position_value',
            'Current position value',
            ['symbol'],
            registry=self.registry
        )
        
        self.exposure_percentage = Gauge(
            'oms_exposure_percentage',
            'Portfolio exposure percentage',
            registry=self.registry
        )
        
        # Risk limits
        self.risk_limit_utilization = Gauge(
            'risk_limit_utilization',
            'Risk limit utilization percentage',
            ['limit_type'],
            registry=self.registry
        )
        
        self.stale_data_count = Gauge(
            'risk_stale_data_count',
            'Number of symbols with stale data',
            registry=self.registry
        )
        
        # System metrics
        self.active_orders = Gauge(
            'oms_active_orders',
            'Number of active orders',
            registry=self.registry
        )
        
        self.pending_fills = Gauge(
            'oms_pending_fills',
            'Number of pending fills',
            registry=self.registry
        )
        
        self.idempotency_violations = Counter(
            'oms_idempotency_violations_total',
            'Total number of idempotency violations',
            registry=self.registry
        )
    
    def record_risk_check(self, symbol: str, decision: str, level: str, duration: float) -> None:
        """Record risk check."""
        self.risk_checks_total.labels(symbol=symbol, decision=decision, level=level).inc()
        self.risk_check_duration.labels(symbol=symbol).observe(duration)
        
        self._add_metric('risk_check', 1.0, {
            'symbol': symbol,
            'decision': decision,
            'level': level
        }, symbol)
    
    def record_risk_rejection(self, symbol: str, reason: str) -> None:
        """Record risk rejection."""
        self.risk_rejections.labels(symbol=symbol, reason=reason).inc()
        self._add_metric('risk_rejection', 1.0, {
            'symbol': symbol,
            'reason': reason
        }, symbol)
    
    def record_kill_switch_activation(self) -> None:
        """Record kill switch activation."""
        self.kill_switch_activations.inc()
        self._add_metric('kill_switch_activation', 1.0, {})
    
    def record_order_submitted(self, symbol: str, side: str, order_type: str, latency: float) -> None:
        """Record order submission."""
        self.orders_submitted.labels(symbol=symbol, side=side, order_type=order_type).inc()
        self.order_latency.labels(symbol=symbol).observe(latency)
        
        self._add_metric('order_submitted', 1.0, {
            'symbol': symbol,
            'side': side,
            'order_type': order_type
        }, symbol)
    
    def record_order_filled(self, symbol: str, side: str, latency: float) -> None:
        """Record order fill."""
        self.orders_filled.labels(symbol=symbol, side=side).inc()
        self.fill_latency.labels(symbol=symbol).observe(latency)
        
        self._add_metric('order_filled', 1.0, {
            'symbol': symbol,
            'side': side
        }, symbol)
    
    def record_order_cancelled(self, symbol: str) -> None:
        """Record order cancellation."""
        self.orders_cancelled.labels(symbol=symbol).inc()
        self._add_metric('order_cancelled', 1.0, {'symbol': symbol}, symbol)
    
    def record_order_rejected(self, symbol: str, reason: str) -> None:
        """Record order rejection."""
        self.orders_rejected.labels(symbol=symbol, reason=reason).inc()
        self._add_metric('order_rejected', 1.0, {
            'symbol': symbol,
            'reason': reason
        }, symbol)
    
    def record_position(self, symbol: str, size: float, value: float) -> None:
        """Record position metrics."""
        self.position_size.labels(symbol=symbol).set(size)
        self.position_value.labels(symbol=symbol).set(value)
        
        self._add_metric('position_size', size, {'symbol': symbol}, symbol)
        self._add_metric('position_value', value, {'symbol': symbol}, symbol)
    
    def record_exposure(self, percentage: float) -> None:
        """Record exposure percentage."""
        self.exposure_percentage.set(percentage)
        self._add_metric('exposure_percentage', percentage, {})
    
    def record_risk_limit_utilization(self, limit_type: str, utilization: float) -> None:
        """Record risk limit utilization."""
        self.risk_limit_utilization.labels(limit_type=limit_type).set(utilization)
        self._add_metric('risk_limit_utilization', utilization, {'limit_type': limit_type})
    
    def record_stale_data(self, count: int) -> None:
        """Record stale data count."""
        self.stale_data_count.set(count)
        self._add_metric('stale_data_count', count, {})
    
    def record_active_orders(self, count: int) -> None:
        """Record active orders count."""
        self.active_orders.set(count)
        self._add_metric('active_orders', count, {})
    
    def record_pending_fills(self, count: int) -> None:
        """Record pending fills count."""
        self.pending_fills.set(count)
        self._add_metric('pending_fills', count, {})
    
    def record_idempotency_violation(self) -> None:
        """Record idempotency violation."""
        self.idempotency_violations.inc()
        self._add_metric('idempotency_violation', 1.0, {})
    
    def _add_metric(self, name: str, value: float, tags: Dict[str, str], symbol: Optional[str] = None) -> None:
        """Add metric to history."""
        metric = RiskMetric(
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
    
    def get_risk_summary(self, symbol: Optional[str] = None, 
                        start_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get risk metrics summary."""
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
    
    def get_symbol_risk_metrics(self, symbol: str) -> Dict[str, Any]:
        """Get risk metrics for specific symbol."""
        symbol_metrics = [m for m in self.metrics_history if m.symbol == symbol]
        
        if not symbol_metrics:
            return {}
        
        # Calculate symbol-specific metrics
        risk_checks = [m for m in symbol_metrics if m.name == 'risk_check']
        risk_rejections = [m for m in symbol_metrics if m.name == 'risk_rejection']
        orders_submitted = [m for m in symbol_metrics if m.name == 'order_submitted']
        orders_filled = [m for m in symbol_metrics if m.name == 'order_filled']
        
        return {
            'risk_checks': len(risk_checks),
            'risk_rejections': len(risk_rejections),
            'rejection_rate': len(risk_rejections) / len(risk_checks) if risk_checks else 0.0,
            'orders_submitted': len(orders_submitted),
            'orders_filled': len(orders_filled),
            'fill_rate': len(orders_filled) / len(orders_submitted) if orders_submitted else 0.0,
            'avg_risk_check_duration': self._get_avg_metric(symbol_metrics, 'risk_check_duration'),
            'avg_order_latency': self._get_avg_metric(symbol_metrics, 'order_latency'),
            'avg_fill_latency': self._get_avg_metric(symbol_metrics, 'fill_latency')
        }
    
    def _get_avg_metric(self, metrics: List[RiskMetric], name: str) -> float:
        """Get average value for metric."""
        values = [m.value for m in metrics if m.name == name]
        return sum(values) / len(values) if values else 0.0
    
    def get_risk_alerts(self) -> List[Dict[str, Any]]:
        """Get current risk alerts."""
        alerts = []
        
        # Check for high rejection rate
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= datetime.utcnow() - timedelta(minutes=5)
        ]
        
        risk_checks = [m for m in recent_metrics if m.name == 'risk_check']
        risk_rejections = [m for m in recent_metrics if m.name == 'risk_rejection']
        
        if risk_checks and len(risk_rejections) / len(risk_checks) > 0.5:
            alerts.append({
                'type': 'HIGH_REJECTION_RATE',
                'severity': 'WARNING',
                'message': f"High rejection rate: {len(risk_rejections)}/{len(risk_checks)}",
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Check for stale data
        stale_data = [m for m in recent_metrics if m.name == 'stale_data_count']
        if stale_data and stale_data[-1].value > 0:
            alerts.append({
                'type': 'STALE_DATA',
                'severity': 'CRITICAL',
                'message': f"Stale data detected for {stale_data[-1].value} symbols",
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return alerts
    
    def clear_old_metrics(self, cutoff_time: datetime) -> None:
        """Clear old metrics from history."""
        self.metrics_history = [
            m for m in self.metrics_history 
            if m.timestamp > cutoff_time
        ]

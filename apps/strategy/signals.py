"""Trading signal generation."""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from ..common.log import get_logger


class SignalType(Enum):
    """Signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    """Trading signal."""
    symbol: str
    signal_type: SignalType
    strength: float
    timestamp: datetime
    features: Dict[str, float]
    reason: str
    confidence: float = 0.0


@dataclass
class SignalConfig:
    """Signal generation configuration."""
    zscore_threshold: float = 2.0
    momentum_threshold: float = 0.001
    volatility_threshold: float = 0.01
    volume_threshold: float = 1.5
    min_confidence: float = 0.6
    max_signals_per_symbol: int = 10


class SignalGenerator:
    """Generate trading signals from features."""
    
    def __init__(self, config: SignalConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.signal_history: Dict[str, List[Signal]] = {}
    
    def generate_signal(self, symbol: str, features: Dict[str, float]) -> Optional[Signal]:
        """Generate trading signal from features."""
        if not features:
            return None
        
        # Check if we have enough data
        required_features = ['zscore', 'momentum_5s', 'volatility_1m', 'volume_ratio']
        if not all(feat in features for feat in required_features):
            return None
        
        # Calculate signal components
        zscore_signal = self._zscore_signal(features['zscore'])
        momentum_signal = self._momentum_signal(features['momentum_5s'])
        volatility_signal = self._volatility_signal(features['volatility_1m'])
        volume_signal = self._volume_signal(features['volume_ratio'])
        
        # Combine signals
        combined_signal, strength, confidence = self._combine_signals(
            zscore_signal, momentum_signal, volatility_signal, volume_signal
        )
        
        # Check confidence threshold
        if confidence < self.config.min_confidence:
            return None
        
        # Check signal history to avoid spam
        if self._is_duplicate_signal(symbol, combined_signal, strength):
            return None
        
        # Create signal
        signal = Signal(
            symbol=symbol,
            signal_type=combined_signal,
            strength=strength,
            timestamp=datetime.utcnow(),
            features=features,
            reason=self._get_signal_reason(features, combined_signal),
            confidence=confidence
        )
        
        # Store in history
        self._store_signal(signal)
        
        return signal
    
    def _zscore_signal(self, zscore: float) -> Tuple[SignalType, float]:
        """Generate signal based on z-score."""
        if zscore > self.config.zscore_threshold:
            return SignalType.SELL, abs(zscore)
        elif zscore < -self.config.zscore_threshold:
            return SignalType.BUY, abs(zscore)
        else:
            return SignalType.HOLD, 0.0
    
    def _momentum_signal(self, momentum: float) -> Tuple[SignalType, float]:
        """Generate signal based on momentum."""
        if momentum > self.config.momentum_threshold:
            return SignalType.BUY, abs(momentum)
        elif momentum < -self.config.momentum_threshold:
            return SignalType.SELL, abs(momentum)
        else:
            return SignalType.HOLD, 0.0
    
    def _volatility_signal(self, volatility: float) -> Tuple[SignalType, float]:
        """Generate signal based on volatility."""
        if volatility > self.config.volatility_threshold:
            # High volatility - reduce position size
            return SignalType.HOLD, 0.0
        else:
            # Low volatility - normal trading
            return SignalType.HOLD, 1.0
    
    def _volume_signal(self, volume_ratio: float) -> Tuple[SignalType, float]:
        """Generate signal based on volume."""
        if volume_ratio > self.config.volume_threshold:
            # High volume - increase confidence
            return SignalType.HOLD, volume_ratio
        else:
            # Low volume - reduce confidence
            return SignalType.HOLD, 0.5
    
    def _combine_signals(self, zscore_sig: Tuple[SignalType, float],
                        momentum_sig: Tuple[SignalType, float],
                        volatility_sig: Tuple[SignalType, float],
                        volume_sig: Tuple[SignalType, float]) -> Tuple[SignalType, float, float]:
        """Combine multiple signals into final signal."""
        
        # Extract signal types and strengths
        zscore_type, zscore_strength = zscore_sig
        momentum_type, momentum_strength = momentum_sig
        volatility_type, volatility_strength = volatility_sig
        volume_type, volume_strength = volume_sig
        
        # Weight the signals
        weights = {
            'zscore': 0.4,
            'momentum': 0.3,
            'volatility': 0.2,
            'volume': 0.1
        }
        
        # Calculate weighted signal
        buy_strength = 0.0
        sell_strength = 0.0
        
        if zscore_type == SignalType.BUY:
            buy_strength += zscore_strength * weights['zscore']
        elif zscore_type == SignalType.SELL:
            sell_strength += zscore_strength * weights['zscore']
        
        if momentum_type == SignalType.BUY:
            buy_strength += momentum_strength * weights['momentum']
        elif momentum_type == SignalType.SELL:
            sell_strength += momentum_strength * weights['momentum']
        
        # Apply volatility filter
        volatility_multiplier = volatility_strength
        buy_strength *= volatility_multiplier
        sell_strength *= volatility_multiplier
        
        # Apply volume filter
        volume_multiplier = volume_strength
        buy_strength *= volume_multiplier
        sell_strength *= volume_multiplier
        
        # Determine final signal
        if buy_strength > sell_strength and buy_strength > 0.5:
            return SignalType.BUY, buy_strength, min(buy_strength, 1.0)
        elif sell_strength > buy_strength and sell_strength > 0.5:
            return SignalType.SELL, sell_strength, min(sell_strength, 1.0)
        else:
            return SignalType.HOLD, 0.0, 0.0
    
    def _get_signal_reason(self, features: Dict[str, float], signal_type: SignalType) -> str:
        """Generate human-readable reason for signal."""
        reasons = []
        
        if abs(features.get('zscore', 0)) > self.config.zscore_threshold:
            reasons.append(f"Z-score: {features['zscore']:.3f}")
        
        if abs(features.get('momentum_5s', 0)) > self.config.momentum_threshold:
            reasons.append(f"Momentum: {features['momentum_5s']:.3f}")
        
        if features.get('volume_ratio', 1) > self.config.volume_threshold:
            reasons.append(f"Volume: {features['volume_ratio']:.2f}x")
        
        if features.get('volatility_1m', 0) < self.config.volatility_threshold:
            reasons.append("Low volatility")
        
        if not reasons:
            reasons.append("No strong indicators")
        
        return f"{signal_type.value}: " + ", ".join(reasons)
    
    def _is_duplicate_signal(self, symbol: str, signal_type: SignalType, strength: float) -> bool:
        """Check if signal is duplicate of recent signal."""
        if symbol not in self.signal_history:
            return False
        
        recent_signals = self.signal_history[symbol][-self.config.max_signals_per_symbol:]
        
        for signal in recent_signals:
            # Check if same type and similar strength
            if (signal.signal_type == signal_type and 
                abs(signal.strength - strength) < 0.1):
                return True
        
        return False
    
    def _store_signal(self, signal: Signal) -> None:
        """Store signal in history."""
        if signal.symbol not in self.signal_history:
            self.signal_history[signal.symbol] = []
        
        self.signal_history[signal.symbol].append(signal)
        
        # Keep only recent signals
        if len(self.signal_history[signal.symbol]) > self.config.max_signals_per_symbol:
            self.signal_history[signal.symbol] = self.signal_history[signal.symbol][-self.config.max_signals_per_symbol:]
    
    def get_signal_history(self, symbol: str, limit: int = 10) -> List[Signal]:
        """Get recent signal history for symbol."""
        if symbol not in self.signal_history:
            return []
        
        return self.signal_history[symbol][-limit:]
    
    def get_signal_stats(self, symbol: str) -> Dict[str, float]:
        """Get signal statistics for symbol."""
        if symbol not in self.signal_history:
            return {}
        
        signals = self.signal_history[symbol]
        if not signals:
            return {}
        
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        return {
            'total_signals': len(signals),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'avg_confidence': np.mean([s.confidence for s in signals]),
            'avg_strength': np.mean([s.strength for s in signals]),
            'buy_ratio': len(buy_signals) / len(signals) if signals else 0.0,
            'sell_ratio': len(sell_signals) / len(signals) if signals else 0.0
        }
    
    def clear_old_signals(self, cutoff_time: datetime) -> None:
        """Clear old signals from history."""
        for symbol in list(self.signal_history.keys()):
            self.signal_history[symbol] = [
                s for s in self.signal_history[symbol] 
                if s.timestamp > cutoff_time
            ]
            
            if not self.signal_history[symbol]:
                del self.signal_history[symbol]

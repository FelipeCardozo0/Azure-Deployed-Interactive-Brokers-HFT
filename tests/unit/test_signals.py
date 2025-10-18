"""Unit tests for signal generation."""

import pytest
from datetime import datetime
from apps.strategy.signals import SignalGenerator, SignalConfig, SignalType
from apps.strategy.features import FeatureCalculator, FeatureConfig


class TestSignalGenerator:
    """Test signal generation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = SignalConfig(
            zscore_threshold=2.0,
            momentum_threshold=0.001,
            volatility_threshold=0.01,
            volume_threshold=1.5,
            min_confidence=0.6
        )
        self.signal_generator = SignalGenerator(self.config)
    
    def test_buy_signal_high_zscore(self):
        """Test buy signal with high negative z-score."""
        features = {
            'zscore': -2.5,
            'momentum_5s': 0.002,
            'volatility_1m': 0.005,
            'volume_ratio': 2.0
        }
        
        signal = self.signal_generator.generate_signal('SPY', features)
        
        assert signal is not None
        assert signal.signal_type == SignalType.BUY
        assert signal.strength > 0
        assert signal.confidence >= self.config.min_confidence
    
    def test_sell_signal_high_zscore(self):
        """Test sell signal with high positive z-score."""
        features = {
            'zscore': 2.5,
            'momentum_5s': -0.002,
            'volatility_1m': 0.005,
            'volume_ratio': 2.0
        }
        
        signal = self.signal_generator.generate_signal('SPY', features)
        
        assert signal is not None
        assert signal.signal_type == SignalType.SELL
        assert signal.strength > 0
        assert signal.confidence >= self.config.min_confidence
    
    def test_hold_signal_low_zscore(self):
        """Test hold signal with low z-score."""
        features = {
            'zscore': 0.5,
            'momentum_5s': 0.0005,
            'volatility_1m': 0.005,
            'volume_ratio': 1.2
        }
        
        signal = self.signal_generator.generate_signal('SPY', features)
        
        assert signal is None or signal.signal_type == SignalType.HOLD
    
    def test_signal_rejected_low_confidence(self):
        """Test signal rejected due to low confidence."""
        features = {
            'zscore': 1.5,
            'momentum_5s': 0.0005,
            'volatility_1m': 0.02,  # High volatility
            'volume_ratio': 0.8  # Low volume
        }
        
        signal = self.signal_generator.generate_signal('SPY', features)
        
        assert signal is None or signal.confidence < self.config.min_confidence
    
    def test_duplicate_signal_prevention(self):
        """Test duplicate signal prevention."""
        features = {
            'zscore': -2.5,
            'momentum_5s': 0.002,
            'volatility_1m': 0.005,
            'volume_ratio': 2.0
        }
        
        # Generate first signal
        signal1 = self.signal_generator.generate_signal('SPY', features)
        assert signal1 is not None
        
        # Generate second signal with same features
        signal2 = self.signal_generator.generate_signal('SPY', features)
        assert signal2 is None  # Should be rejected as duplicate
    
    def test_signal_history(self):
        """Test signal history tracking."""
        features = {
            'zscore': -2.5,
            'momentum_5s': 0.002,
            'volatility_1m': 0.005,
            'volume_ratio': 2.0
        }
        
        # Generate signal
        signal = self.signal_generator.generate_signal('SPY', features)
        assert signal is not None
        
        # Check history
        history = self.signal_generator.get_signal_history('SPY', limit=10)
        assert len(history) == 1
        assert history[0].symbol == 'SPY'
        assert history[0].signal_type == SignalType.BUY
    
    def test_signal_stats(self):
        """Test signal statistics."""
        # Generate multiple signals
        features_buy = {
            'zscore': -2.5,
            'momentum_5s': 0.002,
            'volatility_1m': 0.005,
            'volume_ratio': 2.0
        }
        
        features_sell = {
            'zscore': 2.5,
            'momentum_5s': -0.002,
            'volatility_1m': 0.005,
            'volume_ratio': 2.0
        }
        
        self.signal_generator.generate_signal('SPY', features_buy)
        self.signal_generator.generate_signal('SPY', features_sell)
        
        stats = self.signal_generator.get_signal_stats('SPY')
        assert stats['total_signals'] == 2
        assert stats['buy_signals'] == 1
        assert stats['sell_signals'] == 1
        assert stats['buy_ratio'] == 0.5
        assert stats['sell_ratio'] == 0.5


class TestFeatureCalculator:
    """Test feature calculation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = FeatureConfig(
            lookback_period=60,
            volatility_window=20,
            momentum_window=5,
            zscore_threshold=2.0
        )
        self.feature_calculator = FeatureCalculator(self.config)
    
    def test_add_tick(self):
        """Test adding tick data."""
        symbol = 'SPY'
        timestamp = datetime.utcnow()
        price = 450.0
        volume = 1000
        
        self.feature_calculator.add_tick(symbol, timestamp, price, volume)
        
        # Check if tick was added
        ticks = self.feature_calculator.get_ticks(symbol, limit=1)
        assert len(ticks) == 1
        assert ticks[0].symbol == symbol
        assert ticks[0].price == price
        assert ticks[0].volume == volume
    
    def test_add_bar(self):
        """Test adding bar data."""
        symbol = 'SPY'
        timestamp = datetime.utcnow()
        open_price = 450.0
        high = 451.0
        low = 449.0
        close = 450.5
        volume = 10000
        
        self.feature_calculator.add_bar(symbol, timestamp, open_price, high, low, close, volume)
        
        # Check if bar was added
        bars = self.feature_calculator.get_bars(symbol, limit=1)
        assert len(bars) == 1
        assert bars[0].symbol == symbol
        assert bars[0].open == open_price
        assert bars[0].high == high
        assert bars[0].low == low
        assert bars[0].close == close
        assert bars[0].volume == volume
    
    def test_feature_calculation_insufficient_data(self):
        """Test feature calculation with insufficient data."""
        symbol = 'SPY'
        
        # Add only one tick
        self.feature_calculator.add_tick(symbol, datetime.utcnow(), 450.0, 1000)
        
        # Should return None due to insufficient data
        features = self.feature_calculator.get_features(symbol)
        assert features is None
    
    def test_feature_calculation_sufficient_data(self):
        """Test feature calculation with sufficient data."""
        symbol = 'SPY'
        
        # Add enough ticks for feature calculation
        base_price = 450.0
        for i in range(100):
            price = base_price + (i % 10 - 5) * 0.1  # Some price variation
            timestamp = datetime.utcnow()
            volume = 1000 + i * 10
            self.feature_calculator.add_tick(symbol, timestamp, price, volume)
        
        # Should return features
        features = self.feature_calculator.get_features(symbol)
        assert features is not None
        assert 'zscore' in features
        assert 'momentum_5s' in features
        assert 'volatility_1m' in features
        assert 'volume_ratio' in features
    
    def test_rolling_features(self):
        """Test rolling feature calculation."""
        symbol = 'SPY'
        
        # Add enough data for rolling features
        base_price = 450.0
        for i in range(100):
            price = base_price + (i % 10 - 5) * 0.1
            timestamp = datetime.utcnow()
            volume = 1000 + i * 10
            self.feature_calculator.add_tick(symbol, timestamp, price, volume)
        
        # Get rolling features
        rolling_features = self.feature_calculator.get_rolling_features(symbol, window=20)
        assert rolling_features is not None
        assert len(rolling_features) == 20
        assert 'mean' in rolling_features.columns
        assert 'std' in rolling_features.columns
    
    def test_cache_cleanup(self):
        """Test cache cleanup of old data."""
        symbol = 'SPY'
        cutoff_time = datetime.utcnow()
        
        # Add old data
        old_timestamp = cutoff_time - timedelta(hours=1)
        self.feature_calculator.add_tick(symbol, old_timestamp, 450.0, 1000)
        
        # Add new data
        new_timestamp = cutoff_time + timedelta(minutes=1)
        self.feature_calculator.add_tick(symbol, new_timestamp, 451.0, 1000)
        
        # Clean up old data
        self.feature_calculator.clear_old_data(cutoff_time)
        
        # Check that only new data remains
        ticks = self.feature_calculator.get_ticks(symbol)
        assert len(ticks) == 1
        assert ticks[0].timestamp > cutoff_time

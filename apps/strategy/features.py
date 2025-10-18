"""Feature calculation for trading signals."""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from ..common.log import get_logger


@dataclass
class FeatureConfig:
    """Feature calculation configuration."""
    lookback_period: int = 60
    volatility_window: int = 20
    momentum_window: int = 5
    zscore_threshold: float = 2.0
    min_volume: int = 1000


class FeatureCalculator:
    """Calculate trading features from market data."""
    
    def __init__(self, config: FeatureConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.data_cache: Dict[str, pd.DataFrame] = {}
    
    def add_tick(self, symbol: str, timestamp: datetime, price: float, volume: int) -> None:
        """Add tick data to cache."""
        if symbol not in self.data_cache:
            self.data_cache[symbol] = pd.DataFrame(columns=['timestamp', 'price', 'volume'])
        
        new_row = pd.DataFrame({
            'timestamp': [timestamp],
            'price': [price],
            'volume': [volume]
        })
        
        self.data_cache[symbol] = pd.concat([self.data_cache[symbol], new_row], ignore_index=True)
        
        # Keep only recent data
        cutoff = timestamp - timedelta(seconds=self.config.lookback_period * 2)
        self.data_cache[symbol] = self.data_cache[symbol][
            self.data_cache[symbol]['timestamp'] > cutoff
        ]
    
    def add_bar(self, symbol: str, timestamp: datetime, open_price: float, high: float, 
                low: float, close: float, volume: int) -> None:
        """Add bar data to cache."""
        if symbol not in self.data_cache:
            self.data_cache[symbol] = pd.DataFrame(columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume'
            ])
        
        new_row = pd.DataFrame({
            'timestamp': [timestamp],
            'open': [open_price],
            'high': [high],
            'low': [low],
            'close': [close],
            'volume': [volume]
        })
        
        self.data_cache[symbol] = pd.concat([self.data_cache[symbol], new_row], ignore_index=True)
        
        # Keep only recent data
        cutoff = timestamp - timedelta(seconds=self.config.lookback_period * 2)
        self.data_cache[symbol] = self.data_cache[symbol][
            self.data_cache[symbol]['timestamp'] > cutoff
        ]
    
    def get_features(self, symbol: str) -> Optional[Dict[str, float]]:
        """Calculate features for symbol."""
        if symbol not in self.data_cache or len(self.data_cache[symbol]) < self.config.lookback_period:
            return None
        
        df = self.data_cache[symbol].copy()
        df = df.sort_values('timestamp').tail(self.config.lookback_period)
        
        if 'close' in df.columns:
            # Bar data available
            return self._calculate_bar_features(df)
        else:
            # Tick data only
            return self._calculate_tick_features(df)
    
    def _calculate_bar_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate features from bar data."""
        features = {}
        
        # Price features
        features['close'] = df['close'].iloc[-1]
        features['open'] = df['open'].iloc[-1]
        features['high'] = df['high'].iloc[-1]
        features['low'] = df['low'].iloc[-1]
        
        # Returns
        features['return_1s'] = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] if len(df) > 1 else 0.0
        features['return_5s'] = (df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6] if len(df) > 5 else 0.0
        features['return_1m'] = (df['close'].iloc[-1] - df['close'].iloc[-61]) / df['close'].iloc[-61] if len(df) > 60 else 0.0
        
        # Volatility
        returns = df['close'].pct_change().dropna()
        features['volatility_1m'] = returns.rolling(self.config.volatility_window).std().iloc[-1] if len(returns) >= self.config.volatility_window else 0.0
        features['volatility_5m'] = returns.rolling(min(60, len(returns))).std().iloc[-1] if len(returns) > 0 else 0.0
        
        # Z-score
        if len(returns) >= self.config.volatility_window:
            rolling_mean = returns.rolling(self.config.volatility_window).mean()
            rolling_std = returns.rolling(self.config.volatility_window).std()
            features['zscore'] = (returns.iloc[-1] - rolling_mean.iloc[-1]) / rolling_std.iloc[-1] if rolling_std.iloc[-1] > 0 else 0.0
        else:
            features['zscore'] = 0.0
        
        # Momentum
        features['momentum_5s'] = (df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6] if len(df) > 5 else 0.0
        features['momentum_1m'] = (df['close'].iloc[-1] - df['close'].iloc[-61]) / df['close'].iloc[-61] if len(df) > 60 else 0.0
        
        # Volume features
        features['volume'] = df['volume'].iloc[-1]
        features['volume_avg'] = df['volume'].rolling(min(20, len(df))).mean().iloc[-1] if len(df) > 0 else 0.0
        features['volume_ratio'] = features['volume'] / features['volume_avg'] if features['volume_avg'] > 0 else 1.0
        
        # Price levels
        features['high_1m'] = df['high'].rolling(min(60, len(df))).max().iloc[-1]
        features['low_1m'] = df['low'].rolling(min(60, len(df))).min().iloc[-1]
        features['high_5m'] = df['high'].rolling(min(300, len(df))).max().iloc[-1]
        features['low_5m'] = df['low'].rolling(min(300, len(df))).min().iloc[-1]
        
        # Range features
        features['range_1m'] = (features['high_1m'] - features['low_1m']) / features['close'] if features['close'] > 0 else 0.0
        features['range_5m'] = (features['high_5m'] - features['low_5m']) / features['close'] if features['close'] > 0 else 0.0
        
        # Time features
        features['time_of_day'] = df['timestamp'].iloc[-1].hour + df['timestamp'].iloc[-1].minute / 60.0
        features['is_market_open'] = 1.0 if 9.5 <= features['time_of_day'] <= 16.0 else 0.0
        
        return features
    
    def _calculate_tick_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate features from tick data."""
        features = {}
        
        # Price features
        features['price'] = df['price'].iloc[-1]
        
        # Returns
        features['return_1s'] = (df['price'].iloc[-1] - df['price'].iloc[-2]) / df['price'].iloc[-2] if len(df) > 1 else 0.0
        features['return_5s'] = (df['price'].iloc[-1] - df['price'].iloc[-6]) / df['price'].iloc[-6] if len(df) > 5 else 0.0
        features['return_1m'] = (df['price'].iloc[-1] - df['price'].iloc[-61]) / df['price'].iloc[-61] if len(df) > 60 else 0.0
        
        # Volatility
        returns = df['price'].pct_change().dropna()
        features['volatility_1m'] = returns.rolling(self.config.volatility_window).std().iloc[-1] if len(returns) >= self.config.volatility_window else 0.0
        
        # Z-score
        if len(returns) >= self.config.volatility_window:
            rolling_mean = returns.rolling(self.config.volatility_window).mean()
            rolling_std = returns.rolling(self.config.volatility_window).std()
            features['zscore'] = (returns.iloc[-1] - rolling_mean.iloc[-1]) / rolling_std.iloc[-1] if rolling_std.iloc[-1] > 0 else 0.0
        else:
            features['zscore'] = 0.0
        
        # Momentum
        features['momentum_5s'] = (df['price'].iloc[-1] - df['price'].iloc[-6]) / df['price'].iloc[-6] if len(df) > 5 else 0.0
        features['momentum_1m'] = (df['price'].iloc[-1] - df['price'].iloc[-61]) / df['price'].iloc[-61] if len(df) > 60 else 0.0
        
        # Volume features
        features['volume'] = df['volume'].iloc[-1]
        features['volume_avg'] = df['volume'].rolling(min(20, len(df))).mean().iloc[-1] if len(df) > 0 else 0.0
        features['volume_ratio'] = features['volume'] / features['volume_avg'] if features['volume_avg'] > 0 else 1.0
        
        # Price levels
        features['high_1m'] = df['price'].rolling(min(60, len(df))).max().iloc[-1]
        features['low_1m'] = df['price'].rolling(min(60, len(df))).min().iloc[-1]
        
        # Range features
        features['range_1m'] = (features['high_1m'] - features['low_1m']) / features['price'] if features['price'] > 0 else 0.0
        
        # Time features
        features['time_of_day'] = df['timestamp'].iloc[-1].hour + df['timestamp'].iloc[-1].minute / 60.0
        features['is_market_open'] = 1.0 if 9.5 <= features['time_of_day'] <= 16.0 else 0.0
        
        return features
    
    def get_rolling_features(self, symbol: str, window: int = 20) -> Optional[pd.DataFrame]:
        """Get rolling features for symbol."""
        if symbol not in self.data_cache or len(self.data_cache[symbol]) < window:
            return None
        
        df = self.data_cache[symbol].copy()
        df = df.sort_values('timestamp').tail(window * 2)  # Get more data for rolling calculations
        
        if 'close' in df.columns:
            # Bar data
            returns = df['close'].pct_change().dropna()
        else:
            # Tick data
            returns = df['price'].pct_change().dropna()
        
        if len(returns) < window:
            return None
        
        rolling_features = pd.DataFrame({
            'timestamp': df['timestamp'].iloc[-window:],
            'mean': returns.rolling(window).mean().iloc[-window:],
            'std': returns.rolling(window).std().iloc[-window:],
            'min': returns.rolling(window).min().iloc[-window:],
            'max': returns.rolling(window).max().iloc[-window:],
            'skew': returns.rolling(window).skew().iloc[-window:],
            'kurt': returns.rolling(window).kurt().iloc[-window:]
        })
        
        return rolling_features
    
    def clear_old_data(self, cutoff_time: datetime) -> None:
        """Clear old data from cache."""
        for symbol in list(self.data_cache.keys()):
            df = self.data_cache[symbol]
            self.data_cache[symbol] = df[df['timestamp'] > cutoff_time]
            
            if len(self.data_cache[symbol]) == 0:
                del self.data_cache[symbol]
    
    def get_cache_status(self) -> Dict[str, int]:
        """Get cache status for all symbols."""
        return {
            symbol: len(df) 
            for symbol, df in self.data_cache.items()
        }

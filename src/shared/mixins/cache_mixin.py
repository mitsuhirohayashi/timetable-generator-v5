"""キャッシュ機能を提供するミックスイン

計算結果やデータのキャッシュ機能を提供します。
"""
import time
from typing import Any, Dict, Optional, Callable, Tuple
from functools import wraps
import hashlib
import json


class CacheMixin:
    """キャッシュ機能を提供するミックスイン
    
    使用例:
        class MyClass(CacheMixin):
            @cache_method(ttl=300)  # 5分間キャッシュ
            def expensive_calculation(self, x: int) -> int:
                return x ** 2
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def cache_get(self, key: str, default: Any = None) -> Any:
        """キャッシュから値を取得
        
        Args:
            key: キャッシュキー
            default: デフォルト値
            
        Returns:
            キャッシュされた値、またはデフォルト値
        """
        if key in self._cache:
            value, expiry = self._cache[key]
            if expiry is None or time.time() < expiry:
                self._cache_hits += 1
                return value
            else:
                # 期限切れ
                del self._cache[key]
        
        self._cache_misses += 1
        return default
    
    def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """キャッシュに値を設定
        
        Args:
            key: キャッシュキー
            value: 値
            ttl: 有効期限（秒）。Noneの場合は永続
        """
        expiry = None if ttl is None else time.time() + ttl
        self._cache[key] = (value, expiry)
    
    def cache_clear(self, pattern: Optional[str] = None) -> int:
        """キャッシュをクリア
        
        Args:
            pattern: クリアするキーのパターン（前方一致）
            
        Returns:
            クリアされたエントリ数
        """
        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            return count
        
        keys_to_remove = [
            key for key in self._cache.keys()
            if key.startswith(pattern)
        ]
        
        for key in keys_to_remove:
            del self._cache[key]
        
        return len(keys_to_remove)
    
    def cache_stats(self) -> Dict[str, int]:
        """キャッシュの統計情報を取得
        
        Returns:
            統計情報の辞書
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (
            self._cache_hits / total_requests 
            if total_requests > 0 else 0.0
        )
        
        return {
            'size': len(self._cache),
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'hit_rate': hit_rate
        }
    
    @staticmethod
    def make_cache_key(*args, **kwargs) -> str:
        """引数からキャッシュキーを生成
        
        Args:
            *args: 位置引数
            **kwargs: キーワード引数
            
        Returns:
            キャッシュキー
        """
        # 引数を文字列化してハッシュ
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return key_hash


def cache_method(ttl: Optional[int] = None):
    """メソッドの結果をキャッシュするデコレータ
    
    Args:
        ttl: キャッシュの有効期限（秒）
        
    使用例:
        @cache_method(ttl=60)
        def calculate(self, x: int) -> int:
            return x ** 2
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: CacheMixin, *args, **kwargs) -> Any:
            # キャッシュキーを生成
            cache_key = f"{func.__name__}:{CacheMixin.make_cache_key(*args, **kwargs)}"
            
            # キャッシュから取得を試みる
            cached_value = self.cache_get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 実際の計算を実行
            result = func(self, *args, **kwargs)
            
            # キャッシュに保存
            self.cache_set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator


class LRUCacheMixin(CacheMixin):
    """LRU（Least Recently Used）キャッシュを提供するミックスイン
    
    最大サイズを超えた場合、最も使用されていないエントリを削除します。
    """
    
    def __init__(self, max_size: int = 100, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_size = max_size
        self._access_order: Dict[str, float] = {}
    
    def cache_get(self, key: str, default: Any = None) -> Any:
        """キャッシュから値を取得（アクセス順を記録）"""
        value = super().cache_get(key, default)
        if value is not default:
            self._access_order[key] = time.time()
        return value
    
    def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """キャッシュに値を設定（サイズ制限を適用）"""
        # 既存のキーの場合はアクセス順を更新
        self._access_order[key] = time.time()
        
        # サイズ制限をチェック
        if len(self._cache) >= self._max_size and key not in self._cache:
            # 最も古いアクセスのキーを削除
            oldest_key = min(self._access_order, key=self._access_order.get)
            del self._cache[oldest_key]
            del self._access_order[oldest_key]
        
        super().cache_set(key, value, ttl)
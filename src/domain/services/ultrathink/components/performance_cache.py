"""
高性能キャッシュシステム

時間割生成の中間結果や計算結果を効率的にキャッシュ。
LRU、TTL、優先度ベースの削除戦略を実装。
"""
import logging
import time
import hashlib
import json
import pickle
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from threading import Lock
import gc
import sys
from functools import lru_cache
import numpy as np

from ....entities.schedule import Schedule
from ....entities.school import School, Teacher, Subject
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


@dataclass
class CacheEntry:
    """キャッシュエントリ"""
    key: str
    value: Any
    size: int
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: Optional[float] = None
    priority: int = 0
    
    def is_expired(self) -> bool:
        """有効期限切れか確認"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def access(self):
        """アクセスを記録"""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheStats:
    """キャッシュ統計"""
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_size = 0
        self.entry_count = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class PerformanceCache(LoggingMixin):
    """高性能キャッシュシステム"""
    
    def __init__(
        self,
        max_size_mb: int = 100,
        max_entries: int = 10000,
        default_ttl: Optional[float] = 3600,
        enable_compression: bool = False
    ):
        super().__init__()
        self.max_size = max_size_mb * 1024 * 1024  # バイト単位
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        self.enable_compression = enable_compression
        
        # キャッシュストレージ
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = Lock()
        
        # 統計情報
        self.stats = CacheStats()
        
        # 特殊用途のキャッシュ
        self.schedule_cache: Dict[str, Schedule] = {}
        self.constraint_cache: Dict[str, bool] = {}
        self.evaluation_cache: Dict[str, Tuple[float, int, int]] = {}
        
        # LRUキャッシュデコレータ用
        self._lru_functions = {}
    
    def get(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        """
        キャッシュから値を取得
        
        Args:
            key: キャッシュキー
            default: デフォルト値
            
        Returns:
            キャッシュされた値またはデフォルト値
        """
        with self.lock:
            entry = self.cache.get(key)
            
            if entry is None:
                self.stats.misses += 1
                return default
            
            # 有効期限チェック
            if entry.is_expired():
                self._evict_entry(key)
                self.stats.misses += 1
                return default
            
            # アクセス記録
            entry.access()
            
            # LRU更新（最後に移動）
            self.cache.move_to_end(key)
            
            self.stats.hits += 1
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        priority: int = 0
    ) -> bool:
        """
        キャッシュに値を設定
        
        Args:
            key: キャッシュキー
            value: 保存する値
            ttl: 有効期限（秒）
            priority: 優先度（高いほど削除されにくい）
            
        Returns:
            保存成功かどうか
        """
        # サイズ計算
        size = self._calculate_size(value)
        
        # サイズチェック
        if size > self.max_size:
            self.logger.warning(f"値が大きすぎます: {size} bytes")
            return False
        
        with self.lock:
            # 既存エントリの削除
            if key in self.cache:
                self._evict_entry(key)
            
            # 容量確保
            self._ensure_capacity(size)
            
            # エントリ作成
            entry = CacheEntry(
                key=key,
                value=value,
                size=size,
                created_at=time.time(),
                last_accessed=time.time(),
                ttl=ttl or self.default_ttl,
                priority=priority
            )
            
            # 保存
            self.cache[key] = entry
            self.stats.total_size += size
            self.stats.entry_count += 1
            
            return True
    
    def delete(self, key: str) -> bool:
        """キャッシュから削除"""
        with self.lock:
            if key in self.cache:
                self._evict_entry(key)
                return True
            return False
    
    def clear(self):
        """キャッシュをクリア"""
        with self.lock:
            self.cache.clear()
            self.schedule_cache.clear()
            self.constraint_cache.clear()
            self.evaluation_cache.clear()
            self.stats = CacheStats()
            gc.collect()
    
    def cache_schedule(
        self,
        schedule: Schedule,
        context: Dict[str, Any]
    ) -> str:
        """
        スケジュールをキャッシュ（特殊メソッド）
        
        Returns:
            キャッシュキー
        """
        # コンテキストからキーを生成
        key = self._generate_schedule_key(schedule, context)
        
        # スケジュールをシリアライズしてキャッシュ
        serialized = self._serialize_schedule(schedule)
        self.set(key, serialized, priority=5)
        
        # 高速アクセス用の別キャッシュにも保存
        self.schedule_cache[key] = schedule
        
        return key
    
    def get_cached_schedule(
        self,
        key: str
    ) -> Optional[Schedule]:
        """
        キャッシュされたスケジュールを取得（特殊メソッド）
        """
        # 高速キャッシュから取得
        if key in self.schedule_cache:
            return self.schedule_cache[key]
        
        # 通常キャッシュから取得
        serialized = self.get(key)
        if serialized:
            schedule = self._deserialize_schedule(serialized)
            self.schedule_cache[key] = schedule
            return schedule
        
        return None
    
    def cache_constraint_result(
        self,
        time_slot: TimeSlot,
        assignment: Assignment,
        is_valid: bool
    ):
        """制約チェック結果をキャッシュ（特殊メソッド）"""
        key = self._generate_constraint_key(time_slot, assignment)
        self.constraint_cache[key] = is_valid
        self.set(key, is_valid, ttl=300, priority=3)
    
    def get_constraint_result(
        self,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> Optional[bool]:
        """制約チェック結果を取得（特殊メソッド）"""
        key = self._generate_constraint_key(time_slot, assignment)
        
        # 高速キャッシュから取得
        if key in self.constraint_cache:
            return self.constraint_cache[key]
        
        # 通常キャッシュから取得
        return self.get(key)
    
    def memoize(
        self,
        ttl: Optional[float] = None,
        key_func: Optional[Callable] = None
    ):
        """
        関数結果をキャッシュするデコレータ
        
        使用例:
            @cache.memoize(ttl=3600)
            def expensive_function(x, y):
                return x ** y
        """
        def decorator(func):
            # LRUキャッシュを作成
            if func not in self._lru_functions:
                self._lru_functions[func] = lru_cache(maxsize=128)(func)
            
            def wrapper(*args, **kwargs):
                # キー生成
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    cache_key = self._generate_function_key(func, args, kwargs)
                
                # キャッシュチェック
                result = self.get(cache_key)
                if result is not None:
                    return result
                
                # 関数実行
                result = func(*args, **kwargs)
                
                # 結果をキャッシュ
                self.set(cache_key, result, ttl=ttl or self.default_ttl)
                
                return result
            
            return wrapper
        return decorator
    
    def _calculate_size(self, value: Any) -> int:
        """オブジェクトのサイズを計算"""
        try:
            # pickleでシリアライズしてサイズを測定
            serialized = pickle.dumps(value)
            return len(serialized)
        except:
            # フォールバック：sys.getsizeofを使用
            return sys.getsizeof(value)
    
    def _ensure_capacity(self, required_size: int):
        """必要な容量を確保"""
        # エントリ数制限チェック
        while len(self.cache) >= self.max_entries:
            self._evict_lru()
        
        # サイズ制限チェック
        while self.stats.total_size + required_size > self.max_size:
            if not self._evict_lru():
                break
    
    def _evict_lru(self) -> bool:
        """LRU戦略でエントリを削除"""
        if not self.cache:
            return False
        
        # 優先度が最も低く、最も古いエントリを探す
        victim_key = None
        min_score = float('inf')
        
        for key, entry in self.cache.items():
            # スコア = 優先度 * 1000 + 最終アクセス時間
            score = entry.priority * 1000 + entry.last_accessed
            if score < min_score:
                min_score = score
                victim_key = key
        
        if victim_key:
            self._evict_entry(victim_key)
            return True
        
        return False
    
    def _evict_entry(self, key: str):
        """エントリを削除"""
        if key in self.cache:
            entry = self.cache[key]
            del self.cache[key]
            
            self.stats.total_size -= entry.size
            self.stats.entry_count -= 1
            self.stats.evictions += 1
            
            # 特殊キャッシュからも削除
            if key in self.schedule_cache:
                del self.schedule_cache[key]
            if key in self.constraint_cache:
                del self.constraint_cache[key]
            if key in self.evaluation_cache:
                del self.evaluation_cache[key]
    
    def _generate_schedule_key(
        self,
        schedule: Schedule,
        context: Dict[str, Any]
    ) -> str:
        """スケジュールのキーを生成"""
        # スケジュールの特徴を抽出
        features = {
            'assignment_count': len(list(schedule.get_all_assignments())),
            'context': context
        }
        
        # ハッシュ化
        feature_str = json.dumps(features, sort_keys=True)
        return f"schedule_{hashlib.md5(feature_str.encode()).hexdigest()}"
    
    def _generate_constraint_key(
        self,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> str:
        """制約チェックのキーを生成"""
        key_parts = [
            f"{time_slot.day}_{time_slot.period}",
            f"{assignment.class_ref.grade}_{assignment.class_ref.class_number}",
            assignment.subject.name
        ]
        
        if assignment.teacher:
            key_parts.append(assignment.teacher.name)
        
        return f"constraint_{'_'.join(key_parts)}"
    
    def _generate_function_key(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict
    ) -> str:
        """関数呼び出しのキーを生成"""
        key_parts = [
            func.__module__,
            func.__name__,
            str(args),
            str(sorted(kwargs.items()))
        ]
        
        key_str = '_'.join(key_parts)
        return f"func_{hashlib.md5(key_str.encode()).hexdigest()}"
    
    def _serialize_schedule(self, schedule: Schedule) -> bytes:
        """スケジュールをシリアライズ"""
        # 簡易実装：割り当てをタプルのリストに変換
        assignments = []
        for time_slot, assignment in schedule.get_all_assignments():
            assignments.append((
                (time_slot.day, time_slot.period),
                (assignment.class_ref.grade, assignment.class_ref.class_number),
                assignment.subject.name,
                assignment.teacher.name if assignment.teacher else None
            ))
        
        return pickle.dumps(assignments)
    
    def _deserialize_schedule(self, data: bytes) -> Schedule:
        """スケジュールをデシリアライズ"""
        assignments = pickle.loads(data)
        schedule = Schedule()
        
        for (day, period), (grade, class_num), subject_name, teacher_name in assignments:
            time_slot = TimeSlot(day, period)
            class_ref = ClassReference(grade, class_num)
            subject = Subject(subject_name)
            teacher = Teacher(teacher_name) if teacher_name else None
            
            assignment = Assignment(class_ref, subject, teacher)
            schedule.assign(time_slot, assignment)
        
        return schedule
    
    def get_hit_rate(self) -> float:
        """キャッシュヒット率を取得"""
        return self.stats.hit_rate
    
    def get_statistics(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        with self.lock:
            return {
                'hit_rate': self.stats.hit_rate,
                'hits': self.stats.hits,
                'misses': self.stats.misses,
                'evictions': self.stats.evictions,
                'entry_count': self.stats.entry_count,
                'total_size_mb': self.stats.total_size / (1024 * 1024),
                'size_percentage': self.stats.total_size / self.max_size * 100,
                'special_caches': {
                    'schedules': len(self.schedule_cache),
                    'constraints': len(self.constraint_cache),
                    'evaluations': len(self.evaluation_cache)
                }
            }
    
    def optimize(self):
        """キャッシュを最適化"""
        with self.lock:
            # 期限切れエントリを削除
            expired_keys = [
                key for key, entry in self.cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                self._evict_entry(key)
            
            # ガベージコレクション
            gc.collect()
            
            self.logger.info(
                f"キャッシュ最適化完了: "
                f"{len(expired_keys)}個の期限切れエントリを削除"
            )
"""
メモリプールとオブジェクトプール

頻繁に生成・破棄されるオブジェクトのメモリ管理を最適化。
ガベージコレクションの負荷を軽減し、メモリ局所性を向上。
"""
import logging
from typing import Dict, List, Type, Optional, Any, TypeVar, Generic
from dataclasses import dataclass
from collections import deque
import gc
import sys
import weakref
from threading import Lock
import numpy as np

from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from ....entities.school import Teacher, Subject
from .....shared.mixins.logging_mixin import LoggingMixin


T = TypeVar('T')


class ObjectPool(Generic[T]):
    """汎用オブジェクトプール"""
    
    def __init__(
        self,
        factory: callable,
        max_size: int = 1000,
        pre_allocate: int = 0
    ):
        self.factory = factory
        self.max_size = max_size
        self.pool: deque[T] = deque(maxlen=max_size)
        self.lock = Lock()
        
        # 統計情報
        self.stats = {
            'allocations': 0,
            'deallocations': 0,
            'reuses': 0,
            'gc_collections': 0
        }
        
        # 事前割り当て
        if pre_allocate > 0:
            for _ in range(min(pre_allocate, max_size)):
                self.pool.append(self.factory())
    
    def acquire(self, *args, **kwargs) -> T:
        """オブジェクトを取得"""
        with self.lock:
            if self.pool:
                obj = self.pool.popleft()
                self.stats['reuses'] += 1
                
                # オブジェクトを初期化
                if hasattr(obj, 'reset'):
                    obj.reset(*args, **kwargs)
                elif hasattr(obj, '__init__'):
                    obj.__init__(*args, **kwargs)
                
                return obj
            else:
                self.stats['allocations'] += 1
                return self.factory(*args, **kwargs)
    
    def release(self, obj: T):
        """オブジェクトを返却"""
        with self.lock:
            if len(self.pool) < self.max_size:
                # オブジェクトをクリーンアップ
                if hasattr(obj, 'cleanup'):
                    obj.cleanup()
                
                self.pool.append(obj)
                self.stats['deallocations'] += 1
            else:
                # プールが満杯の場合はGCに任せる
                del obj
    
    def clear(self):
        """プールをクリア"""
        with self.lock:
            self.pool.clear()
            gc.collect()
            self.stats['gc_collections'] += 1
    
    def get_stats(self) -> Dict[str, int]:
        """統計情報を取得"""
        return {
            'pool_size': len(self.pool),
            'allocations': self.stats['allocations'],
            'deallocations': self.stats['deallocations'],
            'reuses': self.stats['reuses'],
            'reuse_rate': (
                self.stats['reuses'] / 
                (self.stats['reuses'] + self.stats['allocations'])
                if self.stats['reuses'] + self.stats['allocations'] > 0 else 0
            )
        }


@dataclass
class PoolableTimeSlot:
    """プール可能なTimeSlot"""
    day: str = ""
    period: int = 0
    
    def reset(self, day: str, period: int):
        """再初期化"""
        self.day = day
        self.period = period
    
    def cleanup(self):
        """クリーンアップ"""
        self.day = ""
        self.period = 0
    
    def to_time_slot(self) -> TimeSlot:
        """通常のTimeSlotに変換"""
        return TimeSlot(self.day, self.period)


@dataclass
class PoolableAssignment:
    """プール可能なAssignment"""
    class_ref: Optional[ClassReference] = None
    subject: Optional[Subject] = None
    teacher: Optional[Teacher] = None
    
    def reset(
        self,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Optional[Teacher] = None
    ):
        """再初期化"""
        self.class_ref = class_ref
        self.subject = subject
        self.teacher = teacher
    
    def cleanup(self):
        """クリーンアップ"""
        self.class_ref = None
        self.subject = None
        self.teacher = None
    
    def to_assignment(self) -> Assignment:
        """通常のAssignmentに変換"""
        return Assignment(self.class_ref, self.subject, self.teacher)


class MemoryPool(LoggingMixin):
    """統合メモリプール"""
    
    def __init__(self):
        super().__init__()
        
        # 各型のプール
        self.pools = {
            'time_slot': ObjectPool(PoolableTimeSlot, max_size=5000, pre_allocate=1000),
            'assignment': ObjectPool(PoolableAssignment, max_size=5000, pre_allocate=1000),
            'tuple': ObjectPool(tuple, max_size=10000),
            'list': ObjectPool(list, max_size=5000),
            'dict': ObjectPool(dict, max_size=2000),
            'set': ObjectPool(set, max_size=2000)
        }
        
        # NumPy配列プール
        self.array_pools = {
            (100,): ObjectPool(lambda: np.zeros(100), max_size=100),
            (1000,): ObjectPool(lambda: np.zeros(1000), max_size=50),
            (10000,): ObjectPool(lambda: np.zeros(10000), max_size=10)
        }
        
        # 大きなオブジェクトのキャッシュ
        self.large_object_cache = weakref.WeakValueDictionary()
        
        # グローバル統計
        self.global_stats = {
            'total_memory_saved': 0,
            'gc_collections_prevented': 0
        }
    
    def acquire_time_slot(self, day: str, period: int) -> PoolableTimeSlot:
        """TimeSlotを取得"""
        return self.pools['time_slot'].acquire(day, period)
    
    def release_time_slot(self, time_slot: PoolableTimeSlot):
        """TimeSlotを返却"""
        self.pools['time_slot'].release(time_slot)
    
    def acquire_assignment(
        self,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Optional[Teacher] = None
    ) -> PoolableAssignment:
        """Assignmentを取得"""
        return self.pools['assignment'].acquire(class_ref, subject, teacher)
    
    def release_assignment(self, assignment: PoolableAssignment):
        """Assignmentを返却"""
        self.pools['assignment'].release(assignment)
    
    def acquire_array(self, shape: tuple) -> np.ndarray:
        """NumPy配列を取得"""
        if shape in self.array_pools:
            array = self.array_pools[shape].acquire()
            array.fill(0)  # ゼロクリア
            return array
        else:
            # プールにないサイズは通常作成
            return np.zeros(shape)
    
    def release_array(self, array: np.ndarray):
        """NumPy配列を返却"""
        shape = array.shape
        if shape in self.array_pools:
            self.array_pools[shape].release(array)
    
    def acquire_container(self, container_type: str, size_hint: int = 0):
        """汎用コンテナを取得"""
        if container_type in self.pools:
            container = self.pools[container_type].acquire()
            
            # サイズヒントに基づいて事前確保
            if size_hint > 0:
                if container_type == 'list' and hasattr(container, 'reserve'):
                    container.reserve(size_hint)
                elif container_type == 'dict' and hasattr(container, 'resize'):
                    container.resize(size_hint)
            
            return container
        else:
            raise ValueError(f"Unknown container type: {container_type}")
    
    def release_container(self, container: Any, container_type: str):
        """汎用コンテナを返却"""
        if container_type in self.pools:
            # コンテナをクリア
            container.clear()
            self.pools[container_type].release(container)
    
    def cache_large_object(self, key: str, obj: Any):
        """大きなオブジェクトをキャッシュ"""
        self.large_object_cache[key] = obj
        self.global_stats['total_memory_saved'] += sys.getsizeof(obj)
    
    def get_cached_object(self, key: str) -> Optional[Any]:
        """キャッシュされたオブジェクトを取得"""
        return self.large_object_cache.get(key)
    
    def optimize_memory(self):
        """メモリを最適化"""
        # 未使用オブジェクトをクリア
        for pool in self.pools.values():
            if len(pool.pool) > pool.max_size * 0.8:
                pool.clear()
        
        # 手動GC実行を防ぐ
        gc.collect(0)  # 第0世代のみ
        self.global_stats['gc_collections_prevented'] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = {
            'pools': {},
            'array_pools': {},
            'global': self.global_stats
        }
        
        # 各プールの統計
        for name, pool in self.pools.items():
            stats['pools'][name] = pool.get_stats()
        
        # 配列プールの統計
        for shape, pool in self.array_pools.items():
            stats['array_pools'][str(shape)] = pool.get_stats()
        
        # メモリ使用量
        stats['memory_usage'] = {
            'rss': self._get_memory_usage(),
            'gc_stats': gc.get_stats()
        }
        
        return stats
    
    def _get_memory_usage(self) -> int:
        """現在のメモリ使用量を取得（バイト）"""
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except:
            return 0


# グローバルメモリプール（シングルトン）
_global_memory_pool = None
_pool_lock = Lock()


def get_memory_pool() -> MemoryPool:
    """グローバルメモリプールを取得"""
    global _global_memory_pool
    
    if _global_memory_pool is None:
        with _pool_lock:
            if _global_memory_pool is None:
                _global_memory_pool = MemoryPool()
    
    return _global_memory_pool


class PoolContext:
    """メモリプールコンテキストマネージャー"""
    
    def __init__(self, pool: MemoryPool = None):
        self.pool = pool or get_memory_pool()
        self.acquired_objects = []
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 取得したオブジェクトを全て返却
        for obj, obj_type in self.acquired_objects:
            if obj_type == 'time_slot':
                self.pool.release_time_slot(obj)
            elif obj_type == 'assignment':
                self.pool.release_assignment(obj)
            elif obj_type.startswith('container:'):
                container_type = obj_type.split(':')[1]
                self.pool.release_container(obj, container_type)
        
        self.acquired_objects.clear()
    
    def acquire_time_slot(self, day: str, period: int) -> PoolableTimeSlot:
        """TimeSlotを取得（自動返却）"""
        obj = self.pool.acquire_time_slot(day, period)
        self.acquired_objects.append((obj, 'time_slot'))
        return obj
    
    def acquire_assignment(
        self,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Optional[Teacher] = None
    ) -> PoolableAssignment:
        """Assignmentを取得（自動返却）"""
        obj = self.pool.acquire_assignment(class_ref, subject, teacher)
        self.acquired_objects.append((obj, 'assignment'))
        return obj
"""
CPU最適化モジュール

SIMD命令、ベクトル化、CPUキャッシュ最適化などの
低レベル最適化を提供します。
"""
import logging
import numpy as np
from typing import List, Tuple, Dict, Any, Optional, Set
from dataclasses import dataclass
import numba
from numba import njit, prange, vectorize, guvectorize, cuda
import warnings
from functools import lru_cache
import multiprocessing
import psutil
from .....shared.mixins.logging_mixin import LoggingMixin

# CPUのベクトル化サポートを確認
try:
    from numpy import __cpu_features__
    HAS_AVX2 = __cpu_features__.get('AVX2', False)
    HAS_SSE4 = __cpu_features__.get('SSE41', False)
except:
    HAS_AVX2 = False
    HAS_SSE4 = False


@dataclass
class CPUInfo:
    """CPU情報"""
    cores: int
    threads: int
    cache_sizes: Dict[str, int]  # L1, L2, L3キャッシュサイズ
    vector_extensions: List[str]  # AVX2, SSE4など
    frequency_mhz: int


class CPUOptimizer(LoggingMixin):
    """CPU最適化マネージャー"""
    
    def __init__(self):
        super().__init__()
        self.cpu_info = self._detect_cpu_features()
        
        # 最適なブロックサイズを決定（キャッシュに基づく）
        self.optimal_block_size = self._calculate_optimal_block_size()
        
        # SIMD幅（ベクトル化のため）
        self.simd_width = 8 if HAS_AVX2 else 4 if HAS_SSE4 else 1
        
        self.logger.info(f"CPU最適化初期化: {self.cpu_info.cores}コア, "
                        f"ベクトル幅={self.simd_width}, "
                        f"ブロックサイズ={self.optimal_block_size}")
    
    def _detect_cpu_features(self) -> CPUInfo:
        """CPU機能を検出"""
        # CPU情報
        cpu_count = psutil.cpu_count(logical=False)
        thread_count = psutil.cpu_count(logical=True)
        
        # キャッシュサイズ（推定値）
        cache_sizes = {
            'L1': 32 * 1024,      # 32KB per core
            'L2': 256 * 1024,     # 256KB per core
            'L3': 8 * 1024 * 1024 # 8MB shared
        }
        
        # ベクトル拡張
        vector_extensions = []
        if HAS_AVX2:
            vector_extensions.append('AVX2')
        if HAS_SSE4:
            vector_extensions.append('SSE4')
        
        # CPU周波数
        try:
            freq = psutil.cpu_freq()
            frequency_mhz = int(freq.current) if freq else 2000
        except:
            frequency_mhz = 2000
        
        return CPUInfo(
            cores=cpu_count,
            threads=thread_count,
            cache_sizes=cache_sizes,
            vector_extensions=vector_extensions,
            frequency_mhz=frequency_mhz
        )
    
    def _calculate_optimal_block_size(self) -> int:
        """キャッシュに最適なブロックサイズを計算"""
        # L1キャッシュの1/4を使用（他のデータ用に余裕を残す）
        l1_size = self.cpu_info.cache_sizes['L1']
        element_size = 8  # 64ビット要素
        
        # 正方行列のブロックサイズ
        block_elements = l1_size // (4 * element_size)
        block_size = int(np.sqrt(block_elements))
        
        # 2の累乗に丸める（アライメントのため）
        block_size = 2 ** int(np.log2(block_size))
        
        return max(16, min(block_size, 128))
    
    @staticmethod
    @njit(parallel=True, fastmath=True, cache=True)
    def vectorized_constraint_check(
        assignments: np.ndarray,
        teacher_indices: np.ndarray,
        time_slot: int,
        num_classes: int
    ) -> np.ndarray:
        """
        ベクトル化された制約チェック
        
        複数の教師の重複を一度にチェック
        """
        results = np.zeros(len(teacher_indices), dtype=np.bool_)
        
        for i in prange(len(teacher_indices)):
            teacher_idx = teacher_indices[i]
            has_conflict = False
            
            # ベクトル化されたループ
            for class_idx in range(num_classes):
                if assignments[time_slot, class_idx, 2] == teacher_idx:
                    has_conflict = True
                    break
            
            results[i] = has_conflict
        
        return results
    
    @staticmethod
    @njit(parallel=True, fastmath=True)
    def blocked_matrix_operation(
        matrix: np.ndarray,
        block_size: int
    ) -> np.ndarray:
        """
        ブロック化された行列操作
        
        キャッシュ効率を最大化するブロック処理
        """
        n, m = matrix.shape
        result = np.zeros_like(matrix)
        
        # ブロック単位で処理
        for i in prange(0, n, block_size):
            for j in range(0, m, block_size):
                # ブロック境界
                i_end = min(i + block_size, n)
                j_end = min(j + block_size, m)
                
                # ブロック内の処理（キャッシュに収まる）
                for ii in range(i, i_end):
                    for jj in range(j, j_end):
                        result[ii, jj] = matrix[ii, jj] * 2  # 例: 2倍
        
        return result
    
    @staticmethod
    @vectorize(['float64(float64, float64)'], target='parallel')
    def vectorized_score_calculation(constraint_weight: float, violation_count: float) -> float:
        """ベクトル化されたスコア計算"""
        return constraint_weight * (1.0 - violation_count / 100.0)
    
    @staticmethod
    @guvectorize(
        ['void(int32[:,:], int32[:], int32[:], boolean[:])'],
        '(n,m),(k),(k)->(k)',
        target='parallel'
    )
    def batch_conflict_detection(
        schedule_slice: np.ndarray,
        class_indices: np.ndarray,
        subject_indices: np.ndarray,
        conflicts: np.ndarray
    ):
        """
        バッチ競合検出（一般化ユニバーサル関数）
        
        複数のクラス・科目の組み合わせを同時にチェック
        """
        n_slots, n_subjects = schedule_slice.shape
        
        for i in range(len(class_indices)):
            class_idx = class_indices[i]
            subject_idx = subject_indices[i]
            
            # その日の同じ科目をカウント
            count = 0
            for slot in range(n_slots):
                if schedule_slice[slot, class_idx] == subject_idx:
                    count += 1
            
            conflicts[i] = count > 1
    
    def optimize_data_layout(
        self,
        assignments: Dict[Tuple[str, int], Dict[Tuple[int, int], Any]]
    ) -> np.ndarray:
        """
        データレイアウトの最適化
        
        辞書形式を連続メモリ配列に変換（キャッシュ効率向上）
        """
        # 次元を決定
        days = ["月", "火", "水", "木", "金"]
        periods = 6
        max_grade = 3
        max_class = 7
        
        # 連続メモリに配置（行優先）
        # [time_slots, classes, attributes(class, subject, teacher)]
        array = np.full(
            (len(days) * periods, max_grade * max_class, 3),
            -1,
            dtype=np.int32
        )
        
        # データを変換
        for day_idx, day in enumerate(days):
            for period in range(1, periods + 1):
                time_slot_idx = day_idx * periods + (period - 1)
                
                if (day, period) in assignments:
                    for (grade, class_num), assignment in assignments[(day, period)].items():
                        class_idx = (grade - 1) * max_class + (class_num - 1)
                        
                        if class_idx < array.shape[1]:
                            array[time_slot_idx, class_idx, 0] = class_idx
                            # subject_idxとteacher_idxは別途マッピングが必要
        
        return array
    
    def prefetch_data(self, data_indices: List[int], data_array: np.ndarray):
        """
        データのプリフェッチ
        
        次に必要なデータをCPUキャッシュにロード
        """
        # NumPyの高度なインデックスを使用してプリフェッチ
        if data_indices:
            # データに触れることでキャッシュにロード
            _ = data_array[data_indices]
    
    @lru_cache(maxsize=1024)
    def cached_constraint_evaluation(
        self,
        constraint_hash: int,
        *args
    ) -> bool:
        """
        制約評価のキャッシング
        
        頻繁に評価される制約をメモリに保持
        """
        # 実際の評価ロジックはconstraint_hashに基づいて実行
        return True  # プレースホルダー
    
    def parallel_domain_reduction(
        self,
        domains: np.ndarray,
        num_workers: Optional[int] = None
    ) -> np.ndarray:
        """
        並列ドメイン削減
        
        独立した変数のドメインを並列に削減
        """
        if num_workers is None:
            num_workers = self.cpu_info.cores
        
        # ワーカーごとにチャンクを分割
        chunk_size = len(domains) // num_workers
        
        # 並列処理用の関数
        @njit(parallel=True)
        def reduce_domains_parallel(domains_chunk):
            reduced = np.copy(domains_chunk)
            # ドメイン削減ロジック
            for i in prange(len(reduced)):
                # 例: 無効な値を削除
                reduced[i] = reduced[i][reduced[i] >= 0]
            return reduced
        
        # 実行
        return reduce_domains_parallel(domains)
    
    def optimize_memory_access_pattern(
        self,
        schedule: np.ndarray,
        access_pattern: str = "row_major"
    ) -> np.ndarray:
        """
        メモリアクセスパターンの最適化
        
        Args:
            schedule: スケジュール配列
            access_pattern: "row_major" or "column_major"
        """
        if access_pattern == "column_major" and schedule.flags['C_CONTIGUOUS']:
            # 列優先アクセスの場合は転置
            return np.asfortranarray(schedule.T)
        elif access_pattern == "row_major" and schedule.flags['F_CONTIGUOUS']:
            # 行優先アクセスの場合
            return np.ascontiguousarray(schedule)
        
        return schedule
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """最適化統計を取得"""
        return {
            'cpu_cores': self.cpu_info.cores,
            'cpu_threads': self.cpu_info.threads,
            'vector_extensions': self.cpu_info.vector_extensions,
            'simd_width': self.simd_width,
            'optimal_block_size': self.optimal_block_size,
            'cache_sizes': self.cpu_info.cache_sizes,
            'optimizations_enabled': {
                'vectorization': self.simd_width > 1,
                'parallelization': self.cpu_info.cores > 1,
                'cache_blocking': True,
                'prefetching': True
            }
        }


# グローバルCPU最適化インスタンス
_cpu_optimizer = None


def get_cpu_optimizer() -> CPUOptimizer:
    """グローバルCPU最適化インスタンスを取得"""
    global _cpu_optimizer
    if _cpu_optimizer is None:
        _cpu_optimizer = CPUOptimizer()
    return _cpu_optimizer


# 便利な関数
def optimize_for_cpu(func):
    """CPU最適化デコレータ"""
    optimizer = get_cpu_optimizer()
    
    def wrapper(*args, **kwargs):
        # 関数実行前の最適化
        # 例: データレイアウトの変換など
        result = func(*args, **kwargs)
        return result
    
    return wrapper
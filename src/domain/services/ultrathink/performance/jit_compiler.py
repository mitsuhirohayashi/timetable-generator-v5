"""
JITコンパイル最適化

Numbaを使用して計算集約的な処理を高速化。
型推論と最適化により、Pythonコードを機械語レベルで実行。
"""
import logging
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from functools import lru_cache
from .....shared.mixins.logging_mixin import LoggingMixin

try:
    from numba import jit, njit, prange, typed, types
    from numba.core import types as nb_types
    from numba.typed import Dict as NumbaDict
    from numba.typed import List as NumbaList
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    logging.warning("Numba not available. JIT compilation disabled.")
    
    # ダミーデコレータ
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    njit = jit
    prange = range
    NumbaDict = dict
    NumbaList = list


# 型定義（Numba用）
if NUMBA_AVAILABLE:
    # 制約チェック用の型
    time_slot_type = types.UniTuple(types.int32, 2)  # (day_idx, period)
    assignment_type = types.UniTuple(types.int32, 3)  # (class_idx, subject_idx, teacher_idx)
    
    # 高速マッピング用の型
    str_to_int_dict = types.DictType(types.unicode_type, types.int32)
    int_to_str_dict = types.DictType(types.int32, types.unicode_type)


@njit(cache=True, fastmath=True)
def check_teacher_conflict_jit(
    assignments: np.ndarray,
    new_teacher_idx: int,
    time_slot_idx: int,
    num_classes: int
) -> bool:
    """
    教師重複をJITコンパイルでチェック
    
    Args:
        assignments: 割り当て配列 [time_slots, classes, 3]
        new_teacher_idx: 新しい教師のインデックス
        time_slot_idx: 時間スロットインデックス
        num_classes: クラス数
        
    Returns:
        True if 重複あり
    """
    if new_teacher_idx < 0:  # 教師なし
        return False
    
    for class_idx in prange(num_classes):
        if assignments[time_slot_idx, class_idx, 2] == new_teacher_idx:
            return True
    
    return False


@njit(cache=True, fastmath=True)
def check_daily_duplicate_jit(
    assignments: np.ndarray,
    new_subject_idx: int,
    day_idx: int,
    class_idx: int,
    periods_per_day: int
) -> bool:
    """
    日内重複をJITコンパイルでチェック
    
    Args:
        assignments: 割り当て配列
        new_subject_idx: 新しい科目のインデックス
        day_idx: 曜日インデックス
        class_idx: クラスインデックス
        periods_per_day: 1日の時限数
        
    Returns:
        True if 重複あり
    """
    start_slot = day_idx * periods_per_day
    end_slot = start_slot + periods_per_day
    
    for slot_idx in range(start_slot, end_slot):
        if assignments[slot_idx, class_idx, 1] == new_subject_idx:
            return True
    
    return False


@njit(cache=True, fastmath=True, parallel=True)
def calculate_domain_sizes_jit(
    domains: np.ndarray,
    assignments: np.ndarray,
    num_slots: int,
    num_classes: int,
    num_values: int
) -> np.ndarray:
    """
    全変数のドメインサイズを高速計算
    
    Args:
        domains: ドメイン配列 [slots, classes, values]
        assignments: 現在の割り当て
        num_slots: スロット数
        num_classes: クラス数
        num_values: 値の数
        
    Returns:
        ドメインサイズ配列 [slots, classes]
    """
    sizes = np.zeros((num_slots, num_classes), dtype=np.int32)
    
    for slot_idx in prange(num_slots):
        for class_idx in range(num_classes):
            if assignments[slot_idx, class_idx, 0] >= 0:  # 既に割り当て済み
                sizes[slot_idx, class_idx] = 0
            else:
                count = 0
                for value_idx in range(num_values):
                    if domains[slot_idx, class_idx, value_idx] > 0:
                        count += 1
                sizes[slot_idx, class_idx] = count
    
    return sizes


@njit(cache=True, fastmath=True)
def find_mrv_variable_jit(
    domain_sizes: np.ndarray,
    num_slots: int,
    num_classes: int
) -> Tuple[int, int]:
    """
    MRV（最小残余値）ヒューリスティックで変数選択
    
    Returns:
        (slot_idx, class_idx) or (-1, -1) if なし
    """
    min_size = 999999
    best_slot = -1
    best_class = -1
    
    for slot_idx in range(num_slots):
        for class_idx in range(num_classes):
            size = domain_sizes[slot_idx, class_idx]
            if 0 < size < min_size:
                min_size = size
                best_slot = slot_idx
                best_class = class_idx
    
    return best_slot, best_class


@njit(cache=True, fastmath=True, parallel=True)
def propagate_constraints_jit(
    domains: np.ndarray,
    assignment: np.ndarray,
    slot_idx: int,
    class_idx: int,
    num_slots: int,
    num_classes: int,
    periods_per_day: int
) -> int:
    """
    制約伝播をJITコンパイルで実行
    
    Returns:
        削除された値の数
    """
    removed_count = 0
    teacher_idx = assignment[2]
    subject_idx = assignment[1]
    day_idx = slot_idx // periods_per_day
    
    # 教師制約の伝播
    if teacher_idx >= 0:
        for other_class in prange(num_classes):
            if other_class != class_idx:
                # 同じ時間の他のクラスから教師を削除
                for value_idx in range(domains.shape[2]):
                    if domains[slot_idx, other_class, value_idx] > 0:
                        # value_idxから教師インデックスを取得する必要がある
                        # ここでは簡略化
                        if value_idx % 100 == teacher_idx:  # 仮の実装
                            domains[slot_idx, other_class, value_idx] = 0
                            removed_count += 1
    
    # 日内重複制約の伝播
    start_slot = day_idx * periods_per_day
    end_slot = start_slot + periods_per_day
    
    for other_slot in range(start_slot, end_slot):
        if other_slot != slot_idx:
            for value_idx in range(domains.shape[2]):
                if domains[other_slot, class_idx, value_idx] > 0:
                    # value_idxから科目インデックスを取得
                    if value_idx // 100 == subject_idx:  # 仮の実装
                        domains[other_slot, class_idx, value_idx] = 0
                        removed_count += 1
    
    return removed_count


class JITOptimizer(LoggingMixin):
    """JIT最適化マネージャー"""
    
    def __init__(self, school_data: Dict[str, Any]):
        super().__init__()
        self.enabled = NUMBA_AVAILABLE
        
        if not self.enabled:
            self.logger.warning("JIT optimization disabled (Numba not available)")
            return
        
        # インデックスマッピングの作成
        self._create_index_mappings(school_data)
        
        # 配列の事前割り当て
        self._preallocate_arrays(school_data)
        
        # JIT関数のウォームアップ
        self._warmup_jit_functions()
        
        self.stats = {
            'jit_calls': 0,
            'jit_time_saved': 0.0,
            'cache_hits': 0
        }
    
    def _create_index_mappings(self, school_data: Dict[str, Any]):
        """文字列とインデックスのマッピングを作成"""
        # 曜日マッピング
        self.day_to_idx = NumbaDict.empty(
            key_type=types.unicode_type,
            value_type=types.int32
        )
        self.idx_to_day = NumbaDict.empty(
            key_type=types.int32,
            value_type=types.unicode_type
        )
        
        days = ["月", "火", "水", "木", "金"]
        for i, day in enumerate(days):
            self.day_to_idx[day] = i
            self.idx_to_day[i] = day
        
        # クラスマッピング
        self.class_to_idx = {}
        self.idx_to_class = {}
        
        for i, class_ref in enumerate(school_data['classes']):
            key = f"{class_ref.grade}-{class_ref.class_number}"
            self.class_to_idx[key] = i
            self.idx_to_class[i] = class_ref
        
        # 教師マッピング
        self.teacher_to_idx = {"": -1}  # 教師なし
        self.idx_to_teacher = {-1: None}
        
        for i, teacher in enumerate(school_data['teachers']):
            self.teacher_to_idx[teacher.name] = i
            self.idx_to_teacher[i] = teacher
        
        # 科目マッピング
        self.subject_to_idx = {}
        self.idx_to_subject = {}
        
        for i, subject in enumerate(school_data['subjects']):
            self.subject_to_idx[subject.name] = i
            self.idx_to_subject[i] = subject
    
    def _preallocate_arrays(self, school_data: Dict[str, Any]):
        """配列を事前割り当て"""
        num_days = 5
        periods_per_day = 6
        num_slots = num_days * periods_per_day
        num_classes = len(school_data['classes'])
        num_teachers = len(school_data['teachers'])
        num_subjects = len(school_data['subjects'])
        
        # 割り当て配列: [slots, classes, 3(class, subject, teacher)]
        self.assignments = np.full(
            (num_slots, num_classes, 3),
            -1,
            dtype=np.int32
        )
        
        # ドメイン配列: [slots, classes, max_values]
        max_values = num_subjects * (num_teachers + 1)  # +1 for no teacher
        self.domains = np.ones(
            (num_slots, num_classes, max_values),
            dtype=np.int8
        )
        
        # ドメインサイズキャッシュ
        self.domain_sizes = np.zeros(
            (num_slots, num_classes),
            dtype=np.int32
        )
        
        self.num_slots = num_slots
        self.num_classes = num_classes
        self.num_teachers = num_teachers
        self.num_subjects = num_subjects
        self.periods_per_day = periods_per_day
    
    def _warmup_jit_functions(self):
        """JIT関数をウォームアップ（初回コンパイル）"""
        if not self.enabled:
            return
        
        self.logger.debug("Warming up JIT functions...")
        
        # ダミーデータで各関数を実行
        dummy_assignments = np.zeros((10, 5, 3), dtype=np.int32)
        dummy_domains = np.ones((10, 5, 20), dtype=np.int8)
        
        # 各JIT関数を実行してコンパイル
        check_teacher_conflict_jit(dummy_assignments, 0, 0, 5)
        check_daily_duplicate_jit(dummy_assignments, 0, 0, 0, 6)
        calculate_domain_sizes_jit(dummy_domains, dummy_assignments, 10, 5, 20)
        find_mrv_variable_jit(np.ones((10, 5), dtype=np.int32), 10, 5)
        propagate_constraints_jit(dummy_domains, np.array([0, 0, 0]), 0, 0, 10, 5, 6)
        
        self.logger.debug("JIT warmup completed")
    
    def convert_to_indices(
        self,
        time_slot: Tuple[str, int],
        class_ref: Tuple[int, int],
        subject_name: str,
        teacher_name: Optional[str]
    ) -> Tuple[int, int, int, int, int]:
        """値をインデックスに変換"""
        day_idx = self.day_to_idx[time_slot[0]]
        period = time_slot[1] - 1
        slot_idx = day_idx * self.periods_per_day + period
        
        class_key = f"{class_ref[0]}-{class_ref[1]}"
        class_idx = self.class_to_idx[class_key]
        
        subject_idx = self.subject_to_idx[subject_name]
        teacher_idx = self.teacher_to_idx.get(teacher_name or "", -1)
        
        return slot_idx, class_idx, subject_idx, teacher_idx, day_idx
    
    def check_constraints_fast(
        self,
        time_slot: Tuple[str, int],
        class_ref: Tuple[int, int],
        subject_name: str,
        teacher_name: Optional[str]
    ) -> bool:
        """
        高速制約チェック
        
        Returns:
            True if 制約違反なし
        """
        if not self.enabled:
            return True  # フォールバック
        
        # インデックスに変換
        slot_idx, class_idx, subject_idx, teacher_idx, day_idx = \
            self.convert_to_indices(time_slot, class_ref, subject_name, teacher_name)
        
        # 教師重複チェック
        if teacher_idx >= 0:
            if check_teacher_conflict_jit(
                self.assignments, teacher_idx, slot_idx, self.num_classes
            ):
                return False
        
        # 日内重複チェック
        if check_daily_duplicate_jit(
            self.assignments, subject_idx, day_idx, 
            class_idx, self.periods_per_day
        ):
            return False
        
        self.stats['jit_calls'] += 1
        return True
    
    def update_assignment(
        self,
        time_slot: Tuple[str, int],
        class_ref: Tuple[int, int],
        subject_name: str,
        teacher_name: Optional[str]
    ):
        """割り当てを更新"""
        if not self.enabled:
            return
        
        slot_idx, class_idx, subject_idx, teacher_idx, _ = \
            self.convert_to_indices(time_slot, class_ref, subject_name, teacher_name)
        
        self.assignments[slot_idx, class_idx] = [class_idx, subject_idx, teacher_idx]
    
    def calculate_all_domain_sizes(self) -> np.ndarray:
        """全ドメインサイズを計算"""
        if not self.enabled:
            return np.ones((self.num_slots, self.num_classes))
        
        return calculate_domain_sizes_jit(
            self.domains,
            self.assignments,
            self.num_slots,
            self.num_classes,
            self.domains.shape[2]
        )
    
    def select_mrv_variable(self) -> Optional[Tuple[Tuple[str, int], Tuple[int, int]]]:
        """MRVヒューリスティックで変数選択"""
        if not self.enabled:
            return None
        
        # ドメインサイズを更新
        self.domain_sizes = self.calculate_all_domain_sizes()
        
        # MRV変数を探す
        slot_idx, class_idx = find_mrv_variable_jit(
            self.domain_sizes,
            self.num_slots,
            self.num_classes
        )
        
        if slot_idx < 0:
            return None
        
        # インデックスを変換して返す
        day_idx = slot_idx // self.periods_per_day
        period = slot_idx % self.periods_per_day + 1
        day = self.idx_to_day[day_idx]
        
        class_ref = self.idx_to_class[class_idx]
        
        return (day, period), (class_ref.grade, class_ref.class_number)
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return {
            'enabled': self.enabled,
            'jit_calls': self.stats['jit_calls'],
            'cached_functions': len(self.__dict__),
            'array_memory_mb': (
                self.assignments.nbytes + 
                self.domains.nbytes + 
                self.domain_sizes.nbytes
            ) / (1024 * 1024) if self.enabled else 0
        }
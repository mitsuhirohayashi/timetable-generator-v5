"""スロットスコア計算器"""
import logging
from typing import Optional

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School
from .....domain.value_objects.time_slot import TimeSlot
from .....domain.value_objects.time_slot import ClassReference


class SlotScorer:
    """スロットのスコアを計算"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # 時限ごとの基本スコア
        self.period_scores = {
            1: 0.7,   # 1限は低め
            2: 0.9,   # 2-4限は高め
            3: 1.0,
            4: 0.9,
            5: 0.8,   # 5限はやや低め
            6: 0.6    # 6限は低め
        }
        
        # 曜日ごとの基本スコア
        self.day_scores = {
            "月": 0.8,  # 月曜は低め
            "火": 1.0,
            "水": 1.0,
            "木": 1.0,
            "金": 0.9   # 金曜はやや低め
        }
    
    def calculate_score(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        teacher: Optional[object],
        subject: Optional[object],
        schedule: Schedule
    ) -> float:
        """スロットのスコアを計算
        
        Args:
            time_slot: タイムスロット
            class_ref: クラス参照
            teacher: 教師（オプション）
            subject: 科目（オプション）
            schedule: スケジュール
            
        Returns:
            スコア（0.0-1.0）
        """
        score = 0.0
        
        # 基本スコア
        score += self.period_scores.get(time_slot.period, 0.5) * 0.3
        score += self.day_scores.get(time_slot.day, 0.5) * 0.2
        
        # 科目固有の評価
        if subject:
            score += self._evaluate_subject_timing(subject, time_slot) * 0.2
        
        # 教師の負荷バランス
        if teacher:
            score += self._evaluate_teacher_load(teacher, time_slot, schedule) * 0.15
        
        # 連続性の評価
        score += self._evaluate_continuity(
            time_slot, class_ref, teacher, schedule
        ) * 0.15
        
        return min(1.0, max(0.0, score))
    
    def _evaluate_subject_timing(self, subject, time_slot: TimeSlot) -> float:
        """科目のタイミングを評価"""
        subject_name = subject.name if hasattr(subject, 'name') else str(subject)
        
        # 主要科目は午前中が好ましい
        if subject_name in ["国", "数", "英"]:
            if time_slot.period <= 3:
                return 0.9
            else:
                return 0.5
        
        # 体育は2-4限が理想
        elif subject_name == "保":
            if 2 <= time_slot.period <= 4:
                return 1.0
            elif time_slot.period in [1, 6]:
                return 0.3
            else:
                return 0.6
        
        # 実技科目は午後でも良い
        elif subject_name in ["音", "美", "技", "家"]:
            if time_slot.period >= 3:
                return 0.8
            else:
                return 0.6
        
        # その他
        return 0.7
    
    def _evaluate_teacher_load(
        self,
        teacher,
        time_slot: TimeSlot,
        schedule: Schedule
    ) -> float:
        """教師の負荷バランスを評価"""
        # その日の教師の授業数をカウント
        daily_count = 0
        for period in range(1, 7):
            slot = TimeSlot(time_slot.day, period)
            for class_ref in schedule.get_all_classes():
                assignment = schedule.get_assignment(slot, class_ref)
                if assignment and assignment.teacher == teacher:
                    daily_count += 1
        
        # 適度な授業数が理想
        if daily_count <= 3:
            return 0.9
        elif daily_count <= 4:
            return 0.7
        elif daily_count <= 5:
            return 0.5
        else:
            return 0.3
    
    def _evaluate_continuity(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        teacher: Optional[object],
        schedule: Schedule
    ) -> float:
        """連続性を評価"""
        if not teacher:
            return 0.5
        
        score = 0.5
        
        # 前の時限をチェック
        if time_slot.period > 1:
            prev_slot = TimeSlot(time_slot.day, time_slot.period - 1)
            prev_assignment = schedule.get_assignment(prev_slot, class_ref)
            if prev_assignment and prev_assignment.teacher == teacher:
                score += 0.25  # 連続授業はやや好ましい
        
        # 次の時限をチェック
        if time_slot.period < 6:
            next_slot = TimeSlot(time_slot.day, time_slot.period + 1)
            next_assignment = schedule.get_assignment(next_slot, class_ref)
            if next_assignment and next_assignment.teacher == teacher:
                score += 0.25  # 連続授業はやや好ましい
        
        return score
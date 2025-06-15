"""固定科目保護ポリシー

固定科目（欠、YT、道、学、総、行など）の絶対的な保護を担保するポリシー。
CSPアルゴリズムの全ての段階で固定科目の変更を防ぐ。
"""
import logging
from typing import Set, Optional
from ..value_objects.time_slot import TimeSlot, ClassReference
from ..value_objects.assignment import Assignment
from ..entities.schedule import Schedule


class FixedSubjectProtectionPolicy:
    """固定科目保護ポリシー
    
    固定科目の絶対的な保護を担保し、いかなる操作でも
    固定科目が変更されないことを保証する。
    """
    
    # 固定科目のセット（絶対に変更不可）
    FIXED_SUBJECTS: Set[str] = {
        "欠", "YT", "道", "道徳", "学", "学活", 
        "学総", "総", "総合", "行", "行事",
        "test", "テスト", "定期テスト", "期末テスト", "中間テスト"  # テスト科目も保護
    }
    
    # 特に重要な固定時間枠（コメントアウト - 強制配置を無効化）
    # CRITICAL_FIXED_SLOTS = {
    #     ("月", 6): "欠",  # Monday P6 must be "欠"
    #     ("火", 6): "YT",  # Tuesday P6
    #     ("水", 6): "YT",  # Wednesday P6
    #     ("金", 6): "YT",  # Friday P6
    # }
    CRITICAL_FIXED_SLOTS = {}  # 空の辞書に変更（強制配置を無効化）
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def is_fixed_subject(self, subject_name: str) -> bool:
        """指定された科目が固定科目かどうかを判定"""
        return subject_name in self.FIXED_SUBJECTS
    
    def is_critical_fixed_slot(self, time_slot: TimeSlot) -> bool:
        """指定された時間枠が重要な固定枠かどうかを判定"""
        return (time_slot.day, time_slot.period) in self.CRITICAL_FIXED_SLOTS
    
    def get_required_subject_for_slot(self, time_slot: TimeSlot) -> Optional[str]:
        """特定の時間枠に必要な固定科目を取得"""
        return self.CRITICAL_FIXED_SLOTS.get((time_slot.day, time_slot.period))
    
    def can_modify_slot(self, schedule: Schedule, time_slot: TimeSlot, 
                       class_ref: ClassReference, new_assignment: Optional[Assignment] = None) -> bool:
        """指定されたスロットが変更可能かどうかを判定
        
        Args:
            schedule: 現在のスケジュール
            time_slot: 時間枠
            class_ref: クラス
            new_assignment: 新しい割り当て（削除の場合はNone）
            
        Returns:
            変更可能な場合True
        """
        # 現在の割り当てを確認
        current_assignment = schedule.get_assignment(time_slot, class_ref)
        
        # 固定科目が既に配置されている場合
        if current_assignment and self.is_fixed_subject(current_assignment.subject.name):
            # 同じ固定科目への変更は許可（教員変更など）
            if new_assignment and new_assignment.subject.name == current_assignment.subject.name:
                return True
            # それ以外の変更は禁止
            self.logger.warning(
                f"固定科目の変更を拒否: {time_slot} {class_ref} - "
                f"現在: {current_assignment.subject.name}"
            )
            return False
        
        # 重要な固定枠の場合
        if self.is_critical_fixed_slot(time_slot):
            required_subject = self.get_required_subject_for_slot(time_slot)
            # 必要な固定科目以外の配置は禁止
            if new_assignment and new_assignment.subject.name != required_subject:
                self.logger.warning(
                    f"固定枠への不正な配置を拒否: {time_slot} {class_ref} - "
                    f"必要: {required_subject}, 試行: {new_assignment.subject.name}"
                )
                return False
            # 削除も禁止
            if not new_assignment:
                self.logger.warning(
                    f"固定枠からの削除を拒否: {time_slot} {class_ref} - "
                    f"必要: {required_subject}"
                )
                return False
        
        # 新規に固定科目を配置しようとしている場合
        if new_assignment and self.is_fixed_subject(new_assignment.subject.name):
            # 初期スケジュールに存在しない固定科目の新規配置は禁止
            # （これは別途初期スケジュールとの比較が必要）
            pass
        
        return True
    
    def enforce_critical_slots(self, schedule: Schedule, school) -> int:
        """重要な固定枠に必要な科目を強制配置（無効化）
        
        この機能は無効化されています。input.csvの内容を尊重します。
        
        Returns:
            強制配置した数（常に0）
        """
        # 強制配置は行わない - input.csvの内容を尊重
        self.logger.info("固定科目の強制配置は無効化されています。input.csvの内容を尊重します。")
        return 0
    
    def validate_schedule(self, schedule: Schedule, school) -> list:
        """スケジュール全体の固定科目を検証
        
        CRITICAL_FIXED_SLOTSが無効化されているため、
        強制配置の検証は行いません。
        
        Returns:
            違反のリスト（常に空）
        """
        # 強制配置の検証は行わない
        return []
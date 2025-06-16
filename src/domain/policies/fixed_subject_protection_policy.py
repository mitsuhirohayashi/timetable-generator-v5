"""固定教科保護ポリシー（無効化済み）"""

class FixedSubjectProtectionPolicy:
    """固定教科の保護と強制配置のポリシー
    
    注意: 現在は強制配置機能は無効化されており、input.csvの内容を尊重します
    """
    
    def __init__(self):
        # 強制配置は無効化
        pass
    
    def enforce_critical_slots(self, schedule, school):
        """固定教科の強制配置（無効化済み）
        
        Returns:
            0 - 強制配置は行わない
        """
        return 0
    
    def validate_schedule(self, schedule, school):
        """スケジュールの検証（無効化済み）
        
        Returns:
            空のリスト - 違反なし
        """
        return []
    
    def can_modify_slot(self, schedule, time_slot, class_ref, assignment):
        """スロットが変更可能かチェック
        
        Args:
            schedule: スケジュール
            time_slot: 時間枠
            class_ref: クラス参照
            assignment: 割り当て（Noneの場合もある）
        
        Returns:
            True - 常に変更可能（強制保護は無効化済み）
        """
        return True
    
    def is_fixed_subject(self, subject_name):
        """固定教科かどうかチェック
        
        Args:
            subject_name: 教科名
        
        Returns:
            True if 固定教科, False otherwise
        """
        # 固定教科のリスト
        fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事"}
        return subject_name in fixed_subjects
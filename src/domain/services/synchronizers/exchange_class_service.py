"""交流学級（支援学級）関連の処理を一元管理するサービス

このサービスは交流学級に関する全てのロジックを集約し、
コードの重複を排除して一貫性のある処理を提供します。
"""
import logging
from typing import Dict, Optional, Set, Tuple, List
from ...value_objects.time_slot import ClassReference, TimeSlot
from ...value_objects.assignment import Assignment
from ...entities.schedule import Schedule
from ...entities.school import School, Subject
from ...utils.schedule_utils import ScheduleUtils
from ....shared.mixins.logging_mixin import LoggingMixin


class ExchangeClassService(LoggingMixin):
    """交流学級関連の処理を一元管理するサービス"""
    
    # 自立活動として扱う科目
    JIRITSU_SUBJECTS = {"自立", "日生", "生単", "作業"}
    
    # 自立活動時に親学級で許可される科目
    ALLOWED_PARENT_SUBJECTS = {"数", "英", "算"}
    
    # 固定科目（同期不要）
    FIXED_SUBJECTS = {"道", "道徳", "YT", "欠", "総", "総合", "学", "学活", "学総", "行", "行事", "テスト", "技家"}
    
    def __init__(self):
        """初期化"""
        super().__init__()
        
        # 交流学級と親学級のマッピングを初期化
        self._exchange_parent_map: Dict[ClassReference, ClassReference] = {}
        self._parent_exchange_map: Dict[ClassReference, ClassReference] = {}
        self._load_exchange_mappings()
    
    def _load_exchange_mappings(self) -> None:
        """交流学級のマッピングを読み込む"""
        # ScheduleUtilsから交流学級ペアを取得
        exchange_pairs = ScheduleUtils.get_exchange_class_pairs()
        
        import re
        for exchange_str, parent_str in exchange_pairs:
            # "1年6組" -> ClassReference(1, 6)
            exchange_match = re.match(r'(\d+)年(\d+)組', exchange_str)
            parent_match = re.match(r'(\d+)年(\d+)組', parent_str)
            
            if exchange_match and parent_match:
                exchange_ref = ClassReference(int(exchange_match.group(1)), int(exchange_match.group(2)))
                parent_ref = ClassReference(int(parent_match.group(1)), int(parent_match.group(2)))
                self._exchange_parent_map[exchange_ref] = parent_ref
                self._parent_exchange_map[parent_ref] = exchange_ref
        
        self.logger.info(f"交流学級マッピングを{len(self._exchange_parent_map)}組読み込みました")
    
    def get_parent_class(self, exchange_class: ClassReference) -> Optional[ClassReference]:
        """交流学級に対応する親学級を取得"""
        return self._exchange_parent_map.get(exchange_class)
    
    def get_exchange_class(self, parent_class: ClassReference) -> Optional[ClassReference]:
        """親学級に対応する交流学級を取得"""
        return self._parent_exchange_map.get(parent_class)
    
    def is_exchange_class(self, class_ref: ClassReference) -> bool:
        """指定されたクラスが交流学級かどうか判定"""
        return class_ref in self._exchange_parent_map
    
    def is_parent_class(self, class_ref: ClassReference) -> bool:
        """指定されたクラスが親学級かどうか判定"""
        return class_ref in self._parent_exchange_map
    
    def is_jiritsu_activity(self, subject_name: str) -> bool:
        """指定された科目が自立活動かどうか判定"""
        return subject_name in self.JIRITSU_SUBJECTS
    
    def is_fixed_subject(self, subject_name: str) -> bool:
        """指定された科目が固定科目かどうか判定"""
        return subject_name in self.FIXED_SUBJECTS
    
    def validate_jiritsu_placement(
        self, 
        exchange_assignment: Optional[Assignment], 
        parent_assignment: Optional[Assignment],
        time_slot: TimeSlot
    ) -> Tuple[bool, Optional[str]]:
        """自立活動の配置が有効かどうか検証
        
        Returns:
            (有効かどうか, エラーメッセージ)
        """
        if not exchange_assignment:
            return True, None
        
        # 交流学級が自立活動の場合
        if self.is_jiritsu_activity(exchange_assignment.subject.name):
            if not parent_assignment:
                return False, f"{time_slot}: 交流学級が自立活動ですが、親学級に授業がありません"
            
            if parent_assignment.subject.name not in self.ALLOWED_PARENT_SUBJECTS:
                return False, (f"{time_slot}: 交流学級が自立活動の時、親学級は"
                             f"{'/'.join(self.ALLOWED_PARENT_SUBJECTS)}である必要がありますが、"
                             f"{parent_assignment.subject.name}です")
        
        return True, None
    
    def validate_exchange_sync(
        self,
        exchange_assignment: Optional[Assignment],
        parent_assignment: Optional[Assignment],
        time_slot: TimeSlot
    ) -> Tuple[bool, Optional[str]]:
        """交流学級と親学級の同期が有効かどうか検証
        
        Returns:
            (有効かどうか, エラーメッセージ)
        """
        # 両方空きの場合は問題なし
        if not exchange_assignment and not parent_assignment:
            return True, None
        
        # 交流学級が自立活動の場合のみ同期をチェック
        if exchange_assignment and self.is_jiritsu_activity(exchange_assignment.subject.name):
            return self.validate_jiritsu_placement(exchange_assignment, parent_assignment, time_slot)
        
        # 自立活動以外の場合は必ず同期が必要（CLAUDE.mdのルールに準拠）
        # 片方だけ空きの場合は違反
        if bool(exchange_assignment) != bool(parent_assignment):
            return False, f"{time_slot}: 交流学級と親学級の一方だけが空きです"
        
        # 両方に授業がある場合、科目が同じである必要がある
        if exchange_assignment and parent_assignment:
            if exchange_assignment.subject.name != parent_assignment.subject.name:
                return False, f"{time_slot}: 交流学級（{exchange_assignment.subject.name}）と親学級（{parent_assignment.subject.name}）の科目が異なります"
        
        return True, None
    
    def can_place_subject_for_exchange_class(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        exchange_class: ClassReference,
        subject: Subject
    ) -> bool:
        """交流学級に指定された科目を配置可能かチェック"""
        parent_class = self.get_parent_class(exchange_class)
        if not parent_class:
            return True
        
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        
        # 自立活動を配置する場合
        if self.is_jiritsu_activity(subject.name):
            if not parent_assignment:
                return False
            return parent_assignment.subject.name in self.ALLOWED_PARENT_SUBJECTS
        
        # 固定科目は制約なし
        if self.is_fixed_subject(subject.name):
            return True
        
        # 通常科目は親学級と同じである必要
        if parent_assignment:
            return parent_assignment.subject.name == subject.name
        
        return True
    
    def can_place_subject_for_parent_class(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        parent_class: ClassReference,
        subject: Subject
    ) -> bool:
        """親学級に指定された科目を配置可能かチェック"""
        exchange_class = self.get_exchange_class(parent_class)
        if not exchange_class:
            return True
        
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        # 交流学級が空きの場合は配置可能
        if not exchange_assignment:
            return True
        
        # 交流学級が自立活動の場合のみ制約を適用
        if self.is_jiritsu_activity(exchange_assignment.subject.name):
            return subject.name in self.ALLOWED_PARENT_SUBJECTS
        
        # 自立活動以外の場合は制約なし（親学級は自由に配置可能）
        return True
    
    def sync_exchange_with_parent(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        parent_class: ClassReference,
        parent_assignment: Assignment
    ) -> bool:
        """親学級の割り当てに合わせて交流学級を同期（自立活動以外の通常授業時のみ）
        
        Returns:
            同期が成功したかどうか
        """
        exchange_class = self.get_exchange_class(parent_class)
        if not exchange_class:
            return True
        
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        # 交流学級が自立活動の場合は同期しない
        if exchange_assignment and self.is_jiritsu_activity(exchange_assignment.subject.name):
            # ただし、親学級が数/英でない場合は警告
            if parent_assignment.subject.name not in self.ALLOWED_PARENT_SUBJECTS:
                self.logger.warning(
                    f"{time_slot}: 交流学級{exchange_class}が自立活動ですが、"
                    f"親学級{parent_class}が{parent_assignment.subject.name}です"
                )
            return True
        
        # 固定科目は同期しない
        if self.is_fixed_subject(parent_assignment.subject.name):
            return True
        
        # 交流学級が自立活動以外（通常授業）の場合のみ同期
        # 既に同じ科目の場合は何もしない
        if exchange_assignment and exchange_assignment.subject.name == parent_assignment.subject.name:
            return True
        
        # 交流学級が空き、または自立活動以外の場合のみ同期を試みる
        if not exchange_assignment or not self.is_jiritsu_activity(exchange_assignment.subject.name):
            # ロックされているセルは変更しない
            if schedule.is_locked(time_slot, exchange_class):
                self.logger.debug(f"同期スキップ: {time_slot} {exchange_class} はロックされています。")
                return True

            # 交流学級の教師を取得
            exchange_teacher = school.get_assigned_teacher(parent_assignment.subject, exchange_class)
            if not exchange_teacher:
                # 親学級の教師を使用
                exchange_teacher = parent_assignment.teacher
                self.logger.debug(
                    f"{exchange_class}に{parent_assignment.subject.name}の教師が"
                    f"割り当てられていないため、親学級の教師{exchange_teacher.name}を使用"
                )
            
            # 新しい割り当てを作成
            new_assignment = Assignment(exchange_class, parent_assignment.subject, exchange_teacher)
            
            # 既存の割り当てを削除し、新しい割り当てを配置
            try:
                if exchange_assignment:
                    schedule.remove_assignment(time_slot, exchange_class)
                
                schedule.assign(time_slot, new_assignment)
                
                self.logger.info(
                    f"交流学級を同期: {exchange_class} {time_slot} → "
                    f"{parent_assignment.subject.name}({exchange_teacher.name})"
                )
                return True
            except InvalidAssignmentException as e:
                self.logger.error(
                    f"交流学級の同期に失敗: {exchange_class} {time_slot} → "
                    f"{parent_assignment.subject.name}. Error: {e}"
                )
                # 失敗した場合は、元の割り当てを復元しようと試みる
                if exchange_assignment:
                    try:
                        # assignを再度呼び出して元に戻す
                        schedule.assign(time_slot, exchange_assignment)
                    except InvalidAssignmentException as restore_e:
                        self.logger.critical(f"元の割り当ての復元に失敗: {restore_e}")
                return False
        
        # 交流学級が自立活動や他の科目の場合は同期しない
        return True
    
    def get_all_exchange_classes(self) -> List[ClassReference]:
        """全ての交流学級のリストを取得"""
        return list(self._exchange_parent_map.keys())
    
    def get_all_parent_classes(self) -> List[ClassReference]:
        """全ての親学級のリストを取得"""
        return list(self._parent_exchange_map.keys())
    
    def can_place_jiritsu_for_exchange_class(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        exchange_class: ClassReference
    ) -> bool:
        """交流学級に自立活動を配置可能かチェック
        
        自立活動を配置する前に、親学級が数学・英語であることを確認する。
        
        Args:
            schedule: 現在のスケジュール
            time_slot: 配置する時間枠
            exchange_class: 交流学級
            
        Returns:
            配置可能な場合True
        """
        parent_class = self.get_parent_class(exchange_class)
        if not parent_class:
            return True  # 親学級がない場合は制約なし
        
        parent_assignment = schedule.get_assignment(time_slot, parent_class)
        
        # 親学級が数学・英語でない場合は配置不可
        if not parent_assignment or parent_assignment.subject.name not in self.ALLOWED_PARENT_SUBJECTS:
            self.logger.debug(f"{time_slot} {exchange_class}: 親学級が{parent_assignment.subject.name if parent_assignment else '空き'}のため自立活動を配置できません")
            return False
        return True
    
    def can_change_parent_class_subject(
        self,
        schedule: Schedule,
        time_slot: TimeSlot,
        parent_class: ClassReference,
        new_subject: Subject
    ) -> bool:
        """親学級の科目を変更可能かチェック
        
        親学級の科目を変更する前に、交流学級が自立活動でないか、
        または新科目が数学・英語であることを確認する。
        
        Args:
            schedule: 現在のスケジュール
            time_slot: 時間枠
            parent_class: 親学級
            new_subject: 新しい科目
            
        Returns:
            変更可能な場合True
        """
        exchange_class = self.get_exchange_class(parent_class)
        if not exchange_class:
            return True  # 交流学級がない場合は制約なし
        
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        # 交流学級が自立活動で、新科目が数学・英語でない場合は変更不可
        if exchange_assignment and self.is_jiritsu_activity(exchange_assignment.subject.name):
            if new_subject.name not in self.ALLOWED_PARENT_SUBJECTS:
                self.logger.debug(f"{time_slot} {parent_class}: 交流学級が自立活動中のため、{new_subject.name}に変更できません")
                return False
        return True
    
    def get_exchange_violations(self, schedule: Schedule) -> List[Dict]:
        """スケジュール内の交流学級同期違反を検出
        
        Returns:
            違反情報のリスト
        """
        violations = []
        
        for exchange_class, parent_class in self._exchange_parent_map.items():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 自立活動の制約をチェック
                    valid, error_msg = self.validate_jiritsu_placement(
                        exchange_assignment, parent_assignment, time_slot
                    )
                    if not valid:
                        violations.append({
                            'type': 'jiritsu_constraint',
                            'exchange_class': exchange_class,
                            'parent_class': parent_class,
                            'time_slot': time_slot,
                            'message': error_msg
                        })
                    
                    # 通常の同期をチェック
                    valid, error_msg = self.validate_exchange_sync(
                        exchange_assignment, parent_assignment, time_slot
                    )
                    if not valid:
                        violations.append({
                            'type': 'sync_violation',
                            'exchange_class': exchange_class,
                            'parent_class': parent_class,
                            'time_slot': time_slot,
                            'message': error_msg
                        })
        
        return violations
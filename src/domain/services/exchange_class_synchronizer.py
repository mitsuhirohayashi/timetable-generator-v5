"""交流学級同期サービス - スケジュール生成後に交流学級を完全に同期する"""
import logging
from typing import Dict, List, Tuple, Optional, Set

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment


class ExchangeClassSynchronizer:
    """交流学級の同期を確実に行うサービス"""
    
    def __init__(self, forbidden_cells: Dict[Tuple[TimeSlot, ClassReference], Set[str]] = None):
        self.logger = logging.getLogger(__name__)
        
        # 交流学級と親学級のマッピング
        self.exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        # セル別配置禁止制約
        self.forbidden_cells = forbidden_cells or {}
        
        # 同期除外教科（なし - 体育も親学級と一緒に実施）
        self.excluded_subjects = set()  # 全教科を同期対象とする
        
        # 必須同期教科（体育は必ず一緒に実施）
        self.required_sync_subjects = {"保"}  # 体育は必須同期
    
    def synchronize_all_exchange_classes(self, schedule: Schedule, school: School) -> int:
        """全ての交流学級を親学級と同期する
        
        Returns:
            同期した時間枠の数
        """
        self.logger.info("=== 交流学級の完全同期を開始 ===")
        
        sync_count = 0
        
        for exchange_class, parent_class in self.exchange_mappings.items():
            # 両方のクラスが存在するかチェック
            if exchange_class not in school.get_all_classes() or parent_class not in school.get_all_classes():
                self.logger.warning(f"クラスが存在しません: {exchange_class} または {parent_class}")
                continue
            
            self.logger.info(f"{exchange_class} を {parent_class} と同期中...")
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # ロックされているセルはスキップ
                    if schedule.is_locked(time_slot, exchange_class):
                        continue
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 固定科目の場合はスキップ
                    from ..policies.fixed_subject_protection_policy import FixedSubjectProtectionPolicy
                    policy = FixedSubjectProtectionPolicy()
                    
                    if exchange_assignment and policy.is_fixed_subject(exchange_assignment.subject.name):
                        self.logger.debug(f"  {time_slot}: 交流学級は固定科目{exchange_assignment.subject}のため同期不要")
                        continue
                    
                    # Case 1: 交流学級が自立活動の場合
                    if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                        # 自立活動の場合は同期不要（それぞれ独立して活動）
                        self.logger.debug(f"  {time_slot}: 交流学級は{exchange_assignment.subject}のため同期不要")
                    
                    # Case 2: 交流学級が自立活動でない場合
                    elif parent_assignment:
                        # 同期除外教科（体育など）のチェック
                        if parent_assignment.subject.name in self.excluded_subjects:
                            self.logger.debug(f"  {time_slot}: {parent_assignment.subject}は同期除外教科のためスキップ")
                            continue
                        
                        # 体育の場合は必ず同期を強制
                        if parent_assignment.subject.name in self.required_sync_subjects:
                            if not exchange_assignment or exchange_assignment.subject != parent_assignment.subject:
                                # 既存の授業を削除してでも体育を配置
                                schedule.remove_assignment(time_slot, exchange_class)
                                schedule.assign(time_slot, Assignment(
                                    class_ref=exchange_class,
                                    subject=parent_assignment.subject,
                                    teacher=parent_assignment.teacher
                                ))
                                self.logger.info(f"  {time_slot}: 交流学級を{parent_assignment.subject}に強制同期")
                                sync_count += 1
                                continue
                        
                        # 交流学級を親学級と同じにする
                        if not exchange_assignment or exchange_assignment.subject != parent_assignment.subject:
                            # 交流学級に既存の授業があり、親学級と異なる場合
                            if exchange_assignment:
                                # 両方とも固定教科（技・家など）の場合は、お互いの授業を交換する必要がある
                                exchange_subj = exchange_assignment.subject.name
                                parent_subj = parent_assignment.subject.name
                                
                                # 技と家の組み合わせで、逆転している場合
                                if ((exchange_subj == "技" and parent_subj == "家") or 
                                    (exchange_subj == "家" and parent_subj == "技")):
                                    # 親学級の同じ日に交流学級が持っている教科があるか探す
                                    swap_slot = self._find_swap_slot(schedule, parent_class, time_slot.day, exchange_subj)
                                    if swap_slot:
                                        # 交換を実行
                                        self._swap_assignments(schedule, parent_class, time_slot, swap_slot)
                                        self.logger.info(f"  {parent_class}の{time_slot}と{swap_slot}を交換（{parent_subj}↔{exchange_subj}）")
                                        sync_count += 1
                                        continue
                            
                            # セル別配置禁止チェック
                            exchange_key = (time_slot, exchange_class)
                            forbidden_subjects = self.forbidden_cells.get(exchange_key, set())
                            if parent_assignment.subject.name in forbidden_subjects:
                                self.logger.warning(f"  {time_slot}: {exchange_class}に{parent_assignment.subject}は配置不可（非{parent_assignment.subject.name}指定）")
                                continue
                            
                            # 日内重複チェック
                            if not self._would_cause_daily_duplicate(schedule, exchange_class, time_slot, parent_assignment.subject):
                                # 既存の割り当てを削除
                                if exchange_assignment:
                                    schedule.remove_assignment(time_slot, exchange_class)
                                
                                # 親学級と同じ教科・教員で割り当て
                                new_assignment = Assignment(exchange_class, parent_assignment.subject, parent_assignment.teacher)
                                schedule.assign(time_slot, new_assignment)
                                sync_count += 1
                                self.logger.info(f"  {time_slot}: 交流学級を{parent_assignment.subject}に同期")
                            else:
                                self.logger.warning(f"  {time_slot}: {exchange_class}に{parent_assignment.subject}を配置すると日内重複が発生するため同期をスキップ")
                    
                    # Case 3: 親学級が空きで交流学級に授業がある場合
                    elif exchange_assignment and exchange_assignment.subject.name not in ["自立", "日生", "生単", "作業"]:
                        # 交流学級を空きにする
                        schedule.remove_assignment(time_slot, exchange_class)
                        sync_count += 1
                        self.logger.info(f"  {time_slot}: 交流学級を空きに（親学級に合わせる）")
        
        self.logger.info(f"=== 交流学級の完全同期完了: {sync_count}件の同期を実行 ===")
        return sync_count
    
    def _set_parent_to_math_or_english(self, schedule: Schedule, school: School,
                                      time_slot: TimeSlot, parent_class: ClassReference,
                                      exchange_class: ClassReference) -> bool:
        """親学級を数学または英語に設定する"""
        # 既存の割り当てを削除
        existing = schedule.get_assignment(time_slot, parent_class)
        if existing and not schedule.is_locked(time_slot, parent_class):
            schedule.remove_assignment(time_slot, parent_class)
        elif schedule.is_locked(time_slot, parent_class):
            self.logger.warning(f"    {parent_class}の{time_slot}はロックされているため変更できません")
            return False
        
        # セル別配置禁止チェック
        parent_key = (time_slot, parent_class)
        forbidden_subjects = self.forbidden_cells.get(parent_key, set())
        
        # 教科オブジェクトを事前に作成
        math_subject = Subject("数")
        eng_subject = Subject("英")
        
        # 数学を優先的に試す（禁止されていない場合）
        if "数" not in forbidden_subjects:
            math_teacher = school.get_assigned_teacher(math_subject, parent_class)
            
            if math_teacher and self._can_assign_teacher(schedule, school, time_slot, math_teacher):
                # 日内重複チェック
                if not self._would_cause_daily_duplicate(schedule, parent_class, time_slot, math_subject):
                    assignment = Assignment(parent_class, math_subject, math_teacher)
                    schedule.assign(time_slot, assignment)
                    return True
        else:
            self.logger.warning(f"    {parent_class}に数学は配置不可（非数指定）")
        
        # 数学がダメなら英語を試す（禁止されていない場合）
        if "英" not in forbidden_subjects:
            eng_teacher = school.get_assigned_teacher(eng_subject, parent_class)
            
            if eng_teacher and self._can_assign_teacher(schedule, school, time_slot, eng_teacher):
                # 日内重複チェック
                if not self._would_cause_daily_duplicate(schedule, parent_class, time_slot, eng_subject):
                    assignment = Assignment(parent_class, eng_subject, eng_teacher)
                    schedule.assign(time_slot, assignment)
                    return True
        else:
            self.logger.warning(f"    {parent_class}に英語は配置不可（非英指定）")
        
        # どちらも配置できない場合は、代替教員を探す
        for subject, subject_name in [(math_subject, "数"), (eng_subject, "英")]:
            for teacher in school.get_subject_teachers(subject):
                if subject_name not in forbidden_subjects and self._can_assign_teacher(schedule, school, time_slot, teacher):
                    # 日内重複チェック
                    if not self._would_cause_daily_duplicate(schedule, parent_class, time_slot, subject):
                        assignment = Assignment(parent_class, subject, teacher)
                        schedule.assign(time_slot, assignment)
                        self.logger.info(f"    代替教員{teacher}で{subject_name}を配置")
                        return True
        
        self.logger.warning(f"    {parent_class}に数学・英語を配置できませんでした")
        return False
    
    def _can_assign_teacher(self, schedule: Schedule, school: School, 
                           time_slot: TimeSlot, teacher: Teacher) -> bool:
        """教員を指定の時間に配置可能かチェック"""
        # 教員が不在でない
        if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
            return False
        
        # 教員が他のクラスを担当していない
        if not schedule.is_teacher_available(time_slot, teacher):
            return False
        
        return True
    
    def _would_cause_daily_duplicate(self, schedule: Schedule, class_ref: ClassReference, 
                                   time_slot: TimeSlot, subject: Subject) -> bool:
        """指定の教科を配置すると日内重複が発生するかチェック"""
        # 同じ日の他の時間に同じ教科があるかチェック
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            other_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(other_slot, class_ref)
            
            if assignment and assignment.subject == subject:
                return True
        
        return False
    
    def verify_synchronization(self, schedule: Schedule, school: School) -> List[str]:
        """交流学級の同期状態を検証し、違反のリストを返す"""
        violations = []
        
        for exchange_class, parent_class in self.exchange_mappings.items():
            if exchange_class not in school.get_all_classes() or parent_class not in school.get_all_classes():
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 違反をチェック
                    if exchange_assignment:
                        if exchange_assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                            # 自立活動の場合は同期不要なので違反チェックしない
                            continue
                        else:
                            if not parent_assignment or exchange_assignment.subject != parent_assignment.subject:
                                violations.append(
                                    f"{time_slot}: {exchange_class}({exchange_assignment.subject})と"
                                    f"{parent_class}({parent_assignment.subject if parent_assignment else '空き'})が不一致"
                                )
        
        return violations
    
    def _find_swap_slot(self, schedule: Schedule, class_ref: ClassReference,
                       day: str, target_subject: str) -> Optional[TimeSlot]:
        """同じ日で指定の教科を持つ時間を探す"""
        for period in range(1, 7):
            slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(slot, class_ref)
            if assignment and assignment.subject.name == target_subject:
                return slot
        return None
    
    def _swap_assignments(self, schedule: Schedule, class_ref: ClassReference,
                         slot1: TimeSlot, slot2: TimeSlot) -> bool:
        """2つの時間枠の授業を交換する"""
        # 両方の割り当てを取得
        assignment1 = schedule.get_assignment(slot1, class_ref)
        assignment2 = schedule.get_assignment(slot2, class_ref)
        
        if not assignment1 or not assignment2:
            return False
        
        # ロックされている場合はスキップ
        if schedule.is_locked(slot1, class_ref) or schedule.is_locked(slot2, class_ref):
            return False
        
        # 一時的に削除
        schedule.remove_assignment(slot1, class_ref)
        schedule.remove_assignment(slot2, class_ref)
        
        # 交換して再配置
        new_assignment1 = Assignment(class_ref, assignment2.subject, assignment2.teacher)
        new_assignment2 = Assignment(class_ref, assignment1.subject, assignment1.teacher)
        
        schedule.assign(slot1, new_assignment1)
        schedule.assign(slot2, new_assignment2)
        
        return True
"""交流学級同期サービス - スケジュール生成後に交流学級を完全に同期する"""
import logging
import re
from typing import Dict, List, Tuple, Optional, Set
from ....shared.mixins.logging_mixin import LoggingMixin

from ...entities.schedule import Schedule
from ...entities.school import School, Teacher, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ...utils.schedule_utils import ScheduleUtils


class ExchangeClassSynchronizer(LoggingMixin):
    """交流学級の同期を確実に行うサービス"""
    
    def __init__(self, forbidden_cells: Dict[Tuple[TimeSlot, ClassReference], Set[str]] = None):
        super().__init__()
        
        # 交流学級と親学級のマッピング（ScheduleUtilsから取得）
        exchange_pairs = ScheduleUtils.get_exchange_class_pairs()
        self.exchange_mappings = {}
        for exchange_str, parent_str in exchange_pairs:
            # "1年6組" -> ClassReference(1, 6)
            # 年と組で区切って学年とクラス番号を取得
            exchange_match = re.match(r'(\d+)年(\d+)組', exchange_str)
            parent_match = re.match(r'(\d+)年(\d+)組', parent_str)
            
            if exchange_match and parent_match:
                exchange_ref = ClassReference(int(exchange_match.group(1)), int(exchange_match.group(2)))
                parent_ref = ClassReference(int(parent_match.group(1)), int(parent_match.group(2)))
                self.exchange_mappings[exchange_ref] = parent_ref
        
        # セル別配置禁止制約
        self.forbidden_cells = forbidden_cells or {}
        
        # 同期除外教科（なし - 体育も親学級と一緒に実施）
        self.excluded_subjects = set()  # 全教科を同期対象とする
        
        # 必須同期教科（体育は必ず一緒に実施）
        self.required_sync_subjects = {"保"}  # 体育は必須同期
    
    def can_place_for_parent_class(self, schedule: Schedule, school: School,
                                   parent_class: ClassReference, time_slot: TimeSlot,
                                   subject: Subject) -> bool:
        """親学級に配置可能かチェック（交流学級の制約も考慮）
        
        Args:
            schedule: スケジュール
            school: 学校情報
            parent_class: 親学級
            time_slot: 時間枠
            subject: 配置したい科目
            
        Returns:
            配置可能な場合True
        """
        # 逆引きマッピングを作成
        parent_to_exchange = {v: k for k, v in self.exchange_mappings.items()}
        
        # 親学級に対応する交流学級がない場合は制約なし
        if parent_class not in parent_to_exchange:
            return True
        
        exchange_class = parent_to_exchange[parent_class]
        
        # 交流学級が存在しない場合は制約なし
        if exchange_class not in school.get_all_classes():
            return True
        
        # 交流学級の現在の割り当てを確認
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        # 交流学級が自立活動の場合
        if exchange_assignment and ScheduleUtils.is_jiritsu_activity(exchange_assignment.subject.name):
            # 親学級は数学か英語でなければならない
            if subject.name not in {"数", "英", "算"}:
                self.logger.debug(f"交流学級{exchange_class}が自立活動のため、親学級{parent_class}は数/英のみ配置可能")
                return False
        
        # 交流学級がロックされている場合
        if schedule.is_locked(time_slot, exchange_class):
            # 交流学級と異なる科目は配置できない
            if exchange_assignment and exchange_assignment.subject != subject:
                if not ScheduleUtils.is_jiritsu_activity(exchange_assignment.subject.name):
                    self.logger.debug(f"交流学級{exchange_class}がロックされており異なる科目のため配置不可")
                    return False
        
        # 交流学級への配置可能性をチェック
        if not ScheduleUtils.is_fixed_subject(subject.name):
            # セル別配置禁止チェック
            exchange_key = (time_slot, exchange_class)
            forbidden_subjects = self.forbidden_cells.get(exchange_key, set())
            if subject.name in forbidden_subjects:
                self.logger.debug(f"交流学級{exchange_class}への{subject}配置が禁止されているため配置不可")
                return False
            
            # 日内重複チェック
            if self._would_cause_daily_duplicate(schedule, exchange_class, time_slot, subject):
                self.logger.debug(f"交流学級{exchange_class}で日内重複が発生するため配置不可")
                return False
        
        return True
    
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
                    
                    # ロックされているセルはスキップ（交流学級と親学級の両方をチェック）
                    if schedule.is_locked(time_slot, exchange_class) or schedule.is_locked(time_slot, parent_class):
                        self.logger.debug(f"  {time_slot}: ロックされているためスキップ")
                        continue
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 固定科目の場合はスキップ
                    if exchange_assignment and ScheduleUtils.is_fixed_subject(exchange_assignment.subject.name):
                        self.logger.debug(f"  {time_slot}: 交流学級は固定科目{exchange_assignment.subject}のため同期不要")
                        continue
                    
                    # Case 1: 交流学級が自立活動の場合
                    if exchange_assignment and ScheduleUtils.is_jiritsu_activity(exchange_assignment.subject.name):
                        # 自立活動の場合は同期不要（それぞれ独立して活動）
                        self.logger.debug(f"  {time_slot}: 交流学級は{exchange_assignment.subject}のため同期不要")
                    
                    # Case 2: 交流学級が自立活動でない場合
                    elif parent_assignment:
                        # 同期除外教科（体育など）のチェック
                        if parent_assignment.subject.name in self.excluded_subjects:
                            self.logger.debug(f"  {time_slot}: {parent_assignment.subject}は同期除外教科のためスキップ")
                            continue
                        
                        # 体育の場合でもロックをチェック（テスト期間等を考慮）
                        if parent_assignment.subject.name in self.required_sync_subjects:
                            if not exchange_assignment or exchange_assignment.subject != parent_assignment.subject:
                                # ロックされていない場合のみ同期
                                if not schedule.is_locked(time_slot, exchange_class):
                                    # 既存の授業を削除してでも体育を配置
                                    schedule.remove_assignment(time_slot, exchange_class)
                                    schedule.assign(time_slot, Assignment(
                                        class_ref=exchange_class,
                                        subject=parent_assignment.subject,
                                        teacher=parent_assignment.teacher
                                    ))
                                    self.logger.info(f"  {time_slot}: 交流学級を{parent_assignment.subject}に強制同期")
                                    sync_count += 1
                                else:
                                    self.logger.debug(f"  {time_slot}: 体育同期はロックのためスキップ")
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
                                # 日内重複が発生する場合、重複している授業を削除してから同期
                                self.logger.warning(f"  {time_slot}: {exchange_class}に{parent_assignment.subject}を配置すると日内重複が発生")
                                
                                # 重複する授業を探して削除
                                for period in range(1, 7):
                                    if period == time_slot.period:
                                        continue
                                    
                                    check_slot = TimeSlot(time_slot.day, period)
                                    existing = schedule.get_assignment(check_slot, exchange_class)
                                    
                                    if existing and existing.subject == parent_assignment.subject and not schedule.is_locked(check_slot, exchange_class):
                                        schedule.remove_assignment(check_slot, exchange_class)
                                        self.logger.info(f"    日内重複解消のため{exchange_class}の{check_slot}から{existing.subject}を削除")
                                        
                                        # 再度日内重複チェック
                                        if not self._would_cause_daily_duplicate(schedule, exchange_class, time_slot, parent_assignment.subject):
                                            # 既存の割り当てを削除
                                            if exchange_assignment:
                                                schedule.remove_assignment(time_slot, exchange_class)
                                            
                                            # 親学級と同じ教科・教員で割り当て
                                            new_assignment = Assignment(exchange_class, parent_assignment.subject, parent_assignment.teacher)
                                            schedule.assign(time_slot, new_assignment)
                                            sync_count += 1
                                            self.logger.info(f"  {time_slot}: 交流学級を{parent_assignment.subject}に同期（日内重複解消後）")
                                        break
                    
                    # Case 3: 親学級が空きで交流学級に授業がある場合
                    elif exchange_assignment and not ScheduleUtils.is_jiritsu_activity(exchange_assignment.subject.name):
                        # 交流学級を空きにする
                        schedule.remove_assignment(time_slot, exchange_class)
                        sync_count += 1
                        self.logger.info(f"  {time_slot}: 交流学級を空きに（親学級に合わせる）")
        
        self.logger.info(f"=== 交流学級の完全同期完了: {sync_count}件の同期を実行 ===")
        
        # 最終的な同期確認
        self._verify_final_synchronization(schedule, school)
        
        return sync_count
    
    def sync_exchange_with_parent(self, schedule: Schedule, school: School,
                                  parent_class: ClassReference, time_slot: TimeSlot,
                                  assignment: Assignment) -> bool:
        """親学級への配置と同時に交流学級も同期する
        
        Args:
            schedule: スケジュール
            school: 学校情報
            parent_class: 親学級
            time_slot: 時間枠
            assignment: 親学級への割り当て
            
        Returns:
            同期に成功した場合True
        """
        # 逆引きマッピングを作成
        parent_to_exchange = {v: k for k, v in self.exchange_mappings.items()}
        
        # 親学級に対応する交流学級がない場合は何もしない
        if parent_class not in parent_to_exchange:
            return True
        
        exchange_class = parent_to_exchange[parent_class]
        
        # 交流学級が存在しない場合はスキップ
        if exchange_class not in school.get_all_classes():
            return True
        
        # 交流学級の現在の割り当てを確認
        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
        
        # 交流学級が自立活動の場合は同期しない
        if exchange_assignment and ScheduleUtils.is_jiritsu_activity(exchange_assignment.subject.name):
            # 親学級は数学か英語でなければならない
            if assignment.subject.name not in {"数", "英", "算"}:
                self.logger.warning(f"交流学級{exchange_class}が自立活動のため、親学級{parent_class}は数/英のみ配置可能")
                return False
            return True
        
        # 交流学級がロックされている場合はスキップ
        if schedule.is_locked(time_slot, exchange_class):
            return True
        
        # 固定科目の場合は同期しない
        if ScheduleUtils.is_fixed_subject(assignment.subject.name):
            return True
        
        # 同期が必要かチェック
        if not exchange_assignment or exchange_assignment.subject != assignment.subject:
            # セル別配置禁止チェック
            exchange_key = (time_slot, exchange_class)
            forbidden_subjects = self.forbidden_cells.get(exchange_key, set())
            if assignment.subject.name in forbidden_subjects:
                self.logger.warning(f"{exchange_class}に{assignment.subject}は配置不可（非{assignment.subject.name}指定）")
                return False
            
            # 日内重複チェック
            if self._would_cause_daily_duplicate(schedule, exchange_class, time_slot, assignment.subject):
                self.logger.warning(f"{exchange_class}に{assignment.subject}を配置すると日内重複が発生")
                return False
            
            # 既存の割り当てがある場合は削除
            if exchange_assignment:
                schedule.remove_assignment(time_slot, exchange_class)
            
            # 交流学級に同じ科目・教師で配置
            exchange_teacher = assignment.teacher
            if not exchange_teacher:
                # 交流学級用の教師を探す
                exchange_teacher = school.get_assigned_teacher(assignment.subject, exchange_class)
            
            if exchange_teacher:
                new_assignment = Assignment(exchange_class, assignment.subject, exchange_teacher)
                if schedule.assign(time_slot, new_assignment):
                    self.logger.info(f"親学級{parent_class}と同時に交流学級{exchange_class}を{assignment.subject}に同期")
                    return True
            else:
                self.logger.warning(f"交流学級{exchange_class}の{assignment.subject}に適切な教師が見つかりません")
                return False
        
        return True
    
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
        # 固定教科は日内重複を許可
        if ScheduleUtils.is_fixed_subject(subject.name):
            return False
            
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
                        if ScheduleUtils.is_jiritsu_activity(exchange_assignment.subject.name):
                            # 自立活動の場合は同期不要なので違反チェックしない
                            continue
                        else:
                            if not parent_assignment or exchange_assignment.subject != parent_assignment.subject:
                                violations.append(
                                    f"{time_slot}: {exchange_class}({exchange_assignment.subject})と"
                                    f"{parent_class}({parent_assignment.subject if parent_assignment else '空き'})が不一致"
                                )
        
        return violations
    
    def _verify_final_synchronization(self, schedule: Schedule, school: School):
        """最終的な同期状態を確認し、警告を出力"""
        self.logger.info("=== 最終同期確認 ===")
        violations = self.verify_synchronization(schedule, school)
        
        if violations:
            self.logger.warning(f"最終同期確認で{len(violations)}件の不整合を発見:")
            for violation in violations[:5]:  # 最初の5件のみ表示
                self.logger.warning(f"  - {violation}")
            if len(violations) > 5:
                self.logger.warning(f"  ... 他{len(violations) - 5}件")
        else:
            self.logger.info("全ての交流学級が正しく同期されています")
    
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
"""貪欲法による通常教科配置サービスの実装"""
import logging
from typing import Optional, List

from ....domain.interfaces.regular_subject_placement_service import RegularSubjectPlacementService
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from ....domain.interfaces.teacher_absence_repository import ITeacherAbsenceRepository
from ....domain.interfaces.csp_configuration import ICSPConfiguration
from ....domain.interfaces.followup_parser import IFollowUpParser
from ....domain.interfaces.path_configuration import IPathConfiguration


class GreedySubjectPlacementService(RegularSubjectPlacementService):
    """貪欲法による通常教科配置サービス"""
    
    def __init__(self, csp_config: ICSPConfiguration = None, 
                 constraint_validator = None,
                 absence_repository: ITeacherAbsenceRepository = None,
                 followup_parser: IFollowUpParser = None,
                 path_config: IPathConfiguration = None):
        # 依存性注入
        if csp_config is None:
            from ....infrastructure.di_container import get_csp_configuration
            csp_config = get_csp_configuration()
        if absence_repository is None:
            from ....infrastructure.di_container import get_teacher_absence_repository
            absence_repository = get_teacher_absence_repository()
        if followup_parser is None:
            from ....infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
        if path_config is None:
            from ....infrastructure.di_container import get_path_configuration
            path_config = get_path_configuration()
            
        self.csp_config = csp_config
        self.constraint_validator = constraint_validator
        self.absence_repository = absence_repository
        self.followup_parser = followup_parser
        self.path_config = path_config
        self.logger = logging.getLogger(__name__)
        self.test_periods = set()
        self._load_test_periods()
        
        # 交流学級マッピング
        self.parent_to_exchange = {
            ClassReference(1, 1): ClassReference(1, 6),
            ClassReference(1, 2): ClassReference(1, 7),
            ClassReference(2, 3): ClassReference(2, 6),
            ClassReference(2, 2): ClassReference(2, 7),
            ClassReference(3, 3): ClassReference(3, 6),
            ClassReference(3, 2): ClassReference(3, 7)
        }
    
    def _load_test_periods(self) -> None:
        """テスト期間情報を読み込む"""
        try:
            # フォローアップパーサーを使用してテスト期間を読み込む
            test_periods = self.followup_parser.parse_test_periods()
            
            for test_period in test_periods:
                # test_periodがどの形式か確認して処理
                if hasattr(test_period, 'start_date') and hasattr(test_period, 'end_date'):
                    # 日付範囲形式の場合は、具体的な曜日と時限に変換が必要
                    # ここでは簡略化のため、スキップ
                    self.logger.debug(f"日付範囲形式のテスト期間: {test_period.description}")
                else:
                    # 曜日・時限形式の場合（既存の処理）
                    if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
                        day = test_period.day
                        for period in test_period.periods:
                            self.test_periods.add((day, period))
                            
            if self.test_periods:
                self.logger.debug(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
        except Exception as e:
            self.logger.warning(f"テスト期間情報の読み込みに失敗: {e}")
    
    def place_subjects(self, schedule: Schedule, school: School) -> int:
        """通常教科を配置"""
        self.logger.info("残りの教科の配置を開始")
        total_placed = 0
        
        # 最初に既存の日内重複を修正
        self._fix_existing_daily_duplicates(schedule, school)
        
        # 各クラスの未配置教科を収集
        for class_ref in school.get_all_classes():
            # 5組と交流学級は既に処理済み
            if class_ref.class_number in [5, 6, 7]:
                continue
            
            for subject in school.get_required_subjects(class_ref):
                if subject.is_protected_subject():
                    continue
                
                required_hours = int(round(school.get_standard_hours(class_ref, subject)))
                placed_hours = sum(
                    1 for _, assignment in schedule.get_all_assignments()
                    if assignment.class_ref == class_ref and assignment.subject == subject
                )
                
                # 技家の場合は特別処理
                if subject.name == "技家":
                    from ..techome_handler import TechHomeHandler
                    techome_handler = TechHomeHandler()
                    # 最適なスロットを探して教師を決定
                    best_teacher = None
                    for slot in self._get_candidate_slots(schedule, school, class_ref):
                        teacher = techome_handler.can_assign_techome(
                            schedule, school, slot, class_ref, subject
                        )
                        if teacher:
                            best_teacher = teacher
                            break
                    teacher = best_teacher
                else:
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    
                if not teacher:
                    continue
                
                # 井上先生と白石先生のデバッグ
                if teacher.name in ["井上", "白石"] or "井上" in teacher.name or "白石" in teacher.name:
                    self.logger.warning(f"\n=== {teacher.name}先生の配置開始: {class_ref} ===")
                    self.logger.warning(f"{teacher.name}先生を{class_ref}の{subject}に配置しようとしています（required: {required_hours}, placed: {placed_hours}）")
                    # 現在の火曜5限の状況を確認
                    tue5_slot = TimeSlot("火", 5)
                    for cls in school.get_all_classes():
                        assignment = schedule.get_assignment(tue5_slot, cls)
                        if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                            self.logger.warning(f"  現在火曜5限: {cls.full_name} - {assignment.subject.name} ({teacher.name}先生)")
                
                # 不足分を配置
                for _ in range(required_hours - placed_hours):
                    slot = self.find_best_slot(schedule, school, class_ref, subject, teacher)
                    if slot:
                        # 井上先生の火曜5限デバッグ
                        if teacher.name == "井上" and slot.day == "火" and slot.period == 5:
                            self.logger.warning(f"井上先生を{class_ref}の火曜5限に配置しようとしています（find_best_slot結果）")
                        
                        assignment = Assignment(class_ref, subject, teacher)
                        try:
                            # 配置前に制約チェックを実行
                            can_place = self.constraint_validator.check_assignment(schedule, school, slot, assignment)
                            if teacher.name == "井上" and slot.day == "火" and slot.period == 5:
                                self.logger.warning(f"制約チェック結果: {can_place} for {class_ref}")
                            
                            if not can_place:
                                # 配置不可の場合は次のスロットを探す
                                if teacher.name == "井上" and slot.day == "火" and slot.period == 5:
                                    self.logger.warning(f"制約違反のため井上先生を{class_ref}の火曜5限に配置できません")
                                continue
                            
                            # 井上先生と白石先生の火曜5限の特別チェック
                            if teacher.name in ["井上", "白石"] and slot.day == "火" and slot.period == 5:
                                # 現在の火曜5限の教師の配置数を確認
                                tue5_count = 0
                                for cls in school.get_all_classes():
                                    existing_assignment = schedule.get_assignment(slot, cls)
                                    if existing_assignment and existing_assignment.teacher and existing_assignment.teacher.name == teacher.name:
                                        tue5_count += 1
                                        self.logger.warning(f"  現在の{teacher.name}先生配置: {cls.full_name}")
                                
                                if tue5_count >= 1:
                                    self.logger.warning(f"{teacher.name}先生は既に火曜5限に{tue5_count}クラス配置済み。{class_ref}への配置をスキップ")
                                    continue
                            
                            schedule.assign(slot, assignment)
                            total_placed += 1
                            
                            # 配置成功のログ
                            if teacher.name in ["井上", "白石"] and slot.day == "火" and slot.period == 5:
                                self.logger.warning(f"{teacher.name}先生を{class_ref}の火曜5限に配置しました！")
                            
                            # 交流学級の同期処理
                            self._sync_exchange_class_if_needed(schedule, school, class_ref, slot, assignment)
                        except ValueError as e:
                            # 固定科目保護により配置できない場合
                            self.logger.debug(f"固定科目保護により配置不可: {e}")
                            continue
        
        return total_placed
    
    def find_best_slot(self, schedule: Schedule, school: School,
                      class_ref: ClassReference, subject: Subject,
                      teacher: Teacher) -> Optional[TimeSlot]:
        """最適なスロットを探索"""
        best_slot = None
        best_score = float('inf')
        
        # 教師配置のデバッグ情報
        if self.logger.isEnabledFor(logging.DEBUG) and teacher:
            self.logger.debug(f"find_best_slot開始: {class_ref}の{subject} ({teacher.name}先生)")
        
        # CSP設定からパラメータを取得
        csp_params = self.csp_config.get_all_parameters()
        weekdays = csp_params.get('weekdays', ["月", "火", "水", "木", "金"])
        periods_min = csp_params.get('periods_min', 1)
        periods_max = csp_params.get('periods_max', 6)
        
        for day in weekdays:
            for period in range(periods_min, periods_max + 1):
                slot = TimeSlot(day, period)
                
                # テスト期間チェックを追加
                if (day, period) in self.test_periods:
                    continue  # テスト期間はスキップ
                
                # 固定制約チェック
                if day == "月" and period == 6:
                    continue
                
                # 配置可能かチェック
                if (not schedule.get_assignment(slot, class_ref) and
                    not schedule.is_locked(slot, class_ref)):  # ロックされていないこと
                    
                    can_place = self.can_place_subject(schedule, school, class_ref, slot, subject, teacher)
                    
                    # 配置可否のデバッグ情報
                    if self.logger.isEnabledFor(logging.DEBUG) and teacher:
                        self.logger.debug(f"{slot}のcan_place_subject結果: {can_place} for {class_ref} ({teacher.name}先生)")
                    
                    if can_place:
                        score = self.evaluate_slot_for_subject(slot, subject)
                        if score < best_score:
                            best_score = score
                            best_slot = slot
                            # 井上先生と白石先生デバッグ
                            if teacher and teacher.name in ["井上", "白石"]:
                                self.logger.warning(f"新しいbest_slot: {slot.day}{slot.period}限 (score: {score}) - {teacher.name}先生")
        
        # 井上先生と白石先生デバッグ
        if teacher and teacher.name in ["井上", "白石"]:
            if best_slot:
                self.logger.warning(f"find_best_slot結果: {best_slot.day}{best_slot.period}限を返します ({teacher.name}先生)")
            else:
                self.logger.warning(f"find_best_slot結果: 配置可能なスロットが見つかりませんでした ({teacher.name}先生)")
        
        return best_slot
    
    def can_place_subject(self, schedule: Schedule, school: School,
                         class_ref: ClassReference, slot: TimeSlot,
                         subject: Subject, teacher: Teacher) -> bool:
        """教科を配置可能かチェック"""
        if not self._is_teacher_available(teacher, slot, schedule, school):
            return False
        
        # 保健体育の場合は体育館使用を事前チェック
        if subject.name == "保":
            # 同じ時間に既に体育館を使用しているクラスがあるかチェック
            pe_count = sum(
                1 for time_slot, a in schedule.get_all_assignments()
                if time_slot == slot and a.subject.name == "保"
            )
            if pe_count >= 1:
                # 5組の合同体育かチェック
                grade5_classes = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
                existing_pe_classes = [
                    a.class_ref for time_slot, a in schedule.get_all_assignments()
                    if time_slot == slot and a.subject.name == "保"
                ]
                proposed_pe_classes = existing_pe_classes + [class_ref]
                all_grade5 = all(c in grade5_classes for c in proposed_pe_classes)
                
                if not all_grade5:
                    self.logger.debug(f"体育館使用制約: {slot}に既に保健体育が実施中のため{class_ref}は配置不可")
                    return False
        
        # 日内重複チェック（_would_cause_daily_duplicateメソッドを使用）
        if self._would_cause_daily_duplicate(schedule, class_ref, slot, subject):
            self.logger.debug(f"{class_ref}の{slot.day}曜日に{subject.name}が既に配置されているため配置不可")
            return False
        
        # 教師重複の事前チェックを強化
        if teacher:
            # 同じ時間に他のクラスで教えているかチェック
            for c in school.get_all_classes():
                if c == class_ref:
                    continue
                existing = schedule.get_assignment(slot, c)
                if existing and existing.teacher and existing.teacher.name == teacher.name:
                    # 5組の合同授業は許可
                    if not (existing.class_ref.class_number == 5 and class_ref.class_number == 5):
                        return False
        
        # 制約チェック
        temp_assignment = Assignment(class_ref, subject, teacher)
        
        # 井上先生と白石先生の火曜5限デバッグ
        if teacher and teacher.name in ["井上", "白石"] and slot.day == "火" and slot.period == 5:
            self.logger.warning(f"{teacher.name}先生の火曜5限配置を制約チェック中: {class_ref}")
        
        result = self.constraint_validator.check_assignment(schedule, school, slot, temp_assignment)
        
        if teacher and teacher.name in ["井上", "白石"] and slot.day == "火" and slot.period == 5:
            self.logger.warning(f"{teacher.name}先生の火曜5限制約チェック結果: {result}")
        
        return result
    
    def evaluate_slot_for_subject(self, slot: TimeSlot, subject: Subject) -> float:
        """教科に対するスロットの評価"""
        score = 0.0
        
        # CSP設定からパラメータを取得
        csp_params = self.csp_config.get_all_parameters()
        pe_preferred_day = csp_params.get('pe_preferred_day', "火")
        main_subjects = csp_params.get('main_subjects', ["国", "数", "英", "理", "社"])
        main_subjects_preferred_periods = csp_params.get('main_subjects_preferred_periods', [1, 2, 3])
        skill_subjects = csp_params.get('skill_subjects', ["音", "美", "技", "家"])
        skill_subjects_preferred_periods = csp_params.get('skill_subjects_preferred_periods', [4, 5, 6])
        
        # 体育は火曜日を優先
        if subject.name == "保" and slot.day == pe_preferred_day:
            score -= 20
        
        # 主要教科は午前中を優先
        if subject.name in main_subjects and slot.period in main_subjects_preferred_periods:
            score -= 10
        
        # 技能教科は午後でも可
        if subject.name in skill_subjects and slot.period in skill_subjects_preferred_periods:
            score -= 5
        
        return score
    
    def _is_teacher_available(self, teacher: Teacher, slot: TimeSlot,
                            schedule: Schedule, school: School) -> bool:
        """教師が利用可能かチェック"""
        if not teacher:
            return True

        # スケジュール上で教師が空いているか確認
        if not schedule.is_teacher_available(slot, teacher):
            return False

        # 不在情報
        if self.absence_repository.is_teacher_absent(teacher.name, slot.day, slot.period):
            return False
        
        # 学校の制約
        if school.is_teacher_unavailable(slot.day, slot.period, teacher):
            return False
        
        return True
    
    def _get_candidate_slots(self, schedule: Schedule, school: School,
                            class_ref: ClassReference) -> List[TimeSlot]:
        """配置候補のスロットを取得"""
        candidates = []
        
        # CSP設定からパラメータを取得
        csp_params = self.csp_config.get_all_parameters()
        weekdays = csp_params.get('weekdays', ["月", "火", "水", "木", "金"])
        periods_min = csp_params.get('periods_min', 1)
        periods_max = csp_params.get('periods_max', 6)
        
        for day in weekdays:
            for period in range(periods_min, periods_max + 1):
                slot = TimeSlot(day, period)
                
                # テスト期間チェックを追加
                if (day, period) in self.test_periods:
                    continue  # テスト期間はスキップ
                
                # 固定制約チェック
                if day == "月" and period == 6:
                    continue
                
                # 配置可能かチェック
                if (not schedule.get_assignment(slot, class_ref) and
                    not schedule.is_locked(slot, class_ref)):
                    candidates.append(slot)
        
        return candidates
    
    def _sync_exchange_class_if_needed(self, schedule: Schedule, school: School,
                                       class_ref: ClassReference, time_slot: TimeSlot,
                                       assignment: Assignment) -> None:
        """必要に応じて交流学級を同期"""
        # 親学級の場合、交流学級も同じ科目にする
        if class_ref in self.parent_to_exchange:
            exchange_class = self.parent_to_exchange[class_ref]
            
            # 交流学級が存在しない場合はスキップ
            if exchange_class not in school.get_all_classes():
                return
            
            # ロックされている場合はスキップ
            if schedule.is_locked(time_slot, exchange_class):
                return
            
            exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
            
            # 交流学級が自立活動の場合はスキップ（同期不要）
            if exchange_assignment and exchange_assignment.subject.name in {"自立", "日生", "作業"}:
                return
            
            # 交流学級が空きまたは異なる科目の場合
            if not exchange_assignment or exchange_assignment.subject != assignment.subject:
                # 固定科目は同期しない
                fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
                if assignment.subject.name in fixed_subjects:
                    return
                
                # 日内重複チェック
                if self._would_cause_daily_duplicate(schedule, exchange_class, time_slot, assignment.subject):
                    self.logger.debug(f"交流学級{exchange_class}で日内重複が発生するため同期をスキップ")
                    return
                
                # 交流学級に同じ科目を配置
                exchange_teacher = school.get_assigned_teacher(assignment.subject, exchange_class)
                if not exchange_teacher:
                    # 親学級の教師を使用
                    exchange_teacher = assignment.teacher
                
                if exchange_teacher and self.constraint_validator.check_assignment(
                    schedule, school, time_slot, 
                    Assignment(exchange_class, assignment.subject, exchange_teacher)
                ):
                    new_assignment = Assignment(exchange_class, assignment.subject, exchange_teacher)
                    if exchange_assignment:
                        schedule.remove_assignment(time_slot, exchange_class)
                    try:
                        schedule.assign(time_slot, new_assignment)
                        self.logger.info(f"交流学級を同期: {exchange_class} {time_slot} → {assignment.subject.name}")
                    except ValueError as e:
                        self.logger.debug(f"交流学級の同期に失敗: {e}")
    
    def _would_cause_daily_duplicate(self, schedule: Schedule, class_ref: ClassReference,
                                    time_slot: TimeSlot, subject: Subject) -> bool:
        """日内重複が発生するかチェック"""
        # 固定科目は日内重複を許可
        fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
        if subject.name in fixed_subjects:
            return False
        
        # 同じ日の他の時間に同じ科目があるかチェック
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            check_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(check_slot, class_ref)
            if assignment and assignment.subject == subject:
                return True
        
        return False
    
    def _fix_existing_daily_duplicates(self, schedule: Schedule, school: School) -> None:
        """既存の日内重複を修正"""
        fixed_subjects = {"欠", "YT", "道", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト", "技家"}
        
        for class_ref in school.get_all_classes():
            # 交流学級は親学級との同期で処理するのでスキップ
            if class_ref.class_number in [6, 7]:
                continue
                
            for day in ["月", "火", "水", "木", "金"]:
                # その日の科目をカウント
                subject_periods = {}
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in fixed_subjects:
                        if assignment.subject.name not in subject_periods:
                            subject_periods[assignment.subject.name] = []
                        subject_periods[assignment.subject.name].append((time_slot, assignment))
                
                # 重複している科目を修正
                for subject_name, slot_assignments in subject_periods.items():
                    if len(slot_assignments) > 1:
                        self.logger.warning(f"{class_ref}の{day}曜日に{subject_name}が{len(slot_assignments)}回重複")
                        
                        # 最初の授業以外を削除（ロックされていないもののみ）
                        for i in range(1, len(slot_assignments)):
                            slot, assignment = slot_assignments[i]
                            if not schedule.is_locked(slot, class_ref):
                                schedule.remove_assignment(slot, class_ref)
                                self.logger.info(f"日内重複を削除: {class_ref} {slot} {subject_name}")
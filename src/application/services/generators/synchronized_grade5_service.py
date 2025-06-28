"""5組同期サービスの実装"""
import logging
from typing import List, Dict, Optional

from ....domain.interfaces.grade5_synchronization_service import Grade5SynchronizationService
from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Subject
from ....domain.value_objects.assignment import Assignment
from ....domain.interfaces.csp_configuration import ICSPConfiguration


class SynchronizedGrade5Service(Grade5SynchronizationService):
    """5組同期サービス"""
    
    def __init__(self, csp_config: ICSPConfiguration = None, constraint_validator = None):
        # 依存性注入
        if csp_config is None:
            from ....infrastructure.di_container import get_csp_configuration
            csp_config = get_csp_configuration()
            
        self.csp_config = csp_config
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
    
    def get_common_subjects(self, school: School, grade5_classes: List[ClassReference]) -> Dict[Subject, int]:
        """共通教科と必要時間数を取得"""
        common_subjects = {}
        
        # 各クラスの必要教科を収集
        class_subjects = {}
        for class_ref in grade5_classes:
            subjects = {}
            for subject in school.get_required_subjects(class_ref):
                if not subject.is_protected_subject():
                    hours = int(round(school.get_standard_hours(class_ref, subject)))
                    if hours > 0:
                        subjects[subject] = hours
            class_subjects[class_ref] = subjects
        
        # 共通教科を抽出
        if class_subjects:
            first_class_subjects = list(class_subjects.values())[0]
            for subject, hours in first_class_subjects.items():
                if all(subject in cs and cs[subject] == hours 
                      for cs in class_subjects.values()):
                    common_subjects[subject] = hours
        
        return common_subjects
    
    def synchronize_placement(self, schedule: Schedule, school: School) -> int:
        """5組の同期配置を実行"""
        self.logger.info("5組の同期配置を開始")
        
        # CSP設定からgrade5クラスを取得
        csp_params = self.csp_config.get_all_parameters()
        grade5_classes = csp_params.get('grade5_classes', [
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        ])
        total_placed = 0
        
        # デバッグ: 開始時の5組テスト期間データを確認
        test_period_count = 0
        test_periods_map = {("月", 1), ("月", 2), ("月", 3), ("火", 1), ("火", 2), ("火", 3), ("水", 1), ("水", 2)}
        for day, period in test_periods_map:
            time_slot = TimeSlot(day, period)
            for class_ref in grade5_classes:
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    test_period_count += 1
                    self.logger.info(f"[5組同期開始時] {time_slot} {class_ref}: {assignment.subject.name}")
        self.logger.info(f"[5組同期開始時] テスト期間データ数: {test_period_count}")
        
        # 共通教科を収集
        common_subjects = self.get_common_subjects(school, grade5_classes)
        
        for subject, required_hours in common_subjects.items():
            # 体育は同期から除外
            # 除外科目をチェック
            excluded_subjects = csp_params.get('excluded_sync_subjects', ["保", "保健体育"])
            if subject.name in excluded_subjects:
                continue
            
            placed_hours = self.count_placed_hours(schedule, grade5_classes, subject)
            self.logger.debug(f"5組同期: {subject.name} - 必要時数: {required_hours}, 配置済み: {placed_hours}")
            
            for _ in range(required_hours - placed_hours):
                slot = self.find_best_slot_for_grade5(schedule, school, grade5_classes, subject)
                if slot:
                    # デバッグ: テスト期間への配置を検出
                    if (slot.day, slot.period) in test_periods_map:
                        self.logger.warning(f"[警告] テスト期間 {slot} に {subject.name} を配置しようとしています")
                    
                    # 全5組に同時配置
                    success = True
                    assignments = []
                    
                    for class_ref in grade5_classes:
                        teacher = school.get_assigned_teacher(subject, class_ref)
                        if teacher:
                            assignment = Assignment(class_ref, subject, teacher)
                            if self.constraint_validator.check_assignment(schedule, school, slot, assignment):
                                assignments.append((slot, assignment))
                            else:
                                success = False
                                break
                        else:
                            success = False
                            break
                    
                    if success:
                        for slot, assignment in assignments:
                            schedule.assign(slot, assignment)
                        total_placed += len(assignments)
                        self.logger.debug(f"{slot}: 5組に{subject.name}を同期配置")
        
        # デバッグ: 終了時の5組テスト期間データを確認
        test_period_count_after = 0
        for day, period in test_periods_map:
            time_slot = TimeSlot(day, period)
            for class_ref in grade5_classes:
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    test_period_count_after += 1
                    self.logger.info(f"[5組同期終了時] {time_slot} {class_ref}: {assignment.subject.name}")
        self.logger.info(f"[5組同期終了時] テスト期間データ数: {test_period_count_after}")
        
        return total_placed
    
    def find_best_slot_for_grade5(self, schedule: Schedule, school: School,
                                  classes: List[ClassReference], subject: Subject) -> Optional[TimeSlot]:
        """5組の最適なスロットを探索"""
        best_slot = None
        best_score = float('inf')
        
        # CSP設定からパラメータを取得
        csp_params = self.csp_config.get_all_parameters()
        weekdays = csp_params.get('weekdays', ["月", "火", "水", "木", "金"])
        periods_min = csp_params.get('periods_min', 1)
        periods_max = csp_params.get('periods_max', 6)
        
        for day in weekdays:
            for period in range(periods_min, periods_max + 1):
                slot = TimeSlot(day, period)
                
                # 固定制約チェック
                if day == "月" and period == 6:
                    continue
                
                # 全クラスで利用可能か
                all_available = True
                for class_ref in classes:
                    # すでに割り当てがある場合はスキップ
                    if schedule.get_assignment(slot, class_ref):
                        all_available = False
                        break
                    
                    # ロックされているセルはスキップ（テスト期間保護を含む）
                    if schedule.is_locked(slot, class_ref):
                        all_available = False
                        self.logger.debug(f"{slot} {class_ref} はロックされているためスキップ")
                        break
                    
                    # 日内重複チェック
                    if self._has_subject_on_day(schedule, class_ref, slot.day, subject):
                        all_available = False
                        break
                    
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    if not self._is_teacher_available(teacher, slot, schedule, school):
                        all_available = False
                        break
                
                if all_available:
                    score = self._evaluate_slot_for_subject(slot, subject)
                    if score < best_score:
                        best_score = score
                        best_slot = slot
        
        return best_slot
    
    def count_placed_hours(self, schedule: Schedule, classes: List[ClassReference],
                          subject: Subject) -> int:
        """配置済み時間数をカウント"""
        count = 0
        checked_slots = set()
        
        for slot, assignment in schedule.get_all_assignments():
            if (assignment.class_ref in classes and 
                assignment.subject == subject and 
                slot not in checked_slots):
                # 全5組が同じ時間に配置されているか確認
                all_have_subject = all(
                    schedule.get_assignment(slot, c) and 
                    schedule.get_assignment(slot, c).subject == subject
                    for c in classes
                )
                if all_have_subject:
                    count += 1
                    checked_slots.add(slot)
        
        return count
    
    def _is_teacher_available(self, teacher, slot: TimeSlot, schedule: Schedule, school: School) -> bool:
        """教師が利用可能かチェック"""
        if not teacher:
            return False
        
        # スケジュール上の重複チェックを削除
        # 理由: Grade5クラスは同じ教師が同時に3クラスを担当することが正常な運用であるため、
        # schedule.is_teacher_available()による単純な重複チェックは不適切
        
        # 学校の制約
        if school.is_teacher_unavailable(slot.day, slot.period, teacher):
            return False
        
        return True
    
    def _has_subject_on_day(self, schedule: Schedule, class_ref: ClassReference, day: str, subject: Subject) -> bool:
        """指定日に指定科目が既に配置されているかチェック"""
        # 保護教科は日内重複を許可
        protected_subjects = {'YT', '道', '学', '欠', '道徳', '学活', '学総', '総合', '行'}
        if subject.name in protected_subjects:
            return False
        
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                return True
        return False
    
    def _evaluate_slot_for_subject(self, slot: TimeSlot, subject: Subject) -> float:
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
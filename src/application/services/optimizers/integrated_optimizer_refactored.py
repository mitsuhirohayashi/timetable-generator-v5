"""統合最適化サービス（リファクタリング版）

重複コードを削除し、既存のサービスに処理を委譲することで
責任を明確に分離した改良版です。
"""
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Subject
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment
from ....domain.interfaces.followup_parser import IFollowUpParser
from ....domain.services.synchronizers.exchange_class_service import ExchangeClassService
from ....domain.services.validators.unified_constraint_validator import UnifiedConstraintValidator
from ....domain.utils.schedule_utils import ScheduleUtils


class IntegratedOptimizerRefactored:
    """統合最適化サービス（リファクタリング版）
    
    主な改善点:
    1. ExchangeClassServiceに交流学級処理を委譲
    2. UnifiedConstraintValidatorに制約チェックを委譲
    3. ScheduleUtilsに共通処理を委譲
    4. 重複コードの削除
    """
    
    def __init__(self, followup_parser: IFollowUpParser = None):
        self.logger = logging.getLogger(__name__)
        
        # 委譲するサービス
        self.exchange_service = ExchangeClassService()
        self.constraint_validator = UnifiedConstraintValidator()
        
        # 固定科目
        self.fixed_subjects = ScheduleUtils.FIXED_SUBJECTS
        
        # 優先配置科目（標準時数が多い順）
        self.priority_subjects = ["国", "数", "英", "理", "社", "保", "音", "美", "技", "家"]
        
        # 5組クラス
        self.grade5_classes = set()
        self._load_grade5_classes()
        
        # テスト期間
        self._load_test_periods(followup_parser)
    
    def _load_grade5_classes(self):
        """5組クラスを読み込む"""
        import re
        for class_str in ScheduleUtils.get_grade5_classes():
            match = re.match(r'(\d+)年(\d+)組', class_str)
            if match:
                self.grade5_classes.add(ClassReference(int(match.group(1)), int(match.group(2))))
    
    def _load_test_periods(self, followup_parser: IFollowUpParser):
        """テスト期間を読み込み（UnifiedConstraintValidatorから取得）"""
        self.test_periods = self.constraint_validator.test_periods
    
    def optimize_schedule(self, schedule: Schedule, school: School) -> Dict[str, int]:
        """スケジュールを包括的に最適化"""
        self.logger.info("=== 統合最適化を開始（リファクタリング版） ===")
        
        results = {
            'empty_slots_filled': 0,
            'standard_hours_improved': 0,
            'test_periods_protected': len(self.test_periods),
            'violations_before': 0,
            'violations_after': 0,
            'exchange_sync_fixed': 0
        }
        
        # 初期状態の分析
        initial_analysis = self._analyze_schedule(schedule, school)
        results['violations_before'] = initial_analysis['total_violations']
        
        self.logger.info(f"初期状態: 空きコマ={initial_analysis['empty_slots']}個, "
                        f"標準時数違反={initial_analysis['hour_violations']}件, "
                        f"交流学級同期違反={initial_analysis['exchange_violations']}件")
        
        # Step 1: テスト期間の保護（最優先）
        self._protect_test_periods(schedule)
        
        # Step 2: 交流学級の同期を修正
        sync_fixed = self._fix_exchange_class_sync(schedule, school)
        results['exchange_sync_fixed'] = sync_fixed
        
        # Step 3: 空きコマを埋める（交流学級同期を考慮）
        filled = self._fill_empty_slots(schedule, school)
        results['empty_slots_filled'] = filled
        
        # Step 4: 標準時数の最適化
        improved = self._optimize_standard_hours(schedule, school)
        results['standard_hours_improved'] = improved
        
        # 最終分析
        final_analysis = self._analyze_schedule(schedule, school)
        results['violations_after'] = final_analysis['total_violations']
        
        self.logger.info(f"=== 統合最適化完了: "
                        f"空きコマ埋め={results['empty_slots_filled']}個, "
                        f"標準時数改善={results['standard_hours_improved']}件, "
                        f"交流学級同期修正={results['exchange_sync_fixed']}件 ===")
        
        return results
    
    def _analyze_schedule(self, schedule: Schedule, school: School) -> Dict[str, int]:
        """スケジュールの現状を分析"""
        analysis = {
            'empty_slots': 0,
            'hour_violations': 0,
            'exchange_violations': 0,
            'total_violations': 0
        }
        
        # 空きコマをカウント
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        analysis['empty_slots'] += 1
        
        # 標準時数違反をカウント
        for class_ref in school.get_all_classes():
            current_hours = self._count_current_hours(schedule, class_ref)
            for subject in self._get_subjects_for_class(school, class_ref):
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject, 0)
                if standard > 0 and current < standard:
                    analysis['hour_violations'] += 1
        
        # 交流学級同期違反をカウント（ExchangeClassServiceに委譲）
        exchange_violations = self.exchange_service.get_exchange_violations(schedule)
        analysis['exchange_violations'] = len(exchange_violations)
        
        analysis['total_violations'] = (analysis['empty_slots'] + 
                                       analysis['hour_violations'] + 
                                       analysis['exchange_violations'])
        return analysis
    
    def _fix_exchange_class_sync(self, schedule: Schedule, school: School) -> int:
        """交流学級の同期違反を修正"""
        fixed_count = 0
        
        # ExchangeClassServiceから全ての交流学級ペアを取得
        for exchange_class in self.exchange_service.get_all_exchange_classes():
            parent_class = self.exchange_service.get_parent_class(exchange_class)
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, exchange_class):
                        continue
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 同期が必要かExchangeClassServiceで判定
                    valid, error_msg = self.exchange_service.validate_exchange_sync(
                        exchange_assignment, parent_assignment, time_slot
                    )
                    
                    if not valid and parent_assignment:
                        # ExchangeClassServiceを使って同期
                        if self.exchange_service.sync_exchange_with_parent(
                            schedule, school, time_slot, parent_class, parent_assignment
                        ):
                            fixed_count += 1
        
        return fixed_count
    
    def _protect_test_periods(self, schedule: Schedule):
        """テスト期間を保護（ロック）"""
        protected_count = 0
        
        # 全ての割り当てからクラスを抽出
        all_classes = set()
        for _, assignment in schedule.get_all_assignments():
            all_classes.add(assignment.class_ref)
        
        for day, period in self.test_periods:
            time_slot = TimeSlot(day, period)
            
            for class_ref in all_classes:
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and not schedule.is_locked(time_slot, class_ref):
                    schedule.lock_cell(time_slot, class_ref)
                    protected_count += 1
        
        if protected_count > 0:
            self.logger.info(f"テスト期間を{protected_count}セル保護しました")
    
    def _fill_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きコマを適切に埋める"""
        filled_count = 0
        
        # 親学級を優先的に処理（交流学級の同期のため）
        all_classes = list(school.get_all_classes())
        parent_classes = [c for c in all_classes if self.exchange_service.is_parent_class(c)]
        exchange_classes = [c for c in all_classes if self.exchange_service.is_exchange_class(c)]
        other_classes = [c for c in all_classes if c not in parent_classes and c not in exchange_classes]
        
        # 処理順序：親学級 → その他 → 交流学級
        ordered_classes = parent_classes + other_classes + exchange_classes
        
        for class_ref in ordered_classes:
            # 現在の時数をカウント
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # 不足している科目を優先度順にソート
            needed_subjects = self._get_needed_subjects(school, class_ref, current_hours)
            
            # 空きコマに配置
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 既に埋まっているかロックされている場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref) or schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    # 配置する科目を選択
                    for subject, shortage, _ in needed_subjects:
                        if shortage <= 0:
                            continue
                        
                        teacher = school.get_assigned_teacher(subject, class_ref)
                        if not teacher and self.exchange_service.is_exchange_class(class_ref):
                            # 交流学級の場合、親学級の教師を使用
                            parent_class = self.exchange_service.get_parent_class(class_ref)
                            teacher = school.get_assigned_teacher(subject, parent_class)
                        
                        if teacher:
                            assignment = Assignment(class_ref, subject, teacher)
                            
                            # UnifiedConstraintValidatorで配置可能かチェック
                            can_place, error_msg = self.constraint_validator.can_place_assignment(
                                schedule, school, time_slot, assignment, 'normal'
                            )
                            
                            if can_place:
                                if schedule.assign(time_slot, assignment):
                                    filled_count += 1
                                    current_hours[subject] = current_hours.get(subject, 0) + 1
                                    
                                    # shortageを更新
                                    for i, (s, sh, p) in enumerate(needed_subjects):
                                        if s == subject:
                                            needed_subjects[i] = (s, sh - 1, p)
                                            break
                                    
                                    # 親学級の場合、交流学級も同期
                                    if self.exchange_service.is_parent_class(class_ref):
                                        self.exchange_service.sync_exchange_with_parent(
                                            schedule, school, time_slot, class_ref, assignment
                                        )
                                    
                                    self.logger.info(f"空きコマを埋めました: {class_ref} {time_slot} → {subject.name}")
                                    break
        
        self.logger.info(f"空きコマ埋め完了: {filled_count}個を埋めました")
        return filled_count
    
    def _get_needed_subjects(self, school: School, class_ref: ClassReference, current_hours: Dict[Subject, float]) -> List[Tuple[Subject, int, int]]:
        """必要な科目を優先度順に取得"""
        needed_subjects = []
        
        for subject in self._get_subjects_for_class(school, class_ref):
            # 固定科目は空きスロット埋めに使用しない
            if subject.name in self.fixed_subjects:
                continue
            
            standard = school.get_standard_hours(class_ref, subject)
            current = current_hours.get(subject, 0)
            
            if current < standard:
                shortage = standard - current
                priority = self.priority_subjects.index(subject.name) if subject.name in self.priority_subjects else 99
                needed_subjects.append((subject, shortage, priority))
        
        # 不足数が多く、優先度が高い順にソート
        needed_subjects.sort(key=lambda x: (x[1], -x[2]), reverse=True)
        return needed_subjects
    
    def _optimize_standard_hours(self, schedule: Schedule, school: School) -> int:
        """標準時数を最適化"""
        improvements = 0
        
        # 各クラスで最適化
        for class_ref in school.get_all_classes():
            # 交流学級と5組は特殊処理が必要なのでスキップ
            if self.exchange_service.is_exchange_class(class_ref) or class_ref in self.grade5_classes:
                continue
            
            # 現在の時数をカウント
            current_hours = self._count_current_hours(schedule, class_ref)
            
            # 不足と過剰を分析
            shortages = []
            excesses = []
            
            for subject in self._get_subjects_for_class(school, class_ref):
                standard = school.get_standard_hours(class_ref, subject)
                current = current_hours.get(subject, 0)
                
                if standard > 0:
                    diff = current - standard
                    if diff < 0:
                        shortages.append((subject, -diff))
                    elif diff > 0:
                        excesses.append((subject, diff))
            
            # 過剰な科目を不足している科目に置換
            for shortage_subject, shortage_amount in shortages:
                for excess_subject, excess_amount in excesses:
                    if shortage_amount <= 0 or excess_amount <= 0:
                        continue
                    
                    # 置換を試みる
                    swaps = self._try_swap_subjects(
                        schedule, school, class_ref,
                        excess_subject, shortage_subject,
                        min(shortage_amount, excess_amount)
                    )
                    
                    if swaps > 0:
                        improvements += swaps
                        # 更新
                        for i, (s, a) in enumerate(shortages):
                            if s == shortage_subject:
                                shortages[i] = (s, a - swaps)
                        for i, (s, a) in enumerate(excesses):
                            if s == excess_subject:
                                excesses[i] = (s, a - swaps)
        
        return improvements
    
    def _count_current_hours(self, schedule: Schedule, class_ref: ClassReference) -> Dict[Subject, float]:
        """現在の時数をカウント"""
        current_hours = defaultdict(float)
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if assignment:
                    if assignment.subject.name == "技家":
                        current_hours[Subject("技")] += 0.5
                        current_hours[Subject("家")] += 0.5
                    else:
                        current_hours[assignment.subject] += 1.0
        
        return dict(current_hours)
    
    def _get_subjects_for_class(self, school: School, class_ref: ClassReference) -> List[Subject]:
        """クラスの科目リストを取得"""
        subjects = set()
        
        # 主要科目
        main_subjects = ["国", "数", "英", "理", "社", "保", "音", "美", "技", "家"]
        for subject_name in main_subjects:
            subject = Subject(subject_name)
            if school.get_standard_hours(class_ref, subject) > 0:
                subjects.add(subject)
        
        # 特別科目（交流学級用）
        if self.exchange_service.is_exchange_class(class_ref):
            special_subjects = ["自立", "日生", "作業"]
            for subject_name in special_subjects:
                subject = Subject(subject_name)
                if school.get_standard_hours(class_ref, subject) > 0:
                    subjects.add(subject)
        
        return list(subjects)
    
    def _try_swap_subjects(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        from_subject: Subject,
        to_subject: Subject,
        max_swaps: int
    ) -> int:
        """科目を入れ替える"""
        swapped = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                if swapped >= max_swaps:
                    return swapped
                
                time_slot = TimeSlot(day, period)
                
                # ロックされたセルはスキップ
                if schedule.is_locked(time_slot, class_ref):
                    continue
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject == from_subject:
                    # to_subjectの教師を取得
                    teacher = school.get_assigned_teacher(to_subject, class_ref)
                    if teacher:
                        new_assignment = Assignment(class_ref, to_subject, teacher)
                        
                        # 配置可能かチェック
                        can_place, _ = self.constraint_validator.can_place_assignment(
                            schedule, school, time_slot, new_assignment, 'normal'
                        )
                        
                        if can_place:
                            # 一時的に削除
                            schedule.remove_assignment(time_slot, class_ref)
                            
                            # 新しい割り当て
                            if schedule.assign(time_slot, new_assignment):
                                swapped += 1
                                self.logger.debug(f"{class_ref} {time_slot}: {from_subject.name} → {to_subject.name}")
                                
                                # 親学級の場合、交流学級も同期
                                if self.exchange_service.is_parent_class(class_ref):
                                    self.exchange_service.sync_exchange_with_parent(
                                        schedule, school, time_slot, class_ref, new_assignment
                                    )
                            else:
                                # 失敗したら元に戻す
                                schedule.assign(time_slot, assignment)
        
        return swapped
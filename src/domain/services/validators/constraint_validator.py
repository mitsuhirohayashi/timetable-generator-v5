"""改良版統一制約検証サービス

配置前の制約チェックを強化し、キャッシング機能を追加して効率化を図ります。
"""
import logging
from typing import Optional, Set, Dict, List, Tuple, Any
from collections import defaultdict
from functools import lru_cache

from ...entities.schedule import Schedule
from ...entities.school import School, Subject, Teacher
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ..synchronizers.exchange_class_service import ExchangeClassService
from ...utils.schedule_utils import ScheduleUtils
from ....shared.mixins.logging_mixin import LoggingMixin
from ..grade5_teacher_mapping_service import Grade5TeacherMappingService


class ConstraintValidatorImproved(LoggingMixin):
    """改良版統一制約検証サービス"""
    
    def __init__(self, absence_loader=None):
        """初期化
        
        Args:
            absence_loader: 教師不在情報ローダー
        """
        super().__init__()
        self.exchange_service = ExchangeClassService()
        self.grade5_teacher_service = Grade5TeacherMappingService()
        
        # 教師の欠席情報
        self.teacher_absences: Dict[str, Set[Tuple[str, int]]] = {}
        if absence_loader and hasattr(absence_loader, 'teacher_absences'):
            self.teacher_absences = absence_loader.teacher_absences
        
        # 5組クラスの設定
        self._load_grade5_classes()
        
        # テスト期間の設定
        self._load_test_periods()
        
        # キャッシュの初期化
        self._cache_teacher_availability: Dict[Tuple[str, str, int], bool] = {}
        self._cache_daily_counts: Dict[Tuple[Any, str, str], int] = {}
        self._cache_validation_results: Dict[str, Tuple[bool, Optional[str]]] = {}
        
        # 学習ルールサービスの初期化
        self._load_learned_rules()
    
    def _load_grade5_classes(self) -> None:
        """5組クラスを読み込む"""
        import re
        grade5_list = ScheduleUtils.get_grade5_classes()
        self.grade5_classes = set()
        
        for class_str in grade5_list:
            # "1年5組" -> ClassReference(1, 5)
            class_match = re.match(r'(\d+)年(\d+)組', class_str)
            if class_match:
                self.grade5_classes.add(ClassReference(int(class_match.group(1)), int(class_match.group(2))))
    
    def _load_test_periods(self) -> None:
        """テスト期間を読み込む"""
        self.test_periods: Set[Tuple[str, int]] = set()
        try:
            from ....infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
            test_periods_list = followup_parser.parse_test_periods()
            
            for test_period in test_periods_list:
                if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
                    day = test_period.day
                    for period in test_period.periods:
                        self.test_periods.add((day, period))
            
            if self.test_periods:
                self.logger.info(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
        except Exception as e:
            self.logger.warning(f"テスト期間情報の読み込みに失敗: {e}")
    
    def _load_learned_rules(self) -> None:
        """学習ルールを読み込む"""
        self.learned_rules: Dict[str, Dict[Tuple[str, int], int]] = {}
        
        # ハードコードされた学習ルール（QA.txtの恒久ルールから）
        # 井上先生は火曜5限に最大1クラスまで
        self.learned_rules['井上'] = {('火', 5): 1}
        
        # 白石先生は火曜5限に最大1クラス（理科実験室の制約）
        self.learned_rules['白石'] = {('火', 5): 1}
        
        self.logger.info(f"学習ルールを{len(self.learned_rules)}件読み込みました")
        
        try:
            # QandAシステムから追加の学習ルールを読み込む
            from ...application.services.learned_rule_application_service import LearnedRuleApplicationService
            learned_service = LearnedRuleApplicationService()
            
            # 追加のルールがあれば統合
            if hasattr(learned_service, 'get_teacher_time_limits'):
                additional_rules = learned_service.get_teacher_time_limits()
                for teacher, rules in additional_rules.items():
                    if teacher not in self.learned_rules:
                        self.learned_rules[teacher] = {}
                    self.learned_rules[teacher].update(rules)
                self.logger.info(f"追加の学習ルールを統合しました")
        except Exception as e:
            self.logger.debug(f"追加の学習ルール読み込みをスキップ: {e}")
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self._cache_teacher_availability.clear()
        self._cache_daily_counts.clear()
        self._cache_validation_results.clear()
    
    def can_place_assignment(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        assignment: Assignment,
        check_level: str = 'strict'
    ) -> Tuple[bool, Optional[str]]:
        """指定された割り当てが配置可能かどうか総合的にチェック（キャッシュ付き）
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: 配置する時間枠
            assignment: 配置する割り当て
            check_level: チェックレベル ('strict', 'normal', 'relaxed')
            
        Returns:
            (配置可能か, エラーメッセージ)
        """
        # キャッシュキーの生成
        cache_key = f"{time_slot.day}_{time_slot.period}_{assignment.class_ref}_{assignment.subject.name}_{assignment.teacher.name if assignment.teacher else 'None'}_{check_level}"
        
        # キャッシュチェック
        if cache_key in self._cache_validation_results:
            return self._cache_validation_results[cache_key]
        
        # 実際の検証処理
        result = self._perform_validation(schedule, school, time_slot, assignment, check_level)
        
        # 結果をキャッシュ
        self._cache_validation_results[cache_key] = result
        
        return result
    
    def _perform_validation(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        assignment: Assignment,
        check_level: str
    ) -> Tuple[bool, Optional[str]]:
        """実際の検証処理"""
        # 基本的なチェック
        if schedule.is_locked(time_slot, assignment.class_ref):
            return False, "このスロットはロックされています"
        
        # 既に割り当てがある場合
        existing = schedule.get_assignment(time_slot, assignment.class_ref)
        if existing:
            return False, "既に割り当てがあります"
        
        # テスト期間チェック
        if self.is_test_period(time_slot):
            return False, "テスト期間です"
        
        # 教師不在チェック（キャッシュ付き）
        if not self.check_teacher_availability_cached(assignment.teacher, time_slot):
            return False, f"{assignment.teacher.name}先生は不在です"
        
        # 5組の教師割り当てチェック
        if assignment.class_ref in self.grade5_classes and assignment.teacher:
            if not self.grade5_teacher_service.validate_teacher_assignment(
                str(assignment.class_ref), 
                assignment.subject.name, 
                assignment.teacher.name
            ):
                expected_teacher = self.grade5_teacher_service.get_teacher_for_subject(assignment.subject.name)
                return False, f"5組の{assignment.subject.name}は{expected_teacher}先生が担当する必要があります"
        
        # 教師重複チェック（5組の合同授業と学習ルールを考慮）
        conflict_class = self.check_teacher_conflict_with_rules(schedule, school, time_slot, assignment)
        if conflict_class:
            return False, f"{assignment.teacher.name}先生は{conflict_class}で授業があります"
        
        # 日内重複チェック（キャッシュ付き）
        if check_level in ['strict', 'normal']:
            duplicate_count = self.get_daily_subject_count_cached(schedule, assignment.class_ref, time_slot.day, assignment.subject)
            max_allowed = self.get_max_daily_occurrences(assignment.subject, check_level)
            if duplicate_count >= max_allowed:
                return False, f"{assignment.subject.name}は既に{duplicate_count}回配置されています"
        
        # 体育館使用チェック
        if assignment.subject.name == "保":
            gym_class = self.check_gym_conflict(schedule, school, time_slot, assignment.class_ref)
            if gym_class:
                return False, f"体育館は{gym_class}が使用中です"
        
        # 交流学級制約チェック
        if self.exchange_service.is_exchange_class(assignment.class_ref):
            # 自立活動を配置する場合は、親学級が数学・英語であることを事前チェック
            if self.exchange_service.is_jiritsu_activity(assignment.subject.name):
                if not self.exchange_service.can_place_jiritsu_for_exchange_class(
                    schedule, time_slot, assignment.class_ref
                ):
                    return False, "交流学級に自立活動を配置できません（親学級が数学・英語ではありません）"
            elif not self.exchange_service.can_place_subject_for_exchange_class(
                schedule, time_slot, assignment.class_ref, assignment.subject
            ):
                return False, "交流学級の制約に違反します"
        
        # 親学級制約チェック
        if self.exchange_service.is_parent_class(assignment.class_ref):
            # 親学級の科目を変更する場合は、交流学級が自立活動でないことを確認
            if not self.exchange_service.can_change_parent_class_subject(
                schedule, time_slot, assignment.class_ref, assignment.subject
            ):
                return False, "親学級の科目を変更できません（交流学級が自立活動中）"
            elif not self.exchange_service.can_place_subject_for_parent_class(
                schedule, time_slot, assignment.class_ref, assignment.subject
            ):
                return False, "親学級の制約に違反します"
        
        # 5組同期チェック
        if assignment.class_ref in self.grade5_classes:
            sync_error = self.check_grade5_sync(schedule, time_slot, assignment)
            if sync_error:
                return False, sync_error
        
        return True, None
    
    def check_teacher_availability_cached(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師が指定された時間に利用可能かチェック（キャッシュ付き）"""
        if not teacher:
            return True
        
        cache_key = (teacher.name, time_slot.day, time_slot.period)
        
        if cache_key in self._cache_teacher_availability:
            return self._cache_teacher_availability[cache_key]
        
        result = self.check_teacher_availability(teacher, time_slot)
        self._cache_teacher_availability[cache_key] = result
        
        return result
    
    def check_teacher_availability(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師が指定された時間に利用可能かチェック"""
        # Noneの場合は常に利用可能（固定科目等）
        if teacher is None:
            return True
        if teacher.name in self.teacher_absences:
            absences = self.teacher_absences[teacher.name]
            return (time_slot.day, time_slot.period) not in absences
        return True
    
    def check_teacher_conflict_with_rules(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        assignment: Assignment
    ) -> Optional[ClassReference]:
        """教師の重複をチェック（5組の合同授業と学習ルールを考慮）
        
        Returns:
            重複しているクラス（なければNone）
        """
        if not assignment.teacher:
            return None
        
        # 学習ルールチェック（例：井上先生の火曜5限は最大1クラス）
        if assignment.teacher.name in self.learned_rules:
            time_key = (time_slot.day, time_slot.period)
            if time_key in self.learned_rules[assignment.teacher.name]:
                max_classes = self.learned_rules[assignment.teacher.name][time_key]
                
                # 現在の配置数をカウント
                current_count = 0
                for class_ref in school.get_all_classes():
                    existing = schedule.get_assignment(time_slot, class_ref)
                    if existing and existing.teacher == assignment.teacher:
                        current_count += 1
                
                if current_count >= max_classes:
                    # 最初に見つかったクラスを返す
                    for class_ref in school.get_all_classes():
                        existing = schedule.get_assignment(time_slot, class_ref)
                        if existing and existing.teacher == assignment.teacher:
                            return class_ref
        
        # 5組の合同授業の場合は特別処理
        if assignment.class_ref in self.grade5_classes:
            # 他のクラスで同じ教師が同じ時間に授業しているかチェック
            classes_with_teacher = []
            for class_ref in school.get_all_classes():
                existing = schedule.get_assignment(time_slot, class_ref)
                if existing and existing.teacher == assignment.teacher:
                    classes_with_teacher.append(class_ref)
            
            # 5組以外のクラスがある場合は違反
            non_grade5_classes = [c for c in classes_with_teacher if c not in self.grade5_classes]
            if non_grade5_classes:
                return non_grade5_classes[0]  # 最初の5組以外のクラスを返す
            
            # 全て5組ならOK
            return None
        
        # 通常の重複チェック
        for class_ref in school.get_all_classes():
            if class_ref == assignment.class_ref:
                continue
            
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing and existing.teacher == assignment.teacher:
                # 5組同士の場合はOK
                if class_ref in self.grade5_classes and assignment.class_ref in self.grade5_classes:
                    continue
                return class_ref
        
        return None
    
    def get_daily_subject_count_cached(
        self, 
        schedule: Schedule, 
        class_ref: ClassReference, 
        day: str, 
        subject: Subject
    ) -> int:
        """指定された日のクラスにおける科目の出現回数を取得（キャッシュ付き）"""
        cache_key = (class_ref, day, subject.name)
        
        if cache_key in self._cache_daily_counts:
            return self._cache_daily_counts[cache_key]
        
        count = self.get_daily_subject_count(schedule, class_ref, day, subject)
        self._cache_daily_counts[cache_key] = count
        
        return count
    
    def get_daily_subject_count(
        self, 
        schedule: Schedule, 
        class_ref: ClassReference, 
        day: str, 
        subject: Subject
    ) -> int:
        """指定された日のクラスにおける科目の出現回数を取得"""
        count = 0
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject == subject:
                count += 1
        return count
    
    def get_max_daily_occurrences(self, subject: Subject, check_level: str) -> int:
        """科目の1日の最大出現回数を取得"""
        if check_level == 'relaxed':
            return 3  # 緩い制限
        elif check_level == 'normal':
            # 主要教科は2回まで許可
            if subject.name in {"算", "国", "理", "社", "英", "数"}:
                return 2
            return 1
        else:  # strict
            return 1
    
    def check_gym_conflict(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        target_class: ClassReference
    ) -> Optional[ClassReference]:
        """体育館の使用競合をチェック
        
        Returns:
            体育館を使用中のクラス（なければNone）
        """
        # テスト期間中は体育館制約なし
        if self.is_test_period(time_slot):
            return None
        
        # 5組の合同体育をチェック
        grade5_pe_classes = []
        for class_ref in self.grade5_classes:
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing and existing.subject.name == "保":
                grade5_pe_classes.append(class_ref)
        
        # 5組の体育がある場合
        if grade5_pe_classes:
            # 配置しようとしているのも5組なら許可
            if target_class in self.grade5_classes:
                return None
            # 5組以外なら競合
            return grade5_pe_classes[0]
        
        # 通常のチェック
        for class_ref in school.get_all_classes():
            if class_ref == target_class:
                continue
            
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing and existing.subject.name == "保":
                return class_ref
        
        return None
    
    def check_grade5_sync(
        self, 
        schedule: Schedule, 
        time_slot: TimeSlot, 
        assignment: Assignment
    ) -> Optional[str]:
        """5組の同期をチェック
        
        Returns:
            エラーメッセージ（問題なければNone）
        """
        if assignment.class_ref not in self.grade5_classes:
            return None
        
        # 他の5組の割り当てをチェック
        for other_class in self.grade5_classes:
            if other_class == assignment.class_ref:
                continue
            
            existing = schedule.get_assignment(time_slot, other_class)
            if existing and existing.subject != assignment.subject:
                return f"5組同期違反: {other_class}は{existing.subject.name}です"
        
        return None
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたスロットがテスト期間かどうか判定"""
        return (time_slot.day, time_slot.period) in self.test_periods
    
    def check_consecutive_periods(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        time_slot: TimeSlot,
        subject: Subject
    ) -> bool:
        """連続コマになるかチェック
        
        Returns:
            連続コマになる場合True
        """
        # 前後の時限を確認
        prev_period = time_slot.period - 1
        next_period = time_slot.period + 1
        
        # 前の時限
        if prev_period >= 1:
            prev_slot = TimeSlot(day=time_slot.day, period=prev_period)
            prev_assignment = schedule.get_assignment(prev_slot, class_ref)
            if prev_assignment and prev_assignment.subject == subject:
                return True
        
        # 次の時限
        if next_period <= 6:
            next_slot = TimeSlot(day=time_slot.day, period=next_period)
            next_assignment = schedule.get_assignment(next_slot, class_ref)
            if next_assignment and next_assignment.subject == subject:
                return True
        
        return False
    
    def validate_all_constraints(
        self,
        schedule: Schedule,
        school: School
    ) -> List[Dict]:
        """スケジュール全体の制約違反を検証（キャッシュをクリアしてから実行）
        
        Returns:
            違反情報のリスト
        """
        # キャッシュをクリア（スケジュール全体の検証時は最新の状態を確認）
        self.clear_cache()
        
        violations = []
        
        # 交流学級同期違反
        exchange_violations = self.exchange_service.get_exchange_violations(schedule)
        violations.extend(exchange_violations)
        
        # 日内重複違反
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subject_counts = defaultdict(int)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subject_counts[assignment.subject.name] += 1
                
                for subject_name, count in subject_counts.items():
                    if subject_name in ScheduleUtils.FIXED_SUBJECTS:
                        continue
                    
                    max_allowed = 1
                    if subject_name in {"算", "国", "理", "社", "英", "数"}:
                        max_allowed = 2
                    
                    if count > max_allowed:
                        violations.append({
                            'type': 'daily_duplicate',
                            'class_ref': class_ref,
                            'day': day,
                            'subject': subject_name,
                            'count': count,
                            'message': f"{class_ref}の{day}曜日に{subject_name}が{count}回配置されています"
                        })
        
        # 教師不在違反
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and not self.check_teacher_availability(assignment.teacher, time_slot):
                        violations.append({
                            'type': 'teacher_absence',
                            'class_ref': class_ref,
                            'time_slot': time_slot,
                            'teacher': assignment.teacher.name,
                            'message': f"{assignment.teacher.name}先生が不在の{time_slot}に{class_ref}で授業が配置されています"
                        })
        
        return violations


# Alias for backward compatibility
ConstraintValidator = ConstraintValidatorImproved
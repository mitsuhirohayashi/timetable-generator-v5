"""統合制約検証サービス

ConstraintValidatorとConstraintValidatorImprovedの機能を統合し、
キャッシング機能と学習ルールを含む包括的な制約検証を提供します。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import defaultdict
from functools import lru_cache

from ...entities.schedule import Schedule
from ...entities.school import School, Subject, Teacher
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ..synchronizers.exchange_class_service import ExchangeClassService
from ..core.unified_constraint_system import UnifiedConstraintSystem, AssignmentContext
from ...utils.schedule_utils import ScheduleUtils
from ....shared.mixins.logging_mixin import LoggingMixin


class UnifiedConstraintValidator(LoggingMixin):
    """統合制約検証サービス
    
    主な機能:
    1. 基本的な制約チェック（教師可用性、日内重複、体育館使用など）
    2. 交流学級制約の検証（ExchangeClassServiceに委譲）
    3. 5組同期の検証
    4. キャッシング機能による高速化
    5. 学習ルールの自動適用
    6. チェックレベルによる柔軟な検証
    """
    
    def __init__(self, unified_system: UnifiedConstraintSystem = None, absence_loader=None):
        """初期化
        
        Args:
            unified_system: 統一制約システム（オプション）
            absence_loader: 教師不在情報ローダー
        """
        super().__init__()
        self.unified_system = unified_system
        self.exchange_service = ExchangeClassService()
        
        # 教師の欠席情報
        self.teacher_absences: Dict[str, Set[Tuple[str, int]]] = {}
        if absence_loader and hasattr(absence_loader, 'teacher_absences'):
            self.teacher_absences = absence_loader.teacher_absences
        
        # 5組クラスの設定
        self._load_grade5_classes()
        
        # テスト期間の設定
        self._load_test_periods()
        
        # キャッシュの初期化（改良版の機能）
        self._cache_teacher_availability: Dict[Tuple[str, str, int, str], bool] = {}
        self._cache_daily_counts: Dict[Tuple[str, str, str], int] = {}
        self._cache_validation_results: Dict[str, Any] = {}
        
        # 統計情報
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'total_checks': 0,
            'learned_rules_applied': 0
        }
        
        # 学習ルール（QandAシステムから）
        self._learned_rules = self._load_learned_rules()
    
    def _load_grade5_classes(self) -> None:
        """5組クラスを読み込む"""
        import re
        grade5_list = ScheduleUtils.get_grade5_classes()
        self.grade5_classes = set()
        
        for class_str in grade5_list:
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
    
    def _load_learned_rules(self) -> List[Dict[str, Any]]:
        """QandAシステムから学習したルールを読み込む"""
        rules = []
        
        # 井上先生の火曜5限ルール
        rules.append({
            'type': 'teacher_period_limit',
            'teacher': '井上',
            'day': '火',
            'period': 5,
            'max_classes': 1,
            'description': '井上先生は火曜5限に最大1クラスまで'
        })
        
        # 3年6組の自立活動ルール
        rules.append({
            'type': 'jiritsu_parent_constraint',
            'exchange_class': '3年6組',
            'parent_class': '3年3組',
            'allowed_subjects': ['数', '英'],
            'description': '3年6組が自立の時、3年3組は数学か英語のみ'
        })
        
        return rules
    
    def can_place_assignment(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        assignment: Assignment,
        check_level: str = 'strict'
    ) -> Tuple[bool, Optional[str]]:
        """指定された割り当てが配置可能かどうか総合的にチェック
        
        キャッシング機能付きで高速化されています。
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: 配置する時間枠
            assignment: 配置する割り当て
            check_level: チェックレベル ('strict', 'normal', 'relaxed')
            
        Returns:
            (配置可能か, エラーメッセージ)
        """
        self._stats['total_checks'] += 1
        
        # キャッシュキーの生成
        cache_key = self._generate_cache_key(time_slot, assignment)
        
        # キャッシュチェック
        if cache_key in self._cache_validation_results:
            self._stats['cache_hits'] += 1
            return self._cache_validation_results[cache_key]
        
        self._stats['cache_misses'] += 1
        
        # 基本的なチェック
        basic_check = self._check_basic_constraints(schedule, school, time_slot, assignment)
        if not basic_check[0]:
            self._cache_validation_results[cache_key] = basic_check
            return basic_check
        
        # 学習ルールの適用
        learned_check = self._check_learned_rules(schedule, school, time_slot, assignment)
        if not learned_check[0]:
            self._cache_validation_results[cache_key] = learned_check
            return learned_check
        
        # レベル別制約チェック
        level_check = self._check_level_constraints(schedule, school, time_slot, assignment, check_level)
        if not level_check[0]:
            self._cache_validation_results[cache_key] = level_check
            return level_check
        
        # 統一制約システムでのチェック（設定されている場合）
        if self.unified_system:
            context = AssignmentContext(
                schedule=schedule,
                school=school,
                time_slot=time_slot,
                assignment=assignment
            )
            result, message = self.unified_system.check_before_assignment(context)
            self._cache_validation_results[cache_key] = (result, message)
            return result, message
        
        # 全てのチェックをパス
        self._cache_validation_results[cache_key] = (True, None)
        return True, None
    
    def _check_basic_constraints(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> Tuple[bool, Optional[str]]:
        """基本的な制約をチェック"""
        # ロックチェック
        if schedule.is_locked(time_slot, assignment.class_ref):
            return False, "このスロットはロックされています"
        
        # 既存割り当てチェック
        existing = schedule.get_assignment(time_slot, assignment.class_ref)
        if existing:
            return False, "既に割り当てがあります"
        
        # テスト期間チェック
        if self.is_test_period(time_slot):
            return False, "テスト期間です"
        
        # 教師不在チェック（キャッシュ付き）
        if assignment.teacher and not self._check_teacher_availability_cached(assignment.teacher, time_slot):
            return False, f"{assignment.teacher.name}先生は不在です"
        
        # 教師重複チェック
        conflict_class = self.check_teacher_conflict(schedule, school, time_slot, assignment)
        if conflict_class:
            return False, f"{assignment.teacher.name}先生は{conflict_class}で授業があります"
        
        return True, None
    
    def _check_level_constraints(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        assignment: Assignment,
        check_level: str
    ) -> Tuple[bool, Optional[str]]:
        """チェックレベルに応じた制約をチェック"""
        # 日内重複チェック
        if check_level in ['strict', 'normal']:
            duplicate_count = self._get_daily_subject_count_cached(schedule, assignment.class_ref, time_slot.day, assignment.subject)
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
            if not self.exchange_service.can_place_subject_for_exchange_class(
                schedule, time_slot, assignment.class_ref, assignment.subject
            ):
                return False, "交流学級の制約に違反します"
        
        # 親学級制約チェック
        if self.exchange_service.is_parent_class(assignment.class_ref):
            if not self.exchange_service.can_place_subject_for_parent_class(
                schedule, time_slot, assignment.class_ref, assignment.subject
            ):
                return False, "親学級の制約に違反します（交流学級が自立活動中）"
        
        # 5組同期チェック
        if assignment.class_ref in self.grade5_classes:
            sync_error = self.check_grade5_sync(schedule, time_slot, assignment)
            if sync_error:
                return False, sync_error
        
        return True, None
    
    def _check_learned_rules(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        assignment: Assignment
    ) -> Tuple[bool, Optional[str]]:
        """学習したルールをチェック"""
        for rule in self._learned_rules:
            if rule['type'] == 'teacher_period_limit':
                # 井上先生の火曜5限ルール
                if (assignment.teacher and 
                    rule['teacher'] in assignment.teacher.name and
                    time_slot.day == rule['day'] and 
                    time_slot.period == rule['period']):
                    
                    # 既に配置されているクラス数をカウント
                    count = 0
                    for class_ref in school.get_all_classes():
                        if class_ref == assignment.class_ref:
                            continue
                        existing = schedule.get_assignment(time_slot, class_ref)
                        if existing and existing.teacher and rule['teacher'] in existing.teacher.name:
                            count += 1
                    
                    if count >= rule['max_classes']:
                        self._stats['learned_rules_applied'] += 1
                        return False, f"{rule['description']} (既に{count}クラス担当)"
            
            elif rule['type'] == 'jiritsu_parent_constraint':
                # 自立活動の親学級制約
                if (str(assignment.class_ref) == rule['exchange_class'] and
                    assignment.subject.name == '自立'):
                    
                    # 親学級の科目をチェック
                    parent_class = next((c for c in school.get_all_classes() 
                                       if str(c) == rule['parent_class']), None)
                    if parent_class:
                        parent_assignment = schedule.get_assignment(time_slot, parent_class)
                        if parent_assignment and parent_assignment.subject.name not in rule['allowed_subjects']:
                            self._stats['learned_rules_applied'] += 1
                            return False, rule['description']
        
        return True, None
    
    def _check_teacher_availability_cached(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師の利用可能性をキャッシュ付きでチェック"""
        cache_key = (time_slot.day, str(time_slot.period), teacher.name, 'availability')
        
        if cache_key in self._cache_teacher_availability:
            return self._cache_teacher_availability[cache_key]
        
        # 実際のチェック
        is_available = True
        if teacher.name in self.teacher_absences:
            absences = self.teacher_absences[teacher.name]
            is_available = (time_slot.day, time_slot.period) not in absences
        
        self._cache_teacher_availability[cache_key] = is_available
        return is_available
    
    def _get_daily_subject_count_cached(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        day: str,
        subject: Subject
    ) -> int:
        """日内の科目カウントをキャッシュ付きで取得"""
        daily_key = (str(class_ref), day, subject.name)
        
        if daily_key in self._cache_daily_counts:
            return self._cache_daily_counts[daily_key]
        
        # 実際のカウント
        count = 0
        for period in range(1, 7):
            ts = TimeSlot(day, period)
            existing = schedule.get_assignment(ts, class_ref)
            if existing and existing.subject.name == subject.name:
                count += 1
        
        self._cache_daily_counts[daily_key] = count
        return count
    
    def check_teacher_conflict(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        assignment: Assignment
    ) -> Optional[ClassReference]:
        """教師の重複をチェック（5組の合同授業を考慮）"""
        # 5組の合同授業の場合は特別処理
        if assignment.class_ref in self.grade5_classes:
            # 他の5組で同じ教師が同じ時間に授業している場合はOK
            grade5_with_teacher = []
            for grade5_class in self.grade5_classes:
                existing = schedule.get_assignment(time_slot, grade5_class)
                if existing and existing.teacher == assignment.teacher:
                    grade5_with_teacher.append(grade5_class)
            
            # 全て5組ならOK
            if len(grade5_with_teacher) == len([c for c in grade5_with_teacher if c in self.grade5_classes]):
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
    
    def check_gym_conflict(
        self, 
        schedule: Schedule, 
        school: School,
        time_slot: TimeSlot, 
        target_class: ClassReference
    ) -> Optional[ClassReference]:
        """体育館の使用競合をチェック"""
        # テスト期間中は体育館制約なし
        if self.is_test_period(time_slot):
            return None
        
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
        """5組の同期をチェック"""
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
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたスロットがテスト期間かどうか判定"""
        return (time_slot.day, time_slot.period) in self.test_periods
    
    def _generate_cache_key(self, time_slot: TimeSlot, assignment: Assignment) -> str:
        """キャッシュキーを生成"""
        teacher_name = assignment.teacher.name if assignment.teacher else "none"
        return f"{time_slot.day}_{time_slot.period}_{str(assignment.class_ref)}_{assignment.subject.name}_{teacher_name}"
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache_teacher_availability.clear()
        self._cache_daily_counts.clear()
        self._cache_validation_results.clear()
        
        self.logger.info(f"キャッシュをクリアしました。統計: {self.get_statistics()}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        total = self._stats['cache_hits'] + self._stats['cache_misses']
        hit_rate = (self._stats['cache_hits'] / total * 100) if total > 0 else 0
        
        return {
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'cache_hit_rate': hit_rate,
            'total_checks': self._stats['total_checks'],
            'learned_rules_applied': self._stats['learned_rules_applied']
        }
    
    def validate_all_constraints(
        self,
        schedule: Schedule,
        school: School
    ) -> List[Dict]:
        """スケジュール全体の制約違反を検証"""
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
                    if assignment and assignment.teacher and not self._check_teacher_availability_cached(assignment.teacher, time_slot):
                        violations.append({
                            'type': 'teacher_absence',
                            'class_ref': class_ref,
                            'time_slot': time_slot,
                            'teacher': assignment.teacher.name,
                            'message': f"{assignment.teacher.name}先生が不在の{time_slot}に{class_ref}で授業が配置されています"
                        })
        
        return violations
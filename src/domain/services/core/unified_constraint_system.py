"""統一制約システム

すべての制約チェックを一元管理するシステム。
優先度別に制約を管理し、効率的なチェックとキャッシングを提供します。
"""
import logging
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING, Set, Any
from dataclasses import dataclass
from ....shared.mixins.logging_mixin import LoggingMixin

if TYPE_CHECKING:
    from ...entities.schedule import Schedule
    from ...entities.school import School
    from ...constraints.base import Constraint, ConstraintViolation
    from ...value_objects.time_slot import TimeSlot
    from ...value_objects.assignment import Assignment

# Import ConstraintPriority from base module instead of redefining
from ...constraints.base import ConstraintPriority

@dataclass
class AssignmentContext(LoggingMixin):
    """割り当てコンテキスト
    
    制約チェック時に必要な情報をまとめたデータクラス。
    
    Attributes:
        schedule: 現在のスケジュール
        school: 学校情報
        time_slot: 割り当て対象の時間枠
        assignment: 割り当てる授業情報
    """
    schedule: 'Schedule'
    school: 'School'
    time_slot: 'TimeSlot'
    assignment: 'Assignment'

@dataclass
class ValidationResult(LoggingMixin):
    """検証結果
    
    スケジュール全体の検証結果を保持するデータクラス。
    
    Attributes:
        is_valid: すべての必須制約を満たしているか
        violations: 発見された制約違反のリスト
        violation_count_by_priority: 優先度別の違反数
    """
    is_valid: bool
    violations: List['ConstraintViolation']
    violation_count_by_priority: Dict[ConstraintPriority, int]
    
    def get_critical_violations(self) -> List['ConstraintViolation']:
        """重大な違反（ERROR）のみを取得
        
        Returns:
            ERRORレベルの違反のリスト
        """
        return [v for v in self.violations if v.severity == "ERROR"]
    
    def get_warnings(self) -> List['ConstraintViolation']:
        """警告（WARNING）のみを取得
        
        Returns:
            WARNINGレベルの違反のリスト
        """
        return [v for v in self.violations if v.severity == "WARNING"]

class UnifiedConstraintSystem(LoggingMixin):
    """統一制約システム
    
    時間割生成における全ての制約を一元管理するシステム。
    優先度別に制約を分類し、効率的なチェックとキャッシングを提供します。
    
    Attributes:
        logger: ロガー
        constraints: 優先度別に分類された制約の辞書
        _check_cache: チェック結果のキャッシュ
        _cache_hits: キャッシュヒット数
        _cache_misses: キャッシュミス数
    """
    
    def __init__(self) -> None:
        """UnifiedConstraintSystemを初期化"""
        super().__init__()
        self.constraints: Dict[ConstraintPriority, List['Constraint']] = {
            ConstraintPriority.CRITICAL: [],
            ConstraintPriority.HIGH: [],
            ConstraintPriority.MEDIUM: [],
            ConstraintPriority.LOW: [],
            ConstraintPriority.SUGGESTION: []
        }
        self._check_cache: Dict[str, Tuple[bool, List[str]]] = {}  # チェック結果のキャッシュ
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        
        # 最適化用の追加キャッシュ
        self._teacher_availability_cache: Dict[str, bool] = {}  # 教師可用性キャッシュ
        self._fixed_slot_cache: Dict[str, bool] = {}  # 固定スロットキャッシュ
        self._class_relation_cache: Dict[str, Optional[str]] = {}  # クラス関係キャッシュ
    
    def check_assignment(self, schedule: 'Schedule', school: 'School', time_slot: 'TimeSlot', assignment: 'Assignment') -> bool:
        """配置前に全ての制約をチェック（ConstraintValidatorとの互換性のため）
        
        Args:
            schedule: 現在のスケジュール
            school: 学校情報
            time_slot: 配置しようとする時間枠
            assignment: 配置しようとする割り当て
            
        Returns:
            配置可能な場合True
        """
        context = AssignmentContext(
            schedule=schedule,
            school=school,
            time_slot=time_slot,
            assignment=assignment
        )
        result, reasons = self.check_before_assignment(context)
        return result
    
    def register_constraint(self, constraint: 'Constraint', 
                          priority: ConstraintPriority = ConstraintPriority.HIGH) -> None:
        """制約を登録
        
        Args:
            constraint: 制約オブジェクト
            priority: 優先度
        """
        self.constraints[priority].append(constraint)
        self.logger.info(f"制約を登録: {constraint.name} (優先度: {priority.name})")
    
    def check_before_assignment(self, context: AssignmentContext) -> Tuple[bool, List[str]]:
        """配置前の事前チェック
        
        Args:
            context: 割り当てコンテキスト
            
        Returns:
            (成功フラグ, 失敗理由のリスト)
        """
        # キャッシュキーの生成
        cache_key = self._generate_cache_key(context)
        
        # キャッシュチェック
        if cache_key in self._check_cache:
            self._cache_hits += 1
            return self._check_cache[cache_key]
        
        self._cache_misses += 1
        
        # 制約チェック（優先度順）
        reasons = []
        
        # Sort priorities by value (descending) to check critical first
        for priority in sorted(ConstraintPriority, key=lambda p: p.value, reverse=True):
            for constraint in self.constraints[priority]:
                try:
                    # check_before_assignmentメソッドがある場合はそれを使用（booleanを返す）
                    if hasattr(constraint, 'check_before_assignment'):
                        if not constraint.check_before_assignment(
                            context.schedule, 
                            context.school, 
                            context.time_slot, 
                            context.assignment
                        ):
                            reason = f"{constraint.name}違反"
                            reasons.append(reason)
                            
                            # CRITICAL制約の場合は即座に失敗
                            if priority == ConstraintPriority.CRITICAL:
                                result = (False, reasons)
                                self._check_cache[cache_key] = result
                                return result
                    # checkメソッドしかない場合
                    elif hasattr(constraint, 'check'):
                        check_result = constraint.check(
                            context.schedule, 
                            context.school, 
                            context.time_slot, 
                            context.assignment
                        )
                        
                        # checkメソッドがboolを返す場合
                        if isinstance(check_result, bool):
                            if not check_result:
                                reason = f"{constraint.name}違反"
                                reasons.append(reason)
                                
                                # CRITICAL制約の場合は即座に失敗
                                if priority == ConstraintPriority.CRITICAL:
                                    result = (False, reasons)
                                    self._check_cache[cache_key] = result
                                    return result
                        # checkメソッドがリストを返す場合
                        elif check_result:  # リストが空でない場合
                            reason = f"{constraint.name}違反"
                            reasons.append(reason)
                            
                            # CRITICAL制約の場合は即座に失敗
                            if priority == ConstraintPriority.CRITICAL:
                                result = (False, reasons)
                                self._check_cache[cache_key] = result
                                return result
                except Exception as e:
                    self.logger.error(f"制約チェックエラー ({constraint.name}): {e}")
                    reasons.append(f"{constraint.name}エラー: {str(e)}")
        
        result = (len(reasons) == 0, reasons)
        self._check_cache[cache_key] = result
        return result
    
    def validate_schedule(self, schedule: 'Schedule', school: 'School') -> ValidationResult:
        """スケジュール全体の事後検証
        
        登録されているすべての制約に対してスケジュールを検証します。
        優先度の高い制約から順にチェックし、違反を収集します。
        
        Args:
            schedule: 検証対象のスケジュール
            school: 学校情報（クラス、教師、教科など）
            
        Returns:
            ValidationResult: 検証結果（有効性、違反リスト、優先度別違反数）
            
        Note:
            このメソッドは完全な検証を行うため、大規模なスケジュールでは
            処理時間がかかる可能性があります。
        """
        all_violations = []
        violation_count_by_priority = {p: 0 for p in ConstraintPriority}
        
        # 優先度順に検証
        for priority in sorted(ConstraintPriority, key=lambda p: p.value, reverse=True):
            for constraint in self.constraints[priority]:
                try:
                    result = constraint.validate(schedule, school)
                    violations = result.violations
                    
                    if violations:
                        all_violations.extend(violations)
                        violation_count_by_priority[priority] += len(violations)
                        
                        self.logger.debug(
                            f"{constraint.name}: {len(violations)}件の違反"
                        )
                except Exception as e:
                    self.logger.error(f"制約検証エラー ({constraint.name}): {e}")
        
        # 結果の生成
        is_valid = len(all_violations) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            violations=all_violations,
            violation_count_by_priority=violation_count_by_priority
        )
    
    def get_constraint_summary(self) -> Dict[str, Any]:
        """制約の概要を取得
        
        登録されている制約の統計情報を取得します。
        
        Returns:
            制約の総数と優先度別の内訳を含む辞書
        """
        summary = {
            'total_constraints': sum(len(cs) for cs in self.constraints.values()),
            'by_priority': {}
        }
        
        for priority in sorted(ConstraintPriority, key=lambda p: p.value, reverse=True):
            constraint_names = [c.name for c in self.constraints[priority]]
            summary['by_priority'][priority.name] = {
                'count': len(constraint_names),
                'constraints': constraint_names
            }
        
        return summary
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """キャッシュ統計を取得
        
        制約チェックキャッシュのパフォーマンス統計を取得します。
        
        Returns:
            キャッシュヒット数、ミス数、ヒット率、キャッシュサイズを含む辞書
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_requests if total_requests > 0 else 0
        
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'hit_rate': hit_rate,
            'cache_size': len(self._check_cache)
        }
    
    def clear_cache(self) -> None:
        """キャッシュをクリア"""
        self._check_cache.clear()
        self._teacher_availability_cache.clear()
        self._fixed_slot_cache.clear()
        self._class_relation_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self.logger.info("制約チェックキャッシュをクリアしました")
    
    def _generate_cache_key(self, context: AssignmentContext) -> str:
        """キャッシュキーを生成"""
        return (
            f"{context.time_slot.day}_{context.time_slot.period}_"
            f"{context.assignment.class_ref.full_name}_"
            f"{context.assignment.subject.name}_"
            f"{context.assignment.teacher.name if context.assignment.teacher else 'None'}"
        )
    
    def log_statistics(self) -> None:
        """統計情報をログ出力"""
        self.logger.info("=== 統一制約システム統計 ===")
        
        # 制約の概要
        summary = self.get_constraint_summary()
        self.logger.info(f"登録制約数: {summary['total_constraints']}")
        for priority_name, info in summary['by_priority'].items():
            self.logger.info(f"  {priority_name}: {info['count']}件")
            for constraint_name in info['constraints']:
                self.logger.info(f"    - {constraint_name}")
        
        # キャッシュ統計
        cache_stats = self.get_cache_statistics()
        self.logger.info(f"キャッシュヒット率: {cache_stats['hit_rate']:.2%}")
        self.logger.info(f"  ヒット: {cache_stats['cache_hits']}")
        self.logger.info(f"  ミス: {cache_stats['cache_misses']}")
        self.logger.info(f"  サイズ: {cache_stats['cache_size']}")
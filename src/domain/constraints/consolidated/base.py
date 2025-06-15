"""Consolidated constraint system base classes and interfaces"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Dict, Any, Set, Tuple
from dataclasses import dataclass, field
import logging

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.assignment import ConstraintViolation
from ...value_objects.time_slot import TimeSlot, ClassReference


class ConstraintType(Enum):
    """制約のタイプ"""
    HARD = "HARD"    # 絶対に守る必要がある制約
    SOFT = "SOFT"    # 可能な限り守りたい制約


class ConstraintPriority(Enum):
    """制約の優先度"""
    CRITICAL = 100   # 最高優先度（システムエラーレベル）
    HIGH = 80        # 高優先度（教員重複など）
    MEDIUM = 60      # 中優先度（標準時数など）
    LOW = 40         # 低優先度（日内重複回避など）
    SUGGESTION = 20  # 提案レベル


class ProtectionLevel(Enum):
    """保護レベル（ProtectedSlotConstraint用）"""
    ABSOLUTE = "ABSOLUTE"      # 絶対に変更不可
    STRONG = "STRONG"          # 強い保護（警告付きで変更可能）
    WEAK = "WEAK"              # 弱い保護（推奨レベル）


@dataclass
class ConstraintConfig:
    """制約の設定情報"""
    name: str
    description: str
    type: ConstraintType
    priority: ConstraintPriority
    enabled: bool = True
    config_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationContext:
    """検証時のコンテキスト情報"""
    schedule: Schedule
    school: School
    time_slot: Optional[TimeSlot] = None
    class_ref: Optional[ClassReference] = None
    subject: Optional[str] = None
    teacher: Optional[str] = None
    
    def get_assignment_at(self, time_slot: TimeSlot, class_ref: ClassReference):
        """指定された時間とクラスの割り当てを取得"""
        return self.schedule.get_assignment(time_slot, class_ref)
    
    def get_assignments_by_time(self, time_slot: TimeSlot):
        """指定された時間の全割り当てを取得"""
        return self.schedule.get_assignments_by_time_slot(time_slot)
    
    def get_assignments_by_class(self, class_ref: ClassReference):
        """指定されたクラスの全割り当てを取得"""
        return self.schedule.get_assignments_by_class(class_ref)


@dataclass
class ConstraintResult:
    """制約検証の結果"""
    constraint_name: str
    violations: List[ConstraintViolation] = field(default_factory=list)
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0
    
    @property
    def violation_count(self) -> int:
        return len(self.violations)
    
    @property
    def has_errors(self) -> bool:
        return any(v.severity == "ERROR" for v in self.violations)
    
    @property
    def has_warnings(self) -> bool:
        return any(v.severity == "WARNING" for v in self.violations)
    
    def add_violation(self, violation: ConstraintViolation):
        """違反を追加"""
        self.violations.append(violation)
    
    def merge(self, other: 'ConstraintResult'):
        """他の結果とマージ"""
        self.violations.extend(other.violations)
        if other.message:
            if self.message:
                self.message += f"; {other.message}"
            else:
                self.message = other.message
        self.metadata.update(other.metadata)
    
    def __bool__(self) -> bool:
        return self.is_valid


class ConsolidatedConstraint(ABC):
    """統合制約の抽象基底クラス"""
    
    def __init__(self, config: ConstraintConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cache = {}  # パフォーマンス向上のためのキャッシュ
        
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def type(self) -> ConstraintType:
        return self.config.type
    
    @property
    def priority(self) -> ConstraintPriority:
        return self.config.priority
    
    @property
    def enabled(self) -> bool:
        return self.config.enabled
    
    def is_hard_constraint(self) -> bool:
        """ハード制約かどうか判定"""
        return self.type == ConstraintType.HARD
    
    def is_soft_constraint(self) -> bool:
        """ソフト制約かどうか判定"""
        return self.type == ConstraintType.SOFT
    
    @abstractmethod
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """制約を検証する（全体チェック）"""
        pass
    
    def check_assignment(self, context: ValidationContext) -> bool:
        """単一の割り当てが制約を満たすかチェック（配置前チェック）"""
        # デフォルト実装：validateを使って判定
        result = self.validate(context)
        return result.is_valid
    
    def clear_cache(self):
        """キャッシュをクリア"""
        self._cache.clear()
    
    def __str__(self) -> str:
        return f"{self.name} ({self.type.value}, Priority: {self.priority.value})"
    
    def __lt__(self, other):
        """優先度による比較（高い優先度が先）"""
        return self.priority.value > other.priority.value


class ConfigurableConstraint(ConsolidatedConstraint):
    """設定可能な制約の基底クラス"""
    
    def __init__(self, config: ConstraintConfig):
        super().__init__(config)
        self._load_configuration()
    
    @abstractmethod
    def _load_configuration(self):
        """設定を読み込む"""
        pass
    
    def reload_configuration(self):
        """設定を再読み込み"""
        self.clear_cache()
        self._load_configuration()


class CompositeConstraint(ConsolidatedConstraint):
    """複数の制約を統合する複合制約"""
    
    def __init__(self, config: ConstraintConfig, sub_constraints: List[ConsolidatedConstraint] = None):
        super().__init__(config)
        self.sub_constraints = sub_constraints or []
    
    def add_constraint(self, constraint: ConsolidatedConstraint):
        """サブ制約を追加"""
        self.sub_constraints.append(constraint)
        self.sub_constraints.sort()  # 優先度順にソート
    
    def validate(self, context: ValidationContext) -> ConstraintResult:
        """全てのサブ制約を検証"""
        result = ConstraintResult(constraint_name=self.name)
        
        for constraint in self.sub_constraints:
            if not constraint.enabled:
                continue
                
            sub_result = constraint.validate(context)
            result.merge(sub_result)
        
        return result
    
    def check_assignment(self, context: ValidationContext) -> bool:
        """全てのサブ制約で配置チェック"""
        for constraint in self.sub_constraints:
            if not constraint.enabled:
                continue
                
            if not constraint.check_assignment(context):
                return False
        
        return True


class ConstraintValidator:
    """制約検証器（新バージョン）"""
    
    def __init__(self, constraints: List[ConsolidatedConstraint]):
        self.constraints = sorted(constraints)  # 優先度順にソート
        self.logger = logging.getLogger(__name__)
    
    def validate_all(self, schedule: Schedule, school: School) -> List[ConstraintResult]:
        """全ての制約を検証"""
        results = []
        context = ValidationContext(schedule=schedule, school=school)
        
        schedule.clear_violations()  # 既存の違反をクリア
        
        for constraint in self.constraints:
            if not constraint.enabled:
                continue
                
            result = constraint.validate(context)
            results.append(result)
            
            # 違反をスケジュールに追加
            for violation in result.violations:
                schedule.add_violation(violation)
        
        return results
    
    def check_assignment(self, schedule: Schedule, school: School, 
                        time_slot: TimeSlot, class_ref: ClassReference,
                        subject: str, teacher: Optional[str] = None) -> bool:
        """配置前に全ての制約をチェック"""
        context = ValidationContext(
            schedule=schedule,
            school=school,
            time_slot=time_slot,
            class_ref=class_ref,
            subject=subject,
            teacher=teacher
        )
        
        for constraint in self.constraints:
            if not constraint.enabled:
                continue
                
            if constraint.is_hard_constraint():  # ハード制約のみチェック
                if not constraint.check_assignment(context):
                    self.logger.debug(f"Assignment blocked by {constraint.name}")
                    return False
        
        return True
    
    def validate_hard_constraints_only(self, schedule: Schedule, school: School) -> List[ConstraintResult]:
        """ハード制約のみを検証"""
        hard_constraints = [c for c in self.constraints if c.is_hard_constraint()]
        results = []
        context = ValidationContext(schedule=schedule, school=school)
        
        for constraint in hard_constraints:
            if not constraint.enabled:
                continue
                
            result = constraint.validate(context)
            results.append(result)
        
        return results
    
    def has_hard_constraint_violations(self, schedule: Schedule, school: School) -> bool:
        """ハード制約の違反があるかどうか判定"""
        results = self.validate_hard_constraints_only(schedule, school)
        return any(not result.is_valid for result in results)
    
    def get_violation_summary(self, schedule: Schedule, school: School) -> str:
        """制約違反のサマリーを取得"""
        results = self.validate_all(schedule, school)
        
        hard_violations = sum(result.violation_count for result in results 
                            if result.has_errors)
        soft_violations = sum(result.violation_count for result in results 
                            if result.has_warnings)
        
        details = []
        for result in results:
            if result.violations:
                details.append(f"  - {result.constraint_name}: {result.violation_count}件")
        
        summary = f"制約違反: ハード制約 {hard_violations}件, ソフト制約 {soft_violations}件"
        if details:
            summary += "\n" + "\n".join(details)
        
        return summary
    
    def add_constraint(self, constraint: ConsolidatedConstraint):
        """制約を追加"""
        self.constraints.append(constraint)
        self.constraints.sort()  # 優先度順に再ソート
    
    def remove_constraint(self, constraint_name: str):
        """制約を削除"""
        self.constraints = [c for c in self.constraints if c.name != constraint_name]
    
    def enable_constraint(self, constraint_name: str):
        """制約を有効化"""
        for constraint in self.constraints:
            if constraint.name == constraint_name:
                constraint.config.enabled = True
                break
    
    def disable_constraint(self, constraint_name: str):
        """制約を無効化"""
        for constraint in self.constraints:
            if constraint.name == constraint_name:
                constraint.config.enabled = False
                break
# 時間割生成システム - 主要コード統合版

# このファイルは主要なコードを1つにまとめたものです



================================================================================

# ファイル: main.py

================================================================================

#!/usr/bin/env python3
"""
時間割生成システム メインエントリーポイント
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.presentation.cli.main import main

if __name__ == "__main__":
    main()



================================================================================

# ファイル: src/application/services/schedule_generation_service.py

================================================================================

"""スケジュール生成サービス（リファクタリング版）

高度なCSPアルゴリズムを使用した時間割生成を管理するサービス。
Strategy パターンを使用してアルゴリズムの選択を管理します。
"""
import logging
from typing import Optional, Dict, List, TYPE_CHECKING, Any
from datetime import datetime

from .generation_strategies.base_generation_strategy import BaseGenerationStrategy
from .generation_strategies.ultrathink_strategy import UltrathinkStrategy
from .generation_strategies.improved_csp_strategy import ImprovedCSPStrategy
from .generation_strategies.grade5_priority_strategy import Grade5PriorityStrategy
from .generation_strategies.advanced_csp_strategy import AdvancedCSPStrategy
from .generation_strategies.legacy_strategy import LegacyStrategy
from .generation_strategies.unified_hybrid_strategy import UnifiedHybridStrategy
from .generation_strategies.unified_hybrid_strategy_fixed import UnifiedHybridStrategyFixed
from .generation_strategies.unified_hybrid_strategy_v2 import UnifiedHybridStrategyV2
from .generation_strategies.unified_hybrid_strategy_v3 import UnifiedHybridStrategyV3
from .simple_generator_v2 import SimpleGeneratorV2
from .generation_helpers.followup_loader import FollowupLoader
from .generation_helpers.empty_slot_filler import EmptySlotFiller
from .generation_helpers.schedule_helper import ScheduleHelper
from .learned_rule_application_service import LearnedRuleApplicationService

if TYPE_CHECKING:
    from ...domain.entities.schedule import Schedule
    from ...domain.entities.school import School
    from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
    from ...infrastructure.config.path_manager import PathManager


class ScheduleGenerationService:
    """スケジュール生成サービス（リファクタリング版）"""
    
    def __init__(
        self,
        constraint_system: 'UnifiedConstraintSystem',
        path_manager: 'PathManager',
        learned_rule_service: Optional[LearnedRuleApplicationService] = None
    ) -> None:
        """初期化
        
        Args:
            constraint_system: 統一制約システムのインスタンス
            path_manager: パス管理のインスタンス
            learned_rule_service: 学習ルール適用サービス（オプション）
        """
        self.constraint_system = constraint_system
        self.path_manager = path_manager
        self.logger = logging.getLogger(__name__)
        
        # 学習ルール適用サービスの初期化
        self.learned_rule_service = learned_rule_service or LearnedRuleApplicationService()
        
        # ヘルパーの初期化
        self.followup_loader = FollowupLoader(path_manager)
        self.empty_slot_filler = EmptySlotFiller(constraint_system, path_manager)
        self.schedule_helper = ScheduleHelper()
        
        # 戦略の初期化
        self._init_strategies()
        
        # 統計情報の初期化
        self.generation_stats: Dict[str, Any] = self._init_stats()
    
    def _init_strategies(self) -> None:
        """生成戦略を初期化"""
        self.strategies = {
            'simple_v2': SimpleGeneratorV2,
            'unified_hybrid': UnifiedHybridStrategyV2(self.constraint_system),
            'ultrathink': UltrathinkStrategy(
                self.constraint_system,
                self.followup_loader.load_followup_data
            ),
            'improved_csp': ImprovedCSPStrategy(self.constraint_system),
            'grade5_priority': Grade5PriorityStrategy(self.constraint_system),
            'advanced_csp': AdvancedCSPStrategy(self.constraint_system),
            'legacy': LegacyStrategy(self.constraint_system)
        }
    
    def _init_stats(self) -> Dict[str, Any]:
        """統計情報を初期化"""
        return {
            'start_time': None,
            'end_time': None,
            'iterations': 0,
            'assignments_made': 0,
            'assignments_failed': 0,
            'violations_fixed': 0,
            'final_violations': 0,
            'empty_slots_filled': 0,
            'algorithm_used': 'unknown'
        }
    
    def generate_schedule(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        strategy: str = 'legacy',
        max_iterations: int = 100,
        search_mode: str = "standard"
    ) -> 'Schedule':
        """スケジュールを生成
        
        Args:
            school: 学校情報
            initial_schedule: 初期スケジュール
            max_iterations: 最大反復回数
            use_advanced_csp: 高度なCSPアルゴリズムを使用するか
            use_improved_csp: 改良版CSPアルゴリズムを使用するか
            use_ultrathink: Ultrathink Perfect Generatorを使用するか
            use_grade5_priority: 5組優先配置アルゴリズムを使用するか
            use_unified_hybrid: 統一ハイブリッドアルゴリズムを使用するか
            search_mode: 探索モード
            
        Returns:
            生成されたスケジュール
        """
        self.logger.info("=== スケジュール生成を開始 ===")
        self.generation_stats['start_time'] = datetime.now()
        
        # QandAシステムから学習したルールを読み込む
        learned_rules_count = self.learned_rule_service.parse_and_load_rules()
        if learned_rules_count > 0:
            self.logger.info(f"QandAシステムから{learned_rules_count}個のルールを学習しました")
        
        # 戦略を選択
        if strategy == 'simple_v2':
            generator = self.strategies[strategy](school, initial_schedule)
            return generator.generate()

        strategy = self._select_strategy(strategy_name=strategy)
        
        self.generation_stats['algorithm_used'] = strategy.get_name()
        
        try:
            # 初期スケジュールの準備
            if initial_schedule:
                schedule = self._prepare_initial_schedule(initial_schedule, school)
            else:
                from ...domain.entities.schedule import Schedule
                schedule = Schedule()
            
            # スケジュール生成
            self.logger.info("--- 戦略実行前のスケジュール状態をデバッグ出力 ---")
            for ts, ass in schedule.get_all_assignments():
                self.logger.debug(f"[PRE-STRATEGY] {ts}: {ass.class_ref} - {ass.subject.name} ({ass.teacher.name if ass.teacher else 'N/A'})")
            self.logger.info("--- デバッグ出力終了 ---")

            schedule = strategy.generate(
                school=school,
                initial_schedule=schedule,
                max_iterations=max_iterations,
                search_mode=search_mode
            )
            
            # 統計情報を更新
            self._update_stats(schedule, school)
            
            # UnifiedHybrid戦略以外の場合のみ空きスロットを埋める
            if strategy != 'unified_hybrid':
                self.logger.info(f"{strategy}戦略のため、空きスロットを埋めます。")
                filled_count = self.empty_slot_filler.fill_empty_slots(schedule, school)
                self.generation_stats['empty_slots_filled'] = filled_count
            else:
                self.logger.info("UnifiedHybrid戦略のため、空きスロット埋めをスキップします。")
            
            # 最終検証
            self._final_validation(schedule, school)
            
        except Exception as e:
            self.logger.error(f"スケジュール生成中にエラーが発生しました: {e}")
            raise
        finally:
            self.generation_stats['end_time'] = datetime.now()
            self._log_statistics()
        
        return schedule
    
    def _select_strategy(self, strategy_name: str) -> BaseGenerationStrategy:
        """使用する戦略を選択"""
        if strategy_name in self.strategies:
            self.logger.info(f"✓ {strategy_name} 戦略を選択しました")
            return self.strategies[strategy_name]
        else:
            self.logger.error(f"無効な戦略名: {strategy_name}")
            raise ValueError(f"無効な戦略名: {strategy_name}")
    
    def _prepare_initial_schedule(
        self,
        initial_schedule: 'Schedule',
        school: 'School'
    ) -> 'Schedule':
        """初期スケジュールを準備"""
        # スケジュールをコピー
        schedule = self.schedule_helper.copy_schedule(initial_schedule)
        
        # 固定科目をロック
        self.schedule_helper.lock_fixed_subjects(schedule)
        
        return schedule
    
    def _update_stats(self, schedule: 'Schedule', school: 'School') -> None:
        """統計情報を更新"""
        self.generation_stats['assignments_made'] = len(schedule.get_all_assignments())
        
        # 制約違反をチェック
        validation_result = self.constraint_system.validate_schedule(schedule, school)
        self.generation_stats['final_violations'] = len(validation_result.violations)
    
    def _final_validation(self, schedule: 'Schedule', school: 'School') -> None:
        """最終検証"""
        validation_result = self.constraint_system.validate_schedule(schedule, school)
        violations = validation_result.violations
        
        if violations:
            self.logger.warning(f"最終検証で{len(violations)}件の制約違反が見つかりました")
            self.schedule_helper.log_violations(violations)
        else:
            self.logger.info("✓ 全ての制約を満たすスケジュールが生成されました！")
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        stats = self.generation_stats
        
        if stats['start_time'] and stats['end_time']:
            duration = (stats['end_time'] - stats['start_time']).total_seconds()
        else:
            duration = 0
        
        self.logger.info("=== 生成統計 ===")
        self.logger.info(f"使用アルゴリズム: {stats['algorithm_used']}")
        self.logger.info(f"実行時間: {duration:.2f}秒")
        self.logger.info(f"配置成功: {stats['assignments_made']}")
        self.logger.info(f"最終違反: {stats['final_violations']}")
        self.logger.info(f"空きスロット埋め: {stats['empty_slots_filled']}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return self.generation_stats.copy()



================================================================================

# ファイル: src/domain/constraints/base.py

================================================================================

"""制約システムの基盤クラス"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Iterator
from dataclasses import dataclass

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.assignment import ConstraintViolation
from ..value_objects.time_slot import TimeSlot
from ..constants import WEEKDAYS, PERIODS


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


@dataclass
class ConstraintResult:
    """制約検証の結果"""
    constraint_name: str
    violations: List['ConstraintViolation']
    message: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0
    
    def __bool__(self) -> bool:
        return self.is_valid


class Constraint(ABC):
    """制約の抽象基底クラス"""
    
    def __init__(self, 
                 constraint_type: ConstraintType,
                 priority: ConstraintPriority,
                 name: str,
                 description: str = ""):
        self.type = constraint_type
        self.priority = priority
        self.name = name
        self.description = description
    
    @abstractmethod
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """制約を検証する"""
        pass
    
    def is_hard_constraint(self) -> bool:
        """ハード制約かどうか判定"""
        return self.type == ConstraintType.HARD
    
    def is_soft_constraint(self) -> bool:
        """ソフト制約かどうか判定"""
        return self.type == ConstraintType.SOFT
    
    def __str__(self) -> str:
        return f"{self.name} ({self.type.value}, Priority: {self.priority.value})"
    
    def __lt__(self, other):
        """優先度による比較（高い優先度が先）"""
        return self.priority.value > other.priority.value
    
    def iterate_all_time_slots(self) -> Iterator[TimeSlot]:
        """全ての時間枠をイテレート（共通ユーティリティメソッド）"""
        for day in WEEKDAYS:
            for period in PERIODS:
                yield TimeSlot(day, period)


class HardConstraint(Constraint):
    """ハード制約の基底クラス"""
    
    def __init__(self, priority: ConstraintPriority, name: str, description: str = ""):
        super().__init__(ConstraintType.HARD, priority, name, description)


class SoftConstraint(Constraint):
    """ソフト制約の基底クラス"""
    
    def __init__(self, priority: ConstraintPriority, name: str, description: str = ""):
        super().__init__(ConstraintType.SOFT, priority, name, description)


class ConstraintValidator:
    """制約検証器"""
    
    def __init__(self, constraints: List[Constraint]):
        self.constraints = sorted(constraints)  # 優先度順にソート
    
    def check_assignment(self, schedule: Schedule, school: School, time_slot, assignment) -> bool:
        """配置前に全ての制約をチェック"""
        from ..value_objects.time_slot import TimeSlot
        from ..value_objects.assignment import Assignment
        
        # 全ての制約に対してcheckメソッドを呼び出す（存在する場合）
        for constraint in self.constraints:
            if hasattr(constraint, 'check'):
                if not constraint.check(schedule, school, time_slot, assignment):
                    return False
        return True
    
    def validate_all(self, schedule: Schedule, school: School) -> List[ConstraintResult]:
        """全ての制約を検証"""
        results = []
        schedule.clear_violations()  # 既存の違反をクリア
        
        for constraint in self.constraints:
            result = constraint.validate(schedule, school)
            results.append(result)
            
            # 違反をスケジュールに追加
            for violation in result.violations:
                schedule.add_violation(violation)
        
        return results
    
    def validate_hard_constraints_only(self, schedule: Schedule, school: School) -> List[ConstraintResult]:
        """ハード制約のみを検証"""
        hard_constraints = [c for c in self.constraints if c.is_hard_constraint()]
        results = []
        
        for constraint in hard_constraints:
            result = constraint.validate(schedule, school)
            results.append(result)
        
        return results
    
    def has_hard_constraint_violations(self, schedule: Schedule, school: School) -> bool:
        """ハード制約の違反があるかどうか判定"""
        results = self.validate_hard_constraints_only(schedule, school)
        return any(not result.is_valid for result in results)
    
    def get_violation_summary(self, schedule: Schedule, school: School) -> str:
        """制約違反のサマリーを取得"""
        results = self.validate_all(schedule, school)
        
        hard_violations = sum(len(r.violations) for r in results 
                            if r.violations and any(v.severity == "ERROR" for v in r.violations))
        soft_violations = sum(len(r.violations) for r in results 
                            if r.violations and any(v.severity == "WARNING" for v in r.violations))
        
        return f"制約違反: ハード制約 {hard_violations}件, ソフト制約 {soft_violations}件"
    
    def add_constraint(self, constraint: Constraint) -> None:
        """制約を追加"""
        self.constraints.append(constraint)
        self.constraints.sort()  # 優先度順に再ソート
    
    def remove_constraint(self, constraint_name: str) -> None:
        """制約を削除"""
        self.constraints = [c for c in self.constraints if c.name != constraint_name]



================================================================================

# ファイル: src/domain/constraints/basic_constraints.py

================================================================================

"""基本的な制約の実装"""
from typing import List, Dict, Set
from collections import defaultdict

from .base import HardConstraint, SoftConstraint, ConstraintResult, ConstraintPriority
from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, Teacher
from ..value_objects.assignment import ConstraintViolation
from ..constants import WEEKDAYS, PERIODS, FIXED_SUBJECTS


class TeacherConflictConstraint(HardConstraint):
    """教員重複制約：同じ時間に同じ教員が複数の場所にいることを防ぐ"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教員重複制約",
            description="同じ時間に同じ教員が複数のクラスを担当することを防ぐ"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：この時間に教員が利用可能かチェック"""
        if not assignment.has_teacher():
            return True
        
        # 欠課は複数クラスで同時に発生しても問題ない
        if assignment.teacher.name == "欠課":
            return True
        
        # YT担当は全クラス同時実施のため複数クラスで同時に発生しても問題ない
        if assignment.teacher.name == "YT担当":
            return True
        
        # 道担当（道徳）も全クラス同時実施のため複数クラスで同時に発生しても問題ない
        if assignment.teacher.name == "道担当":
            return True
        
        # 5組（1-5, 2-5, 3-5）の教師は同時に複数の5組クラスを担当可能
        # ClassValidatorから5組チームティーチング教師を取得
        from ..value_objects.class_validator import ClassValidator
        class_validator = ClassValidator()
        grade5_tt_teachers = class_validator.get_grade5_team_teaching_teachers()
        
        if (assignment.class_ref.class_number == 5 and
            assignment.teacher.name in grade5_tt_teachers):
            # この時間の他の5組クラスの割り当てをチェック
            assignments = schedule.get_assignments_by_time_slot(time_slot)
            for existing_assignment in assignments:
                if (existing_assignment.has_teacher() and 
                    existing_assignment.teacher == assignment.teacher and
                    existing_assignment.class_ref != assignment.class_ref and
                    existing_assignment.class_ref.class_number != 5):
                    # 5組以外のクラスとの重複は不可
                    return False
            return True  # 5組同士の重複は許可
        
        # この時間の全ての割り当てをチェック
        assignments = schedule.get_assignments_by_time_slot(time_slot)
        for existing_assignment in assignments:
            if (existing_assignment.has_teacher() and 
                existing_assignment.teacher == assignment.teacher and
                existing_assignment.class_ref != assignment.class_ref):
                return False  # 既に他のクラスでこの教員が授業中
        
        return True
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        # 各時間枠で教員の重複をチェック
        for day in WEEKDAYS:
            for period in PERIODS:
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                # 教員ごとの割り当てをグループ化
                teacher_assignments = defaultdict(list)
                for assignment in assignments:
                    if assignment.has_teacher():
                        teacher_assignments[assignment.teacher].append(assignment)
                
                # 重複をチェック
                for teacher, teacher_assignments_list in teacher_assignments.items():
                    # 欠課は複数クラスで同時に発生しても問題ない
                    if teacher.name == "欠課":
                        continue
                    
                    # YT担当は全クラス同時実施のため複数クラスで同時に発生しても問題ない
                    if teacher.name == "YT担当":
                        continue
                    
                    # 道担当（道徳）も全クラス同時実施のため複数クラスで同時に発生しても問題ない
                    if teacher.name == "道担当":
                        continue
                    
                    # 5組の教師が複数の5組クラスを担当している場合は許可
                    # ClassValidatorから5組チームティーチング教師を取得
                    from ..value_objects.class_validator import ClassValidator
                    class_validator = ClassValidator()
                    grade5_tt_teachers = class_validator.get_grade5_team_teaching_teachers()
                    
                    if teacher.name in grade5_tt_teachers:
                        # 5組以外のクラスが含まれているかチェック
                        non_grade5_classes = [a for a in teacher_assignments_list 
                                            if a.class_ref.class_number != 5]
                        if len(non_grade5_classes) == 0:
                            # 全て5組クラスなら問題なし
                            continue
                        elif len(non_grade5_classes) > 0 and len(teacher_assignments_list) > 1:
                            # 5組の国語の特殊ケースをチェック
                            grade5_kokugo_assignments = [a for a in teacher_assignments_list 
                                                       if a.class_ref.class_number == 5 and a.subject.name == "国"]
                            
                            if teacher.name in ["寺田", "金子み"]:
                                # 5組の国語の特殊ケース
                                # 寺田先生または金子み先生が5組の国語を担当している場合
                                grade5_kokugo_count = len(grade5_kokugo_assignments)
                                if grade5_kokugo_count > 0:
                                    # 5組の国語を担当している
                                    # 他のクラスも全て国語なら問題なし（例：寺田先生が2-1国語と5組国語を同時に担当）
                                    non_grade5_kokugo = [a for a in non_grade5_classes if a.subject.name == "国"]
                                    if len(non_grade5_classes) == len(non_grade5_kokugo):
                                        # 5組以外も全て国語の授業
                                        continue
                            
                            # それ以外の場合は違反
                            for assignment in teacher_assignments_list:
                                violation = ConstraintViolation(
                                    description=f"教員{teacher}が5組と他クラスで同時刻に授業: {[a.class_ref for a in teacher_assignments_list]}",
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
                            continue
                        
                    if len(teacher_assignments_list) > 1:
                        for assignment in teacher_assignments_list:
                            violation = ConstraintViolation(
                                description=f"教員{teacher}が同時刻に複数クラスを担当: {[a.class_ref for a in teacher_assignments_list]}",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"教員重複チェック完了: {len(violations)}件の違反"
        )


class TeacherAvailabilityConstraint(HardConstraint):
    """教員利用可能性制約：教員の不在時間への割り当てを防ぐ"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教員利用可能性制約", 
            description="教員の不在時間（年休・外勤・出張）への割り当てを防ぐ"
        )
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：教員が利用可能かチェック"""
        if not assignment.has_teacher():
            return True
        
        unavailable_teachers = school.get_unavailable_teachers(time_slot.day, time_slot.period)
        return assignment.teacher not in unavailable_teachers
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for day in WEEKDAYS:
            for period in PERIODS:
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                unavailable_teachers = school.get_unavailable_teachers(day, period)
                
                for assignment in assignments:
                    if assignment.has_teacher() and assignment.teacher in unavailable_teachers:
                        violation = ConstraintViolation(
                            description=f"不在の教員{assignment.teacher}に授業が割り当てられています",
                            time_slot=time_slot,
                            assignment=assignment,
                            severity="ERROR"
                        )
                        violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"教員利用可能性チェック完了: {len(violations)}件の違反"
        )


class ExchangeClassConstraint(HardConstraint):
    """交流学級制約：6組・7組が自立活動の時、親学級は数学か英語である必要がある"""
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.HIGH,
            name="交流学級制約",
            description="交流学級の自立活動時間に親学級が適切な教科を実施することを保証"
        )
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for day in WEEKDAYS:
            for period in PERIODS:
                time_slot = TimeSlot(day, period)
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                
                # 交流学級で自立活動を実施している場合をチェック
                for assignment in assignments:
                    if (assignment.class_ref.is_exchange_class() and 
                        assignment.subject.name == "自立"):
                        
                        # 親学級の授業をチェック
                        parent_class = assignment.class_ref.get_parent_class()
                        parent_assignment = schedule.get_assignment(time_slot, parent_class)
                        
                        if parent_assignment:
                            if parent_assignment.subject.name not in ["数", "英"]:
                                violation = ConstraintViolation(
                                    description=f"交流学級{assignment.class_ref}が自立活動中、親学級{parent_class}は{parent_assignment.subject}を実施中（数学か英語である必要）",
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
                        else:
                            violation = ConstraintViolation(
                                description=f"交流学級{assignment.class_ref}が自立活動中、親学級{parent_class}に授業が設定されていません",
                                time_slot=time_slot,
                                assignment=assignment,
                                severity="ERROR"
                            )
                            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"交流学級制約チェック完了: {len(violations)}件の違反"
        )


class DailySubjectDuplicateConstraint(HardConstraint):
    """日内重複制約：同じ日に同じ教科が重複することを完全に防ぐ"""
    
    def __init__(self, max_daily_occurrences: int = 1):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,  # 最高優先度
            name="日内重複制約",
            description="同じ日に同じ教科が2回以上実施されることを完全に防ぐ"
        )
        self.max_daily_occurrences = max_daily_occurrences
        # 保護された教科（これらは重複可能）
        self.protected_subjects = FIXED_SUBJECTS
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: 'Assignment') -> bool:
        """配置前チェック：この教科が既に同じ日に配置されていないかチェック"""
        # 保護された教科は制限なし
        if assignment.subject.name in self.protected_subjects:
            return True
        
        # 同じ日の同じクラスの授業をチェック
        same_day_count = 0
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            check_slot = TimeSlot(time_slot.day, period)
            existing_assignment = schedule.get_assignment(check_slot, assignment.class_ref)
            
            if (existing_assignment and 
                existing_assignment.subject.name == assignment.subject.name):
                same_day_count += 1
        
        # 1回でも既に配置されていたら配置不可
        return same_day_count < self.max_daily_occurrences
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subjects = schedule.get_daily_subjects(class_ref, day)
                subject_count = defaultdict(int)
                subject_periods = defaultdict(list)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject:
                        subject_count[assignment.subject.name] += 1
                        subject_periods[assignment.subject.name].append(period)
                
                # 重複をチェック（2回以上は完全禁止）
                for subject_name, count in subject_count.items():
                    if count > self.max_daily_occurrences:
                        # 保護された教科はスキップ
                        if subject_name in self.protected_subjects:
                            continue
                        
                        # 2回目以降の違反を記録
                        periods_str = ", ".join([f"{p}時限" for p in subject_periods[subject_name]])
                        
                        for i, period in enumerate(subject_periods[subject_name]):
                            if i >= self.max_daily_occurrences:  # 2回目以降
                                time_slot = TimeSlot(day, period)
                                assignment = schedule.get_assignment(time_slot, class_ref)
                                if assignment:
                                    violation = ConstraintViolation(
                                        description=f"{class_ref}の{day}曜日に{subject_name}が"
                                                   f"{count}回配置されています（{periods_str}）。"
                                                   f"日内重複は完全に禁止されています。",
                                        time_slot=time_slot,
                                        assignment=assignment,
                                        severity="CRITICAL"  # ERRORからCRITICALに変更
                                    )
                                    violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"日内重複チェック完了: {len(violations)}件の過度な重複"
        )


class StandardHoursConstraint(SoftConstraint):
    """標準時数制約：各教科の週当たり時数が標準に合致することを確認"""
    
    def __init__(self, tolerance: float = 0.5):
        super().__init__(
            priority=ConstraintPriority.MEDIUM,
            name="標準時数制約",
            description="各教科の週当たり時数が標準時数に合致することを確認"
        )
        self.tolerance = tolerance  # 許容誤差
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        violations = []
        
        for class_ref in school.get_all_classes():
            required_subjects = school.get_required_subjects(class_ref)
            
            for subject in required_subjects:
                required_hours = school.get_standard_hours(class_ref, subject)
                actual_hours = schedule.count_subject_hours(class_ref, subject)
                
                difference = abs(actual_hours - required_hours)
                if difference > self.tolerance:
                    # 代表的な時間枠を取得（最初の割り当て）
                    assignments = schedule.get_assignments_by_class(class_ref)
                    representative_time_slot = None
                    representative_assignment = None
                    
                    for ts, assignment in assignments:
                        if assignment.subject == subject:
                            representative_time_slot = ts
                            representative_assignment = assignment
                            break
                    
                    if representative_time_slot and representative_assignment:
                        violation = ConstraintViolation(
                            description=f"{class_ref}の{subject}: 標準{required_hours}時間 vs 実際{actual_hours}時間（差分: {difference}）",
                            time_slot=representative_time_slot,
                            assignment=representative_assignment,
                            severity="WARNING"
                        )
                        violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.__class__.__name__,
            violations=violations,
            message=f"標準時数チェック完了: {len(violations)}件の違反"
        )



================================================================================

# ファイル: src/domain/entities/schedule.py

================================================================================

"""スケジュールエンティティ"""
from typing import Dict, List, Optional, Set
from collections import defaultdict

from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment, ConstraintViolation
from .grade5_unit import Grade5Unit
from ..exceptions import (
    SubjectAssignmentException,
    FixedSubjectModificationException,
    InvalidAssignmentException
)


class Schedule:
    """時間割を管理するエンティティ"""
    
    def __init__(self):
        self._assignments: Dict[TimeSlot, Dict[ClassReference, Assignment]] = defaultdict(dict)
        self._locked_cells: Set[tuple[TimeSlot, ClassReference]] = set()
        self._violations: List[ConstraintViolation] = []
        # 5組ユニット
        self._grade5_unit = Grade5Unit()
        self._grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
        # 固定科目保護ポリシー
        from ..policies.fixed_subject_protection_policy import FixedSubjectProtectionPolicy
        self._fixed_subject_policy = FixedSubjectProtectionPolicy()
        self._fixed_subject_protection_enabled = True
        # 初期読み込み中は5組の特別処理を無効化
        self._grade5_sync_enabled = True
        # テスト期間情報を格納 (day -> [periods])
        self.test_periods: Dict[str, List[int]] = {}
    
    @property
    def grade5_unit(self) -> Grade5Unit:
        """5組ユニットを取得"""
        return self._grade5_unit
    
    def assign(self, time_slot: TimeSlot, assignment: Assignment) -> None:
        """指定された時間枠にクラスの割り当てを設定"""
        if self.is_locked(time_slot, assignment.class_ref):
            raise InvalidAssignmentException(f"セルがロックされています: {time_slot} - {assignment.class_ref}")
        
        # テスト期間保護チェック
        if self.is_test_period(time_slot):
            # テスト期間中は既存の割り当てを保護
            existing = self.get_assignment(time_slot, assignment.class_ref)
            if existing:
                # 既存の割り当てと同じ場合は許可（再設定）
                if (existing.subject.name == assignment.subject.name and
                    (not existing.teacher or not assignment.teacher or 
                     existing.teacher.name == assignment.teacher.name)):
                    # 同じ内容なので処理を続行
                    pass
                else:
                    # 異なる内容への変更は拒否
                    raise InvalidAssignmentException(
                        f"テスト期間中は変更できません: {time_slot} - {assignment.class_ref} "
                        f"(現在: {existing.subject.name}, 変更先: {assignment.subject.name})"
                    )
        
        # 固定科目保護チェック（有効な場合のみ）
        if self._fixed_subject_protection_enabled:
            if not self._fixed_subject_policy.can_modify_slot(self, time_slot, assignment.class_ref, assignment):
                current_assignment = self.get_assignment(time_slot, assignment.class_ref)
                if current_assignment:
                    raise FixedSubjectModificationException(
                        current_assignment.subject.name, time_slot
                    )
                else:
                    raise InvalidAssignmentException(
                        f"固定科目スロットを変更できません: {time_slot} - {assignment.class_ref}"
                    )
        
        # 5組の場合は特別処理（5組同期が有効な場合のみ）
        if self._grade5_sync_enabled and assignment.class_ref in self._grade5_classes:
            # 5組全体に同じ教科・教員を割り当て
            # ただし、ロックされているセルはスキップ
            can_assign_to_unit = True
            locked_classes = []
            for grade5_class in self._grade5_classes:
                if self.is_locked(time_slot, grade5_class):
                    can_assign_to_unit = False
                    locked_classes.append(grade5_class)
            
            if can_assign_to_unit:
                # 全ての5組セルがロックされていない場合のみユニットに割り当て
                self._grade5_unit.assign(time_slot, assignment.subject, assignment.teacher)
                # 通常の割り当ても行う（互換性のため）
                for grade5_class in self._grade5_classes:
                    self._assignments[time_slot][grade5_class] = Assignment(
                        grade5_class, assignment.subject, assignment.teacher
                    )
            else:
                # 一部がロックされている場合は、個別に割り当て（同期は崩れる可能性がある）
                if not self.is_locked(time_slot, assignment.class_ref):
                    self._assignments[time_slot][assignment.class_ref] = assignment
                else:
                    # ロックされている場合はエラー（既にチェック済みだが念のため）
                    raise InvalidAssignmentException(
                        f"セルがロックされています（5組同期中）: {time_slot} - {assignment.class_ref} "
                        f"(ロック済み: {locked_classes})"
                    )
        else:
            # 5組同期が無効の場合、または5組以外の場合は通常の割り当て
            self._assignments[time_slot][assignment.class_ref] = assignment
    
    def get_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[Assignment]:
        """指定された時間枠・クラスの割り当てを取得"""
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            # Grade5Unitから取得を試みる
            unit_assignment = self._grade5_unit.get_assignment(time_slot, class_ref)
            if unit_assignment:
                return unit_assignment
            
            # Grade5Unitに無い場合は、通常の_assignmentsから取得（CSV読み込み時のデータ）
            direct_assignment = self._assignments[time_slot].get(class_ref)
            if direct_assignment:
                # Grade5Unitに同期（5組同期が有効な場合のみ）
                if self._grade5_sync_enabled:
                    # 他の5組クラスも同じ教科を持っているか確認
                    all_have_same = True
                    for other_class in self._grade5_classes:
                        other_assignment = self._assignments[time_slot].get(other_class)
                        if not other_assignment or other_assignment.subject != direct_assignment.subject:
                            all_have_same = False
                            break
                    
                    # 全ての5組が同じ教科を持っている場合のみGrade5Unitに同期
                    if all_have_same:
                        try:
                            self._grade5_unit.assign(time_slot, direct_assignment.subject, direct_assignment.teacher)
                        except Exception:
                            # ロックされている場合などは無視
                            pass
                
                return direct_assignment
            
            return None
        return self._assignments[time_slot].get(class_ref)
    
    def remove_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """指定された時間枠・クラスの割り当てを削除"""
        if self.is_locked(time_slot, class_ref):
            raise InvalidAssignmentException(f"セルがロックされています: {time_slot} - {class_ref}")
        
        # 固定科目保護チェック（有効な場合のみ）
        if self._fixed_subject_protection_enabled:
            if not self._fixed_subject_policy.can_modify_slot(self, time_slot, class_ref, None):
                current_assignment = self.get_assignment(time_slot, class_ref)
                if current_assignment:
                    raise FixedSubjectModificationException(
                        current_assignment.subject.name, time_slot
                    )
                else:
                    raise InvalidAssignmentException(
                        f"固定科目スロットから削除できません: {time_slot} - {class_ref}"
                    )
        
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            # 5組全体から削除
            self._grade5_unit.remove_assignment(time_slot)
            # 通常の割り当ても削除（互換性のため）
            for grade5_class in self._grade5_classes:
                if time_slot in self._assignments and grade5_class in self._assignments[time_slot]:
                    del self._assignments[time_slot][grade5_class]
        else:
            if time_slot in self._assignments and class_ref in self._assignments[time_slot]:
                del self._assignments[time_slot][class_ref]
    
    def lock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """セルをロック（変更禁止）"""
        # 5組の場合は全5組をロック（5組同期が有効な場合のみ）
        if self._grade5_sync_enabled and class_ref in self._grade5_classes:
            self._grade5_unit.lock_slot(time_slot)
            for grade5_class in self._grade5_classes:
                self._locked_cells.add((time_slot, grade5_class))
        else:
            # 5組同期が無効の場合、または5組以外の場合は個別にロック
            self._locked_cells.add((time_slot, class_ref))
    
    def unlock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> None:
        """セルのロックを解除"""
        # 5組の場合は全5組のロックを解除
        if class_ref in self._grade5_classes:
            self._grade5_unit.unlock_slot(time_slot)
            for grade5_class in self._grade5_classes:
                self._locked_cells.discard((time_slot, grade5_class))
        else:
            self._locked_cells.discard((time_slot, class_ref))
    
    def is_locked(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """セルがロックされているかどうか判定"""
        # 5組の場合は特別処理（5組同期が有効な場合のみ）
        if self._grade5_sync_enabled and class_ref in self._grade5_classes:
            return self._grade5_unit.is_locked(time_slot)
        return (time_slot, class_ref) in self._locked_cells
    
    def disable_fixed_subject_protection(self) -> None:
        """固定科目保護を一時的に無効化"""
        self._fixed_subject_protection_enabled = False
    
    def enable_fixed_subject_protection(self) -> None:
        """固定科目保護を有効化"""
        self._fixed_subject_protection_enabled = True
    
    def disable_grade5_sync(self) -> None:
        """5組同期を一時的に無効化"""
        self._grade5_sync_enabled = False
    
    def enable_grade5_sync(self) -> None:
        """5組同期を有効化"""
        self._grade5_sync_enabled = True
    
    def get_all_assignments(self) -> List[tuple[TimeSlot, Assignment]]:
        """全ての割り当てを取得"""
        result = []
        # 5組以外の通常の割り当て
        for time_slot, class_assignments in self._assignments.items():
            for class_ref, assignment in class_assignments.items():
                # 5組は後で追加するのでスキップ
                if class_ref not in self._grade5_classes:
                    result.append((time_slot, assignment))
        
        # 5組の割り当てを追加
        for time_slot, class_ref, assignment in self._grade5_unit.get_all_assignments():
            result.append((time_slot, assignment))
        
        return result
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたタイムスロットがテスト期間かどうか"""
        if time_slot.day in self.test_periods:
            return time_slot.period in self.test_periods[time_slot.day]
        return False
    
    def set_test_periods(self, test_periods: Set[tuple[str, int]]) -> None:
        """テスト期間を設定"""
        self.test_periods.clear()
        for day, period in test_periods:
            if day not in self.test_periods:
                self.test_periods[day] = []
            self.test_periods[day].append(period)
    
    def get_assignments_by_time_slot(self, time_slot: TimeSlot) -> List[Assignment]:
        """指定された時間枠の全ての割り当てを取得"""
        result = []
        # 5組以外の通常の割り当て
        for class_ref, assignment in self._assignments[time_slot].items():
            if class_ref not in self._grade5_classes:
                result.append(assignment)
        
        # 5組の割り当てを追加
        for class_ref in self._grade5_classes:
            assignment = self._grade5_unit.get_assignment(time_slot, class_ref)
            if assignment:
                result.append(assignment)
        
        return result
    
    def get_assignments_by_class(self, class_ref: ClassReference) -> List[tuple[TimeSlot, Assignment]]:
        """指定されたクラスの全ての割り当てを取得"""
        result = []
        
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            for time_slot, unit_class_ref, assignment in self._grade5_unit.get_all_assignments():
                if unit_class_ref == class_ref:
                    result.append((time_slot, assignment))
        else:
            # 通常の処理
            for time_slot, class_assignments in self._assignments.items():
                if class_ref in class_assignments:
                    result.append((time_slot, class_assignments[class_ref]))
        
        return result
    
    def get_assignments_by_teacher(self, teacher: Teacher) -> List[tuple[TimeSlot, Assignment]]:
        """指定された教員の全ての割り当てを取得"""
        result = []
        for time_slot, class_assignments in self._assignments.items():
            for assignment in class_assignments.values():
                if assignment.involves_teacher(teacher):
                    result.append((time_slot, assignment))
        return result
    
    def get_teacher_at_time(self, time_slot: TimeSlot, teacher: Teacher) -> List[Assignment]:
        """指定された時間枠で指定された教員が担当している割り当てを取得"""
        assignments = self.get_assignments_by_time_slot(time_slot)
        result = [a for a in assignments if a.involves_teacher(teacher)]
        
        # 5組の場合、1つの教員が3クラスを同時に担当していることを正しく反映
        grade5_assignments = [a for a in result if a.class_ref in self._grade5_classes]
        if len(grade5_assignments) > 1:
            # 5組の授業は1つとしてカウント（実際には3クラス同時指導）
            # 最初の1つだけを残す
            result = [a for a in result if a.class_ref not in self._grade5_classes]
            if grade5_assignments:
                result.append(grade5_assignments[0])
        
        return result
    
    def is_teacher_available(self, time_slot: TimeSlot, teacher: Teacher) -> bool:
        """指定された時間枠で教員が空いているかどうかを厳密に判定"""
        if not teacher:
            return True

        assignments = self.get_assignments_by_time_slot(time_slot)
        teacher_assignments = [a for a in assignments if a.involves_teacher(teacher)]

        if not teacher_assignments:
            return True

        # 5組の合同授業を考慮
        is_grade5_class = any(a.class_ref in self._grade5_classes for a in teacher_assignments)
        if is_grade5_class:
            # 5組の授業を担当している場合、他の5組以外のクラスとの重複は許されない
            non_grade5_assignments = [a for a in teacher_assignments if a.class_ref not in self._grade5_classes]
            if non_grade5_assignments:
                return False # 5組と通常クラスの重複
            return True # 5組同士の重複は許可

        # 通常のクラスで重複がある場合は許されない
        return len(teacher_assignments) == 0
    
    def get_empty_slots(self, class_ref: ClassReference) -> List[TimeSlot]:
        """指定されたクラスの空いている時間枠を取得"""
        all_time_slots = [
            TimeSlot(day, period) 
            for day in ["月", "火", "水", "木", "金"] 
            for period in range(1, 7)
        ]
        
        # 5組の場合は特別処理
        if class_ref in self._grade5_classes:
            return self._grade5_unit.get_empty_slots()
        
        assigned_slots = {ts for ts, _ in self.get_assignments_by_class(class_ref)}
        # ロックされているセルも除外
        locked_slots = {ts for ts in all_time_slots if self.is_locked(ts, class_ref)}
        return [ts for ts in all_time_slots if ts not in assigned_slots and ts not in locked_slots]
    
    def count_subject_hours(self, class_ref: ClassReference, subject: Subject) -> int:
        """指定されたクラス・教科の週当たり時数をカウント"""
        assignments = self.get_assignments_by_class(class_ref)
        return sum(1 for _, assignment in assignments if assignment.subject == subject)
    
    def get_daily_subjects(self, class_ref: ClassReference, day: str) -> List[Subject]:
        """指定されたクラス・曜日の教科一覧を取得"""
        subjects = []
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = self.get_assignment(time_slot, class_ref)
            if assignment:
                subjects.append(assignment.subject)
        return subjects
    
    def has_daily_duplicate(self, class_ref: ClassReference, day: str) -> bool:
        """指定されたクラス・曜日に同じ教科が重複しているかどうか判定"""
        subjects = self.get_daily_subjects(class_ref, day)
        return len(subjects) != len(set(subjects))
    
    def add_violation(self, violation: ConstraintViolation) -> None:
        """制約違反を追加"""
        self._violations.append(violation)
    
    def clear_violations(self) -> None:
        """制約違反をクリア"""
        self._violations.clear()
    
    def get_violations(self) -> List[ConstraintViolation]:
        """制約違反の一覧を取得"""
        return self._violations.copy()
    
    def has_violations(self) -> bool:
        """制約違反があるかどうか判定"""
        return len(self._violations) > 0
    
    def clone(self) -> 'Schedule':
        """スケジュールの複製を作成"""
        new_schedule = Schedule()
        new_schedule._assignments = {
            ts: dict(assignments) for ts, assignments in self._assignments.items()
        }
        new_schedule._locked_cells = self._locked_cells.copy()
        new_schedule._violations = self._violations.copy()
        # Grade5Unitも複製
        new_schedule._grade5_unit = Grade5Unit()
        for time_slot, assignment in self._grade5_unit._assignments.items():
            new_schedule._grade5_unit._assignments[time_slot] = assignment
        new_schedule._grade5_unit._locked_slots = self._grade5_unit._locked_slots.copy()
        return new_schedule
    
    def __str__(self) -> str:
        total_assignments = sum(len(assignments) for assignments in self._assignments.values())
        return f"Schedule(assignments={total_assignments}, violations={len(self._violations)})"



================================================================================

# ファイル: src/domain/entities/school.py

================================================================================

"""学校エンティティ"""
from typing import Dict, List, Set
from collections import defaultdict

from ..value_objects.time_slot import ClassReference, Subject, Teacher
from ..value_objects.assignment import StandardHours
from ...shared.mixins.validation_mixin import ValidationMixin, ValidationError


class School(ValidationMixin):
    """学校全体の情報を管理するエンティティ"""
    
    def __init__(self):
        self._classes: Set[ClassReference] = set()
        self._teachers: Set[Teacher] = set()
        self._teacher_subjects: Dict[Teacher, Set[Subject]] = defaultdict(set)
        self._subject_teachers: Dict[Subject, Set[Teacher]] = defaultdict(set)
        self._teacher_assignments: Dict[tuple[Subject, ClassReference], Teacher] = {}
        self._standard_hours: Dict[tuple[ClassReference, Subject], float] = {}
        self._teacher_unavailable: Dict[tuple[str, int], Set[Teacher]] = defaultdict(set)
    
    # クラス管理
    def add_class(self, class_ref: ClassReference) -> None:
        """クラスを追加"""
        self._classes.add(class_ref)
    
    def get_all_classes(self) -> List[ClassReference]:
        """全てのクラスを取得"""
        return sorted(list(self._classes), key=lambda c: (c.grade, c.class_number))
    
    def get_classes_by_type(self, regular: bool = None, special_needs: bool = None, 
                           exchange: bool = None) -> List[ClassReference]:
        """タイプ別にクラスを取得"""
        classes = self.get_all_classes()
        
        if regular is not None:
            classes = [c for c in classes if c.is_regular_class() == regular]
        if special_needs is not None:
            classes = [c for c in classes if c.is_special_needs_class() == special_needs]
        if exchange is not None:
            classes = [c for c in classes if c.is_exchange_class() == exchange]
        
        return classes
    
    # 教員管理
    def add_teacher(self, teacher: Teacher) -> None:
        """教員を追加"""
        self._teachers.add(teacher)
    
    def get_all_teachers(self) -> List[Teacher]:
        """全ての教員を取得"""
        return sorted(list(self._teachers), key=lambda t: t.name)
    
    def assign_teacher_subject(self, teacher: Teacher, subject: Subject) -> None:
        """教員の担当教科を設定"""
        self.add_teacher(teacher)
        self._teacher_subjects[teacher].add(subject)
        self._subject_teachers[subject].add(teacher)
    
    def get_teacher_subjects(self, teacher: Teacher) -> Set[Subject]:
        """教員の担当教科を取得"""
        return self._teacher_subjects[teacher].copy()
    
    def get_subject_teachers(self, subject: Subject) -> Set[Teacher]:
        """教科の担当教員を取得"""
        return self._subject_teachers[subject].copy()
    
    def can_teacher_teach_subject(self, teacher: Teacher, subject: Subject) -> bool:
        """教員が指定された教科を担当できるかどうか判定"""
        return subject in self._teacher_subjects[teacher]
    
    # 教員-クラス割り当て管理
    def assign_teacher_to_class(self, teacher: Teacher, subject: Subject, class_ref: ClassReference) -> None:
        """教員を特定のクラス・教科に割り当て"""
        if not self.can_teacher_teach_subject(teacher, subject):
            raise ValidationError(f"{teacher} cannot teach {subject}")
        
        self._teacher_assignments[(subject, class_ref)] = teacher
    
    def get_assigned_teacher(self, subject: Subject, class_ref: ClassReference) -> Teacher:
        """指定されたクラス・教科の担当教員を取得"""
        return self._teacher_assignments.get((subject, class_ref))
    
    def get_teacher_class_assignments(self, teacher: Teacher) -> List[tuple[Subject, ClassReference]]:
        """教員の担当クラス・教科一覧を取得"""
        return [(subject, class_ref) for (subject, class_ref), t in self._teacher_assignments.items() 
                if t == teacher]
    
    # 標準時数管理
    def set_standard_hours(self, class_ref: ClassReference, subject: Subject, hours: float) -> None:
        """標準時数を設定"""
        self._standard_hours[(class_ref, subject)] = hours
    
    def get_standard_hours(self, class_ref: ClassReference, subject: Subject) -> float:
        """標準時数を取得"""
        # 学総は総合と同じ標準時数として扱う
        if subject.name == "学総":
            sougou_subject = Subject("総")
            return self._standard_hours.get((class_ref, sougou_subject), 0.0)
        return self._standard_hours.get((class_ref, subject), 0.0)
    
    def get_all_subjects(self) -> Set[Subject]:
        """全ての科目を取得"""
        return set(self._subject_teachers.keys())
    
    def get_all_standard_hours(self, class_ref: ClassReference) -> Dict[Subject, float]:
        """指定されたクラスの全ての標準時数を取得"""
        result = {}
        for (c, subject), hours in self._standard_hours.items():
            if c == class_ref and hours > 0:
                result[subject] = hours
        return result
    
    def get_required_subjects(self, class_ref: ClassReference) -> List[Subject]:
        """指定されたクラスで必要な教科一覧を取得"""
        return [subject for subject, hours in self.get_all_standard_hours(class_ref).items() 
                if hours > 0]
    
    # 教員の利用不可時間管理
    def set_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> None:
        """教員の利用不可時間を設定"""
        self._teacher_unavailable[(day, period)].add(teacher)
    
    def is_teacher_unavailable(self, day: str, period: int, teacher: Teacher) -> bool:
        """教員が指定された時間に利用不可かどうか判定"""
        return teacher in self._teacher_unavailable[(day, period)]
    
    def get_unavailable_teachers(self, day: str, period: int) -> Set[Teacher]:
        """指定された時間に利用不可の教員一覧を取得"""
        return self._teacher_unavailable[(day, period)].copy()
    
    def get_available_teachers(self, day: str, period: int) -> Set[Teacher]:
        """指定された時間に利用可能な教員一覧を取得"""
        unavailable = self.get_unavailable_teachers(day, period)
        return self._teachers - unavailable
    
    # バリデーション
    def validate_setup(self) -> List[str]:
        """学校設定の妥当性を検証"""
        errors = []
        
        # 全てのクラス・教科に担当教員が割り当てられているかチェック
        for class_ref in self._classes:
            required_subjects = self.get_required_subjects(class_ref)
            for subject in required_subjects:
                if not self.get_assigned_teacher(subject, class_ref):
                    errors.append(f"No teacher assigned for {class_ref} {subject}")
        
        # 教員の担当可能教科と実際の割り当てに矛盾がないかチェック
        for (subject, class_ref), teacher in self._teacher_assignments.items():
            if not self.can_teacher_teach_subject(teacher, subject):
                errors.append(f"Teacher {teacher} cannot teach {subject} but assigned to {class_ref}")
        
        return errors
    
    def __str__(self) -> str:
        return f"School(classes={len(self._classes)}, teachers={len(self._teachers)})"



================================================================================

# ファイル: src/infrastructure/repositories/csv_repository.py

================================================================================

"""リファクタリング版CSVScheduleRepository - ファサードパターンで各責務を統合"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.entities.grade5_unit import Grade5Unit
from ...domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...domain.value_objects.assignment import Assignment
from ...domain.value_objects.special_support_hours import SpecialSupportHourMapping, SpecialSupportHourMappingEnhanced
from ...domain.utils import parse_class_reference
from ...domain.interfaces.repositories import IScheduleRepository, ISchoolRepository
from ..config.path_config import path_config
from .schedule_io.csv_reader import CSVScheduleReader
from .schedule_io.csv_writer import CSVScheduleWriter
from .schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from .teacher_schedule_repository import TeacherScheduleRepository
# Validation service removed to avoid circular import
from .teacher_absence_loader import TeacherAbsenceLoader
from .teacher_mapping_repository import TeacherMappingRepository
from ...shared.utils.csv_operations import CSVOperations
from ...shared.mixins.logging_mixin import LoggingMixin


class CSVScheduleRepository(LoggingMixin, IScheduleRepository):
    """リファクタリング版スケジュールリポジトリ - 各責務を専門クラスに委譲"""
    
    def __init__(
        self,
        base_path: Path = Path("."),
        use_enhanced_features: bool = False,
        use_support_hours: bool = False
    ):
        """初期化
        
        Args:
            base_path: ベースパス
            use_enhanced_features: 拡張機能を使用するか
            use_support_hours: 特別支援時数表記を使用するか
        """
        super().__init__()
        self.base_path = Path(base_path)
        self.use_enhanced_features = use_enhanced_features
        self.use_support_hours = use_support_hours
        
        # 責務ごとのコンポーネントを初期化
        self.reader = CSVScheduleReader()
        # 改良版のWriterを使用（5組を確実に出力）
        self.writer = CSVScheduleWriterImproved(use_support_hours)
        
        # 読み込んだSchoolオブジェクトを保持（Writerで使用）
        self._loaded_school = None
        self.teacher_schedule_repo = TeacherScheduleRepository(use_enhanced_features)
        self.absence_loader = TeacherAbsenceLoader()
        
        # 読み込んだ制約情報
        self._forbidden_cells = {}
        # テスト期間情報
        self._test_periods = {}
    
    def save(self, schedule: Schedule, filename: str = "output.csv") -> None:
        """スケジュールをCSVファイルに保存"""
        # Schoolオブジェクトがある場合はWriterに設定
        if self._loaded_school:
            self.writer.school = self._loaded_school
        # テスト期間データを復元
        for (time_slot, class_ref), original_assignment in self._test_periods.items():
            current_assignment = schedule.get_assignment(time_slot, class_ref)
            if current_assignment != original_assignment:
                self.logger.warning(
                    f"テスト期間のデータが変更されています: {class_ref} {time_slot} "
                    f"{original_assignment.subject.name} → "
                    f"{current_assignment.subject.name if current_assignment else '空き'}"
                )
                # 元のテスト期間データを復元
                # ロックされている場合は一時的にアンロック
                was_locked = schedule.is_locked(time_slot, class_ref)
                if was_locked:
                    schedule.unlock_cell(time_slot, class_ref)
                
                # 現在の割り当てを削除してから元のデータを復元
                if current_assignment:
                    schedule.remove_assignment(time_slot, class_ref)
                schedule.assign(time_slot, original_assignment)
                
                # ロックを復元
                if was_locked:
                    schedule.lock_cell(time_slot, class_ref)
        
        file_path = self._resolve_output_path(filename)
        self.writer.write(schedule, file_path)
    
    def load(self, filename: str, school: Optional[School] = None) -> Schedule:
        """スケジュールを読み込む（loadメソッドのエイリアス）"""
        return self.load_desired_schedule(filename, school)
    
    def load_desired_schedule(
        self,
        filename: str = "input.csv",
        school: Optional[School] = None
    ) -> Schedule:
        """希望時間割をCSVファイルから読み込み"""
        file_path = self._resolve_input_path(filename)
        
        # 基本的な読み込み
        schedule = self.reader.read(file_path, school)
        
        # 制約情報を保存
        self._forbidden_cells = self.reader.get_forbidden_cells()
        # テスト期間情報を保存
        if hasattr(self.reader, 'get_test_periods'):
            self._test_periods = self.reader.get_test_periods()
        else:
            self._test_periods = {}
        
        if school:
            # Grade5Unitに教師不在チェッカーを設定
            schedule.grade5_unit.set_teacher_absence_checker(
                self.absence_loader.is_teacher_absent
            )
        
        return schedule
    
    def save_teacher_schedule(
        self,
        schedule: Schedule,
        school: School,
        filename: str = "teacher_schedule.csv"
    ) -> None:
        """教師別時間割をCSVファイルに保存"""
        self.teacher_schedule_repo.save_teacher_schedule(
            schedule, school, filename
        )
    
    def get_forbidden_cells(self) -> Dict[Tuple[TimeSlot, ClassReference], Set[str]]:
        """読み込んだCSVファイルから抽出した非○○制約を取得"""
        return self._forbidden_cells
    
    def _resolve_output_path(self, filename: str) -> Path:
        """出力ファイルパスを解決"""
        if filename.startswith("/"):
            return Path(filename)
        elif str(path_config.output_dir) in filename:
            return Path(filename)
        elif filename.startswith("data/"):
            return path_config.base_dir / filename
        elif filename == "output.csv":
            return path_config.default_output_csv
        else:
            return path_config.get_output_path(filename)
    
    def _resolve_input_path(self, filename: str) -> Path:
        """入力ファイルパスを解決"""
        if filename.startswith("/"):
            return Path(filename)
        elif filename.startswith("data/"):
            if str(self.base_path).endswith("/data") or str(self.base_path) == "data":
                return self.base_path.parent / filename
            else:
                return Path(filename)
        else:
            return self.base_path / filename


class CSVSchoolRepository(LoggingMixin, ISchoolRepository):
    """学校データのCSV入出力を担当"""
    
    def __init__(self, base_path: Path = Path(".")):
        super().__init__()
        self.base_path = Path(base_path)
        self.teacher_mapping_repo = TeacherMappingRepository(self.base_path)
    
    def load_standard_hours(self, filename: str = "base_timetable.csv") -> Dict[tuple[ClassReference, Subject], float]:
        """標準時数データをCSVから読み込み"""
        # filenameがdata/で始まる場合は、base_pathとの重複を避ける
        if filename.startswith('data/'):
            file_path = Path(filename)
        else:
            file_path = self.base_path / filename
        standard_hours = {}
        
        try:
            lines = CSVOperations.read_csv_raw(str(file_path))
            
            if len(lines) < 3:
                raise ValueError("標準時数CSVファイルの形式が正しくありません")
            
            # 教科ヘッダー（2行目）
            subject_headers = []
            for header in lines[1][1:]:  # 最初の列はクラス名なのでスキップ
                if header and header.strip():
                    try:
                        subject_headers.append(Subject(header.strip()))
                    except ValueError:
                        subject_headers.append(None)  # 無効な教科名はNone
                else:
                    subject_headers.append(None)
            
            # 各クラスの標準時数（3行目以降）
            for line in lines[2:]:
                if not line or not line[0].strip():
                    continue
                
                class_name = line[0].strip()
                class_ref = parse_class_reference(class_name)
                if not class_ref:
                    continue
                
                # 各教科の時数
                for i, hours_str in enumerate(line[1:], 0):
                    if (i < len(subject_headers) and 
                        subject_headers[i] and 
                        hours_str and hours_str.strip()):
                        
                        try:
                            hours = float(hours_str.strip())
                            if hours > 0:
                                standard_hours[(class_ref, subject_headers[i])] = hours
                        except ValueError:
                            continue
            
            self.logger.info(f"標準時数データを読み込みました: {len(standard_hours)}件")
            return standard_hours
            
        except Exception as e:
            self.logger.error(f"標準時数読み込みエラー: {e}")
            raise
    
    def load_school_data(self, base_timetable_file: str = "base_timetable.csv") -> School:
        """学校の基本データを読み込んでSchoolエンティティを構築"""
        school = School()
        
        # 標準時数データから学校情報を構築
        standard_hours = self.load_standard_hours(base_timetable_file)
        
        # 教員マッピングを読み込み
        # self.base_pathが既にdata/configを指している場合は、configを重複させない
        # Always use just the filename since base_path already points to config
        teacher_mapping_repo = TeacherMappingRepository(self.base_path)
        teacher_mapping = teacher_mapping_repo.load_teacher_mapping("teacher_subject_mapping.csv")
        
        for (class_ref, subject), hours in standard_hours.items():
            # クラスを追加
            school.add_class(class_ref)
            
            # クラスに対して無効な教科はスキップ
            if not subject.is_valid_for_class(class_ref):
                self.logger.warning(f"標準時数データ: クラス{class_ref}に無効な教科をスキップ: {subject}")
                continue
            
            # 標準時数を設定
            school.set_standard_hours(class_ref, subject, hours)
            
            # 交流学級の特別処理
            if class_ref.is_exchange_class():
                # 交流学級は自立以外の教科では教員を割り当てない
                if subject.name != "自立":
                    self.logger.debug(f"交流学級 {class_ref} の {subject} は教員割り当て不要（親学級と一緒に授業）")
                    continue
                # 自立の場合は通常通り教員マッピングから取得
            
            # 教員マッピングから全ての教員を取得（複数教師対応）
            if hasattr(teacher_mapping_repo, 'get_all_teachers_for_subject_class'):
                teachers = teacher_mapping_repo.get_all_teachers_for_subject_class(teacher_mapping, subject, class_ref)
            else:
                # 後方互換性のため
                teacher = teacher_mapping_repo.get_teacher_for_subject_class(teacher_mapping, subject, class_ref)
                teachers = [teacher] if teacher else []
            
            # マッピングにない場合はスキップ（実在の教員のみを使用）
            if not teachers:
                # 交流学級の自立以外は正常な状態なので、警告レベルを下げる
                if class_ref.is_exchange_class():
                    self.logger.debug(f"教員マッピングなし: {class_ref} {subject}")
                else:
                    self.logger.warning(f"教員マッピングなし: {class_ref} {subject} - この教科は担当教員が設定されていないため、スキップします")
                continue
            
            # 全ての教師を登録
            for teacher in teachers:
                school.add_teacher(teacher)
                school.assign_teacher_subject(teacher, subject)
                # 注：assign_teacher_to_classは1人しか登録できないため、
                # 最初の教師のみを「正式な担当」として登録
                if teachers.index(teacher) == 0:
                    school.assign_teacher_to_class(teacher, subject, class_ref)
        
        # 恒久的な教師の休み情報を適用
        permanent_absences = teacher_mapping_repo.get_permanent_absences()
        for teacher_name, absences in permanent_absences.items():
            for day, absence_type in absences:
                periods = self._get_periods_from_absence_type(absence_type)
                for period in periods:
                    # 教師名のバリエーションを試す
                    teacher_variations = [teacher_name, f"{teacher_name}先生"]
                    for variation in teacher_variations:
                        school.set_teacher_unavailable(day, period, Teacher(variation))
                    self.logger.info(f"恒久的休み設定: {teacher_name} - {day}{period}時限")
        
        self.logger.info(f"学校データを構築しました: {school}")
        
        # Schoolオブジェクトを保持（CSVWriter用）
        self._loaded_school = school
        
        return school
    
    def _get_periods_from_absence_type(self, absence_type: str) -> List[int]:
        """休み種別から対象時限を取得"""
        if absence_type == '終日':
            return [1, 2, 3, 4, 5, 6]
        elif absence_type == '午後':
            return [4, 5, 6]
        else:
            return []
    
    def _get_parent_class(self, exchange_class: ClassReference) -> Optional[ClassReference]:
        """交流学級の親学級を取得"""
        exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        return exchange_mappings.get(exchange_class)
    
    # ========== 拡張機能用のメソッド ==========
    
    def _load_desired_schedule_enhanced(self, filename: str, school: School) -> Schedule:
        """拡張版の希望時間割読み込み（教師不在を考慮）"""
        file_path = self.base_path / filename
        schedule = Schedule()
        # 初期スケジュール読み込み時は固定科目保護を一時的に無効化
        schedule.disable_fixed_subject_protection()
        
        # Grade5Unitの初期化
        grade5_unit = Grade5Unit()
        schedule.grade5_unit = grade5_unit
        
        try:
            rows = CSVOperations.read_csv_raw(str(file_path))
            
            # ヘッダー行をスキップ
            if len(rows) < 3:
                self.logger.warning(f"ファイルが短すぎます: {file_path}")
                return schedule
            
            # 各クラスの行を処理
            for row_idx in range(2, len(rows)):
                if row_idx >= len(rows) or not rows[row_idx]:
                    continue
                
                row = rows[row_idx]
                if len(row) < 31:  # クラス名 + 30コマ
                    continue
                
                class_name = row[0].strip()
                if not class_name or '組' not in class_name:
                    continue
                
                # クラス参照を作成
                try:
                    grade, class_num = self._parse_class_name(class_name)
                    class_ref = ClassReference(grade, class_num)
                except ValueError:
                    self.logger.warning(f"無効なクラス名: {class_name}")
                    continue
                
                # 5組かどうか判定
                is_grade5 = class_num == 5
                
                # 各時限の割り当てを処理
                for col_idx in range(1, min(31, len(row))):
                    subject_name = row[col_idx].strip()
                    
                    if not subject_name:
                        continue
                    
                    # 時間枠を計算
                    day_idx = (col_idx - 1) // 6
                    period = ((col_idx - 1) % 6) + 1
                    days = ["月", "火", "水", "木", "金"]
                    if day_idx >= len(days):
                        continue
                    
                    time_slot = TimeSlot(days[day_idx], period)
                    
                    # 無効な教科名をスキップ
                    if subject_name == '0':
                        self.logger.warning(f"無効な教科名をスキップ: {subject_name} (Invalid subject: {subject_name})")
                        continue
                    
                    # 「非○○」形式の場合、配置禁止として記録
                    if subject_name.startswith('非'):
                        forbidden_subject = subject_name[1:]
                        self._add_forbidden_cell(class_ref, time_slot, forbidden_subject)
                        self.logger.info(f"セル配置禁止を追加: {class_ref}の{time_slot}に{forbidden_subject}を配置禁止")
                        continue
                    
                    # 固定教科の場合はロック
                    if subject_name in ['欠', 'YT', '道', '学', '学活', '学総', '総', '総合', '行']:
                        subject = Subject(subject_name)
                        # 「欠」の場合は教員なし、それ以外は担当教員を設定
                        if subject_name == '欠':
                            assignment = Assignment(class_ref, subject, None)
                        else:
                            teacher = Teacher(f"{subject_name}担当")
                            assignment = Assignment(class_ref, subject, teacher)
                        
                        if is_grade5:
                            # 5組の場合、ユニットに登録
                            # 「欠」の場合はteacherがNone
                            if subject_name == '欠':
                                grade5_unit.assign(time_slot, subject, None)
                            else:
                                grade5_unit.assign(time_slot, subject, teacher)
                            grade5_unit.lock_slot(time_slot)
                        else:
                            schedule.assign(time_slot, assignment)
                            schedule.lock_cell(time_slot, class_ref)
                        continue
                    
                    # 教師を取得
                    teacher = school.get_assigned_teacher(Subject(subject_name), class_ref)
                    if not teacher:
                        # 教師が見つからない場合、マッピングリポジトリから取得
                        teacher_name = self.teacher_mapping_repo.get_teacher_for_subject(
                            subject_name, grade, class_num)
                        if teacher_name:
                            teacher = Teacher(teacher_name)
                        else:
                            teacher = Teacher(f"{subject_name}担当")
                    
                    # 教師不在チェックは読み込み時には行わない
                    # 初期スケジュールの読み込みでは、教師不在でも割り当てを保持する
                    # （教師不在による削除は後の処理で行う）
                    
                    # 通常の割り当て
                    subject = Subject(subject_name)
                    assignment = Assignment(class_ref, subject, teacher)
                    
                    if is_grade5:
                        grade5_unit.assign(time_slot, subject, teacher)
                        self.logger.info(f"5組ユニット: {time_slot}に{subject}({teacher})を割り当て")
                    else:
                        schedule.assign(time_slot, assignment)
                
            
            # 5組の初期同期処理
            self._sync_grade5_initial_enhanced(schedule, grade5_unit)
            
            # 交流学級の初期同期処理
            self._sync_exchange_classes_initial_enhanced(schedule, school)
            
            self.logger.info(f"希望時間割を読み込みました: {file_path}")
            # 読み込み完了後に固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            return schedule
            
        except Exception as e:
            self.logger.error(f"希望時間割の読み込みエラー: {e}")
            # エラー時も固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
            raise
    
    def _parse_class_name(self, class_name: str) -> Tuple[int, int]:
        """クラス名から学年とクラス番号を抽出"""
        parts = class_name.replace('年', ' ').replace('組', '').split()
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        raise ValueError(f"Invalid class name format: {class_name}")
    
    def _add_forbidden_cell(self, class_ref: ClassReference, time_slot: TimeSlot, 
                          forbidden_subject: str) -> None:
        """セル別配置禁止を追加"""
        key = (class_ref, time_slot)
        if key not in self._forbidden_cells:
            self._forbidden_cells[key] = set()
        self._forbidden_cells[key].add(forbidden_subject)
    
    def _find_alternative_for_grade5(self, school: School, class_ref: ClassReference,
                                    time_slot: TimeSlot, original_subject: str, 
                                    absent_teacher: str) -> Optional[Dict[str, str]]:
        """5組の代替教科・教師を探す"""
        # 利用可能な教科と教師のペアを探す
        alternatives = []
        
        # 主要教科を優先
        for subject_name in ['国', '数', '理', '社', '英', '音', '美', '技', '家', '保']:
            if subject_name == original_subject:
                continue
            
            # この教科の教師を取得
            teacher_name = self.teacher_mapping_repo.get_teacher_for_subject(
                subject_name, class_ref.grade, class_ref.class_num)
            
            if teacher_name and not self.absence_loader.is_teacher_absent(
                teacher_name, time_slot.day, time_slot.period):
                alternatives.append({
                    'subject': subject_name,
                    'teacher': teacher_name,
                    'priority': 1 if subject_name in ['国', '数', '理', '社', '英'] else 2
                })
        
        # 優先度順にソート
        alternatives.sort(key=lambda x: x['priority'])
        
        return alternatives[0] if alternatives else None
    
    def _sync_grade5_initial_enhanced(self, schedule: Schedule, grade5_unit: Grade5Unit) -> None:
        """5組の初期同期処理（拡張版）"""
        self.logger.info("=== 5組の初期同期処理を開始 ===")
        sync_count = 0
        
        # Grade5Unitから全ての割り当てを取得してScheduleに反映
        for time_slot, class_ref, assignment in grade5_unit.get_all_assignments():
            schedule.assign(time_slot, assignment)
            if grade5_unit.is_locked(time_slot):
                schedule.lock_cell(time_slot, class_ref)
            sync_count += 1
        
        self.logger.info(f"=== 5組の初期同期完了: {sync_count}時限を同期 ===")
    
    def _sync_exchange_classes_initial_enhanced(self, schedule: Schedule, school: School) -> None:
        """交流学級の初期同期処理（拡張版）"""
        self.logger.info("=== 交流学級の初期同期処理を開始（CSV読み込み時） ===")
        
        # 交流学級のペアを定義
        exchange_pairs = [
            (ClassReference(1, 1), ClassReference(1, 6)),
            (ClassReference(2, 3), ClassReference(2, 6)),
            (ClassReference(3, 3), ClassReference(3, 6))
        ]
        
        sync_count = 0
        jiritsu_sync_count = 0
        
        for parent_class, child_class in exchange_pairs:
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    child_assignment = schedule.get_assignment(time_slot, child_class)
                    
                    # 自立の同期処理
                    if child_assignment and child_assignment.subject.name == "自立":
                        if parent_assignment:
                            self.logger.info(
                                f"交流学級同期（自立）: {time_slot} {child_class}の自立をロック")
                            schedule.lock_cell(time_slot, child_class)
                            self.logger.info(f"  {parent_class}の{parent_assignment.subject}をロック")
                            schedule.lock_cell(time_slot, parent_class)
                            jiritsu_sync_count += 1
        
        self.logger.info(
            f"=== 交流学級の初期同期完了: 通常同期{sync_count}件、自立同期{jiritsu_sync_count}件 ===")
    
    def _get_grade5_display(self, class_ref: ClassReference, subject: str, 
                           day: str, period: int) -> str:
        """5組の表示を取得（時数表記または通常教科）"""
        # 時数表記を使用すべきか判定
        if self.support_hour_system.should_use_support_hour(class_ref, subject, day, period):
            return self.support_hour_system.get_support_hour_code(class_ref, subject, day, period)
        return subject
    
    # ========== 支援時数機能用のメソッド ==========
    
    def _get_support_hour_display(self, assignment: Assignment, 
                                  time_slot: TimeSlot, 
                                  class_ref: ClassReference) -> str:
        """5組の時数表記を取得（支援時数版）"""
        # 特別な教科はそのまま表示
        if assignment.subject.name in ["欠", "YT", "道", "日生", "自立", "作業"]:
            return assignment.subject.name
        
        # 支援時数表記の場合は、CSVWriterに処理を委譲する
        # ここでは単純に教科名を返す
        return assignment.subject.name
    
    # ========== 教師別時間割 ==========
    
    def save_teacher_schedule(self, schedule: Schedule, school: School, 
                             filename: str = "teacher_schedule.csv") -> None:
        """教師別時間割をCSVファイルに保存"""
        if filename == "teacher_schedule.csv":
            file_path = path_config.get_output_path(filename)
        else:
            file_path = Path(filename) if filename.startswith("/") else self.base_path / filename
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # データを準備
            all_rows = []
            
            # ヘッダー行
            header = ["教員"]
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    header.append(day)
            all_rows.append(header)
                
            # 校時行
            period_row = [""]
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    period_row.append(str(period))
            all_rows.append(period_row)
                
            # 各教師の行
            all_teachers = list(school.get_all_teachers())
            
            for teacher in sorted(all_teachers, key=lambda t: t.name):
                row = [teacher.name]
                
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 7):
                        time_slot = TimeSlot(day, period)
                        
                        # この時間の授業を探す
                        cell_content = ""
                        for class_ref in school.get_all_classes():
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                                # クラス表示形式の選択
                                if self.use_enhanced_features:
                                    cell_content = f"{class_ref.short_name_alt}"
                                else:
                                    cell_content = f"{class_ref.grade}-{class_ref.class_number}"
                                break
                        
                        row.append(cell_content)
                
                all_rows.append(row)
                
            # 拡張機能が有効な場合は会議時間の行も追加
            if self.use_enhanced_features:
                self._add_meeting_rows_to_list(all_rows)
            
            # CSVOperationsを使用して書き込み
            CSVOperations.write_csv_raw(str(file_path), all_rows, quoting=csv.QUOTE_ALL)
            
            if self.use_enhanced_features or self.use_support_hours:
                self.logger.info(f"教師別時間割を保存しました（5組時数表記対応）: {file_path}")
            else:
                self.logger.info(f"教師別時間割を保存しました: {file_path}")
            
        except Exception as e:
            self.logger.error(f"教師別時間割保存エラー: {e}")
            raise
    
    def _add_meeting_rows(self, writer) -> None:
        """会議時間の行を追加（旧バージョン - 互換性のため残存）"""
        all_rows = []
        self._add_meeting_rows_to_list(all_rows)
        for row in all_rows:
            writer.writerow(row)
    
    def _add_meeting_rows_to_list(self, rows_list: List[List[str]]) -> None:
        """会議時間の行を追加"""
        # 会議情報（理想の結果から）
        meetings = {
            "青井": ["", "", "", "", "", "", "3-1選", "", "", "", "", "YT", 
                    "", "", "", "", "", "YT", "", "", "", "", "", "", 
                    "", "", "", "", "", "YT"],
            "校長": ["企画", "HF", "", "", "", "", "生指", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", "",
                    "終日不在（赤色で表示）"],
            "児玉": ["企画", "HF", "", "", "", "", "生指", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", ""],
            "吉村": ["企画", "HF", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", "", "", "", "", "", "", "",
                    "", "", "", "", "", ""],
        }
        
        # 空行を追加
        rows_list.append([""] * 31)
        
        # 会議行を追加
        for teacher, schedule in meetings.items():
            rows_list.append([teacher] + schedule)
    
    def _get_default_teacher_name(self, subject: Subject, class_ref: ClassReference) -> str:
        """教科・クラスに基づくデフォルト教員名を生成 - 削除予定"""
        # 注意: デフォルト教員は使用しない。実在の教員のみを使用する。
        # この関数は互換性のために残されているが、使用すべきではない
        self.logger.warning(f"警告: デフォルト教員名が要求されました: {subject.name} for {class_ref}")




================================================================================

# ファイル: src/infrastructure/config/constraint_loader.py

================================================================================

"""制約条件を各種ファイルから読み込む統合ローダー"""
from pathlib import Path
from typing import List, Optional

from ...domain.constraints.base import Constraint, ConstraintValidator
from ..parsers.basics_constraint_parser import BasicsConstraintParser
from ..parsers.followup_constraint_parser import FollowupConstraintParser
from .path_config import path_config
from .qa_rules_loader import QARulesLoader
from ...shared.mixins.logging_mixin import LoggingMixin

# 既存の制約クラスのインポート
from ...domain.constraints.monday_sixth_period_constraint import MondaySixthPeriodConstraint
from ...domain.constraints.tuesday_pe_constraint import TuesdayPEMultipleConstraint
from ...domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint
from ...domain.constraints.subject_validity_constraint import SubjectValidityConstraint
from ...domain.constraints.exchange_class_sync_constraint import ExchangeClassSyncConstraint
from ...domain.constraints.daily_duplicate_constraint import DailyDuplicateConstraint
from ...domain.constraints.hf_meeting_constraint import HFMeetingConstraint
from ...domain.constraints.grade5_test_exclusion_constraint import Grade5TestExclusionConstraint
from ...domain.constraints.part_time_teacher_constraint import PartTimeTeacherConstraint
from ...domain.constraints.home_economics_teacher_constraint import HomeEconomicsTeacherConstraint
from ...domain.constraints.grade5_teacher_constraint import Grade5TeacherConstraint


class ConstraintLoader(LoggingMixin):
    """制約条件の統合ローダー"""
    
    def __init__(self):
        super().__init__()
        self.basics_path = path_config.config_dir / "basics.csv"
        self.followup_path = path_config.input_dir / "Follow-up.csv"
        
        # QA.txtからビジネスルールを読み込み
        self.qa_rules_loader = QARulesLoader()
    
    def load_all_constraints(self) -> List[Constraint]:
        """すべての制約を読み込む"""
        constraints = []
        
        # 基本制約を読み込み（basics.csv）
        if self.basics_path.exists():
            try:
                basics_parser = BasicsConstraintParser(self.basics_path)
                basic_constraints = basics_parser.parse()
                constraints.extend(basic_constraints)
                self.logger.info(f"basics.csvから{len(basic_constraints)}個の制約を読み込みました")
            except Exception as e:
                self.logger.error(f"basics.csv読み込みエラー: {e}")
        
        # 週次制約を読み込み（Follow-up.csv）
        if self.followup_path.exists():
            try:
                followup_parser = FollowupConstraintParser(self.followup_path)
                weekly_constraints = followup_parser.parse()
                constraints.extend(weekly_constraints)
                self.logger.info(f"Follow-up.csvから{len(weekly_constraints)}個の制約を読み込みました")
            except Exception as e:
                self.logger.error(f"Follow-up.csv読み込みエラー: {e}")
        
        # システム定義の制約を追加（ハードコードされていた制約）
        system_constraints = self._get_system_constraints()
        constraints.extend(system_constraints)
        
        self.logger.info(f"合計{len(constraints)}個の制約を読み込みました")
        return constraints
    
    def create_constraint_validator(self) -> ConstraintValidator:
        """制約バリデーターを作成"""
        constraints = self.load_all_constraints()
        return ConstraintValidator(constraints)
    
    def _get_system_constraints(self) -> List[Constraint]:
        """システム定義の制約を取得（QA.txtのルールを注入）"""
        # QA.txtから読み込んだルールを取得
        rules = self.qa_rules_loader.rules
        
        # これらは元々ハードコードされていた重要な制約
        constraints = [
            # 月曜6限のルール（QA.txtから注入）
            MondaySixthPeriodConstraint(
                sixth_period_rules=rules.get('grade_6th_period_rules', {})
            ),
            
            # 火曜日は体育優先
            TuesdayPEMultipleConstraint(),
            
            # 教員の重複防止
            TeacherConflictConstraint(),
            
            # 教科の妥当性チェック
            SubjectValidityConstraint(),
            
            # 交流学級同期制約
            ExchangeClassSyncConstraint(),
            
            # 日内重複制約
            DailyDuplicateConstraint(),
            
            # HF会議制約（火曜4限の2年生授業禁止）
            HFMeetingConstraint(),
            
            # 5組テスト除外制約（テスト期間中、5組は通常クラスのテスト科目を受けられない）
            Grade5TestExclusionConstraint(),
            
            # 非常勤教師時間制約（QA.txtから注入）
            PartTimeTeacherConstraint(
                part_time_schedules=rules.get('part_time_schedules', {})
            ),
            
            # 家庭科教師制約（金子み先生のみ）
            HomeEconomicsTeacherConstraint(),
            
            # 5組教師制約（各教科の指定教師）
            Grade5TeacherConstraint()
        ]
        
        return constraints
    
    def reload_constraints(self, validator: ConstraintValidator) -> None:
        """制約を再読み込みしてバリデーターを更新"""
        new_constraints = self.load_all_constraints()
        
        # 既存の制約をクリア
        validator.constraints.clear()
        
        # 新しい制約を追加
        for constraint in new_constraints:
            validator.add_constraint(constraint)
        
        self.logger.info(f"制約を再読み込みしました: {len(new_constraints)}個")


# グローバルインスタンス（シングルトン）
constraint_loader = ConstraintLoader()


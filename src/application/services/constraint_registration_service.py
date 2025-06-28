"""制約登録サービス - 制約の登録を一元管理"""
import logging
from pathlib import Path
from typing import Dict, List

from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem, ConstraintPriority
from .followup_processor import FollowUpProcessor
from ...infrastructure.di_container import get_configuration_reader, get_followup_parser, get_schedule_repository
from ...domain.constraints import (
    TeacherAvailabilityConstraint,
    DailySubjectDuplicateConstraint,
    StandardHoursConstraint,
    MondaySixthPeriodConstraint,
    TuesdayPEMultipleConstraint,
    FixedSubjectLockConstraint,
    MeetingLockConstraint,
    TeacherAbsenceConstraint,
    PlacementForbiddenConstraint,
    CellForbiddenSubjectConstraint,
    SubjectValidityConstraint,
    PartTimeTeacherConstraint,
    Grade5SameSubjectConstraint
)
from ...domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint
from ...domain.constraints.gym_usage_constraint import GymUsageConstraintRefactored
from ...domain.constraints.learned_rule_constraint import LearnedRuleConstraint
from .learned_rule_application_service import LearnedRuleApplicationService
# from ...domain.constraints.test_period_exclusion import TestPeriodExclusionConstraint  # TODO: validateメソッドを実装後に有効化


class ConstraintRegistrationService:
    """制約の登録を一元管理するサービス
    
    このサービスは制約の登録ロジックを集約し、
    GenerateScheduleUseCaseとValidateScheduleUseCaseの重複を解消します。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.followup_processor = FollowUpProcessor()
        self.learned_rule_service = None  # 後で設定
        
    def register_all_constraints(
        self, 
        constraint_system: UnifiedConstraintSystem,
        data_dir: Path,
        teacher_absences: Dict[str, List] = None
    ) -> None:
        """すべての制約を統一システムに登録
        
        Args:
            constraint_system: 制約システム
            data_dir: データディレクトリのパス
            teacher_absences: 教師不在情報（オプション）
        """
        # 1. 標準制約の登録
        self._register_standard_constraints(constraint_system)
        
        # 2. 配置禁止セル制約（非保・非数・非理）の登録
        self._register_forbidden_cells_from_input(constraint_system, data_dir)
        
        # 3. Basics.csvからの制約読み込み
        self._register_basics_constraints(constraint_system, data_dir)
        
        # 4. Follow-up.csvからのテスト期間制約
        self._register_test_period_constraints(constraint_system, data_dir)
        
        # 5. 教師不在制約（提供された場合）
        if teacher_absences:
            self._register_teacher_absence_constraints(constraint_system, teacher_absences)
        
        # 6. QandAシステムから学習したルール制約
        self.logger.warning("学習ルール制約の登録を開始")
        self._register_learned_rule_constraints(constraint_system)
        
        self.logger.warning(f"制約登録完了: {len(constraint_system.constraints)}件")
    
    def _register_standard_constraints(self, constraint_system: UnifiedConstraintSystem) -> None:
        """標準制約を登録"""
        # 学習ルールサービスを先に作成
        if not self.learned_rule_service:
            self.learned_rule_service = LearnedRuleApplicationService()
            self.learned_rule_service.parse_and_load_rules()
        
        # テスト期間チェッカーを作成（後で使用）
        self.test_period_checker = None
        
        # 制約を保存（後でテスト期間チェッカーを更新）
        self.teacher_conflict_constraint = TeacherConflictConstraint()
        
        standard_constraints = [
            # 高優先度制約
            (self.teacher_conflict_constraint, ConstraintPriority.CRITICAL),
            (MondaySixthPeriodConstraint(), ConstraintPriority.CRITICAL),
            (FixedSubjectLockConstraint(), ConstraintPriority.CRITICAL),
            # (TestPeriodExclusionConstraint({}), ConstraintPriority.CRITICAL),  # TODO: validateメソッドを実装後に有効化
            
            # 中優先度制約
            (DailySubjectDuplicateConstraint(), ConstraintPriority.HIGH),
            (GymUsageConstraintRefactored(), ConstraintPriority.HIGH),
            (MeetingLockConstraint(), ConstraintPriority.HIGH),
            # (PlacementForbiddenConstraint(['道', '学', '総']), ConstraintPriority.HIGH),  # 設定データ必要
            # (TeacherAbsenceConstraint({}), ConstraintPriority.HIGH),  # 動的に追加
            (Grade5SameSubjectConstraint(), ConstraintPriority.HIGH),
            
            # 低優先度制約
            (StandardHoursConstraint(), ConstraintPriority.MEDIUM),
            (TuesdayPEMultipleConstraint(), ConstraintPriority.MEDIUM),
            # (CellForbiddenSubjectConstraint(), ConstraintPriority.MEDIUM),  # 設定データ必要
            (SubjectValidityConstraint(), ConstraintPriority.MEDIUM),
            # (PartTimeTeacherConstraint(), ConstraintPriority.LOW),  # 設定データ必要
        ]
        
        # 技家実現可能性制約を追加（テスト期間チェッカー付き）
        try:
            from ...domain.constraints.techome_feasibility_constraint import TechHomeFeasibilityConstraint
            from ...domain.services.core.test_period_checker import TestPeriodChecker
            
            # テスト期間チェッカーはまだ作成できない（Follow-up.csvが読まれていないため）
            # 後で_register_test_period_constraintsで更新する
            self.techome_constraint = TechHomeFeasibilityConstraint()
            standard_constraints.insert(4, (self.techome_constraint, ConstraintPriority.HIGH))
        except ImportError:
            self.logger.warning("技家実現可能性制約のインポートに失敗しました")
        
        for constraint, priority in standard_constraints:
            constraint_system.register_constraint(constraint, priority)
        
        self.logger.debug(f"標準制約を{len(standard_constraints)}件登録しました")
    
    def _register_basics_constraints(
        self, 
        constraint_system: UnifiedConstraintSystem,
        data_dir: Path
    ) -> None:
        """Basics.csvから追加制約を読み込んで登録"""
        basics_file = data_dir / "config" / "basics.csv"
        
        if not basics_file.exists():
            self.logger.warning(f"Basics.csvが見つかりません: {basics_file}")
            return
        
        try:
            from ...infrastructure.parsers.basics_constraint_parser import BasicsConstraintParser
            basics_parser = BasicsConstraintParser(basics_file)
            additional_constraints = basics_parser.parse()
            
            for constraint in additional_constraints:
                # BasicsParserから返される制約には優先度が設定されているはず
                priority = getattr(constraint, 'priority', ConstraintPriority.HIGH)
                constraint_system.register_constraint(constraint, priority)
            
            self.logger.info(f"Basics.csvから{len(additional_constraints)}件の制約を追加登録")
            
        except Exception as e:
            self.logger.error(f"Basics.csv読み込みエラー: {e}")
    
    def _register_test_period_constraints(
        self,
        constraint_system: UnifiedConstraintSystem,
        data_dir: Path
    ) -> None:
        """Follow-up.csvからテスト期間制約を読み込んで登録"""
        followup_file = data_dir / "input" / "Follow-up.csv"
        
        if not followup_file.exists():
            self.logger.debug("Follow-up.csvが見つかりません")
            return
        
        try:
            followup_parser = get_followup_parser()
            
            # Follow-up情報をパース
            natural_result = {}
            test_periods = followup_parser.parse_test_periods()
            if test_periods:
                natural_result["test_periods"] = test_periods
            
            # テスト期間情報を抽出
            if "test_periods" in natural_result:
                test_period_dict = {}
                test_period_set = set()
                for test_period in natural_result["test_periods"]:
                    day = test_period.day
                    description = getattr(test_period, 'reason', 'テスト期間')
                    for period in test_period.periods:
                        test_period_dict[(day, period)] = description
                        test_period_set.add((day, period))
                
                if test_period_dict:
                    # テスト期間チェッカーを作成
                    from ...domain.services.core.test_period_checker import TestPeriodChecker
                    test_period_checker = TestPeriodChecker(test_period_set)
                    
                    # 技家制約のテスト期間チェッカーを更新
                    if hasattr(self, 'techome_constraint'):
                        self.techome_constraint.test_period_checker = test_period_checker
                        self.logger.info(f"技家制約にテスト期間情報を設定: {len(test_period_set)}件")
                    
                    # 教師重複制約のテスト期間チェッカーを更新
                    if hasattr(self, 'teacher_conflict_constraint'):
                        self.teacher_conflict_constraint.test_period_checker = test_period_checker
                        self.logger.info(f"教師重複制約にテスト期間情報を設定: {len(test_period_set)}件")
                    
                    # TODO: TestPeriodExclusionConstraintのvalidateメソッド実装後に有効化
                    pass
                    # # 既存のTestPeriodExclusionConstraintを更新
                    # for constraint in constraint_system.constraints:
                    #     if isinstance(constraint, TestPeriodExclusionConstraint):
                    #         constraint.test_periods.update(test_period_dict)
                    #         break
                    # else:
                    #     # 新規作成
                    #     constraint_system.register_constraint(
                    #         TestPeriodExclusionConstraint(test_period_dict),
                    #         ConstraintPriority.CRITICAL
                    #     )
                    
                    self.logger.info(f"テスト期間制約を{len(test_period_dict)}件登録")
                    
        except Exception as e:
            self.logger.error(f"テスト期間制約の読み込みエラー: {e}")
    
    def _register_teacher_absence_constraints(
        self,
        constraint_system: UnifiedConstraintSystem,
        teacher_absences: Dict[str, List]
    ) -> None:
        """教師不在制約を登録"""
        if not teacher_absences:
            return
        
        # TeacherAbsenceConstraintを登録
        # 既存の制約があるかチェック
        has_teacher_absence_constraint = any(
            isinstance(constraint, TeacherAbsenceConstraint) 
            for constraint in constraint_system.constraints
        )
        
        if not has_teacher_absence_constraint:
            # 新規作成 - TeacherAbsenceConstraintは引数なしで呼び出す
            # （DIコンテナから自動的にリポジトリを取得）
            constraint_system.register_constraint(
                TeacherAbsenceConstraint(),
                ConstraintPriority.HIGH
            )
        
        self.logger.info(f"教師不在制約を{len(teacher_absences)}件登録")
    
    def _register_learned_rule_constraints(
        self,
        constraint_system: UnifiedConstraintSystem
    ) -> None:
        """QandAシステムから学習したルール制約を登録"""
        try:
            # 既に作成済みのlearned_rule_serviceを使用
            if not self.learned_rule_service:
                self.learned_rule_service = LearnedRuleApplicationService()
                self.learned_rule_service.parse_and_load_rules()
            
            # ルール数を取得
            rules_count = len(self.learned_rule_service.parsed_rules)
            
            if rules_count > 0:
                # 学習ルール制約を作成して登録
                learned_constraint = LearnedRuleConstraint(self.learned_rule_service)
                constraint_system.register_constraint(
                    learned_constraint,
                    ConstraintPriority.HIGH
                )
                self.logger.warning(f"学習ルール制約を登録（{rules_count}個のルール）")
            else:
                self.logger.warning("学習ルールがないため、学習ルール制約は登録しません")
                
        except Exception as e:
            self.logger.warning(f"学習ルール制約の登録に失敗: {e}")
    
    def _register_forbidden_cells_from_input(self, constraint_system: UnifiedConstraintSystem, data_dir: Path) -> None:
        """input.csvから配置禁止セル制約（非保・非数・非理）を読み込んで登録"""
        try:
            # スケジュールリポジトリを取得
            schedule_repo = get_schedule_repository()
            
            # input.csvを読み込み（forbidden_cellsデータを取得するため）
            from ...domain.entities.schedule import Schedule
            schedule = Schedule()
            schedule.disable_fixed_subject_protection()
            schedule.disable_grade5_sync()
            
            # 一時的に読み込み
            schedule_repo.load("data/input/input.csv", None)
            
            # 配置禁止セルを取得
            forbidden_cells = schedule_repo.get_forbidden_cells()
            
            if forbidden_cells:
                # CellForbiddenSubjectConstraintを作成して登録
                constraint = CellForbiddenSubjectConstraint(forbidden_cells)
                constraint_system.register_constraint(constraint, ConstraintPriority.CRITICAL)
                self.logger.info(f"配置禁止セル制約を登録: {len(forbidden_cells)}件")
                
                # デバッグ用に最初の3件を表示
                for i, ((time_slot, class_ref), subjects) in enumerate(forbidden_cells.items()):
                    if i >= 3:
                        break
                    self.logger.debug(f"  例: {class_ref} {time_slot} - {subjects}")
            
        except Exception as e:
            self.logger.error(f"配置禁止セル制約の読み込みエラー: {e}")
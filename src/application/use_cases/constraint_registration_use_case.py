"""制約登録ユースケース

各種制約の読み込みと登録を担当する。
"""
import logging
from pathlib import Path
from typing import Dict, List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ...infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from ...domain.constraints.base import ConstraintPriority
from ...domain.value_objects.time_slot import TimeSlot

# 制約のインポート
from ...domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint
from ...domain.constraints.monday_sixth_period_constraint import MondaySixthPeriodConstraint
from ...domain.constraints.fixed_subject_constraint import FixedSubjectConstraint
from ...domain.constraints.daily_duplicate_constraint import DailyDuplicateConstraint
from ...domain.constraints.techome_feasibility_constraint import TechHomeFeasibilityConstraint
from ...domain.constraints.gym_usage_constraint import GymUsageConstraint
from ...domain.constraints.meeting_lock_constraint import MeetingLockConstraint
from ...domain.constraints.grade5_same_subject_constraint import Grade5SameSubjectConstraint
from ...domain.constraints.teacher_absence_constraint import TeacherAbsenceConstraint
from ...domain.constraints.test_period_exclusion import TestPeriodExclusionConstraint
from ...domain.constraints.basic_constraints import StandardHoursConstraint
from ...domain.constraints.subject_validity_constraint import SubjectValidityConstraint
from ...domain.constraints.tuesday_pe_constraint import TuesdayPEMultipleConstraint
from ...domain.constraints.cell_forbidden_subject_constraint import CellForbiddenSubjectConstraint

from ...infrastructure.di_container import (
    get_constraint_loader,
    get_configuration_reader,
    get_teacher_absence_repository
)
from ...infrastructure.parsers.basics_parser import BasicsParser
from ...infrastructure.config.constraint_loader import ConstraintLoader
from ..services.learned_rule_application_service import LearnedRuleApplicationService


class ConstraintRegistrationUseCase:
    """制約登録ユースケース
    
    責任：
    - 基本制約の読み込みと登録
    - テスト期間制約の設定
    - 教師不在制約の設定
    - 学習ルールの適用
    """
    
    def __init__(
        self,
        constraint_system: UnifiedConstraintSystem,
        data_dir: Path,
        teacher_absence_loader: 'TeacherAbsenceLoader'
    ):
        """初期化
        
        Args:
            constraint_system: 統一制約システム
            data_dir: データディレクトリ
            teacher_absence_loader: 教師不在情報ローダー
        """
        self.constraint_system = constraint_system
        self.data_dir = data_dir
        self.teacher_absence_loader = teacher_absence_loader
        self.logger = logging.getLogger(__name__)
        
        # 学習ルールサービス
        self.learned_rule_service = LearnedRuleApplicationService(constraint_system)
        
        # テスト期間情報
        self.test_periods: Set[tuple] = set()
    
    def execute(
        self,
        school: School,
        schedule: Schedule,
        followup_data: Dict,
        forbidden_cells: Dict = None,
        enable_soft_constraints: bool = False
    ) -> None:
        """制約登録を実行
        
        Args:
            school: 学校データ
            schedule: スケジュール
            followup_data: Follow-upデータ
            forbidden_cells: 配置禁止セル情報（非保・非数・非理）
            enable_soft_constraints: ソフト制約を有効にするか
        """
        # 基本制約の登録
        self._register_basic_constraints()
        
        # 配置禁止セル制約の登録（非保・非数・非理）
        if forbidden_cells:
            self._register_forbidden_cells_constraint(forbidden_cells)
        
        # テスト期間制約の登録
        self._register_test_period_constraints(followup_data)
        
        # 教師不在制約の登録
        self._register_teacher_absence_constraint()
        
        # 学習ルールの適用
        self._apply_learned_rules()
        
        # ソフト制約の登録（オプション）
        if enable_soft_constraints:
            self._register_soft_constraints()
        
        # 制約登録の統計を出力
        summary = self.constraint_system.get_constraint_summary()
        self.logger.info(f"制約登録完了: {summary['total_constraints']}件")
    
    def _register_basic_constraints(self) -> None:
        """基本制約を登録"""
        # CRITICAL制約
        self.constraint_system.register_constraint(
            TeacherConflictConstraint(),
            ConstraintPriority.CRITICAL
        )
        self.constraint_system.register_constraint(
            Monday6thPeriodConstraint(),
            ConstraintPriority.CRITICAL
        )
        self.constraint_system.register_constraint(
            FixedSubjectConstraint(),
            ConstraintPriority.CRITICAL
        )
        
        # HIGH制約
        self.constraint_system.register_constraint(
            DailyDuplicateConstraint(),
            ConstraintPriority.HIGH
        )
        self.constraint_system.register_constraint(
            TechHomeFeasibilityConstraint(),
            ConstraintPriority.HIGH
        )
        self.constraint_system.register_constraint(
            GymUsageConstraint(),
            ConstraintPriority.HIGH
        )
        self.constraint_system.register_constraint(
            MeetingLockConstraint(),
            ConstraintPriority.HIGH
        )
        self.constraint_system.register_constraint(
            Grade5SameSubjectConstraint(),
            ConstraintPriority.HIGH
        )
        
        # MEDIUM制約
        self.constraint_system.register_constraint(
            StandardHoursConstraint(),
            ConstraintPriority.MEDIUM
        )
        self.constraint_system.register_constraint(
            TuesdayPEMultipleConstraint(),
            ConstraintPriority.MEDIUM
        )
        self.constraint_system.register_constraint(
            SubjectValidityConstraint(),
            ConstraintPriority.MEDIUM
        )
    
    def _register_forbidden_cells_constraint(self, forbidden_cells: Dict) -> None:
        """配置禁止セル制約を登録（非保・非数・非理）"""
        self.logger.info(f"配置禁止セル制約の登録を開始: forbidden_cells={type(forbidden_cells)}, len={len(forbidden_cells) if forbidden_cells else 0}")
        if forbidden_cells:
            constraint = CellForbiddenSubjectConstraint(forbidden_cells)
            self.constraint_system.register_constraint(
                constraint,
                ConstraintPriority.CRITICAL
            )
            self.logger.info(f"配置禁止セル制約を登録: {len(forbidden_cells)}件")
        else:
            self.logger.warning("配置禁止セルが空のため、制約を登録しません")
    
    def _register_test_period_constraints(self, followup_data: Dict) -> None:
        """テスト期間制約を登録"""
        if followup_data.get("parse_success") and followup_data.get("test_periods"):
            self.test_periods = set(followup_data["test_periods"])
            
            if self.test_periods:
                # TestPeriodExclusionConstraintを登録
                test_constraint = TestPeriodExclusionConstraint(self.test_periods)
                self.constraint_system.register_constraint(
                    test_constraint,
                    ConstraintPriority.CRITICAL
                )
                
                self.logger.info(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
    
    def _register_teacher_absence_constraint(self) -> None:
        """教師不在制約を登録"""
        # Basicsファイルから基本的な制約を読み込む
        try:
            basics_path = self.data_dir / "config" / "basics.csv"
            if basics_path.exists():
                parser = BasicsParser(self.data_dir)
                basics_data = parser.parse_basics_file()
                
                # 教師不在制約を登録
                if basics_data:
                    loader = ConstraintLoader(self.data_dir / "config")
                    loader.load_and_register_constraints(
                        self.constraint_system,
                        self.teacher_absence_loader
                    )
        except Exception as e:
            self.logger.error(f"Basics.csv読み込みエラー: {e}")
        
        # 標準の教師不在制約を登録
        self.constraint_system.register_constraint(
            TeacherAbsenceConstraint(self.teacher_absence_loader),
            ConstraintPriority.HIGH
        )
    
    def _apply_learned_rules(self) -> None:
        """学習ルールを適用"""
        self.learned_rule_service.apply_learned_rules()
    
    def _register_soft_constraints(self) -> None:
        """ソフト制約を登録（オプション）"""
        # 将来的に追加のソフト制約をここに登録
        pass
    
    def get_test_periods(self) -> Set[tuple]:
        """テスト期間情報を取得"""
        return self.test_periods
"""制約条件を各種ファイルから読み込む統合ローダー"""
import logging
from pathlib import Path
from typing import List, Optional

from ...domain.constraints.base import Constraint, ConstraintValidator
from ..parsers.basics_constraint_parser import BasicsConstraintParser
from ..parsers.followup_constraint_parser import FollowupConstraintParser
from .path_config import path_config

# 既存の制約クラスのインポート
from ...domain.constraints.monday_sixth_period_constraint import MondaySixthPeriodConstraint
from ...domain.constraints.tuesday_pe_constraint import TuesdayPEMultipleConstraint
from ...domain.constraints.teacher_conflict_constraint_refactored import TeacherConflictConstraintRefactored
from ...domain.constraints.subject_validity_constraint import SubjectValidityConstraint
from ...domain.constraints.exchange_class_sync_constraint import ExchangeClassSyncConstraint
from ...domain.constraints.daily_duplicate_constraint import DailyDuplicateConstraint


class ConstraintLoader:
    """制約条件の統合ローダー"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.basics_path = path_config.config_dir / "basics.csv"
        self.followup_path = path_config.input_dir / "Follow-up.csv"
    
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
        """システム定義の制約を取得"""
        # これらは元々ハードコードされていた重要な制約
        constraints = [
            # 月曜6限は欠課
            MondaySixthPeriodConstraint(),
            
            # 火曜日は体育優先
            TuesdayPEMultipleConstraint(),
            
            # 教員の重複防止
            TeacherConflictConstraintRefactored(),
            
            # 教科の妥当性チェック
            SubjectValidityConstraint(),
            
            # 交流学級同期制約
            ExchangeClassSyncConstraint(),
            
            # 日内重複制約
            DailyDuplicateConstraint()
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
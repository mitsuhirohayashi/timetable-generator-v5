"""統合制約ローダー - 新しい統合制約システムを使用"""
import logging
from pathlib import Path
from typing import List, Optional

from ...domain.constraints.consolidated import (
    ConstraintValidator,
    ProtectedSlotConstraint,
    TeacherSchedulingConstraint,
    ClassSynchronizationConstraint,
    ResourceUsageConstraint,
    SchedulingRuleConstraint,
    SubjectValidationConstraint,
    ConsolidatedConstraint
)
from .path_config import path_config


class ConsolidatedConstraintLoader:
    """統合制約ローダー
    
    6つの統合制約クラスを使用して、従来の20以上の制約機能を提供
    """
    
    def __init__(self, initial_schedule=None):
        self.logger = logging.getLogger(__name__)
        self.initial_schedule = initial_schedule
        self._constraints_cache = None
        
    def load_all_constraints(self) -> List[ConsolidatedConstraint]:
        """すべての統合制約を読み込む"""
        if self._constraints_cache is not None:
            return self._constraints_cache
            
        constraints = []
        
        try:
            # 1. 保護スロット制約（最高優先度）
            protected_slots = ProtectedSlotConstraint(self.initial_schedule)
            constraints.append(protected_slots)
            self.logger.info("保護スロット制約を読み込みました")
            
            # 2. 教師スケジューリング制約
            teacher_scheduling = TeacherSchedulingConstraint()
            constraints.append(teacher_scheduling)
            self.logger.info("教師スケジューリング制約を読み込みました")
            
            # 3. クラス同期制約
            class_sync = ClassSynchronizationConstraint()
            constraints.append(class_sync)
            self.logger.info("クラス同期制約を読み込みました")
            
            # 4. リソース使用制約
            resource_usage = ResourceUsageConstraint()
            constraints.append(resource_usage)
            self.logger.info("リソース使用制約を読み込みました")
            
            # 5. スケジューリングルール制約
            scheduling_rules = SchedulingRuleConstraint()
            constraints.append(scheduling_rules)
            self.logger.info("スケジューリングルール制約を読み込みました")
            
            # 6. 教科検証制約
            subject_validation = SubjectValidationConstraint()
            constraints.append(subject_validation)
            self.logger.info("教科検証制約を読み込みました")
            
            # 制約の優先度順にソート
            constraints.sort()
            
            self._constraints_cache = constraints
            self.logger.info(f"合計{len(constraints)}個の統合制約を読み込みました")
            
        except Exception as e:
            self.logger.error(f"制約の読み込みエラー: {e}")
            raise
            
        return constraints
        
    def create_constraint_validator(self) -> ConstraintValidator:
        """制約バリデーターを作成"""
        constraints = self.load_all_constraints()
        return ConstraintValidator(constraints)
        
    def reload_constraints(self) -> None:
        """制約を再読み込み"""
        self._constraints_cache = None
        self.logger.info("制約キャッシュをクリアしました")
        
    def get_constraint_by_name(self, name: str) -> Optional[ConsolidatedConstraint]:
        """名前で制約を取得"""
        constraints = self.load_all_constraints()
        for constraint in constraints:
            if constraint.name == name:
                return constraint
        return None
        
    def enable_constraint(self, name: str) -> bool:
        """制約を有効化"""
        constraint = self.get_constraint_by_name(name)
        if constraint:
            constraint.config.enabled = True
            self.logger.info(f"制約 '{name}' を有効化しました")
            return True
        return False
        
    def disable_constraint(self, name: str) -> bool:
        """制約を無効化"""
        constraint = self.get_constraint_by_name(name)
        if constraint:
            constraint.config.enabled = False
            self.logger.info(f"制約 '{name}' を無効化しました")
            return True
        return False
        
    def get_constraint_summary(self) -> str:
        """制約の概要を取得"""
        constraints = self.load_all_constraints()
        summary = ["統合制約システム概要:"]
        summary.append(f"総制約数: {len(constraints)}")
        summary.append("")
        
        for constraint in constraints:
            status = "有効" if constraint.enabled else "無効"
            summary.append(f"- {constraint.name} ({constraint.type.value}, 優先度: {constraint.priority.value}) [{status}]")
            summary.append(f"  {constraint.config.description}")
            
            # CompositeConstraintの場合はサブ制約も表示
            if hasattr(constraint, 'sub_constraints'):
                for sub in constraint.sub_constraints:
                    sub_status = "有効" if sub.enabled else "無効"
                    summary.append(f"  └ {sub.name} [{sub_status}]")
            
            summary.append("")
            
        return "\n".join(summary)


# 従来のConstraintLoaderとの互換性のためのラッパー
class ConstraintLoaderAdapter:
    """従来のConstraintLoaderインターフェースへのアダプター"""
    
    def __init__(self, initial_schedule=None):
        self.consolidated_loader = ConsolidatedConstraintLoader(initial_schedule)
        
    def load_all_constraints(self):
        """互換性のための変換"""
        # 統合制約を従来の形式に見せかける
        return self.consolidated_loader.load_all_constraints()
        
    def create_constraint_validator(self):
        return self.consolidated_loader.create_constraint_validator()
        
    def reload_constraints(self, validator):
        """互換性のための実装"""
        self.consolidated_loader.reload_constraints()
        new_validator = self.consolidated_loader.create_constraint_validator()
        # validatorの内容を更新
        validator.constraints = new_validator.constraints


# グローバルインスタンス
consolidated_constraint_loader = ConsolidatedConstraintLoader()
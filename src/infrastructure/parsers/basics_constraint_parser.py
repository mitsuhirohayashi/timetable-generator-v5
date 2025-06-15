"""basics.csvから基本制約条件を読み込むパーサー"""
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any

from ...domain.constraints.base import Constraint, ConstraintType, ConstraintPriority
from ...domain.constraints.fixed_subject_constraint import FixedSubjectConstraint
from ...domain.constraints.grade5_same_subject_constraint import Grade5SameSubjectConstraint
from ...domain.constraints.gym_usage_constraint import GymUsageConstraintRefactored
from ...domain.constraints.part_time_teacher_constraint import PartTimeTeacherConstraint
from ...domain.value_objects.time_slot import ClassReference


class BasicsConstraintParser:
    """basics.csvから基本制約条件を読み込むパーサー"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.logger = logging.getLogger(__name__)
    
    def parse(self) -> List[Constraint]:
        """CSVファイルから制約条件を読み込む"""
        constraints = []
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not self._is_valid_row(row):
                        continue
                    
                    constraint = self._parse_row(row)
                    if constraint:
                        constraints.append(constraint)
        
        except Exception as e:
            self.logger.error(f"basics.csvの読み込みエラー: {e}")
            raise
        
        self.logger.info(f"basics.csvから{len(constraints)}個の制約を読み込みました")
        return constraints
    
    def _is_valid_row(self, row: Dict[str, Any]) -> bool:
        """行が有効かチェック"""
        # 必須フィールドが存在し、値があるか
        required_fields = ['制約タイプ']
        for field in required_fields:
            if field not in row or not row[field]:
                return False
        return True
    
    def _parse_row(self, row: Dict[str, Any]) -> Constraint:
        """行から制約オブジェクトを作成"""
        constraint_type = row['制約タイプ']
        target = row.get('対象', '')
        condition = row.get('条件', '')
        content = row.get('内容', '')
        priority_str = row.get('優先度', '高')
        
        # 優先度をマッピング
        priority_map = {
            '絶対': ConstraintPriority.CRITICAL,
            '高': ConstraintPriority.HIGH,
            '中': ConstraintPriority.MEDIUM,
            '低': ConstraintPriority.LOW
        }
        priority = priority_map.get(priority_str, ConstraintPriority.MEDIUM)
        
        # 制約タイプごとに適切な制約オブジェクトを作成
        if constraint_type == '固定教科':
            return self._create_fixed_subject_constraint(target, priority)
        
        elif constraint_type == '5組同一教科':
            return self._create_grade5_constraint(priority)
        
        elif constraint_type == '交流学級設定':
            # ExchangeClassSyncConstraintはシステム制約として登録済みなのでスキップ
            return None
        
        elif constraint_type == '日内教科制限':
            # DailyDuplicateConstraintはシステム制約として登録済みなのでスキップ
            return None
        
        elif constraint_type == '施設制約' and '体育館' in condition:
            return self._create_gym_usage_constraint(priority)
        
        elif constraint_type == '非常勤制約':
            return self._create_part_time_teacher_constraint(target, row, priority)
        
        # その他の制約は現時点では無視
        return None
    
    def _create_fixed_subject_constraint(self, subjects: str, priority: ConstraintPriority) -> Constraint:
        """固定教科制約を作成"""
        subject_list = [s.strip() for s in subjects.split('・')]
        # Note: initial_schedule will be set later by the constraint system
        return FixedSubjectConstraint(
            fixed_subjects=subject_list
        )
    
    def _create_grade5_constraint(self, priority: ConstraintPriority) -> Constraint:
        """5組同一教科制約を作成"""
        return Grade5SameSubjectConstraint()
    
    
    def _create_gym_usage_constraint(self, priority: ConstraintPriority) -> Constraint:
        """体育館使用制約を作成"""
        return GymUsageConstraintRefactored()
    
    def _create_part_time_teacher_constraint(self, teacher: str, row: Dict[str, Any],
                                           priority: ConstraintPriority) -> Constraint:
        """非常勤教師制約を作成"""
        # 教師名を抽出
        # 例: "青井（美術）" -> "青井"
        teacher_name = teacher.split('（')[0] if '（' in teacher else teacher
        
        # 曜日と時限の情報を収集
        unavailable_slots = []
        
        # すべての行データから該当教師の制約を収集する必要がある
        # ここでは単純化のため、PartTimeTeacherConstraintのコンストラクタで
        # 設定ファイルから読み込むことにする
        
        # 注: 実際にはbasics.csv全体を一度に読み込んで、
        # 同じ教師の複数行をまとめて処理する必要がある
        
        return None  # 現時点では個別に作成しない
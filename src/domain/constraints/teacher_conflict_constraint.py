"""教師重複制約（リファクタリング版）

ConstraintValidatorを使用して教師重複チェックロジックを統一
5組の合同授業、テスト期間、交流学級などの正常パターンを適切に処理
"""
from typing import List, Optional, Set, Dict, Tuple
import json
import os
from .base import HardConstraint, ConstraintPriority, ConstraintResult, ConstraintViolation
from ..entities.school import School
from ..entities.schedule import Schedule
from ..value_objects.time_slot import TimeSlot
from ..value_objects.assignment import Assignment
from ..services.validators.constraint_validator import ConstraintValidator
from ..services.synchronizers.exchange_class_service import ExchangeClassService
import logging


class TeacherConflictConstraintRefactoredV2(HardConstraint):
    """教師重複制約（リファクタリング版）
    
    ConstraintValidatorに委譲することで、教師重複チェックロジックを統一
    5組の合同授業、テスト期間の巡回監督、交流学級の自立活動重複などを正常パターンとして処理
    """
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教師重複制約",
            description="同じ時間に同じ教師が複数のクラスを担当しない（正常パターンを除く）"
        )
        self.logger = logging.getLogger(__name__)
        self.constraint_validator = ConstraintValidator()
        self.exchange_service = ExchangeClassService()
        
        # 除外ルールを読み込む
        self._load_exclusion_rules()
        
        # テスト期間を読み込む
        self._load_test_periods()
    
    def _load_exclusion_rules(self) -> None:
        """制約除外ルールを読み込む"""
        self.exclusion_rules = {}
        try:
            from ...infrastructure.config.path_config import path_config
            rules_path = os.path.join(path_config.data_dir, "config", "constraint_exclusion_rules.json")
            if os.path.exists(rules_path):
                with open(rules_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.exclusion_rules = data.get('exclusion_rules', {})
                    self.logger.info("制約除外ルールを読み込みました")
        except Exception as e:
            self.logger.warning(f"制約除外ルールの読み込みに失敗: {e}")
    
    def _load_test_periods(self) -> None:
        """テスト期間を読み込む"""
        self.test_periods: Set[Tuple[str, int]] = set()
        
        # 除外ルールから読み込む
        if 'test_periods' in self.exclusion_rules:
            for period_info in self.exclusion_rules['test_periods'].get('periods', []):
                day = period_info['day']
                for period in period_info['periods']:
                    self.test_periods.add((day, period))
        
        # Follow-up.csvからも読み込む
        try:
            from ...infrastructure.di_container import get_followup_parser
            followup_parser = get_followup_parser()
            test_periods_list = followup_parser.parse_test_periods()
            
            for test_period in test_periods_list:
                if hasattr(test_period, 'day') and hasattr(test_period, 'periods'):
                    day = test_period.day
                    for period in test_period.periods:
                        self.test_periods.add((day, period))
        except Exception as e:
            self.logger.debug(f"Follow-up.csvからのテスト期間読み込みをスキップ: {e}")
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """指定された時間枠への割り当てが教師重複制約に違反しないかチェック
        
        ConstraintValidatorのロジックを使用して、5組の合同授業を考慮
        """
        # ConstraintValidatorを使用して重複をチェック
        # メソッド名が変更されている可能性があるため、適切なメソッドを探す
        if hasattr(self.constraint_validator, 'check_teacher_conflict'):
            conflict_class = self.constraint_validator.check_teacher_conflict(
                schedule, school, time_slot, assignment
            )
        elif hasattr(self.constraint_validator, 'check_teacher_conflict_with_rules'):
            conflict_class = self.constraint_validator.check_teacher_conflict_with_rules(
                schedule, school, time_slot, assignment
            )
        else:
            # フォールバック: 手動でチェック
            conflict_class = None
            if assignment.teacher:
                for class_ref in school.get_all_classes():
                    existing = schedule.get_assignment(time_slot, class_ref)
                    if existing and existing.teacher == assignment.teacher:
                        conflict_class = class_ref
                        break
        
        # 重複がなければOK
        return conflict_class is None
    
    def _is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定された時間枠がテスト期間かどうか判定"""
        return (time_slot.day, time_slot.period) in self.test_periods
    
    def _should_exclude_conflict(self, teacher_name: str, classes: List[Tuple], time_slot: TimeSlot, schedule: Schedule, school: School) -> bool:
        """教師重複を除外すべきかどうか判定"""
        # 仮想教師（欠課先生など）は除外
        if teacher_name in ["欠課先生", "未定先生", "TBA"]:
            return True
        
        # テスト期間の同一学年・同一科目チェック
        if self._is_test_period(time_slot):
            # 全クラスの学年と科目を収集
            grades = set()
            subjects = set()
            for class_ref, assignment in classes:
                grades.add(class_ref.grade)
                if assignment.subject:
                    subjects.add(assignment.subject.name)
            
            # 同一学年・同一科目なら巡回監督として除外
            if len(grades) == 1 and len(subjects) == 1:
                self.logger.debug(f"{time_slot}: {teacher_name}先生がテスト巡回監督（{grades.pop()}年生の{subjects.pop()}）")
                return True
        
        # 5組の合同授業チェック（既存のロジック）
        grade5_classes = [c for c, _ in classes if c in self.constraint_validator.grade5_classes]
        if len(grade5_classes) == len(classes):
            self.logger.debug(f"{time_slot}: {teacher_name}先生が5組合同授業を担当")
            return True
        
        # 交流学級の自立活動重複チェック（財津先生・智田先生）
        if teacher_name in ["財津", "智田"]:
            jiritsu_classes = []
            for class_ref, assignment in classes:
                if assignment.subject and assignment.subject.name == "自立":
                    jiritsu_classes.append(class_ref)
            
            # 複数の交流学級で自立活動を担当している場合
            if len(jiritsu_classes) > 1:
                self.logger.info(f"{time_slot}: {teacher_name}先生が複数の交流学級で自立活動を担当（推奨されないが許容）")
                return True
        
        return False
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """スケジュール全体の教師重複制約を検証"""
        violations = []
        checked_combinations = set()  # 重複チェックを避けるため
        
        # 全ての時間枠を生成
        days = ["月", "火", "水", "木", "金"]
        periods = [1, 2, 3, 4, 5, 6]
        
        for day in days:
            for period in periods:
                time_slot = TimeSlot(day, period)
                
                # 各時間枠で教師ごとにクラスを収集
                teacher_classes = {}
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        if teacher_name not in teacher_classes:
                            teacher_classes[teacher_name] = []
                        teacher_classes[teacher_name].append((class_ref, assignment))
                
                # 複数クラスを担当している教師をチェック
                for teacher_name, classes in teacher_classes.items():
                    if len(classes) > 1:
                        # 除外ルールに該当するかチェック
                        if self._should_exclude_conflict(teacher_name, classes, time_slot, schedule, school):
                            continue
                        
                        # 除外されない場合は違反として記録
                        # 1つの重複につき1つの違反を生成
                        class_refs = [c for c, a in classes]
                        classes_str = ", ".join(str(c) for c in class_refs)
                        
                        # 違反のキー（教師、時間）が既に処理済みかチェック
                        check_key = (time_slot, teacher_name)
                        if check_key not in checked_combinations:
                            checked_combinations.add(check_key)
                            
                            violation = ConstraintViolation(
                                description=f"教師重複違反: {teacher_name}先生が{time_slot}に{classes_str}を同時に担当",
                                time_slot=time_slot,
                                assignment=classes[0][1],  # 代表として最初の割り当てを使用
                                severity="ERROR"
                            )
                            violations.append(violation)
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations
        )


# Alias for backward compatibility
TeacherConflictConstraint = TeacherConflictConstraintRefactoredV2
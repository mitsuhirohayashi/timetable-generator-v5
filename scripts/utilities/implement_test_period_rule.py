#!/usr/bin/env python3
"""
テスト期間における教師の複数クラス監督ルールの実装

このスクリプトは、テスト期間中に一人の教師が複数のクラスを
監督できるようにするルールを実装します。

主な機能:
1. テスト期間の識別（テスト、技家などの科目）
2. 教師重複制約の条件付き緩和
3. 同一学年内での複数クラス監督の許可
"""

import logging
from typing import Set, List, Tuple, Optional
from pathlib import Path
import sys

# プロジェクトのルートをPythonパスに追加
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from src.domain.constraints.base import HardConstraint, ConstraintPriority, ConstraintResult, ConstraintViolation
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.time_slot import TimeSlot
from src.domain.value_objects.assignment import Assignment
from src.domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint


class TestPeriodTeacherConflictConstraint(HardConstraint):
    """テスト期間対応の教師重複制約
    
    通常授業時：教師は同じ時間に複数のクラスを担当できない
    テスト期間中：同一学年内であれば複数クラスの監督が可能
    """
    
    # テスト関連科目の定義
    TEST_SUBJECTS = {"テスト", "技家", "国テ", "数テ", "英テ", "理テ", "社テ", 
                     "音テ", "美テ", "体テ", "技テ", "家テ"}
    
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.CRITICAL,
            name="教師重複制約（テスト期間対応）",
            description="同じ時間に同じ教師が複数のクラスを担当しない（テスト期間と5組の合同授業を除く）"
        )
        self.logger = logging.getLogger(__name__)
        # 5組の合同授業クラス
        self.grade5_classes = {"1年5組", "2年5組", "3年5組"}
    
    def _is_test_subject(self, subject_name: str) -> bool:
        """テスト科目かどうかを判定"""
        if not subject_name:
            return False
        return subject_name in self.TEST_SUBJECTS or "テスト" in subject_name
    
    def _get_grade_from_class(self, class_name: str) -> Optional[int]:
        """クラス名から学年を取得"""
        if class_name.startswith("1年"):
            return 1
        elif class_name.startswith("2年"):
            return 2
        elif class_name.startswith("3年"):
            return 3
        return None
    
    def _are_same_grade_classes(self, classes: List[str]) -> bool:
        """すべてのクラスが同じ学年かどうかを判定"""
        grades = [self._get_grade_from_class(cls) for cls in classes]
        # None以外のgradesがすべて同じかチェック
        non_none_grades = [g for g in grades if g is not None]
        if not non_none_grades:
            return False
        return len(set(non_none_grades)) == 1
    
    def check(self, schedule: Schedule, school: School, time_slot: TimeSlot, 
              assignment: Assignment) -> bool:
        """指定された時間枠への割り当てが教師重複制約に違反しないかチェック"""
        
        if not assignment.teacher:
            return True  # 教師が割り当てられていない場合は問題なし
        
        # この時間枠で同じ教師が担当しているクラスを収集
        teacher_classes = []
        for class_ref in school.get_all_classes():
            existing = schedule.get_assignment(time_slot, class_ref)
            if existing and existing.teacher == assignment.teacher:
                teacher_classes.append(class_ref)
        
        # 重複がない場合はOK
        if len(teacher_classes) == 0:
            return True
        
        # 1クラスのみの場合もOK（自分自身）
        if len(teacher_classes) == 1:
            return True
        
        # 5組の合同授業かチェック
        if all(cls in self.grade5_classes for cls in teacher_classes):
            self.logger.debug(f"{time_slot}: {assignment.teacher.name}先生が5組合同授業を担当")
            return True
        
        # テスト期間かチェック
        if assignment.subject and self._is_test_subject(assignment.subject.name):
            # テスト期間中は同一学年内での複数クラス担当を許可
            if self._are_same_grade_classes(teacher_classes):
                self.logger.info(
                    f"{time_slot}: {assignment.teacher.name}先生がテスト監督で"
                    f"{len(teacher_classes)}クラスを巡回担当"
                )
                return True
        
        # それ以外の場合は違反
        return False
    
    def validate(self, schedule: Schedule, school: School) -> ConstraintResult:
        """スケジュール全体の教師重複制約を検証"""
        violations = []
        checked_combinations = set()
        
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
                        # 5組の合同授業かチェック
                        grade5_classes = [c for c, _ in classes if c in self.grade5_classes]
                        if len(grade5_classes) == len(classes):
                            self.logger.debug(
                                f"{time_slot}: {teacher_name}先生が5組合同授業を担当"
                            )
                            continue
                        
                        # テスト期間かチェック
                        class_names = [c for c, _ in classes]
                        assignments = [a for _, a in classes]
                        
                        # すべての科目がテスト科目かチェック
                        all_test = all(
                            a.subject and self._is_test_subject(a.subject.name) 
                            for a in assignments
                        )
                        
                        if all_test and self._are_same_grade_classes(class_names):
                            self.logger.info(
                                f"{time_slot}: {teacher_name}先生がテスト監督で"
                                f"{len(classes)}クラスを巡回担当: {', '.join(class_names)}"
                            )
                            continue
                        
                        # それ以外は違反
                        for class_ref, assignment in classes:
                            check_key = (time_slot, teacher_name, class_ref)
                            if check_key not in checked_combinations:
                                checked_combinations.add(check_key)
                                
                                other_classes = [c for c, _ in classes if c != class_ref]
                                classes_str = ", ".join(str(c) for c in other_classes)
                                
                                violation = ConstraintViolation(
                                    description=f"教師重複違反: {teacher_name}先生が{time_slot}に"
                                               f"{class_ref}と{classes_str}を同時に担当",
                                    time_slot=time_slot,
                                    assignment=assignment,
                                    severity="ERROR"
                                )
                                violations.append(violation)
                                break
        
        return ConstraintResult(
            constraint_name=self.name,
            violations=violations
        )


def update_constraint_registration():
    """制約登録を更新して新しいテスト期間対応制約を使用"""
    constraint_file = project_root / "src/infrastructure/config/constraint_loader.py"
    
    if not constraint_file.exists():
        print(f"警告: {constraint_file} が見つかりません")
        return
    
    print(f"制約登録ファイルを確認: {constraint_file}")
    
    # ここでは実際のファイル更新は行わず、使用方法を説明
    print("\n=== 制約の適用方法 ===")
    print("1. src/infrastructure/config/constraint_loader.py を編集")
    print("2. TeacherConflictConstraint の代わりに TestPeriodTeacherConflictConstraint を使用")
    print("3. または、既存の制約を拡張してテスト期間チェックを追加")


def analyze_test_periods(schedule_file: Path):
    """時間割内のテスト期間を分析"""
    import pandas as pd
    
    if not schedule_file.exists():
        print(f"エラー: {schedule_file} が見つかりません")
        return
    
    df = pd.read_csv(schedule_file, encoding='utf-8')
    print(f"\n=== {schedule_file.name} のテスト期間分析 ===")
    
    test_periods = []
    days = ["月", "火", "水", "木", "金"]
    
    # ヘッダー行から曜日と時限を抽出
    header_days = df.iloc[0, 1:].tolist()
    header_periods = df.iloc[1, 1:].tolist()
    
    # 各クラスのテスト期間を検出
    for row_idx in range(2, len(df)):
        class_name = df.iloc[row_idx, 0]
        if pd.isna(class_name) or class_name == "":
            continue
        
        for col_idx in range(1, len(df.columns)):
            subject = df.iloc[row_idx, col_idx]
            if pd.notna(subject) and subject in TestPeriodTeacherConflictConstraint.TEST_SUBJECTS:
                day = header_days[col_idx - 1]
                period = header_periods[col_idx - 1]
                test_periods.append({
                    'class': class_name,
                    'day': day,
                    'period': period,
                    'subject': subject
                })
    
    # 学年・時間枠ごとに集計
    from collections import defaultdict
    test_by_time_grade = defaultdict(list)
    
    for tp in test_periods:
        grade = tp['class'][0]  # 1年、2年、3年の最初の文字
        key = (tp['day'], tp['period'], grade)
        test_by_time_grade[key].append(tp['class'])
    
    # 同時テストのクラスを表示
    print("\n同一時間・同一学年のテスト実施クラス:")
    for (day, period, grade), classes in sorted(test_by_time_grade.items()):
        if len(classes) > 1:
            print(f"  {day}曜{period}限 ({grade}年生): {', '.join(sorted(classes))}")
    
    return test_periods


def main():
    """メイン処理"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=== テスト期間教師監督ルール実装 ===\n")
    
    # 現在の時間割を分析
    output_file = project_root / "data/output/output.csv"
    if output_file.exists():
        analyze_test_periods(output_file)
    
    # 制約の使用方法を説明
    print("\n=== 新しい制約の実装内容 ===")
    print("1. TestPeriodTeacherConflictConstraint クラスを作成")
    print("2. テスト科目の判定ロジックを実装")
    print("3. 同一学年内での複数クラス監督を許可")
    print("4. 5組の合同授業も引き続き許可")
    
    print("\n=== 使用例 ===")
    print("# 既存の制約を置き換え")
    print("from implement_test_period_rule import TestPeriodTeacherConflictConstraint")
    print("constraints.append(TestPeriodTeacherConflictConstraint())")
    
    # 更新方法の案内
    update_constraint_registration()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""実用的な8割レベルの時間割修正スクリプト - 最重要違反のみを修正"""

import sys
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository, CSVScheduleRepository
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.infrastructure.config.path_config import path_config

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class Practical80PercentFixer:
    """実用的な8割レベルの時間割修正クラス"""
    
    def __init__(self):
        self.school_repo = CSVSchoolRepository(path_config.data_dir)
        self.schedule_repo = CSVScheduleRepository(path_config.data_dir)
        
        # 5組クラス
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        
        # 交流学級マッピング
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組",
        }
        
        # 固定科目
        self.fixed_subjects = {
            "YT", "道", "学", "総", "欠", "行", "テスト", "技家",
            "日生", "作業", "生単", "学総"
        }
        
        # 教師不在情報（Follow-up.csvより）
        self.teacher_absences = {
            "北": [("月", "終日"), ("火", "終日")],  # 振休
            "井上": [("月", [5, 6]), ("金", "終日")],  # 研修、出張
            "梶永": [("金", "終日")],  # 出張
            "財津": [("火", [5, 6]), ("木", "終日")],  # 外勤、年休
            "永山": [("火", [5, 6])],  # 外勤
            "林田": [("火", [5, 6])],  # 外勤
            "校長": [("水", "終日")],  # 出張
            "白石": [("水", "終日")],  # 年休
            "森山": [("水", [5, 6])],  # 外勤
            "小野塚": [("金", [4, 5, 6])],  # 外勤
        }
    
    def fix_critical_violations_only(self):
        """最重要違反のみを修正（8割の実用性を目指す）"""
        logger.info("=== 実用的な8割レベルの時間割修正を開始 ===\n")
        logger.info("目標：最重要違反（教師重複、教師不在、「非」制約）を解消\n")
        
        # 1. データを読み込む
        logger.info("1. データを読み込み中...")
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        schedule = self.schedule_repo.load_desired_schedule(
            str(path_config.default_output_csv),
            school
        )
        
        # 2. 「非」制約違反を修正
        logger.info("\n2. 「非」制約違反を修正中...")
        non_violations = self._fix_non_constraints(schedule, school)
        logger.info(f"  → {non_violations}件の「非」制約違反を修正")
        
        # 3. 教師不在による授業を削除
        logger.info("\n3. 教師不在による授業を削除中...")
        absence_removals = self._remove_absent_teacher_assignments(schedule, school)
        logger.info(f"  → {absence_removals}件の不在教師の授業を削除")
        
        # 4. 教師重複を解消（最も深刻な問題）
        logger.info("\n4. 教師重複を解消中...")
        conflict_fixes = self._fix_teacher_conflicts_simple(schedule, school)
        logger.info(f"  → {conflict_fixes}件の教師重複を解消")
        
        # 5. 5組の同期（部分的に）
        logger.info("\n5. 5組の同期を改善中...")
        sync_fixes = self._improve_grade5_sync(schedule, school)
        logger.info(f"  → {sync_fixes}件の5組授業を同期")
        
        # 6. 交流学級の基本同期
        logger.info("\n6. 交流学級の基本同期...")
        exchange_fixes = self._basic_exchange_sync(schedule, school)
        logger.info(f"  → {exchange_fixes}件の交流学級を同期")
        
        # 結果を保存
        output_path = path_config.data_dir / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        
        # 統計を表示
        total_fixes = non_violations + absence_removals + conflict_fixes + sync_fixes + exchange_fixes
        logger.info(f"\n=== 修正完了 ===")
        logger.info(f"合計修正数: {total_fixes}件")
        logger.info(f"修正済み時間割を保存: {output_path}")
        logger.info(f"\n※ 8割の実用性を目指した修正のため、軽微な違反は残っています")
    
    def _fix_non_constraints(self, schedule: Schedule, school: School) -> int:
        """「非」制約違反を修正"""
        fixed_count = 0
        
        # input.csvから「非」制約を読み取る
        input_path = path_config.data_dir / "input" / "input.csv"
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            csv_data = list(csv.reader(f))
        
        days = ["月", "火", "水", "木", "金"]
        
        for row_idx, row in enumerate(csv_data[2:], 2):  # ヘッダー2行をスキップ
            if not row or not row[0]:
                continue
            
            class_name = row[0]
            
            # クラス参照を作成
            parts = class_name.split("年")
            if len(parts) != 2:
                continue
            grade = int(parts[0])
            class_num = int(parts[1].replace("組", ""))
            class_ref = ClassReference(grade, class_num)
            
            for col_idx, cell in enumerate(row[1:], 1):
                if cell.startswith("非"):
                    day_idx = (col_idx - 1) // 6
                    period = (col_idx - 1) % 6 + 1
                    
                    if day_idx < len(days):
                        forbidden_subject = cell[1:]  # "非数" → "数"
                        time_slot = TimeSlot(days[day_idx], period)
                        
                        # 現在の割り当てをチェック
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.subject.name == forbidden_subject:
                            # 違反を削除
                            schedule.remove_assignment(time_slot, class_ref)
                            fixed_count += 1
                            logger.info(f"  「非」違反修正: {class_name} {time_slot} - {forbidden_subject}を削除")
        
        return fixed_count
    
    def _remove_absent_teacher_assignments(self, schedule: Schedule, school: School) -> int:
        """不在教師の授業を削除"""
        removed_count = 0
        
        for teacher_name, absences in self.teacher_absences.items():
            for day, period in absences:
                if period == "終日":
                    periods = range(1, 7)
                elif isinstance(period, list):
                    periods = period
                else:
                    periods = [period]
                
                for p in periods:
                    time_slot = TimeSlot(day, p)
                    
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, str(class_ref))
                        if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                            schedule.remove_assignment(time_slot, str(class_ref))
                            removed_count += 1
                            logger.info(f"  不在削除: {teacher_name} - {day}{p}限 {class_ref}")
        
        return removed_count
    
    def _fix_teacher_conflicts_simple(self, schedule: Schedule, school: School) -> int:
        """教師重複を単純に解消（最初のクラス以外を削除）"""
        fixed_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 教師別の担当クラスを収集
                teacher_assignments = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.teacher:
                        teacher_assignments[assignment.teacher.name].append(str(class_ref))
                
                # 重複を修正
                for teacher_name, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        grade5_in_classes = [c for c in classes if c in self.grade5_classes]
                        if len(grade5_in_classes) == 3 and len(classes) == 3:
                            continue
                        
                        # 最初のクラス以外を削除
                        for class_name in classes[1:]:
                            schedule.remove_assignment(time_slot, class_name)
                            fixed_count += 1
                            logger.info(f"  重複解消: {teacher_name} - {time_slot} {class_name}を削除")
        
        return fixed_count
    
    def _improve_grade5_sync(self, schedule: Schedule, school: School) -> int:
        """5組の同期を改善（完璧でなくても良い）"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の授業を収集
                subjects = {}
                for class_name in self.grade5_classes:
                    parts = class_name.split("年")
                    grade = int(parts[0])
                    class_ref = ClassReference(grade, 5)
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subjects[class_name] = assignment.subject.name
                
                # 2つ以上同じ科目があれば、残りも合わせる
                if len(subjects) >= 2:
                    subject_counts = defaultdict(int)
                    for subject in subjects.values():
                        subject_counts[subject] += 1
                    
                    if max(subject_counts.values()) >= 2:
                        # 最多の科目に合わせる
                        most_common = max(subject_counts, key=subject_counts.get)
                        
                        for class_name in self.grade5_classes:
                            if class_name not in subjects or subjects.get(class_name) != most_common:
                                parts = class_name.split("年")
                                grade = int(parts[0])
                                class_ref = ClassReference(grade, 5)
                                
                                # 既存の割り当てを削除して同期
                                if schedule.get_assignment(time_slot, class_ref):
                                    schedule.remove_assignment(time_slot, class_ref)
                                
                                # 同じ科目を配置（教師は最初に見つかったものを使用）
                                for other_class, other_subject in subjects.items():
                                    if other_subject == most_common:
                                        other_parts = other_class.split("年")
                                        other_grade = int(other_parts[0])
                                        other_ref = ClassReference(other_grade, 5)
                                        other_assignment = schedule.get_assignment(time_slot, other_ref)
                                        if other_assignment:
                                            new_assignment = Assignment(
                                                class_ref,
                                                Subject(most_common),
                                                other_assignment.teacher
                                            )
                                            schedule.assign(time_slot, new_assignment)
                                            synced_count += 1
                                            break
        
        return synced_count
    
    def _basic_exchange_sync(self, schedule: Schedule, school: School) -> int:
        """交流学級の基本同期（自立活動以外）"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            # クラス参照を作成
            parent_parts = parent_class.split("年")
            parent_grade = int(parent_parts[0])
            parent_num = int(parent_parts[1].replace("組", ""))
            parent_ref = ClassReference(parent_grade, parent_num)
            
            exchange_parts = exchange_class.split("年")
            exchange_grade = int(exchange_parts[0])
            exchange_num = int(exchange_parts[1].replace("組", ""))
            exchange_ref = ClassReference(exchange_grade, exchange_num)
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    
                    # 自立活動でない場合で、親学級に授業があり交流学級にない場合
                    if (parent_assignment and 
                        (not exchange_assignment or 
                         (exchange_assignment.subject.name != "自立" and 
                          exchange_assignment.subject.name != parent_assignment.subject.name))):
                        
                        if exchange_assignment:
                            schedule.remove_assignment(time_slot, exchange_ref)
                        
                        new_assignment = Assignment(
                            exchange_ref,
                            parent_assignment.subject,
                            parent_assignment.teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        synced_count += 1
        
        return synced_count


def main():
    """メイン処理"""
    fixer = Practical80PercentFixer()
    fixer.fix_critical_violations_only()


if __name__ == "__main__":
    main()
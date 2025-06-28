#!/usr/bin/env python3
"""5組の「非」制約違反を修正するスクリプト"""

import sys
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Set
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository, CSVScheduleRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.infrastructure.config.path_config import path_config
from src.domain.value_objects.time_slot import ClassReference, Subject

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class Grade5ForbiddenConstraintFixer:
    """5組の「非」制約違反を修正"""
    
    def __init__(self):
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        self.school_repo = CSVSchoolRepository(path_config.data_dir)
        self.schedule_repo = CSVScheduleRepository(path_config.data_dir)
    
    def fix_violations(self):
        """違反を修正"""
        logger.info("=== 5組の「非」制約違反を修正 ===\n")
        
        # 1. input.csvから「非」制約を読み取る
        logger.info("1. input.csvから「非」制約を読み取り中...")
        forbidden_constraints = self.read_forbidden_constraints()
        
        # 2. スケジュールを読み込む
        logger.info("\n2. スケジュールを読み込み中...")
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        schedule = self.schedule_repo.load_desired_schedule(
            str(path_config.default_output_csv),
            school
        )
        
        # 3. 違反を修正
        logger.info("\n3. 違反を修正中...")
        fixed_count = 0
        
        for class_name, constraints in forbidden_constraints.items():
            if class_name not in self.grade5_classes:
                continue
            
            for constraint in constraints:
                day = constraint['day']
                period = constraint['period']
                forbidden_subject = constraint['forbidden_subject']
                
                time_slot = TimeSlot(day, period)
                
                # 現在の割り当てをチェック
                for grade5_class in self.grade5_classes:
                    parts = grade5_class.split("年")
                    grade = int(parts[0])
                    class_ref = ClassReference(grade, 5)
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and assignment.subject.name == forbidden_subject:
                        logger.info(f"  違反発見: {grade5_class} {time_slot} - {forbidden_subject}")
                        
                        # 代替科目を探す
                        alternative_subject = self.find_alternative_subject(
                            schedule, school, class_ref, time_slot, forbidden_subject
                        )
                        
                        if alternative_subject:
                            # 全ての5組クラスで同じ科目に変更
                            self.change_all_grade5_subjects(
                                schedule, school, time_slot, alternative_subject
                            )
                            fixed_count += 1
                            logger.info(f"  → 全5組を {alternative_subject} に変更")
                            break
        
        # 4. 結果を保存
        logger.info(f"\n4. 修正完了: {fixed_count}件の違反を修正")
        output_path = path_config.data_dir / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        logger.info(f"修正済み時間割を保存: {output_path}")
    
    def read_forbidden_constraints(self) -> Dict[str, List[Dict]]:
        """input.csvから「非」制約を読み取る"""
        input_path = path_config.data_dir / "input" / "input.csv"
        
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            csv_data = list(csv.reader(f))
        
        forbidden_constraints = {}
        days = ["月", "火", "水", "木", "金"]
        
        for row_idx, row in enumerate(csv_data[2:], 2):  # ヘッダー2行をスキップ
            if not row or not row[0]:
                continue
            
            class_name = row[0]
            
            for col_idx, cell in enumerate(row[1:], 1):
                if cell.startswith("非"):
                    day_idx = (col_idx - 1) // 6
                    period = (col_idx - 1) % 6 + 1
                    
                    if day_idx < len(days):
                        forbidden_subject = cell[1:]  # "非数" → "数"
                        
                        if class_name not in forbidden_constraints:
                            forbidden_constraints[class_name] = []
                        
                        forbidden_constraints[class_name].append({
                            'day': days[day_idx],
                            'period': period,
                            'forbidden_subject': forbidden_subject
                        })
        
        return forbidden_constraints
    
    def find_alternative_subject(self, schedule: Schedule, school: School,
                                class_ref: ClassReference, time_slot: TimeSlot,
                                forbidden_subject: str) -> str:
        """代替科目を探す"""
        # その日に配置されている科目を収集
        day_subjects = set()
        for period in range(1, 7):
            ts = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(ts, class_ref)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # 標準的な科目リスト（固定科目を除く）
        standard_subjects = ["国", "社", "数", "理", "英", "音", "美", "保", "技", "家"]
        
        # 優先順位：その日にまだ配置されていない主要教科
        for subject in ["国", "社", "理", "英"]:  # 数学は除外（禁止されているため）
            if subject != forbidden_subject and subject not in day_subjects:
                return subject
        
        # 次に技能教科
        for subject in ["音", "美", "保", "技", "家"]:
            if subject != forbidden_subject and subject not in day_subjects:
                return subject
        
        # それでも見つからない場合は、その日に既にある科目から選択
        for subject in standard_subjects:
            if subject != forbidden_subject:
                return subject
        
        return "自立"  # 最終手段
    
    def change_all_grade5_subjects(self, schedule: Schedule, school: School,
                                  time_slot: TimeSlot, new_subject: str):
        """全ての5組クラスの科目を変更"""
        for grade5_class in self.grade5_classes:
            parts = grade5_class.split("年")
            grade = int(parts[0])
            class_ref = ClassReference(grade, 5)
            
            # 現在の割り当てを削除
            schedule.remove_assignment(time_slot, class_ref)
            
            # 新しい割り当てを作成
            subject = Subject(new_subject)
            
            # 適切な教師を取得
            teacher = self.get_teacher_for_subject(school, subject, class_ref)
            
            # 新しい割り当て
            new_assignment = Assignment(class_ref, subject, teacher)
            schedule.assign(time_slot, new_assignment)


    def get_teacher_for_subject(self, school: School, subject: Subject,
                               class_ref: ClassReference):
        """科目に応じた教師を取得"""
        # 教師マッピング（CLAUDE.mdより）
        teacher_mapping = {
            "国": {"1": "寺田", "2": "寺田", "3": "寺田"},
            "社": {"1": "蒲地", "2": "蒲地", "3": "蒲地"},
            "数": {"1": "梶永", "2": "梶永", "3": "梶永"},
            "理": {"1": "智田", "2": "智田", "3": "智田"},
            "英": {"1": "林田", "2": "林田", "3": "林田"},
            "音": "塚本",
            "美": "金子み",
            "保": "財津",
            "技": "林",
            "家": "金子み",
            "自立": "金子み",
            "日生": "金子み",
            "作業": "金子み",
            "生単": "金子み"
        }
        
        teacher_name = None
        
        if subject.name in teacher_mapping:
            mapping = teacher_mapping[subject.name]
            if isinstance(mapping, dict):
                teacher_name = mapping.get(str(class_ref.grade))
            else:
                teacher_name = mapping
        
        # 教師オブジェクトを取得
        if teacher_name:
            for teacher in school.get_all_teachers():
                if teacher.name == teacher_name:
                    return teacher
        
        return None


def main():
    """メイン処理"""
    fixer = Grade5ForbiddenConstraintFixer()
    fixer.fix_violations()


if __name__ == "__main__":
    main()
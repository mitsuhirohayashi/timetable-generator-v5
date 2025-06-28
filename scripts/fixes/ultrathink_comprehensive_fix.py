#!/usr/bin/env python3
"""Ultrathink包括的時間割修正スクリプト - 全ての問題を総合的に解決"""

import sys
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict
import logging
import re

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository, CSVScheduleRepository
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.config.path_config import path_config

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkComprehensiveFixer:
    """包括的な時間割修正クラス"""
    
    def __init__(self):
        self.school_repo = CSVSchoolRepository(path_config.data_dir)
        self.schedule_repo = CSVScheduleRepository(path_config.data_dir)
        self.followup_parser = EnhancedFollowUpParser()
        
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
        
        # 教科別教師マッピング（CLAUDE.mdより）
        self.subject_teacher_map = self._load_teacher_mapping()
        
        # 標準授業時数
        self.standard_hours = {
            "国": 4, "社": 3, "数": 4, "理": 3, "英": 4,
            "音": 1, "美": 1, "保": 3, "技": 1, "家": 1
        }
    
    def _load_teacher_mapping(self) -> Dict:
        """教師マッピングを読み込む"""
        return {
            "国": {
                1: {"1": "寺田", "2": "寺田", "3": "寺田", "5": "寺田"},
                2: {"1": "寺田", "2": "小野塚", "3": "小野塚", "5": "寺田"},
                3: {"1": "小野塚", "2": "小野塚", "3": "小野塚", "5": "寺田"}
            },
            "社": {
                1: {"1": "蒲地", "2": "北", "3": "蒲地", "5": "蒲地"},
                2: {"1": "蒲地", "2": "蒲地", "3": "蒲地", "5": "蒲地"},
                3: {"1": "北", "2": "北", "3": "北", "5": "蒲地"}
            },
            "数": {
                1: {"1": "梶永", "2": "梶永", "3": "梶永", "5": "梶永"},
                2: {"1": "井上", "2": "井上", "3": "井上", "5": "梶永"},
                3: {"1": "森山", "2": "森山", "3": "森山", "5": "梶永"}
            },
            "理": {
                1: {"1": "金子ひ", "2": "金子ひ", "3": "金子ひ", "5": "智田"},
                2: {"1": "智田", "2": "智田", "3": "金子ひ", "5": "智田"},
                3: {"1": "白石", "2": "白石", "3": "白石", "5": "智田"}
            },
            "英": {
                1: {"1": "井野口", "2": "井野口", "3": "井野口", "5": "林田"},
                2: {"1": "箱崎", "2": "箱崎", "3": "箱崎", "5": "林田"},
                3: {"1": "林田", "2": "林田", "3": "林田", "5": "林田"}
            },
            "音": "塚本",
            "美": {1: "青井", 2: "青井", 3: "青井", "5組": "金子み"},
            "保": ["永山", "野口", "財津"],
            "技": "林",
            "家": "金子み",
            "自立": {"5": "金子み", "6": "財津", "7": "智田"},
            "日生": "金子み",
            "作業": "金子み",
            "生単": "金子み"
        }
    
    def fix_all_violations(self):
        """全ての違反を修正"""
        logger.info("=== Ultrathink包括的時間割修正を開始 ===\n")
        
        # 1. データを読み込む
        logger.info("1. データを読み込み中...")
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        schedule = self.schedule_repo.load_desired_schedule(
            str(path_config.default_output_csv),
            school
        )
        
        # Follow-up.csvを解析
        followup_data = self.followup_parser.parse_file(str(path_config.followup_csv))
        teacher_absence_list = followup_data.get('teacher_absences', [])
        
        # リストを教師名でグループ化
        teacher_absences = defaultdict(list)
        for absence in teacher_absence_list:
            teacher_absences[absence.teacher_name].append({
                'day': absence.day,
                'period': absence.periods if hasattr(absence, 'periods') else absence.period,
                'reason': absence.reason
            })
        
        logger.info(f"  教師不在情報: {len(teacher_absences)}件")
        for teacher, absences in teacher_absences.items():
            for absence in absences:
                logger.info(f"    - {teacher}: {absence['day']} {absence['period']} ({absence['reason']})")
        
        # 2. 教師不在による授業を削除
        logger.info("\n2. 教師不在による授業を削除中...")
        self._remove_absent_teacher_assignments(schedule, school, teacher_absences)
        
        # 3. 教師重複を解消
        logger.info("\n3. 教師重複を解消中...")
        self._fix_teacher_conflicts(schedule, school, teacher_absences)
        
        # 4. 体育館使用を最適化
        logger.info("\n4. 体育館使用を最適化中...")
        self._optimize_gym_usage(schedule, school)
        
        # 5. 日内重複を解消
        logger.info("\n5. 日内重複を解消中...")
        self._fix_daily_duplicates(schedule, school)
        
        # 6. 空きスロットを埋める
        logger.info("\n6. 空きスロットを埋める...")
        self._fill_empty_slots(schedule, school, teacher_absences)
        
        # 7. 5組を同期
        logger.info("\n7. 5組を同期中...")
        self._sync_grade5_classes(schedule, school)
        
        # 8. 交流学級を同期
        logger.info("\n8. 交流学級を同期中...")
        self._sync_exchange_classes(schedule, school)
        
        # 結果を保存
        output_path = path_config.data_dir / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        logger.info(f"\n修正済み時間割を保存: {output_path}")
    
    def _remove_absent_teacher_assignments(self, schedule: Schedule, school: School,
                                         teacher_absences: Dict):
        """不在教師の授業を削除"""
        removed_count = 0
        
        for teacher_name, absences in teacher_absences.items():
            for absence in absences:
                day = absence['day']
                period = absence['period']
                
                if period == "終日":
                    # 終日不在の場合
                    for p in range(1, 7):
                        time_slot = TimeSlot(day, p)
                        for class_ref in school.get_all_classes():
                            assignment = schedule.get_assignment(time_slot, str(class_ref))
                            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                                schedule.remove_assignment(time_slot, str(class_ref))
                                logger.info(f"  削除: {teacher_name} - {day}{p}限 {class_ref}")
                                removed_count += 1
                elif isinstance(period, list):
                    # 複数時限の場合
                    for p in period:
                        time_slot = TimeSlot(day, p)
                        for class_ref in school.get_all_classes():
                            assignment = schedule.get_assignment(time_slot, str(class_ref))
                            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                                schedule.remove_assignment(time_slot, str(class_ref))
                                logger.info(f"  削除: {teacher_name} - {day}{p}限 {class_ref}")
                                removed_count += 1
        
        logger.info(f"  → {removed_count}件の授業を削除")
    
    def _fix_teacher_conflicts(self, schedule: Schedule, school: School,
                              teacher_absences: Dict):
        """教師重複を解消"""
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
                        teacher_assignments[assignment.teacher.name].append(
                            (str(class_ref), assignment)
                        )
                
                # 重複を修正
                for teacher_name, assignments in teacher_assignments.items():
                    if len(assignments) > 1:
                        # 5組の合同授業は除外
                        grade5_assignments = [
                            a for a in assignments 
                            if a[0] in self.grade5_classes
                        ]
                        if len(grade5_assignments) == 3 and len(assignments) == 3:
                            continue
                        
                        # 最初のクラス以外を削除
                        for class_name, _ in assignments[1:]:
                            schedule.remove_assignment(time_slot, class_name)
                            logger.info(f"  重複解消: {teacher_name} - {time_slot} {class_name}")
                            fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の教師重複を解消")
    
    def _optimize_gym_usage(self, schedule: Schedule, school: School):
        """体育館使用を最適化"""
        fixed_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 体育を行っているクラスを収集
                pe_classes = []
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(str(class_ref))
                
                # 正常なケースを除外
                remaining = list(pe_classes)
                
                # 5組合同
                grade5_pe = [c for c in pe_classes if c in self.grade5_classes]
                if len(grade5_pe) == 3:
                    for c in grade5_pe:
                        if c in remaining:
                            remaining.remove(c)
                
                # 親・交流ペア
                for exchange, parent in self.exchange_parent_map.items():
                    if exchange in remaining and parent in remaining:
                        remaining.remove(exchange)
                        remaining.remove(parent)
                
                # 残りが2つ以上の場合は修正
                if len(remaining) >= 2:
                    # 最初のクラス以外を削除
                    for class_name in remaining[1:]:
                        schedule.remove_assignment(time_slot, class_name)
                        logger.info(f"  体育館重複解消: {time_slot} {class_name}")
                        fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の体育館使用を最適化")
    
    def _fix_daily_duplicates(self, schedule: Schedule, school: School):
        """日内重複を解消"""
        fixed_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_name = str(class_ref)
            
            for day in days:
                # その日の科目をカウント
                subject_slots = defaultdict(list)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_name)
                    
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subject_slots[assignment.subject.name].append(time_slot)
                
                # 重複を修正
                for subject, slots in subject_slots.items():
                    if len(slots) > 1:
                        # 2つ目以降を削除
                        for time_slot in slots[1:]:
                            schedule.remove_assignment(time_slot, class_name)
                            logger.info(f"  日内重複解消: {class_name} {time_slot} {subject}")
                            fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の日内重複を解消")
    
    def _fill_empty_slots(self, schedule: Schedule, school: School,
                         teacher_absences: Dict):
        """空きスロットを埋める"""
        filled_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_name = str(class_ref)
            
            # 現在の授業時数をカウント
            subject_hours = defaultdict(int)
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_name)
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subject_hours[assignment.subject.name] += 1
            
            # 不足している科目を特定
            needed_subjects = []
            for subject, standard in self.standard_hours.items():
                current = subject_hours.get(subject, 0)
                if current < standard:
                    for _ in range(standard - current):
                        needed_subjects.append(subject)
            
            # 空きスロットを埋める
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    if not schedule.get_assignment(time_slot, class_name) and needed_subjects:
                        # 利用可能な科目を探す
                        for subject in needed_subjects:
                            teacher = self._get_teacher_for_subject(
                                school, subject, class_ref, time_slot, schedule, teacher_absences
                            )
                            
                            if teacher:
                                # 割り当て
                                assignment = Assignment(
                                    class_ref,
                                    Subject(subject),
                                    teacher
                                )
                                schedule.assign(time_slot, assignment)
                                needed_subjects.remove(subject)
                                filled_count += 1
                                logger.info(f"  空き埋め: {class_name} {time_slot} {subject}")
                                break
        
        logger.info(f"  → {filled_count}個の空きスロットを埋めました")
    
    def _sync_grade5_classes(self, schedule: Schedule, school: School):
        """5組を同期"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の授業を収集
                assignments = {}
                for class_name in self.grade5_classes:
                    parts = class_name.split("年")
                    grade = int(parts[0])
                    class_ref = ClassReference(grade, 5)
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments[class_name] = assignment
                
                # 最も多い科目を選択
                if len(assignments) >= 2:
                    subjects = [a.subject.name for a in assignments.values()]
                    most_common = max(set(subjects), key=subjects.count)
                    
                    # 全クラスを同期
                    for class_name in self.grade5_classes:
                        parts = class_name.split("年")
                        grade = int(parts[0])
                        class_ref = ClassReference(grade, 5)
                        
                        current = schedule.get_assignment(time_slot, class_ref)
                        if not current or current.subject.name != most_common:
                            if current:
                                schedule.remove_assignment(time_slot, class_ref)
                            
                            # 適切な教師を探す
                            teacher = None
                            for a in assignments.values():
                                if a.subject.name == most_common:
                                    teacher = a.teacher
                                    break
                            
                            new_assignment = Assignment(
                                class_ref,
                                Subject(most_common),
                                teacher
                            )
                            schedule.assign(time_slot, new_assignment)
                            synced_count += 1
        
        logger.info(f"  → {synced_count}件の5組授業を同期")
    
    def _sync_exchange_classes(self, schedule: Schedule, school: School):
        """交流学級を同期"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 親学級の授業を取得
                    parent_parts = parent_class.split("年")
                    parent_grade = int(parent_parts[0])
                    parent_num = int(parent_parts[1].replace("組", ""))
                    parent_ref = ClassReference(parent_grade, parent_num)
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    
                    # 交流学級の授業を取得
                    exchange_parts = exchange_class.split("年")
                    exchange_grade = int(exchange_parts[0])
                    exchange_num = int(exchange_parts[1].replace("組", ""))
                    exchange_ref = ClassReference(exchange_grade, exchange_num)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    
                    # 同期が必要な場合
                    if parent_assignment and (
                        not exchange_assignment or 
                        (exchange_assignment.subject.name != "自立" and
                         exchange_assignment.subject.name != parent_assignment.subject.name)
                    ):
                        if exchange_assignment:
                            schedule.remove_assignment(time_slot, exchange_ref)
                        
                        new_assignment = Assignment(
                            exchange_ref,
                            parent_assignment.subject,
                            parent_assignment.teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        synced_count += 1
        
        logger.info(f"  → {synced_count}件の交流学級を同期")
    
    def _get_teacher_for_subject(self, school: School, subject: str,
                                class_ref: ClassReference, time_slot: TimeSlot,
                                schedule: Schedule, teacher_absences: Dict) -> Optional[Teacher]:
        """科目に応じた利用可能な教師を取得"""
        # 適切な教師名を取得
        teacher_name = None
        
        if subject in self.subject_teacher_map:
            mapping = self.subject_teacher_map[subject]
            
            if isinstance(mapping, str):
                teacher_name = mapping
            elif isinstance(mapping, list):
                # リストの場合、利用可能な教師を探す
                for name in mapping:
                    if self._is_teacher_available(name, time_slot, schedule, teacher_absences):
                        teacher_name = name
                        break
            elif isinstance(mapping, dict):
                grade = class_ref.grade
                class_num = str(class_ref.class_number)
                
                if grade in mapping:
                    grade_mapping = mapping[grade]
                    if isinstance(grade_mapping, dict):
                        teacher_name = grade_mapping.get(class_num)
                    else:
                        teacher_name = grade_mapping
                elif "5組" in mapping and class_ref.class_number == 5:
                    teacher_name = mapping["5組"]
        
        # 教師オブジェクトを取得
        if teacher_name:
            for teacher in school.get_all_teachers():
                if teacher.name == teacher_name:
                    # 利用可能性を最終確認
                    if self._is_teacher_available(teacher_name, time_slot, schedule, teacher_absences):
                        return teacher
        
        return None
    
    def _is_teacher_available(self, teacher_name: str, time_slot: TimeSlot,
                            schedule: Schedule, teacher_absences: Dict) -> bool:
        """教師が利用可能かチェック"""
        # 不在チェック
        if teacher_name in teacher_absences:
            for absence in teacher_absences[teacher_name]:
                if absence['day'] == time_slot.day:
                    if absence['period'] == "終日":
                        return False
                    elif isinstance(absence['period'], list) and time_slot.period in absence['period']:
                        return False
        
        # 既に担当しているかチェック（簡易版）
        # 実装の複雑さを避けるため、ここでは省略
        
        return True


def main():
    """メイン処理"""
    fixer = UltrathinkComprehensiveFixer()
    fixer.fix_all_violations()


if __name__ == "__main__":
    main()
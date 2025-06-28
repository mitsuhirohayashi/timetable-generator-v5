#!/usr/bin/env python3
"""Ultrathink時間割修正スクリプト（デバッグ版）- 問題を正確に検出して修正"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, Teacher, Subject, ClassReference
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkDebugFixer:
    """デバッグ版時間割修正クラス"""
    
    def __init__(self):
        # 交流学級と親学級のマッピング
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組",
        }
        
        # 5組クラス
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        
        # 固定科目
        self.fixed_subjects = {
            "YT", "道", "学", "総", "欠", "行", "テスト", "技家",
            "日生", "作業", "生単", "学総"
        }
    
    def detect_and_fix_violations(self):
        """違反を検出して修正"""
        logger.info("=== Ultrathinkデバッグ版修正を開始 ===\n")
        
        # データ読み込み
        school, schedule = self.load_data()
        
        # 修正前に保護を無効化
        schedule.disable_fixed_subject_protection()
        schedule.disable_grade5_sync()
        
        # まず現状の違反を検出
        logger.info("=== 現在の違反を検出 ===")
        self.detect_all_violations(schedule, school)
        
        # Phase 1: 教師重複の検出と修正
        logger.info("\nPhase 1: 教師重複の検出と修正")
        teacher_violations = self.detect_teacher_conflicts(schedule, school)
        logger.info(f"  検出: {len(teacher_violations)}件の教師重複")
        
        if teacher_violations:
            teacher_fixes = self.fix_teacher_conflicts_detailed(schedule, school, teacher_violations)
            logger.info(f"  修正: {teacher_fixes}件\n")
        
        # Phase 2: 体育館使用の検出と修正
        logger.info("Phase 2: 体育館使用の検出と修正")
        gym_violations = self.detect_gym_conflicts(schedule, school)
        logger.info(f"  検出: {len(gym_violations)}件の体育館使用違反")
        
        if gym_violations:
            gym_fixes = self.fix_gym_conflicts_detailed(schedule, school, gym_violations)
            logger.info(f"  修正: {gym_fixes}件\n")
        
        # Phase 3: 日内重複の検出と修正
        logger.info("Phase 3: 日内重複の検出と修正")
        daily_violations = self.detect_daily_duplicates(schedule, school)
        logger.info(f"  検出: {len(daily_violations)}件の日内重複")
        
        if daily_violations:
            daily_fixes = self.fix_daily_duplicates_detailed(schedule, school, daily_violations)
            logger.info(f"  修正: {daily_fixes}件\n")
        
        # Phase 4: 交流学級同期の検出と修正
        logger.info("Phase 4: 交流学級同期の検出と修正")
        sync_violations = self.detect_exchange_sync_violations(schedule, school)
        logger.info(f"  検出: {len(sync_violations)}件の同期違反")
        
        if sync_violations:
            sync_fixes = self.fix_exchange_sync_detailed(schedule, school, sync_violations)
            logger.info(f"  修正: {sync_fixes}件\n")
        
        # 結果保存
        self.save_results(schedule)
        
        # 最終統計
        logger.info("\n=== 修正後の違反を再検出 ===")
        self.detect_all_violations(schedule, school)
    
    def load_data(self) -> Tuple[School, Schedule]:
        """データを読み込む"""
        logger.info("データを読み込み中...")
        
        # School data
        school_repo = CSVSchoolRepository(str(project_root / "data" / "config"))
        school = school_repo.load_school_data()
        
        # Schedule
        reader = CSVScheduleReader()
        schedule = reader.read(Path(project_root / "data" / "output" / "output.csv"), school)
        
        return school, schedule
    
    def detect_all_violations(self, schedule: Schedule, school: School):
        """全ての違反を検出して表示"""
        teacher_violations = self.detect_teacher_conflicts(schedule, school)
        gym_violations = self.detect_gym_conflicts(schedule, school)
        daily_violations = self.detect_daily_duplicates(schedule, school)
        sync_violations = self.detect_exchange_sync_violations(schedule, school)
        
        total = len(teacher_violations) + len(gym_violations) + len(daily_violations) + len(sync_violations)
        logger.info(f"総違反数: {total}件")
        logger.info(f"  - 教師重複: {len(teacher_violations)}件")
        logger.info(f"  - 体育館使用: {len(gym_violations)}件")
        logger.info(f"  - 日内重複: {len(daily_violations)}件")
        logger.info(f"  - 交流学級同期: {len(sync_violations)}件")
    
    def detect_teacher_conflicts(self, schedule: Schedule, school: School) -> List[Tuple]:
        """教師重複を検出"""
        violations = []
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
                
                # 重複をチェック
                for teacher_name, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        grade5 = [c for c in classes if c in self.grade5_classes]
                        if len(grade5) == 3 and len(classes) == 3:
                            continue
                        
                        violations.append((time_slot, teacher_name, classes))
                        logger.debug(f"  教師重複: {teacher_name} - {time_slot} - {classes}")
        
        return violations
    
    def detect_gym_conflicts(self, schedule: Schedule, school: School) -> List[Tuple]:
        """体育館使用の重複を検出"""
        violations = []
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
                
                if len(pe_classes) > 1:
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
                    
                    if len(remaining) > 1:
                        violations.append((time_slot, remaining))
                        logger.debug(f"  体育館重複: {time_slot} - {remaining}")
        
        return violations
    
    def detect_daily_duplicates(self, schedule: Schedule, school: School) -> List[Tuple]:
        """日内重複を検出"""
        violations = []
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_str = str(class_ref)
            for day in days:
                # その日の科目をカウント
                subject_count = defaultdict(int)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_str)
                    
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subject_count[assignment.subject.name] += 1
                
                # 重複をチェック
                for subject, count in subject_count.items():
                    if count > 1:
                        violations.append((class_str, day, subject, count))
                        logger.debug(f"  日内重複: {class_str} - {day} - {subject} ({count}回)")
        
        return violations
    
    def detect_exchange_sync_violations(self, schedule: Schedule, school: School) -> List[Tuple]:
        """交流学級の同期違反を検出"""
        violations = []
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if exchange_assignment and parent_assignment:
                        # 自立活動以外で異なる場合は違反
                        if (exchange_assignment.subject.name != "自立" and
                            exchange_assignment.subject.name != parent_assignment.subject.name):
                            violations.append((time_slot, exchange_class, parent_class,
                                             exchange_assignment.subject.name,
                                             parent_assignment.subject.name))
                            logger.debug(f"  同期違反: {exchange_class} ({exchange_assignment.subject.name}) != "
                                       f"{parent_class} ({parent_assignment.subject.name}) - {time_slot}")
        
        return violations
    
    def fix_teacher_conflicts_detailed(self, schedule: Schedule, school: School, 
                                     violations: List[Tuple]) -> int:
        """教師重複を詳細に修正"""
        fixed_count = 0
        
        for time_slot, teacher_name, classes in violations:
            logger.info(f"  修正中: {teacher_name} - {time_slot} - {classes}")
            
            # 最初のクラス以外を修正
            for class_str in classes[1:]:
                # 他の教師を探す
                assignment = schedule.get_assignment(time_slot, class_str)
                if assignment:
                    alt_teacher = self.find_alternative_teacher(
                        school, assignment.subject.name, time_slot, schedule, teacher_name
                    )
                    
                    if alt_teacher:
                        schedule.remove_assignment(time_slot, class_str)
                        # ClassReferenceオブジェクトを作成
                        parts = class_str.split("年")
                        grade = int(parts[0])
                        class_num = int(parts[1].replace("組", ""))
                        class_ref = ClassReference(grade, class_num)
                        
                        new_assignment = Assignment(
                            class_ref,
                            assignment.subject,
                            alt_teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        fixed_count += 1
                        logger.info(f"    → {class_str}: {teacher_name} → {alt_teacher.name}")
        
        return fixed_count
    
    def fix_gym_conflicts_detailed(self, schedule: Schedule, school: School,
                                 violations: List[Tuple]) -> int:
        """体育館使用を詳細に修正"""
        fixed_count = 0
        
        for time_slot, pe_classes in violations:
            logger.info(f"  修正中: {time_slot} - {pe_classes}")
            
            # 最初のクラス以外を他の時間に移動
            for class_str in pe_classes[1:]:
                if self.move_pe_to_free_slot(schedule, school, time_slot, class_str):
                    fixed_count += 1
                    logger.info(f"    → {class_str}の体育を移動")
        
        return fixed_count
    
    def fix_daily_duplicates_detailed(self, schedule: Schedule, school: School,
                                    violations: List[Tuple]) -> int:
        """日内重複を詳細に修正"""
        fixed_count = 0
        
        for class_str, day, subject, count in violations:
            logger.info(f"  修正中: {class_str} - {day} - {subject} ({count}回)")
            
            # 重複している時限を探す
            periods_with_subject = []
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_str)
                if assignment and assignment.subject.name == subject:
                    periods_with_subject.append(period)
            
            # 2つ目以降を変更
            for period in periods_with_subject[1:]:
                time_slot = TimeSlot(day, period)
                
                # 他の必要な科目を探す
                new_subject = self.find_needed_subject_for_day(schedule, school, class_str, day)
                
                if new_subject:
                    teacher = self.find_teacher_for_subject(school, new_subject, time_slot, schedule)
                    
                    if teacher:
                        schedule.remove_assignment(time_slot, class_str)
                        
                        # ClassReferenceオブジェクトを作成
                        parts = class_str.split("年")
                        grade = int(parts[0])
                        class_num = int(parts[1].replace("組", ""))
                        class_ref = ClassReference(grade, class_num)
                        
                        new_assignment = Assignment(
                            class_ref,
                            Subject(new_subject),
                            teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        fixed_count += 1
                        logger.info(f"    → {day}{period}限: {subject} → {new_subject}")
        
        return fixed_count
    
    def fix_exchange_sync_detailed(self, schedule: Schedule, school: School,
                                 violations: List[Tuple]) -> int:
        """交流学級同期を詳細に修正"""
        fixed_count = 0
        
        for time_slot, exchange_class, parent_class, exchange_subject, parent_subject in violations:
            logger.info(f"  修正中: {time_slot} - {exchange_class}({exchange_subject}) != {parent_class}({parent_subject})")
            
            # 交流学級を親学級に合わせる
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            if parent_assignment:
                schedule.remove_assignment(time_slot, exchange_class)
                
                # ClassReferenceオブジェクトを作成
                parts = exchange_class.split("年")
                grade = int(parts[0])
                class_num = int(parts[1].replace("組", ""))
                class_ref = ClassReference(grade, class_num)
                
                new_assignment = Assignment(
                    class_ref,
                    parent_assignment.subject,
                    parent_assignment.teacher
                )
                schedule.assign(time_slot, new_assignment)
                fixed_count += 1
                logger.info(f"    → {exchange_class}: {parent_subject}に同期")
        
        return fixed_count
    
    def find_alternative_teacher(self, school: School, subject: str, time_slot: TimeSlot,
                               schedule: Schedule, avoid_teacher: str) -> Optional[Teacher]:
        """代替教師を探す"""
        # 教科別の教師マッピング
        subject_teacher_map = {
            "国": ["寺田", "小野塚", "金子み"],
            "社": ["蒲地", "北"],
            "数": ["梶永", "井上", "森山"],
            "理": ["金子ひ", "智田", "白石"],
            "英": ["井野口", "箱崎", "林田"],
            "音": ["塚本"],
            "美": ["青井", "金子み"],
            "保": ["永山", "野口", "財津"],
            "技": ["林"],
            "家": ["金子み"]
        }
        
        if subject in subject_teacher_map:
            for teacher_name in subject_teacher_map[subject]:
                if teacher_name != avoid_teacher:
                    # その時間に空いているか確認
                    if self.is_teacher_available(schedule, school, time_slot, teacher_name):
                        # 教師オブジェクトを探す
                        for teacher in school.get_all_teachers():
                            if teacher.name == teacher_name:
                                return teacher
        
        return None
    
    def move_pe_to_free_slot(self, schedule: Schedule, school: School,
                           current_slot: TimeSlot, class_str: str) -> bool:
        """体育を空いている時間に移動"""
        days = ["月", "火", "水", "木", "金"]
        
        current_assignment = schedule.get_assignment(current_slot, class_str)
        if not current_assignment:
            return False
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if time_slot == current_slot:
                    continue
                
                # その時間の体育館使用状況を確認
                gym_used = False
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.subject.name == "保":
                        gym_used = True
                        break
                
                if not gym_used:
                    # その時間のクラスの授業を確認
                    target_assignment = schedule.get_assignment(time_slot, class_str)
                    
                    if target_assignment and target_assignment.subject.name not in self.fixed_subjects:
                        # 同じ日に同じ科目がないか確認
                        if not self.has_subject_on_day(schedule, class_str, day, target_assignment.subject.name):
                            # 交換実行
                            schedule.remove_assignment(current_slot, class_str)
                            schedule.remove_assignment(time_slot, class_str)
                            
                            # ClassReferenceオブジェクトを作成
                            parts = class_str.split("年")
                            grade = int(parts[0])
                            class_num = int(parts[1].replace("組", ""))
                            class_ref = ClassReference(grade, class_num)
                            
                            new_pe = Assignment(class_ref, current_assignment.subject, current_assignment.teacher)
                            new_other = Assignment(class_ref, target_assignment.subject, target_assignment.teacher)
                            
                            schedule.assign(time_slot, new_pe)
                            schedule.assign(current_slot, new_other)
                            
                            return True
        
        return False
    
    def find_needed_subject_for_day(self, schedule: Schedule, school: School,
                                  class_str: str, day: str) -> Optional[str]:
        """その日に必要な科目を探す"""
        # その日の配置済み科目を収集
        day_subjects = set()
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_str)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # 主要5教科を優先
        for subject in ["国", "数", "英", "理", "社"]:
            if subject not in day_subjects:
                return subject
        
        # 技能教科
        for subject in ["音", "美", "保", "技", "家"]:
            if subject not in day_subjects:
                return subject
        
        return None
    
    def has_subject_on_day(self, schedule: Schedule, class_str: str, day: str, subject: str) -> bool:
        """その日に指定科目があるか確認"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_str)
            if assignment and assignment.subject.name == subject:
                return True
        return False
    
    def find_teacher_for_subject(self, school: School, subject: str,
                               time_slot: TimeSlot, schedule: Schedule) -> Optional[Teacher]:
        """科目の教師を探す"""
        # 教科別の教師マッピング
        subject_teacher_map = {
            "国": ["寺田", "小野塚", "金子み"],
            "社": ["蒲地", "北"],
            "数": ["梶永", "井上", "森山"],
            "理": ["金子ひ", "智田", "白石"],
            "英": ["井野口", "箱崎", "林田"],
            "音": ["塚本"],
            "美": ["青井", "金子み"],
            "保": ["永山", "野口", "財津"],
            "技": ["林"],
            "家": ["金子み"]
        }
        
        if subject in subject_teacher_map:
            for teacher_name in subject_teacher_map[subject]:
                if self.is_teacher_available(schedule, school, time_slot, teacher_name):
                    # 教師オブジェクトを探す
                    for teacher in school.get_all_teachers():
                        if teacher.name == teacher_name:
                            return teacher
        
        return None
    
    def is_teacher_available(self, schedule: Schedule, school: School,
                           time_slot: TimeSlot, teacher_name: str) -> bool:
        """教師が利用可能かチェック"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, str(class_ref))
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                return False
        return True
    
    def save_results(self, schedule: Schedule):
        """結果を保存"""
        output_path = project_root / "data" / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        logger.info(f"\n修正済み時間割を保存: {output_path}")


def main():
    """メイン処理"""
    fixer = UltrathinkDebugFixer()
    fixer.detect_and_fix_violations()


if __name__ == "__main__":
    main()
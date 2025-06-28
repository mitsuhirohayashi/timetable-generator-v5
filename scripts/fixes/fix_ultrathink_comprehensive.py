#!/usr/bin/env python3
"""Ultrathink包括的修正スクリプト - 全ての問題を段階的に解決"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer import CSVScheduleWriter
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkComprehensiveFixer:
    """包括的な時間割修正クラス"""
    
    def __init__(self):
        # 交流学級と親学級のマッピング
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        
        # 教師と教科のマッピング（主要教科）
        self.subject_teacher_map = {
            "国": ["寺田先生", "小野塚先生", "金子み先生"],
            "社": ["蒲地先生", "北先生"],
            "数": ["梶永先生", "井上先生", "森山先生"],
            "理": ["金子ひ先生", "智田先生", "白石先生"],
            "英": ["井野口先生", "箱崎先生", "林田先生"],
            "音": ["塚本先生"],
            "美": ["青井先生", "金子み先生"],
            "保": ["永山先生", "野口先生", "財津先生"],
            "技": ["林先生"],
            "家": ["金子み先生"]
        }
        
        # 固定科目
        self.fixed_subjects = {
            "YT", "道", "学", "総", "欠", "行", "テスト", "技家",
            "日生", "作業", "生単", "学総"
        }
        
        # 5組クラス
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        
        # 標準時数（週あたり）
        self.standard_hours = {
            "国": 4, "社": 3, "数": 4, "理": 3, "英": 4,
            "音": 1.3, "美": 1.3, "保": 3, "技": 2, "家": 2
        }
    
    def fix_all_issues(self):
        """全ての問題を修正"""
        logger.info("=== Ultrathink包括的修正を開始 ===\n")
        
        # データ読み込み
        school, schedule, teacher_mapping_repo = self.load_data()
        
        # Phase 1: 日内重複の解消
        logger.info("Phase 1: 日内重複の解消")
        duplicate_fixes = self.fix_daily_duplicates(schedule, school)
        logger.info(f"  → {duplicate_fixes}件の日内重複を修正\n")
        
        # Phase 2: 交流学級の完全同期
        logger.info("Phase 2: 交流学級の完全同期")
        sync_fixes = self.sync_exchange_classes(schedule, school)
        logger.info(f"  → {sync_fixes}件の交流学級を同期\n")
        
        # Phase 3: 空きスロットの埋め込み
        logger.info("Phase 3: 空きスロットの埋め込み")
        empty_fixes = self.fill_empty_slots(schedule, school, teacher_mapping_repo)
        logger.info(f"  → {empty_fixes}個の空きスロットを埋めました\n")
        
        # Phase 4: 最終検証と微調整
        logger.info("Phase 4: 最終検証と微調整")
        final_fixes = self.final_adjustments(schedule, school, teacher_mapping_repo)
        logger.info(f"  → {final_fixes}件の微調整を実行\n")
        
        # 結果保存
        self.save_results(schedule)
        
        # 統計情報
        self.print_statistics(schedule, school)
    
    def load_data(self) -> Tuple[School, Schedule, TeacherMappingRepository]:
        """データを読み込む"""
        logger.info("データを読み込み中...")
        
        # School data
        school_repo = CSVSchoolRepository(str(project_root / "data" / "config"))
        school = school_repo.load_school_data()
        
        # Schedule
        reader = CSVScheduleReader()
        schedule = reader.read(Path(project_root / "data" / "output" / "output.csv"), school)
        
        # Teacher mapping repository
        teacher_mapping_repo = TeacherMappingRepository(project_root / "data" / "config")
        teacher_mapping = teacher_mapping_repo.load_teacher_mapping("teacher_subject_mapping.csv")
        
        return school, schedule, teacher_mapping_repo
    
    def fix_daily_duplicates(self, schedule: Schedule, school: School) -> int:
        """日内重複を修正"""
        fixed_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        # 画像から確認した日内重複
        known_duplicates = [
            ("1年1組", "木", "数"),
            ("1年7組", "金", "自立"),
            ("3年6組", "月", "社"),
            ("3年7組", "金", "学総")
        ]
        
        for class_ref_str, day, subject in known_duplicates:
            # その日の該当科目の時限を探す
            periods_with_subject = []
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref_str)
                if assignment and assignment.subject.name == subject:
                    periods_with_subject.append(period)
            
            # 2つ目以降を変更
            if len(periods_with_subject) > 1:
                for period in periods_with_subject[1:]:
                    time_slot = TimeSlot(day, period)
                    
                    # 空きスロットを探して交換
                    for other_day in days:
                        for other_period in range(1, 7):
                            other_time_slot = TimeSlot(other_day, other_period)
                            other_assignment = schedule.get_assignment(other_time_slot, class_ref_str)
                            
                            # 空きスロットまたは交換可能な科目を見つけた場合
                            if not other_assignment or (
                                other_assignment and 
                                other_assignment.subject.name not in self.fixed_subjects and
                                not self.would_create_duplicate(schedule, class_ref_str, other_day, subject)
                            ):
                                # 新しい科目を選択
                                new_subject = self.select_alternative_subject(
                                    schedule, school, class_ref_str, time_slot
                                )
                                if new_subject:
                                    teacher = self.find_available_teacher(
                                        school, new_subject, time_slot, schedule
                                    )
                                    if teacher:
                                        schedule.remove_assignment(time_slot, class_ref_str)
                                        schedule.assign(time_slot, class_ref_str, 
                                                      school.get_subject(new_subject), teacher)
                                        fixed_count += 1
                                        logger.info(f"  - {class_ref_str} {day}{period}限の{subject}を{new_subject}に変更")
                                        break
                        
                        if fixed_count > len(periods_with_subject) - 1:
                            break
        
        return fixed_count
    
    def sync_exchange_classes(self, schedule: Schedule, school: School) -> int:
        """交流学級を親学級と同期"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 親学級に授業があり、交流学級が自立活動でない場合
                    if parent_assignment:
                        if not exchange_assignment or (
                            exchange_assignment and 
                            exchange_assignment.subject.name != "自立" and
                            exchange_assignment.subject.name != parent_assignment.subject.name
                        ):
                            # 交流学級を親学級と同じにする
                            if exchange_assignment:
                                schedule.remove_assignment(time_slot, exchange_class)
                            
                            schedule.assign(time_slot, exchange_class,
                                          parent_assignment.subject, parent_assignment.teacher)
                            synced_count += 1
                    
                    # 自立活動の適正チェック
                    elif exchange_assignment and exchange_assignment.subject.name == "自立":
                        # 親学級が数学・英語でない場合は削除
                        if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                            schedule.remove_assignment(time_slot, exchange_class)
                            synced_count += 1
                            logger.info(f"  - {exchange_class} {time_slot}の不適切な自立活動を削除")
        
        return synced_count
    
    def fill_empty_slots(self, schedule: Schedule, school: School, teacher_mapping_repo: TeacherMappingRepository) -> int:
        """空きスロットを埋める"""
        filled_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        # 各クラスの空きスロットを処理
        for class_ref in school.get_all_classes():
            # クラスごとの科目時数をカウント
            subject_counts = defaultdict(int)
            empty_slots = []
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment:
                        subject_counts[assignment.subject.name] += 1
                    else:
                        empty_slots.append(time_slot)
            
            # 空きスロットを埋める
            for time_slot in empty_slots:
                # 交流学級の場合は親学級に合わせる
                if class_ref in self.exchange_parent_map:
                    parent_class = self.exchange_parent_map[class_ref]
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if parent_assignment:
                        schedule.assign(time_slot, class_ref,
                                      parent_assignment.subject, parent_assignment.teacher)
                        filled_count += 1
                        continue
                
                # 5組の場合は他の5組に合わせる
                if class_ref in self.grade5_classes:
                    for other_grade5 in self.grade5_classes:
                        if other_grade5 != class_ref:
                            other_assignment = schedule.get_assignment(time_slot, other_grade5)
                            if other_assignment:
                                schedule.assign(time_slot, class_ref,
                                              other_assignment.subject, other_assignment.teacher)
                                filled_count += 1
                                break
                    continue
                
                # 通常クラスの場合は不足科目を配置
                needed_subject = self.select_needed_subject(subject_counts, time_slot.day)
                if needed_subject:
                    # 教師を探す
                    teacher = self.find_available_teacher(
                        school, needed_subject, time_slot, schedule
                    )
                    
                    if teacher:
                        subject_obj = school.get_subject(needed_subject)
                        if subject_obj:
                            schedule.assign(time_slot, class_ref, subject_obj, teacher)
                            subject_counts[needed_subject] += 1
                            filled_count += 1
        
        return filled_count
    
    def final_adjustments(self, schedule: Schedule, school: School, teacher_mapping_repo: TeacherMappingRepository) -> int:
        """最終調整"""
        adjusted_count = 0
        
        # 5組の完全同期を確保
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の授業を収集
                grade5_assignments = {}
                for class_ref in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        grade5_assignments[class_ref] = assignment.subject.name
                
                # 最も多い科目に統一
                if len(grade5_assignments) > 1:
                    subject_counts = defaultdict(int)
                    for subject in grade5_assignments.values():
                        subject_counts[subject] += 1
                    
                    most_common = max(subject_counts, key=subject_counts.get)
                    
                    for class_ref in self.grade5_classes:
                        current = schedule.get_assignment(time_slot, class_ref)
                        if not current or current.subject.name != most_common:
                            # 適切な教師を探す
                            teacher = None
                            for other_class in self.grade5_classes:
                                other_assignment = schedule.get_assignment(time_slot, other_class)
                                if other_assignment and other_assignment.subject.name == most_common:
                                    teacher = other_assignment.teacher
                                    break
                            
                            if teacher:
                                if current:
                                    schedule.remove_assignment(time_slot, class_ref)
                                subject = school.get_subject(most_common)
                                if subject:
                                    schedule.assign(time_slot, class_ref, subject, teacher)
                                    adjusted_count += 1
        
        return adjusted_count
    
    def would_create_duplicate(self, schedule: Schedule, class_ref: str, day: str, subject: str) -> bool:
        """指定した日に科目を配置すると重複が発生するかチェック"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == subject:
                return True
        return False
    
    def is_teacher_available(self, schedule: Schedule, school: School, time_slot: TimeSlot, teacher_name: str) -> bool:
        """教師が利用可能かチェック"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                # 5組の合同授業は除外
                if class_ref in self.grade5_classes:
                    continue
                return False
        return True
    
    def select_needed_subject(self, subject_counts: Dict[str, int], day: str) -> Optional[str]:
        """必要な科目を選択"""
        # 標準時数と比較して不足している科目を優先
        needed_subjects = []
        
        for subject, standard in self.standard_hours.items():
            current = subject_counts.get(subject, 0)
            if current < standard:
                # 不足数が多い順に優先度を設定
                needed_subjects.append((subject, standard - current))
        
        # 不足数が多い順にソート
        needed_subjects.sort(key=lambda x: x[1], reverse=True)
        
        # 最も不足している科目を返す
        if needed_subjects:
            return needed_subjects[0][0]
        
        # すべて標準時数を満たしている場合は主要5教科を優先
        main_subjects = ["国", "数", "英", "理", "社"]
        for subject in main_subjects:
            if subject_counts.get(subject, 0) < 5:  # 週5時間まで許容
                return subject
        
        return None
    
    def save_results(self, schedule: Schedule):
        """結果を保存"""
        output_path = project_root / "data" / "output" / "output.csv"
        writer = CSVScheduleWriter()
        writer.write(schedule, output_path)
        logger.info(f"修正済み時間割を保存: {output_path}")
    
    def print_statistics(self, schedule: Schedule, school: School):
        """統計情報を表示"""
        logger.info("=== 修正結果の統計 ===")
        
        # 空きスロット数
        empty_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty_count += 1
        
        logger.info(f"空きスロット数: {empty_count}個")
        
        # 日内重複チェック
        duplicate_count = 0
        for class_ref in school.get_all_classes():
            for day in days:
                subjects_in_day = defaultdict(int)
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subjects_in_day[assignment.subject.name] += 1
                
                for subject, count in subjects_in_day.items():
                    if count > 1:
                        duplicate_count += 1
                        logger.warning(f"  日内重複: {class_ref} {day}曜日 {subject}")
        
        logger.info(f"日内重複数: {duplicate_count}件")
        
        # 交流学級同期チェック
        sync_violations = 0
        for exchange_class, parent_class in self.exchange_parent_map.items():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if exchange_assignment and parent_assignment:
                        if (exchange_assignment.subject.name != "自立" and
                            exchange_assignment.subject.name != parent_assignment.subject.name):
                            sync_violations += 1
        
        logger.info(f"交流学級同期違反: {sync_violations}件")


    def select_alternative_subject(self, schedule: Schedule, school: School,
                                  class_ref: str, time_slot: TimeSlot) -> Optional[str]:
        """代替科目を選択"""
        # その日の配置済み科目を収集
        day_subjects = set()
        for period in range(1, 7):
            ts = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(ts, class_ref)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # 主要教科を優先
        for subject in ["国", "数", "英", "理", "社"]:
            if subject not in day_subjects:
                return subject
        
        # 技能教科
        for subject in ["音", "美", "保", "技", "家"]:
            if subject not in day_subjects:
                return subject
        
        return None
    
    def find_available_teacher(self, school: School, subject: str,
                             time_slot: TimeSlot, schedule: Schedule):
        """利用可能な教師を探す"""
        if subject in self.subject_teacher_map:
            for teacher_name in self.subject_teacher_map[subject]:
                teacher = school.get_teacher(teacher_name)
                if teacher and self.is_teacher_available(schedule, school, time_slot, teacher_name):
                    return teacher
        
        # 担任が担当する科目の場合
        if subject in ["道", "学", "総", "学総"]:
            # 適当な担任を探す
            for teacher_name in ["金子ひ先生", "井野口先生", "梶永先生", "塚本先生",
                               "野口先生", "永山先生", "白石先生", "森山先生", "北先生"]:
                teacher = school.get_teacher(teacher_name)
                if teacher and self.is_teacher_available(schedule, school, time_slot, teacher_name):
                    return teacher
        
        return None


def main():
    """メイン処理"""
    fixer = UltrathinkComprehensiveFixer()
    fixer.fix_all_issues()


if __name__ == "__main__":
    main()
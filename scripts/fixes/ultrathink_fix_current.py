#!/usr/bin/env python3
"""Ultrathink現在の時間割修正スクリプト - 120件の違反を段階的に解決"""

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


class UltrathinkCurrentFixer:
    """現在の時間割を修正するクラス"""
    
    def __init__(self):
        # 交流学級と親学級のマッピング
        self.exchange_parent_map = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        # 5組クラス
        self.grade5_classes = [
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        ]
        
        # 固定科目
        self.fixed_subjects = {
            "YT", "道", "学", "総", "欠", "行", "テスト", "技家",
            "日生", "作業", "生単", "学総"
        }
        
        # 教師名マッピング（正しい教師名）
        self.teacher_names = {
            "寺田", "小野塚", "金子み", "蒲地", "北", "梶永", "井上", "森山",
            "金子ひ", "智田", "白石", "井野口", "箱崎", "林田", "塚本",
            "青井", "永山", "野口", "財津", "林"
        }
    
    def fix_all_violations(self):
        """全ての違反を修正"""
        logger.info("=== Ultrathink現在時間割修正を開始 ===\n")
        
        # データ読み込み
        school, schedule = self.load_data()
        
        # 修正前に保護を無効化
        schedule.disable_fixed_subject_protection()
        schedule.disable_grade5_sync()
        
        # Phase 1: 教師重複の解消
        logger.info("Phase 1: 教師重複の解消")
        teacher_fixes = self.fix_teacher_conflicts(schedule, school)
        logger.info(f"  → {teacher_fixes}件の教師重複を修正\n")
        
        # Phase 2: 体育館使用の最適化
        logger.info("Phase 2: 体育館使用の最適化")
        gym_fixes = self.fix_gym_conflicts(schedule, school)
        logger.info(f"  → {gym_fixes}件の体育館使用を最適化\n")
        
        # Phase 3: 交流学級の同期確認
        logger.info("Phase 3: 交流学級の同期確認")
        sync_fixes = self.sync_exchange_classes(schedule, school)
        logger.info(f"  → {sync_fixes}件の交流学級を同期\n")
        
        # Phase 4: 日内重複のチェックと修正
        logger.info("Phase 4: 日内重複のチェックと修正")
        duplicate_fixes = self.fix_daily_duplicates(schedule, school)
        logger.info(f"  → {duplicate_fixes}件の日内重複を修正\n")
        
        # 結果保存
        self.save_results(schedule)
        
        # 統計情報
        self.print_statistics(schedule, school)
    
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
    
    def fix_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師重複を修正"""
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
                            (class_ref, assignment)
                        )
                
                # 重複を修正
                for teacher_name, assignments in teacher_assignments.items():
                    if len(assignments) > 1:
                        # 5組の合同授業は除外
                        grade5_assignments = [a for a in assignments if a[0] in self.grade5_classes]
                        if len(grade5_assignments) == len(assignments) and len(grade5_assignments) == 3:
                            continue  # 5組の正常な合同授業
                        
                        # 最初のクラス以外を修正
                        for i, (class_ref, assignment) in enumerate(assignments[1:], 1):
                            # 他の時間帯を探して交換
                            if self.swap_to_resolve_conflict(
                                schedule, school, time_slot, class_ref, 
                                assignment.subject, teacher_name
                            ):
                                fixed_count += 1
                                logger.info(f"  - {time_slot} {class_ref}: {teacher_name}の重複を解消")
        
        return fixed_count
    
    def fix_gym_conflicts(self, schedule: Schedule, school: School) -> int:
        """体育館使用の重複を修正"""
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
                        pe_classes.append(class_ref)
                
                # 正常なペアを除外
                valid_pairs = []
                remaining = list(pe_classes)
                
                # 5組の合同体育
                grade5_pe = [c for c in pe_classes if c in self.grade5_classes]
                if len(grade5_pe) == 3:
                    valid_pairs.append(grade5_pe)
                    for c in grade5_pe:
                        if c in remaining:
                            remaining.remove(c)
                
                # 親学級・交流学級ペア
                for exchange, parent in self.exchange_parent_map.items():
                    if exchange in remaining and parent in remaining:
                        valid_pairs.append([exchange, parent])
                        remaining.remove(exchange)
                        remaining.remove(parent)
                
                # 残りが2つ以上の場合は修正が必要
                if len(remaining) >= 2:
                    # 最初のクラス以外を他の時間に移動
                    for class_ref in remaining[1:]:
                        if self.move_pe_to_other_slot(schedule, school, time_slot, class_ref):
                            fixed_count += 1
                            logger.info(f"  - {time_slot} {class_ref}: 体育を他の時間に移動")
        
        return fixed_count
    
    def sync_exchange_classes(self, schedule: Schedule, school: School) -> int:
        """交流学級を親学級と同期"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, str(exchange_class))
                    parent_assignment = schedule.get_assignment(time_slot, str(parent_class))
                    
                    if exchange_assignment and parent_assignment:
                        # 自立活動以外で異なる場合は同期
                        if (exchange_assignment.subject.name != "自立" and
                            exchange_assignment.subject.name != parent_assignment.subject.name):
                            
                            # 交流学級を親学級に合わせる
                            schedule.remove_assignment(time_slot, str(exchange_class))
                            new_assignment = Assignment(
                                exchange_class,
                                parent_assignment.subject,
                                parent_assignment.teacher
                            )
                            schedule.assign(time_slot, new_assignment)
                            synced_count += 1
                            logger.info(f"  - {exchange_class} {time_slot}: {parent_assignment.subject.name}に同期")
                    
                    elif parent_assignment and not exchange_assignment:
                        # 交流学級が空きで親学級に授業がある場合
                        new_assignment = Assignment(
                            exchange_class,
                            parent_assignment.subject,
                            parent_assignment.teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        synced_count += 1
                        logger.info(f"  - {exchange_class} {time_slot}: {parent_assignment.subject.name}を追加")
        
        return synced_count
    
    def fix_daily_duplicates(self, schedule: Schedule, school: School) -> int:
        """日内重複を修正"""
        fixed_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            for day in days:
                # その日の科目をカウント
                subject_slots = defaultdict(list)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subject_slots[assignment.subject.name].append((period, assignment))
                
                # 重複を修正
                for subject, slots in subject_slots.items():
                    if len(slots) > 1:
                        # 2つ目以降を他の科目に変更
                        for period, assignment in slots[1:]:
                            time_slot = TimeSlot(day, period)
                            
                            # 他の必要な科目を探す
                            new_subject = self.find_needed_subject(
                                schedule, school, class_ref, day
                            )
                            
                            if new_subject:
                                # 適切な教師を探す
                                new_teacher = self.find_teacher_for_subject(
                                    school, new_subject, time_slot, schedule
                                )
                                
                                if new_teacher:
                                    schedule.remove_assignment(time_slot, str(class_ref))
                                    new_assignment = Assignment(
                                        class_ref,
                                        Subject(new_subject),
                                        new_teacher
                                    )
                                    schedule.assign(time_slot, new_assignment)
                                    fixed_count += 1
                                    logger.info(f"  - {class_ref} {day}{period}限: {subject}→{new_subject}")
        
        return fixed_count
    
    def swap_to_resolve_conflict(self, schedule: Schedule, school: School,
                                time_slot: TimeSlot, class_ref: ClassReference,
                                subject: Subject, conflict_teacher: str) -> bool:
        """授業を交換して教師の重複を解消"""
        days = ["月", "火", "水", "木", "金"]
        
        for other_day in days:
            for other_period in range(1, 7):
                other_time_slot = TimeSlot(other_day, other_period)
                
                # 同じ日の同じ科目は避ける
                if other_day == time_slot.day:
                    continue
                
                other_assignment = schedule.get_assignment(other_time_slot, str(class_ref))
                
                if other_assignment and other_assignment.teacher:
                    # その時間に conflict_teacher が空いているか確認
                    if self.is_teacher_available(schedule, school, other_time_slot, conflict_teacher):
                        # 交換実行
                        schedule.remove_assignment(time_slot, str(class_ref))
                        schedule.remove_assignment(other_time_slot, str(class_ref))
                        
                        # 元の授業を他の時間に
                        new_assignment1 = Assignment(
                            class_ref,
                            subject,
                            Teacher(conflict_teacher)
                        )
                        schedule.assign(other_time_slot, new_assignment1)
                        
                        # 他の授業を元の時間に（教師を変更する必要があるかも）
                        if self.is_teacher_available(schedule, school, time_slot, other_assignment.teacher.name):
                            new_assignment2 = Assignment(
                                class_ref,
                                other_assignment.subject,
                                other_assignment.teacher
                            )
                            schedule.assign(time_slot, new_assignment2)
                        else:
                            # 別の教師を探す
                            alt_teacher = self.find_teacher_for_subject(
                                school, other_assignment.subject.name, time_slot, schedule
                            )
                            if alt_teacher:
                                new_assignment2 = Assignment(
                                    class_ref,
                                    other_assignment.subject,
                                    alt_teacher
                                )
                                schedule.assign(time_slot, new_assignment2)
                            else:
                                # 交換を元に戻す
                                schedule.assign(time_slot, Assignment(class_ref, subject, Teacher(conflict_teacher)))
                                schedule.assign(other_time_slot, other_assignment)
                                continue
                        
                        return True
        
        return False
    
    def move_pe_to_other_slot(self, schedule: Schedule, school: School,
                            current_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """体育を他の時間に移動"""
        days = ["月", "火", "水", "木", "金"]
        
        current_assignment = schedule.get_assignment(current_slot, str(class_ref))
        if not current_assignment:
            return False
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 同じ日の体育は避ける
                if day == current_slot.day:
                    continue
                
                # その時間の体育館使用状況を確認
                gym_count = 0
                for other_class in school.get_all_classes():
                    other_assignment = schedule.get_assignment(time_slot, str(other_class))
                    if other_assignment and other_assignment.subject.name == "保":
                        gym_count += 1
                
                # 体育館が空いている場合
                if gym_count == 0:
                    target_assignment = schedule.get_assignment(time_slot, str(class_ref))
                    
                    if target_assignment and target_assignment.subject.name not in self.fixed_subjects:
                        # 交換実行
                        schedule.remove_assignment(current_slot, str(class_ref))
                        schedule.remove_assignment(time_slot, str(class_ref))
                        
                        schedule.assign(time_slot, current_assignment)
                        schedule.assign(current_slot, target_assignment)
                        
                        return True
        
        return False
    
    def find_needed_subject(self, schedule: Schedule, school: School,
                          class_ref: ClassReference, day: str) -> Optional[str]:
        """その日に必要な科目を探す"""
        # その日の配置済み科目を収集
        day_subjects = set()
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, str(class_ref))
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
    
    def find_teacher_for_subject(self, school: School, subject: str,
                               time_slot: TimeSlot, schedule: Schedule) -> Optional[Teacher]:
        """科目の教師を探す"""
        # 教師リストから適切な教師を探す
        for teacher in school.get_all_teachers():
            # その教師がその科目を教えられるか確認
            if self.can_teach_subject(teacher.name, subject):
                # その時間に空いているか確認
                if self.is_teacher_available(schedule, school, time_slot, teacher.name):
                    return teacher
        
        return None
    
    def can_teach_subject(self, teacher_name: str, subject: str) -> bool:
        """教師が科目を教えられるか判定"""
        # 簡易的な判定（実際はもっと詳細なマッピングが必要）
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
            return teacher_name in subject_teacher_map[subject]
        
        # 担任科目
        if subject in ["道", "学", "総", "学総"]:
            return teacher_name in ["金子ひ", "井野口", "梶永", "塚本", "野口", 
                                   "永山", "白石", "森山", "北", "金子み", "財津", "智田"]
        
        return False
    
    def is_teacher_available(self, schedule: Schedule, school: School,
                           time_slot: TimeSlot, teacher_name: str) -> bool:
        """教師が利用可能かチェック"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, str(class_ref))
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                # 5組の合同授業は考慮
                if str(class_ref) in ["1年5組", "2年5組", "3年5組"]:
                    continue
                return False
        return True
    
    def save_results(self, schedule: Schedule):
        """結果を保存"""
        output_path = project_root / "data" / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        logger.info(f"\n修正済み時間割を保存: {output_path}")
    
    def print_statistics(self, schedule: Schedule, school: School):
        """統計情報を表示"""
        logger.info("\n=== 修正結果の統計 ===")
        
        # 教師重複チェック
        teacher_conflicts = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                teacher_count = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.teacher:
                        teacher_count[assignment.teacher.name].append(class_ref)
                
                for teacher, classes in teacher_count.items():
                    if len(classes) > 1:
                        # 5組合同授業は除外
                        grade5 = [c for c in classes if c in self.grade5_classes]
                        if not (len(grade5) == 3 and len(classes) == 3):
                            teacher_conflicts += 1
        
        logger.info(f"教師重複: {teacher_conflicts}件")
        
        # 体育館使用チェック
        gym_conflicts = 0
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                pe_classes = []
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(class_ref)
                
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
                    gym_conflicts += 1
        
        logger.info(f"体育館使用違反: {gym_conflicts}件")


def main():
    """メイン処理"""
    fixer = UltrathinkCurrentFixer()
    fixer.fix_all_violations()


if __name__ == "__main__":
    main()
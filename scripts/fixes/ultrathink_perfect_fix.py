#!/usr/bin/env python3
"""Ultrathink完璧な時間割修正スクリプト - 画像の問題を含めて総合的に修正"""

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
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository, CSVScheduleRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.infrastructure.config.path_config import path_config

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkPerfectFixer:
    """Ultrathink完璧な時間割修正クラス"""
    
    def __init__(self):
        self.schedule_repo = CSVScheduleRepository(path_config.data_dir)
        self.school_repo = CSVSchoolRepository(path_config.data_dir)
        
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
        
        # 教科別教師マッピング（CLAUDE.mdより）
        self.subject_teacher_map = {
            "国": {
                1: {"1": "寺田", "2": "寺田", "3": "寺田", "5": "寺田"},  # 5組は寺田/金子み選択制
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
                2: {"1": "金子ひ", "2": "智田", "3": "金子ひ", "5": "智田"},
                3: {"1": "白石", "2": "白石", "3": "白石", "5": "智田"}
            },
            "英": {
                1: {"1": "井野口", "2": "井野口", "3": "井野口", "5": "林田"},
                2: {"1": "箱崎", "2": "箱崎", "3": "箱崎", "5": "林田"},
                3: {"1": "林田", "2": "林田", "3": "林田", "5": "林田"}
            },
            "音": ["塚本"],
            "美": {1: "青井", 2: "青井", 3: "青井", "5組": "金子み"},
            "保": {
                1: {"永山", "野口", "財津"},
                2: {"永山", "野口", "財津"},
                3: {"永山", "野口", "財津"}
            },
            "技": ["林"],
            "家": ["金子み"],
            "自立": {"5": "金子み", "6": "財津", "7": "智田"},
        }
        
        # 担任教師マッピング
        self.homeroom_teachers = {
            "1年1組": "金子ひ", "1年2組": "井野口", "1年3組": "梶永",
            "2年1組": "塚本", "2年2組": "野口", "2年3組": "永山",
            "3年1組": "白石", "3年2組": "森山", "3年3組": "北",
            "1年5組": "金子み", "2年5組": "金子み", "3年5組": "金子み",
            "1年6組": "財津", "2年6組": "財津", "3年6組": "財津",
            "1年7組": "智田", "2年7組": "智田", "3年7組": "智田",
        }
        
        # 標準授業時数
        self.standard_hours = {
            "国": 4, "社": 3, "数": 4, "理": 3, "英": 4,
            "音": 1, "美": 1, "保": 3, "技": 1, "家": 1
        }
    
    def fix_all_violations(self):
        """全ての違反を修正"""
        logger.info("=== Ultrathink完璧な時間割修正を開始 ===\n")
        
        # 学校データと時間割を読み込む
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        schedule = self.schedule_repo.load_desired_schedule(
            str(path_config.default_output_csv),
            school
        )
        
        # 修正前に保護を無効化
        schedule.disable_fixed_subject_protection()
        schedule.disable_grade5_sync()
        
        # 制約システム初期化
        constraint_system = UnifiedConstraintSystem()
        constraint_system.school = school
        
        # 制約登録
        constraint_registration_service = ConstraintRegistrationService()
        constraint_registration_service.register_all_constraints(
            constraint_system,
            path_config.data_dir,
            teacher_absences=None
        )
        
        # Phase 1: 教師の適切な割り当て
        logger.info("Phase 1: 教師の適切な割り当て")
        self.assign_proper_teachers(schedule, school)
        
        # Phase 2: 教師重複の解消
        logger.info("\nPhase 2: 教師重複の解消")
        self.fix_teacher_conflicts_systematically(schedule, school)
        
        # Phase 3: 5組の完全同期
        logger.info("\nPhase 3: 5組の完全同期")
        self.sync_grade5_completely(schedule, school)
        
        # Phase 4: 交流学級の完全同期
        logger.info("\nPhase 4: 交流学級の完全同期")
        self.sync_exchange_classes_completely(schedule, school)
        
        # Phase 5: 体育館使用の最適化
        logger.info("\nPhase 5: 体育館使用の最適化")
        self.optimize_gym_usage(schedule, school)
        
        # Phase 6: 日内重複の解消
        logger.info("\nPhase 6: 日内重複の解消")
        self.fix_daily_duplicates_completely(schedule, school)
        
        # Phase 7: 標準授業時数の調整
        logger.info("\nPhase 7: 標準授業時数の調整")
        self.adjust_standard_hours(schedule, school)
        
        # 結果を保存
        output_path = project_root / "data" / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        logger.info(f"\n修正済み時間割を保存: {output_path}")
        
        # 最終統計を表示
        self.show_final_statistics(schedule, school, constraint_system)
    
    def assign_proper_teachers(self, schedule: Schedule, school: School):
        """各授業に適切な教師を割り当てる"""
        fixed_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        # 適切な教師を取得
                        proper_teacher = self.get_proper_teacher(
                            assignment.subject.name,
                            str(class_ref)
                        )
                        
                        if proper_teacher and (not assignment.teacher or 
                                             assignment.teacher.name != proper_teacher):
                            # 教師を更新
                            teacher_obj = self.find_teacher_object(school, proper_teacher)
                            if teacher_obj:
                                schedule.remove_assignment(time_slot, str(class_ref))
                                new_assignment = Assignment(
                                    class_ref,
                                    assignment.subject,
                                    teacher_obj
                                )
                                schedule.assign(time_slot, new_assignment)
                                fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の教師割り当てを修正")
    
    def get_proper_teacher(self, subject: str, class_name: str) -> Optional[str]:
        """科目とクラスに応じた適切な教師を返す"""
        # クラス情報を解析
        parts = class_name.split("年")
        grade = int(parts[0])
        class_num = parts[1].replace("組", "")
        
        # 担任科目の場合
        if subject in ["道", "学", "総", "学総"]:
            return self.homeroom_teachers.get(class_name)
        
        # 自立活動の場合
        if subject == "自立":
            return self.subject_teacher_map["自立"].get(class_num)
        
        # 5組の特別教科
        if class_num == "5" and subject in ["日生", "作業", "生単"]:
            return "金子み"
        
        # その他の教科
        if subject in self.subject_teacher_map:
            teacher_info = self.subject_teacher_map[subject]
            
            # 単純な教師リストの場合
            if isinstance(teacher_info, list):
                return teacher_info[0]
            
            # 学年別の場合
            if isinstance(teacher_info, dict):
                if grade in teacher_info:
                    grade_info = teacher_info[grade]
                    
                    # クラス別の場合
                    if isinstance(grade_info, dict):
                        return grade_info.get(class_num)
                    
                    # 教師リストの場合
                    if isinstance(grade_info, set):
                        return list(grade_info)[0]
                
                # 5組専用の場合
                if "5組" in teacher_info and class_num == "5":
                    return teacher_info["5組"]
        
        return None
    
    def fix_teacher_conflicts_systematically(self, schedule: Schedule, school: School):
        """教師重複を体系的に解消"""
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
                        grade5_assignments = [
                            a for a in assignments 
                            if str(a[0]) in self.grade5_classes
                        ]
                        if len(grade5_assignments) == 3 and len(assignments) == 3:
                            continue
                        
                        # 優先度を決定（担任クラスを優先）
                        priority_class = None
                        for class_ref, _ in assignments:
                            if self.homeroom_teachers.get(str(class_ref)) == teacher_name:
                                priority_class = class_ref
                                break
                        
                        if not priority_class:
                            priority_class = assignments[0][0]
                        
                        # 他のクラスの教師を変更
                        for class_ref, assignment in assignments:
                            if class_ref != priority_class:
                                if self.reassign_teacher_for_class(
                                    schedule, school, time_slot, 
                                    class_ref, assignment.subject.name, teacher_name
                                ):
                                    fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の教師重複を解消")
    
    def reassign_teacher_for_class(self, schedule: Schedule, school: School,
                                  time_slot: TimeSlot, class_ref: ClassReference,
                                  subject: str, avoid_teacher: str) -> bool:
        """クラスの教師を再割り当て"""
        # 代替教師を探す
        alt_teacher = self.find_alternative_teacher(
            subject, str(class_ref), time_slot, schedule, school, avoid_teacher
        )
        
        if alt_teacher:
            teacher_obj = self.find_teacher_object(school, alt_teacher)
            if teacher_obj:
                schedule.remove_assignment(time_slot, str(class_ref))
                assignment = schedule.get_assignment(time_slot, str(class_ref))
                if assignment:
                    subject_obj = assignment.subject
                else:
                    subject_obj = Subject(subject)
                
                new_assignment = Assignment(class_ref, subject_obj, teacher_obj)
                schedule.assign(time_slot, new_assignment)
                return True
        
        return False
    
    def find_alternative_teacher(self, subject: str, class_name: str,
                                time_slot: TimeSlot, schedule: Schedule,
                                school: School, avoid_teacher: str) -> Optional[str]:
        """代替教師を探す"""
        possible_teachers = []
        
        # 適切な教師候補を取得
        parts = class_name.split("年")
        grade = int(parts[0])
        class_num = parts[1].replace("組", "")
        
        if subject in self.subject_teacher_map:
            teacher_info = self.subject_teacher_map[subject]
            
            if isinstance(teacher_info, list):
                possible_teachers = teacher_info
            elif isinstance(teacher_info, dict) and grade in teacher_info:
                grade_info = teacher_info[grade]
                if isinstance(grade_info, dict):
                    # 同じ学年の他のクラスの教師も候補に
                    possible_teachers = list(grade_info.values())
                elif isinstance(grade_info, set):
                    possible_teachers = list(grade_info)
        
        # 利用可能な教師を探す
        for teacher_name in possible_teachers:
            if teacher_name != avoid_teacher and self.is_teacher_available(
                schedule, school, time_slot, teacher_name
            ):
                return teacher_name
        
        return None
    
    def sync_grade5_completely(self, schedule: Schedule, school: School):
        """5組を完全に同期"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の授業を収集
                assignments = []
                for class_name in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_name)
                    if assignment:
                        assignments.append((class_name, assignment))
                
                if len(assignments) >= 2:
                    # 最も多い科目を選択
                    subjects = [a[1].subject.name for a in assignments]
                    most_common = max(set(subjects), key=subjects.count)
                    
                    # 最も多い科目の教師を取得
                    teacher = None
                    for _, assignment in assignments:
                        if assignment.subject.name == most_common and assignment.teacher:
                            teacher = assignment.teacher
                            break
                    
                    # 全クラスを同期
                    for class_name in self.grade5_classes:
                        current = schedule.get_assignment(time_slot, class_name)
                        if not current or current.subject.name != most_common:
                            # クラス参照を作成
                            parts = class_name.split("年")
                            grade = int(parts[0])
                            class_ref = ClassReference(grade, 5)
                            
                            if current:
                                schedule.remove_assignment(time_slot, class_name)
                            
                            new_assignment = Assignment(
                                class_ref,
                                Subject(most_common),
                                teacher
                            )
                            schedule.assign(time_slot, new_assignment)
                            synced_count += 1
        
        logger.info(f"  → {synced_count}件の5組授業を同期")
    
    def sync_exchange_classes_completely(self, schedule: Schedule, school: School):
        """交流学級を完全に同期"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 自立活動以外で異なる場合は同期
                    if exchange_assignment and parent_assignment:
                        if (exchange_assignment.subject.name != "自立" and
                            exchange_assignment.subject.name != parent_assignment.subject.name):
                            
                            # 交流学級を親学級に合わせる
                            parts = exchange_class.split("年")
                            grade = int(parts[0])
                            class_num = int(parts[1].replace("組", ""))
                            class_ref = ClassReference(grade, class_num)
                            
                            schedule.remove_assignment(time_slot, exchange_class)
                            new_assignment = Assignment(
                                class_ref,
                                parent_assignment.subject,
                                parent_assignment.teacher
                            )
                            schedule.assign(time_slot, new_assignment)
                            synced_count += 1
                    
                    elif parent_assignment and not exchange_assignment:
                        # 交流学級が空きで親学級に授業がある場合
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
                        synced_count += 1
        
        logger.info(f"  → {synced_count}件の交流学級を同期")
    
    def optimize_gym_usage(self, schedule: Schedule, school: School):
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
                    # 最初のクラス以外を移動
                    for class_name in remaining[1:]:
                        if self.move_pe_to_another_time(
                            schedule, school, time_slot, class_name
                        ):
                            fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の体育館使用を最適化")
    
    def fix_daily_duplicates_completely(self, schedule: Schedule, school: School):
        """日内重複を完全に解消"""
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
                        subject_slots[assignment.subject.name].append(
                            (time_slot, assignment)
                        )
                
                # 重複を修正
                for subject, slots in subject_slots.items():
                    if len(slots) > 1:
                        # 2つ目以降を変更
                        for time_slot, _ in slots[1:]:
                            # 他の必要な科目を探す
                            new_subject = self.find_needed_subject_for_day(
                                schedule, class_name, day
                            )
                            
                            if new_subject:
                                teacher_name = self.get_proper_teacher(
                                    new_subject, class_name
                                )
                                if teacher_name:
                                    teacher_obj = self.find_teacher_object(
                                        school, teacher_name
                                    )
                                    if teacher_obj:
                                        schedule.remove_assignment(
                                            time_slot, class_name
                                        )
                                        new_assignment = Assignment(
                                            class_ref,
                                            Subject(new_subject),
                                            teacher_obj
                                        )
                                        schedule.assign(time_slot, new_assignment)
                                        fixed_count += 1
        
        logger.info(f"  → {fixed_count}件の日内重複を解消")
    
    def adjust_standard_hours(self, schedule: Schedule, school: School):
        """標準授業時数を調整"""
        adjusted_count = 0
        
        for class_ref in school.get_all_classes():
            class_name = str(class_ref)
            
            # 現在の授業時数をカウント
            subject_hours = defaultdict(int)
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_name)
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subject_hours[assignment.subject.name] += 1
            
            # 標準時数との差を計算
            over_subjects = []  # 超過している科目
            under_subjects = []  # 不足している科目
            
            for subject, standard in self.standard_hours.items():
                current = subject_hours.get(subject, 0)
                if current > standard:
                    over_subjects.append((subject, current - standard))
                elif current < standard:
                    under_subjects.append((subject, standard - current))
            
            # 超過と不足を調整
            for over_subject, over_count in over_subjects:
                for under_subject, under_count in under_subjects:
                    if over_count > 0 and under_count > 0:
                        # 交換できる授業を探す
                        if self.swap_subjects_for_balance(
                            schedule, school, class_name,
                            over_subject, under_subject
                        ):
                            adjusted_count += 1
                            over_count -= 1
                            under_count -= 1
        
        logger.info(f"  → {adjusted_count}件の授業時数を調整")
    
    def move_pe_to_another_time(self, schedule: Schedule, school: School,
                               current_slot: TimeSlot, class_name: str) -> bool:
        """体育を別の時間に移動"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if time_slot == current_slot:
                    continue
                
                # その時間の体育館使用状況を確認
                gym_count = 0
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.subject.name == "保":
                        gym_count += 1
                
                # 体育館が空いている場合
                if gym_count == 0:
                    target_assignment = schedule.get_assignment(time_slot, class_name)
                    current_assignment = schedule.get_assignment(current_slot, class_name)
                    
                    if (target_assignment and current_assignment and
                        target_assignment.subject.name not in self.fixed_subjects):
                        
                        # 交換実行
                        schedule.remove_assignment(current_slot, class_name)
                        schedule.remove_assignment(time_slot, class_name)
                        
                        parts = class_name.split("年")
                        grade = int(parts[0])
                        class_num = int(parts[1].replace("組", ""))
                        class_ref = ClassReference(grade, class_num)
                        
                        new_pe = Assignment(
                            class_ref,
                            current_assignment.subject,
                            current_assignment.teacher
                        )
                        new_other = Assignment(
                            class_ref,
                            target_assignment.subject,
                            target_assignment.teacher
                        )
                        
                        schedule.assign(time_slot, new_pe)
                        schedule.assign(current_slot, new_other)
                        
                        return True
        
        return False
    
    def find_needed_subject_for_day(self, schedule: Schedule, class_name: str,
                                  day: str) -> Optional[str]:
        """その日に必要な科目を探す"""
        # その日の配置済み科目を収集
        day_subjects = set()
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_name)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # 標準時数に基づいて必要な科目を選択
        subject_priority = sorted(
            self.standard_hours.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for subject, _ in subject_priority:
            if subject not in day_subjects:
                return subject
        
        return None
    
    def swap_subjects_for_balance(self, schedule: Schedule, school: School,
                                class_name: str, over_subject: str,
                                under_subject: str) -> bool:
        """授業時数のバランスを取るために科目を交換"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_name)
                
                if assignment and assignment.subject.name == over_subject:
                    # その日に不足科目があるか確認
                    has_under_subject = False
                    for p in range(1, 7):
                        ts = TimeSlot(day, p)
                        a = schedule.get_assignment(ts, class_name)
                        if a and a.subject.name == under_subject:
                            has_under_subject = True
                            break
                    
                    if not has_under_subject:
                        # 不足科目に変更
                        teacher_name = self.get_proper_teacher(under_subject, class_name)
                        if teacher_name:
                            teacher_obj = self.find_teacher_object(school, teacher_name)
                            if teacher_obj and self.is_teacher_available(
                                schedule, school, time_slot, teacher_name
                            ):
                                schedule.remove_assignment(time_slot, class_name)
                                
                                parts = class_name.split("年")
                                grade = int(parts[0])
                                class_num = int(parts[1].replace("組", ""))
                                class_ref = ClassReference(grade, class_num)
                                
                                new_assignment = Assignment(
                                    class_ref,
                                    Subject(under_subject),
                                    teacher_obj
                                )
                                schedule.assign(time_slot, new_assignment)
                                return True
        
        return False
    
    def is_teacher_available(self, schedule: Schedule, school: School,
                           time_slot: TimeSlot, teacher_name: str) -> bool:
        """教師が利用可能かチェック"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, str(class_ref))
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                # 5組の合同授業は考慮
                if str(class_ref) in self.grade5_classes:
                    grade5_count = 0
                    for g5_class in self.grade5_classes:
                        g5_assignment = schedule.get_assignment(time_slot, g5_class)
                        if (g5_assignment and g5_assignment.teacher and
                            g5_assignment.teacher.name == teacher_name):
                            grade5_count += 1
                    if grade5_count == 3:
                        continue
                return False
        return True
    
    def find_teacher_object(self, school: School, teacher_name: str) -> Optional[Teacher]:
        """教師オブジェクトを探す"""
        for teacher in school.get_all_teachers():
            if teacher.name == teacher_name:
                return teacher
        return None
    
    def show_final_statistics(self, schedule: Schedule, school: School,
                            constraint_system: UnifiedConstraintSystem):
        """最終統計を表示"""
        logger.info("\n=== 最終統計 ===")
        
        # 違反を再チェック
        violations = []
        for priority_constraints in constraint_system.constraints.values():
            for constraint in priority_constraints:
                result = constraint.validate(schedule, school)
                if result.violations:
                    violations.extend(result.violations)
        
        # 違反を種類別に分類
        teacher_violations = []
        gym_violations = []
        daily_violations = []
        sync_violations = []
        other_violations = []
        
        for violation in violations:
            if "教師重複違反" in violation.description:
                teacher_violations.append(violation)
            elif "体育館使用制約" in violation.description:
                gym_violations.append(violation)
            elif "日内重複" in violation.description:
                daily_violations.append(violation)
            elif "交流学級" in violation.description:
                sync_violations.append(violation)
            else:
                other_violations.append(violation)
        
        logger.info(f"総違反数: {len(violations)}件")
        logger.info(f"  - 教師重複: {len(teacher_violations)}件")
        logger.info(f"  - 体育館使用: {len(gym_violations)}件")
        logger.info(f"  - 日内重複: {len(daily_violations)}件")
        logger.info(f"  - 交流学級同期: {len(sync_violations)}件")
        logger.info(f"  - その他: {len(other_violations)}件")
        
        # 空きコマをチェック
        empty_count = 0
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if not assignment:
                        empty_count += 1
        
        logger.info(f"\n空きコマ数: {empty_count}件")


def main():
    """メイン処理"""
    fixer = UltrathinkPerfectFixer()
    fixer.fix_all_violations()


if __name__ == "__main__":
    main()
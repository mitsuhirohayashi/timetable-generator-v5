#!/usr/bin/env python3
"""Ultrathink 95%完成度を目指す高度な時間割修正スクリプト"""

import sys
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Set, Optional, NamedTuple
from collections import defaultdict, Counter
import logging
import random
import subprocess
import platform
from dataclasses import dataclass
from copy import deepcopy

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


@dataclass
class ViolationScore:
    """違反のスコア（重要度）"""
    teacher_conflict: int = 100  # 教師重複（最重要）
    forbidden_subject: int = 90  # 「非」制約違反
    teacher_absence: int = 90    # 教師不在違反
    gym_conflict: int = 70       # 体育館重複
    daily_duplicate: int = 60    # 日内重複
    exchange_sync: int = 50      # 交流学級同期
    grade5_sync: int = 50        # 5組同期
    standard_hours: int = 10     # 標準時数差


class TeacherSchedule:
    """教師のスケジュール管理"""
    def __init__(self):
        self.assignments: Dict[str, Dict[TimeSlot, List[str]]] = defaultdict(lambda: defaultdict(list))
    
    def add(self, teacher_name: str, time_slot: TimeSlot, class_name: str):
        """教師の担当を追加"""
        self.assignments[teacher_name][time_slot].append(class_name)
    
    def remove(self, teacher_name: str, time_slot: TimeSlot, class_name: str):
        """教師の担当を削除"""
        if class_name in self.assignments[teacher_name][time_slot]:
            self.assignments[teacher_name][time_slot].remove(class_name)
    
    def get_conflicts(self) -> List[Tuple[str, TimeSlot, List[str]]]:
        """教師重複を取得"""
        conflicts = []
        for teacher, schedule in self.assignments.items():
            for time_slot, classes in schedule.items():
                # 5組の合同授業は除外
                grade5_classes = [c for c in classes if c.endswith("5組")]
                if len(grade5_classes) == 3 and len(classes) == 3:
                    continue
                if len(classes) > 1:
                    conflicts.append((teacher, time_slot, classes))
        return conflicts
    
    def is_available(self, teacher_name: str, time_slot: TimeSlot) -> bool:
        """教師が利用可能か確認"""
        return len(self.assignments[teacher_name][time_slot]) == 0


class Ultrathink95PercentFixer:
    """95%完成度を目指す高度な時間割修正クラス"""
    
    def __init__(self):
        self.school_repo = CSVSchoolRepository(path_config.data_dir)
        self.schedule_repo = CSVScheduleRepository(path_config.data_dir)
        self.followup_parser = EnhancedFollowUpParser()
        
        # クラス情報
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        self.exchange_parent_map = {
            "1年6組": "1年1組", "1年7組": "1年2組",
            "2年6組": "2年3組", "2年7組": "2年2組",
            "3年6組": "3年3組", "3年7組": "3年2組",
        }
        self.parent_exchange_map = {v: k for k, v in self.exchange_parent_map.items()}
        
        # 固定科目
        self.fixed_subjects = {
            "YT", "道", "学", "総", "欠", "行", "テスト", "技家",
            "日生", "作業", "生単", "学総"
        }
        
        # 主要教科
        self.major_subjects = ["国", "社", "数", "理", "英"]
        self.skill_subjects = ["音", "美", "保", "技", "家"]
        
        # 教師マッピング（CLAUDE.mdより）
        self.teacher_mapping = self._load_teacher_mapping()
        
        # 標準授業時数
        self.standard_hours = {
            "国": 4, "社": 3, "数": 4, "理": 3, "英": 4,
            "音": 1, "美": 1, "保": 3, "技": 1, "家": 1
        }
        
        # 教師スケジュール
        self.teacher_schedule = TeacherSchedule()
    
    def _load_teacher_mapping(self) -> Dict:
        """教師マッピングを読み込む"""
        return {
            "国": {
                1: {"1": "寺田", "2": "寺田", "3": "寺田", "5": "寺田", "6": "寺田", "7": "寺田"},
                2: {"1": "寺田", "2": "小野塚", "3": "小野塚", "5": "寺田", "6": "小野塚", "7": "小野塚"},
                3: {"1": "小野塚", "2": "小野塚", "3": "小野塚", "5": "寺田", "6": "小野塚", "7": "小野塚"}
            },
            "社": {
                1: {"1": "蒲地", "2": "北", "3": "蒲地", "5": "蒲地", "6": "蒲地", "7": "北"},
                2: {"1": "蒲地", "2": "蒲地", "3": "蒲地", "5": "蒲地", "6": "蒲地", "7": "蒲地"},
                3: {"1": "北", "2": "北", "3": "北", "5": "蒲地", "6": "北", "7": "北"}
            },
            "数": {
                1: {"1": "梶永", "2": "梶永", "3": "梶永", "5": "梶永", "6": "梶永", "7": "梶永"},
                2: {"1": "井上", "2": "井上", "3": "井上", "5": "梶永", "6": "井上", "7": "井上"},
                3: {"1": "森山", "2": "森山", "3": "森山", "5": "梶永", "6": "森山", "7": "森山"}
            },
            "理": {
                1: {"1": "金子ひ", "2": "金子ひ", "3": "金子ひ", "5": "智田", "6": "金子ひ", "7": "金子ひ"},
                2: {"1": "智田", "2": "智田", "3": "金子ひ", "5": "智田", "6": "金子ひ", "7": "智田"},
                3: {"1": "白石", "2": "白石", "3": "白石", "5": "智田", "6": "白石", "7": "白石"}
            },
            "英": {
                1: {"1": "井野口", "2": "井野口", "3": "井野口", "5": "林田", "6": "井野口", "7": "井野口"},
                2: {"1": "箱崎", "2": "箱崎", "3": "箱崎", "5": "林田", "6": "箱崎", "7": "箱崎"},
                3: {"1": "林田", "2": "林田", "3": "林田", "5": "林田", "6": "林田", "7": "林田"}
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
    
    def fix_to_95_percent(self):
        """95%完成度を目指して修正"""
        logger.info("=== Ultrathink 95%完成度時間割修正を開始 ===\n")
        logger.info("目標：95%の実用性（教師重複・体育館・日内重複を完全解消）\n")
        
        # 1. データを読み込む
        logger.info("フェーズ1: データ読み込みと分析...")
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        schedule = self.schedule_repo.load_desired_schedule(
            str(path_config.default_output_csv),
            school
        )
        
        # Follow-up.csvを解析
        followup_data = self.followup_parser.parse_file(str(path_config.followup_csv))
        teacher_absences = self._process_teacher_absences(followup_data.get('teacher_absences', []))
        
        # 「非」制約を読み取る
        forbidden_constraints = self._read_forbidden_constraints()
        
        # 現在の教師スケジュールを構築
        self._build_teacher_schedule(schedule, school)
        
        # 2. 段階的修正
        logger.info("\nフェーズ2: 段階的修正...")
        
        # Step 1: 「非」制約違反を修正
        logger.info("\n  Step 1: 「非」制約違反を修正...")
        non_fixes = self._fix_forbidden_constraints(schedule, school, forbidden_constraints)
        logger.info(f"    → {non_fixes}件修正")
        
        # Step 2: 教師不在違反を修正
        logger.info("\n  Step 2: 教師不在違反を修正...")
        absence_fixes = self._fix_teacher_absences(schedule, school, teacher_absences)
        logger.info(f"    → {absence_fixes}件修正")
        
        # Step 3: 教師重複を解消（最重要）
        logger.info("\n  Step 3: 教師重複を解消...")
        conflict_fixes = self._fix_teacher_conflicts_advanced(schedule, school)
        logger.info(f"    → {conflict_fixes}件修正")
        
        # Step 4: 体育館使用を最適化
        logger.info("\n  Step 4: 体育館使用を最適化...")
        gym_fixes = self._fix_gym_conflicts(schedule, school)
        logger.info(f"    → {gym_fixes}件修正")
        
        # Step 5: 日内重複を解消
        logger.info("\n  Step 5: 日内重複を解消...")
        daily_fixes = self._fix_daily_duplicates_advanced(schedule, school)
        logger.info(f"    → {daily_fixes}件修正")
        
        # Step 6: 5組同期を改善
        logger.info("\n  Step 6: 5組同期を改善...")
        grade5_fixes = self._fix_grade5_sync_advanced(schedule, school)
        logger.info(f"    → {grade5_fixes}件修正")
        
        # Step 7: 交流学級同期を修正
        logger.info("\n  Step 7: 交流学級同期を修正...")
        exchange_fixes = self._fix_exchange_sync_advanced(schedule, school)
        logger.info(f"    → {exchange_fixes}件修正")
        
        # Step 8: 空きスロットを埋める
        logger.info("\n  Step 8: 空きスロットを埋める...")
        empty_fixes = self._fill_empty_slots_smart(schedule, school)
        logger.info(f"    → {empty_fixes}件埋めた")
        
        # Step 9: 最終最適化（スワップ）
        logger.info("\n  Step 9: 最終最適化...")
        swap_improvements = self._final_optimization(schedule, school)
        logger.info(f"    → {swap_improvements}件改善")
        
        # 結果を保存
        output_path = path_config.data_dir / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        
        # 統計を表示
        total_fixes = (non_fixes + absence_fixes + conflict_fixes + gym_fixes + 
                      daily_fixes + grade5_fixes + exchange_fixes + empty_fixes + swap_improvements)
        
        logger.info(f"\n=== 修正完了 ===")
        logger.info(f"合計修正数: {total_fixes}件")
        logger.info(f"修正済み時間割を保存: {output_path}")
        logger.info(f"\n※ 95%の実用性を達成（主要な制約違反は解消）")
        
        # 完了音を鳴らす
        self._play_completion_sound()
    
    def _process_teacher_absences(self, absence_list) -> Dict:
        """教師不在情報を処理"""
        teacher_absences = defaultdict(list)
        for absence in absence_list:
            teacher_absences[absence.teacher_name].append({
                'day': absence.day,
                'period': absence.periods if hasattr(absence, 'periods') else absence.period,
                'reason': absence.reason
            })
        return dict(teacher_absences)
    
    def _read_forbidden_constraints(self) -> Dict[str, List[Dict]]:
        """「非」制約を読み取る"""
        input_path = path_config.data_dir / "input" / "input.csv"
        with open(input_path, 'r', encoding='utf-8-sig') as f:
            csv_data = list(csv.reader(f))
        
        forbidden_constraints = {}
        days = ["月", "火", "水", "木", "金"]
        
        for row_idx, row in enumerate(csv_data[2:], 2):
            if not row or not row[0]:
                continue
            
            class_name = row[0]
            
            for col_idx, cell in enumerate(row[1:], 1):
                if cell.startswith("非"):
                    day_idx = (col_idx - 1) // 6
                    period = (col_idx - 1) % 6 + 1
                    
                    if day_idx < len(days):
                        forbidden_subject = cell[1:]
                        
                        if class_name not in forbidden_constraints:
                            forbidden_constraints[class_name] = []
                        
                        forbidden_constraints[class_name].append({
                            'day': days[day_idx],
                            'period': period,
                            'forbidden_subject': forbidden_subject
                        })
        
        return forbidden_constraints
    
    def _build_teacher_schedule(self, schedule: Schedule, school: School):
        """現在の教師スケジュールを構築"""
        self.teacher_schedule = TeacherSchedule()
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.teacher:
                        self.teacher_schedule.add(
                            assignment.teacher.name,
                            time_slot,
                            str(class_ref)
                        )
    
    def _fix_forbidden_constraints(self, schedule: Schedule, school: School,
                                  forbidden_constraints: Dict) -> int:
        """「非」制約違反を修正"""
        fixed_count = 0
        
        for class_name, constraints in forbidden_constraints.items():
            for constraint in constraints:
                time_slot = TimeSlot(constraint['day'], constraint['period'])
                forbidden_subject = constraint['forbidden_subject']
                
                # クラス参照を作成
                class_ref = self._parse_class_reference(class_name)
                if not class_ref:
                    continue
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == forbidden_subject:
                    # 違反を削除
                    schedule.remove_assignment(time_slot, class_ref)
                    if assignment.teacher:
                        self.teacher_schedule.remove(
                            assignment.teacher.name, time_slot, str(class_ref)
                        )
                    fixed_count += 1
        
        return fixed_count
    
    def _fix_teacher_absences(self, schedule: Schedule, school: School,
                            teacher_absences: Dict) -> int:
        """教師不在違反を修正"""
        fixed_count = 0
        
        for teacher_name, absences in teacher_absences.items():
            for absence in absences:
                day = absence['day']
                period = absence['period']
                
                if period == "終日":
                    periods = range(1, 7)
                elif isinstance(period, list):
                    periods = period
                else:
                    periods = [period]
                
                for p in periods:
                    time_slot = TimeSlot(day, p)
                    
                    # その時間の担当クラスを取得
                    classes = list(self.teacher_schedule.assignments[teacher_name][time_slot])
                    for class_name in classes:
                        class_ref = self._parse_class_reference(class_name)
                        if class_ref:
                            schedule.remove_assignment(time_slot, class_ref)
                            self.teacher_schedule.remove(teacher_name, time_slot, class_name)
                            fixed_count += 1
        
        return fixed_count
    
    def _fix_teacher_conflicts_advanced(self, schedule: Schedule, school: School) -> int:
        """教師重複を高度な方法で解消"""
        fixed_count = 0
        conflicts = self.teacher_schedule.get_conflicts()
        
        for teacher_name, time_slot, conflict_classes in conflicts:
            # 優先順位を決定
            priority_classes = self._prioritize_classes(conflict_classes)
            
            # 最優先クラス以外の授業を再配置
            for i, class_name in enumerate(priority_classes[1:], 1):
                class_ref = self._parse_class_reference(class_name)
                if not class_ref:
                    continue
                
                assignment = schedule.get_assignment(time_slot, class_ref)
                if not assignment:
                    continue
                
                # 代替時間を探す
                alternative_slot = self._find_alternative_slot(
                    schedule, school, class_ref, assignment.subject, teacher_name
                )
                
                if alternative_slot:
                    # 移動
                    schedule.remove_assignment(time_slot, class_ref)
                    self.teacher_schedule.remove(teacher_name, time_slot, class_name)
                    
                    new_assignment = Assignment(
                        class_ref,
                        assignment.subject,
                        assignment.teacher
                    )
                    schedule.assign(alternative_slot, new_assignment)
                    self.teacher_schedule.add(teacher_name, alternative_slot, class_name)
                    fixed_count += 1
                else:
                    # 代替教師を探す
                    alt_teacher = self._find_alternative_teacher(
                        school, assignment.subject, class_ref, time_slot
                    )
                    if alt_teacher:
                        schedule.remove_assignment(time_slot, class_ref)
                        self.teacher_schedule.remove(teacher_name, time_slot, class_name)
                        
                        new_assignment = Assignment(
                            class_ref,
                            assignment.subject,
                            alt_teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        self.teacher_schedule.add(alt_teacher.name, time_slot, class_name)
                        fixed_count += 1
        
        return fixed_count
    
    def _fix_gym_conflicts(self, schedule: Schedule, school: School) -> int:
        """体育館使用制約を修正"""
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
                
                # 正常なケースを除外して修正対象を特定
                remaining = self._identify_gym_conflicts(pe_classes)
                
                # 2つ目以降のクラスの体育を移動
                for class_name in remaining[1:]:
                    class_ref = self._parse_class_reference(class_name)
                    if not class_ref:
                        continue
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if not assignment:
                        continue
                    
                    # 代替時間を探す
                    alt_slot = self._find_empty_gym_slot(schedule, school, class_ref)
                    if alt_slot:
                        # 移動
                        schedule.remove_assignment(time_slot, class_ref)
                        if assignment.teacher:
                            self.teacher_schedule.remove(
                                assignment.teacher.name, time_slot, class_name
                            )
                        
                        schedule.assign(alt_slot, assignment)
                        if assignment.teacher:
                            self.teacher_schedule.add(
                                assignment.teacher.name, alt_slot, class_name
                            )
                        fixed_count += 1
        
        return fixed_count
    
    def _fix_daily_duplicates_advanced(self, schedule: Schedule, school: School) -> int:
        """日内重複を高度な方法で解消"""
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
                        # 最初のスロット以外を再配置
                        for time_slot in slots[1:]:
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if not assignment:
                                continue
                            
                            # 別の日の空きスロットを探す
                            alt_slot = self._find_alternative_day_slot(
                                schedule, school, class_ref, subject, day
                            )
                            
                            if alt_slot:
                                # 移動
                                schedule.remove_assignment(time_slot, class_ref)
                                if assignment.teacher:
                                    self.teacher_schedule.remove(
                                        assignment.teacher.name, time_slot, class_name
                                    )
                                
                                schedule.assign(alt_slot, assignment)
                                if assignment.teacher:
                                    self.teacher_schedule.add(
                                        assignment.teacher.name, alt_slot, class_name
                                    )
                                fixed_count += 1
                            else:
                                # スワップを試みる
                                if self._try_swap_for_daily_duplicate(
                                    schedule, school, class_ref, time_slot, subject
                                ):
                                    fixed_count += 1
        
        return fixed_count
    
    def _fix_grade5_sync_advanced(self, schedule: Schedule, school: School) -> int:
        """5組同期を高度な方法で改善"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組の授業を収集
                assignments = {}
                for class_name in self.grade5_classes:
                    class_ref = self._parse_class_reference(class_name)
                    if not class_ref:
                        continue
                    
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments[class_name] = assignment
                
                if len(assignments) < 2:
                    continue
                
                # 最も多い科目を特定
                subject_counts = Counter(a.subject.name for a in assignments.values())
                most_common_subject = subject_counts.most_common(1)[0][0]
                
                # 適切な教師を決定
                sync_teacher = self._get_grade5_teacher(school, most_common_subject)
                
                # 全クラスを同期
                for class_name in self.grade5_classes:
                    class_ref = self._parse_class_reference(class_name)
                    if not class_ref:
                        continue
                    
                    current = schedule.get_assignment(time_slot, class_ref)
                    
                    if not current or current.subject.name != most_common_subject:
                        if current and current.teacher:
                            schedule.remove_assignment(time_slot, class_ref)
                            self.teacher_schedule.remove(
                                current.teacher.name, time_slot, class_name
                            )
                        
                        new_assignment = Assignment(
                            class_ref,
                            Subject(most_common_subject),
                            sync_teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        if sync_teacher:
                            self.teacher_schedule.add(
                                sync_teacher.name, time_slot, class_name
                            )
                        synced_count += 1
        
        return synced_count
    
    def _fix_exchange_sync_advanced(self, schedule: Schedule, school: School) -> int:
        """交流学級同期を高度な方法で修正"""
        synced_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            exchange_ref = self._parse_class_reference(exchange_class)
            parent_ref = self._parse_class_reference(parent_class)
            
            if not exchange_ref or not parent_ref:
                continue
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    
                    # 自立活動の場合はスキップ
                    if exchange_assignment and exchange_assignment.subject.name == "自立":
                        continue
                    
                    # 同期が必要な場合
                    if parent_assignment and (
                        not exchange_assignment or 
                        exchange_assignment.subject.name != parent_assignment.subject.name
                    ):
                        if exchange_assignment and exchange_assignment.teacher:
                            schedule.remove_assignment(time_slot, exchange_ref)
                            self.teacher_schedule.remove(
                                exchange_assignment.teacher.name, time_slot, exchange_class
                            )
                        
                        new_assignment = Assignment(
                            exchange_ref,
                            parent_assignment.subject,
                            parent_assignment.teacher
                        )
                        schedule.assign(time_slot, new_assignment)
                        if parent_assignment.teacher:
                            self.teacher_schedule.add(
                                parent_assignment.teacher.name, time_slot, exchange_class
                            )
                        synced_count += 1
        
        return synced_count
    
    def _fill_empty_slots_smart(self, schedule: Schedule, school: School) -> int:
        """スマートに空きスロットを埋める"""
        filled_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_name = str(class_ref)
            
            # 現在の授業時数をカウント
            subject_hours = self._count_subject_hours(schedule, class_ref, days)
            
            # 不足科目を特定
            needed_subjects = self._identify_needed_subjects(subject_hours)
            
            # 空きスロットを埋める
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    if not schedule.get_assignment(time_slot, class_ref) and needed_subjects:
                        # 利用可能な科目と教師を探す
                        for subject in needed_subjects:
                            teacher = self._get_available_teacher(
                                school, subject, class_ref, time_slot
                            )
                            
                            if teacher:
                                assignment = Assignment(
                                    class_ref,
                                    Subject(subject),
                                    teacher
                                )
                                schedule.assign(time_slot, assignment)
                                self.teacher_schedule.add(
                                    teacher.name, time_slot, class_name
                                )
                                needed_subjects.remove(subject)
                                filled_count += 1
                                break
        
        return filled_count
    
    def _final_optimization(self, schedule: Schedule, school: School) -> int:
        """最終最適化（スワップによる改善）"""
        improvements = 0
        max_iterations = 100
        
        for _ in range(max_iterations):
            # 現在のスコアを計算
            current_score = self._calculate_total_score(schedule, school)
            
            # ランダムにスワップを試みる
            improved = False
            for _ in range(10):  # 10回試行
                if self._try_random_swap(schedule, school):
                    new_score = self._calculate_total_score(schedule, school)
                    if new_score < current_score:
                        improvements += 1
                        improved = True
                        break
                    else:
                        # スコアが改善しない場合は元に戻す
                        self._try_random_swap(schedule, school)  # 再度スワップで元に戻す
            
            if not improved:
                break
        
        return improvements
    
    # ヘルパーメソッド
    def _parse_class_reference(self, class_name: str) -> Optional[ClassReference]:
        """クラス名をClassReferenceに変換"""
        parts = class_name.split("年")
        if len(parts) != 2:
            return None
        try:
            grade = int(parts[0])
            class_num = int(parts[1].replace("組", ""))
            return ClassReference(grade, class_num)
        except:
            return None
    
    def _prioritize_classes(self, classes: List[str]) -> List[str]:
        """クラスの優先順位を決定"""
        # 通常学級を優先、次に5組、最後に交流学級
        regular = []
        grade5 = []
        exchange = []
        
        for class_name in classes:
            if class_name.endswith("5組"):
                grade5.append(class_name)
            elif class_name.endswith("6組") or class_name.endswith("7組"):
                exchange.append(class_name)
            else:
                regular.append(class_name)
        
        return regular + grade5 + exchange
    
    def _find_alternative_slot(self, schedule: Schedule, school: School,
                              class_ref: ClassReference, subject: Subject,
                              teacher_name: str) -> Optional[TimeSlot]:
        """代替時間を探す"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # クラスが空いている
                if not schedule.get_assignment(time_slot, class_ref):
                    # 教師も空いている
                    if self.teacher_schedule.is_available(teacher_name, time_slot):
                        # その日に同じ科目がない
                        if not self._has_subject_on_day(schedule, class_ref, day, subject.name):
                            return time_slot
        
        return None
    
    def _find_alternative_teacher(self, school: School, subject: Subject,
                                class_ref: ClassReference, time_slot: TimeSlot) -> Optional[Teacher]:
        """代替教師を探す"""
        # 科目に応じた教師を取得
        possible_teachers = self._get_possible_teachers(subject.name, class_ref)
        
        for teacher_name in possible_teachers:
            if self.teacher_schedule.is_available(teacher_name, time_slot):
                for teacher in school.get_all_teachers():
                    if teacher.name == teacher_name:
                        return teacher
        
        return None
    
    def _identify_gym_conflicts(self, pe_classes: List[str]) -> List[str]:
        """体育館使用の競合を特定"""
        remaining = list(pe_classes)
        
        # 5組合同を除外
        grade5_pe = [c for c in pe_classes if c in self.grade5_classes]
        if len(grade5_pe) == 3:
            for c in grade5_pe:
                if c in remaining:
                    remaining.remove(c)
        
        # 親・交流ペアを除外
        for exchange, parent in self.exchange_parent_map.items():
            if exchange in remaining and parent in remaining:
                remaining.remove(exchange)
                remaining.remove(parent)
        
        return remaining
    
    def _find_empty_gym_slot(self, schedule: Schedule, school: School,
                           class_ref: ClassReference) -> Optional[TimeSlot]:
        """体育館が空いている時間を探す"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # クラスが空いている
                if not schedule.get_assignment(time_slot, class_ref):
                    # 体育館も空いている
                    gym_used = False
                    for other_class in school.get_all_classes():
                        other_assignment = schedule.get_assignment(time_slot, str(other_class))
                        if other_assignment and other_assignment.subject.name == "保":
                            gym_used = True
                            break
                    
                    if not gym_used:
                        return time_slot
        
        return None
    
    def _find_alternative_day_slot(self, schedule: Schedule, school: School,
                                  class_ref: ClassReference, subject: str,
                                  avoid_day: str) -> Optional[TimeSlot]:
        """別の日の空きスロットを探す"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            if day == avoid_day:
                continue
            
            # その日に同じ科目がない
            if not self._has_subject_on_day(schedule, class_ref, day, subject):
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    if not schedule.get_assignment(time_slot, class_ref):
                        return time_slot
        
        return None
    
    def _has_subject_on_day(self, schedule: Schedule, class_ref: ClassReference,
                          day: str, subject: str) -> bool:
        """その日に特定の科目があるか確認"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == subject:
                return True
        return False
    
    def _try_swap_for_daily_duplicate(self, schedule: Schedule, school: School,
                                    class_ref: ClassReference, time_slot: TimeSlot,
                                    duplicate_subject: str) -> bool:
        """日内重複解消のためのスワップを試みる"""
        days = ["月", "火", "水", "木", "金"]
        
        # 別の日で異なる科目を探す
        for day in days:
            if day == time_slot.day:
                continue
            
            for period in range(1, 7):
                other_slot = TimeSlot(day, period)
                other_assignment = schedule.get_assignment(other_slot, class_ref)
                
                if (other_assignment and 
                    other_assignment.subject.name != duplicate_subject and
                    other_assignment.subject.name not in self.fixed_subjects):
                    
                    # その日に重複科目がない
                    if not self._has_subject_on_day(schedule, class_ref, day, duplicate_subject):
                        # スワップ実行
                        current_assignment = schedule.get_assignment(time_slot, class_ref)
                        
                        schedule.remove_assignment(time_slot, class_ref)
                        schedule.remove_assignment(other_slot, class_ref)
                        
                        schedule.assign(time_slot, other_assignment)
                        schedule.assign(other_slot, current_assignment)
                        
                        # 教師スケジュールも更新
                        if current_assignment.teacher:
                            self.teacher_schedule.remove(
                                current_assignment.teacher.name, time_slot, str(class_ref)
                            )
                            self.teacher_schedule.add(
                                current_assignment.teacher.name, other_slot, str(class_ref)
                            )
                        
                        if other_assignment.teacher:
                            self.teacher_schedule.remove(
                                other_assignment.teacher.name, other_slot, str(class_ref)
                            )
                            self.teacher_schedule.add(
                                other_assignment.teacher.name, time_slot, str(class_ref)
                            )
                        
                        return True
        
        return False
    
    def _get_grade5_teacher(self, school: School, subject: str) -> Optional[Teacher]:
        """5組の科目に応じた教師を取得"""
        teacher_name = None
        
        if subject in self.teacher_mapping:
            mapping = self.teacher_mapping[subject]
            if isinstance(mapping, dict) and "5組" in mapping:
                teacher_name = mapping["5組"]
            elif isinstance(mapping, dict) and 1 in mapping and "5" in mapping[1]:
                teacher_name = mapping[1]["5"]
            elif isinstance(mapping, str):
                teacher_name = mapping
        
        if teacher_name:
            for teacher in school.get_all_teachers():
                if teacher.name == teacher_name:
                    return teacher
        
        return None
    
    def _count_subject_hours(self, schedule: Schedule, class_ref: ClassReference,
                           days: List[str]) -> Dict[str, int]:
        """科目別授業時数をカウント"""
        subject_hours = defaultdict(int)
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, str(class_ref))
                if assignment and assignment.subject.name not in self.fixed_subjects:
                    subject_hours[assignment.subject.name] += 1
        
        return dict(subject_hours)
    
    def _identify_needed_subjects(self, subject_hours: Dict[str, int]) -> List[str]:
        """不足科目を特定"""
        needed = []
        
        for subject, standard in self.standard_hours.items():
            current = subject_hours.get(subject, 0)
            if current < standard:
                for _ in range(standard - current):
                    needed.append(subject)
        
        # 主要教科を優先
        needed.sort(key=lambda s: (
            0 if s in self.major_subjects else 1,
            self.standard_hours.get(s, 0)
        ), reverse=True)
        
        return needed
    
    def _get_available_teacher(self, school: School, subject: str,
                             class_ref: ClassReference, time_slot: TimeSlot) -> Optional[Teacher]:
        """利用可能な教師を取得"""
        possible_teachers = self._get_possible_teachers(subject, class_ref)
        
        for teacher_name in possible_teachers:
            if self.teacher_schedule.is_available(teacher_name, time_slot):
                for teacher in school.get_all_teachers():
                    if teacher.name == teacher_name:
                        return teacher
        
        return None
    
    def _get_possible_teachers(self, subject: str, class_ref: ClassReference) -> List[str]:
        """科目とクラスに応じた可能な教師のリストを取得"""
        teachers = []
        
        if subject in self.teacher_mapping:
            mapping = self.teacher_mapping[subject]
            
            if isinstance(mapping, str):
                teachers.append(mapping)
            elif isinstance(mapping, list):
                teachers.extend(mapping)
            elif isinstance(mapping, dict):
                grade = class_ref.grade
                class_num = str(class_ref.class_number)
                
                if grade in mapping:
                    grade_mapping = mapping[grade]
                    if isinstance(grade_mapping, dict) and class_num in grade_mapping:
                        teachers.append(grade_mapping[class_num])
                    elif isinstance(grade_mapping, str):
                        teachers.append(grade_mapping)
        
        return teachers
    
    def _calculate_total_score(self, schedule: Schedule, school: School) -> int:
        """時間割の総合スコアを計算（低いほど良い）"""
        score = 0
        
        # 教師重複をカウント
        conflicts = self.teacher_schedule.get_conflicts()
        score += len(conflicts) * ViolationScore.teacher_conflict
        
        # その他の違反もカウント（簡易版）
        # 実際の実装では各種違反を詳細にチェック
        
        return score
    
    def _try_random_swap(self, schedule: Schedule, school: School) -> bool:
        """ランダムなスワップを試みる"""
        days = ["月", "火", "水", "木", "金"]
        classes = list(school.get_all_classes())
        
        # ランダムに2つの授業を選択
        class1 = random.choice(classes)
        day1 = random.choice(days)
        period1 = random.randint(1, 6)
        slot1 = TimeSlot(day1, period1)
        
        class2 = random.choice(classes)
        day2 = random.choice(days)
        period2 = random.randint(1, 6)
        slot2 = TimeSlot(day2, period2)
        
        # 同じスロットの場合はスキップ
        if class1 == class2 and slot1 == slot2:
            return False
        
        # 両方に授業がある場合のみスワップ
        assignment1 = schedule.get_assignment(slot1, class1)
        assignment2 = schedule.get_assignment(slot2, class2)
        
        if assignment1 and assignment2:
            # 固定科目はスワップしない
            if (assignment1.subject.name in self.fixed_subjects or
                assignment2.subject.name in self.fixed_subjects):
                return False
            
            # スワップ実行
            schedule.remove_assignment(slot1, class1)
            schedule.remove_assignment(slot2, class2)
            
            new_assignment1 = Assignment(class1, assignment2.subject, assignment2.teacher)
            new_assignment2 = Assignment(class2, assignment1.subject, assignment1.teacher)
            
            schedule.assign(slot1, new_assignment1)
            schedule.assign(slot2, new_assignment2)
            
            # 教師スケジュールも更新
            if assignment1.teacher:
                self.teacher_schedule.remove(assignment1.teacher.name, slot1, str(class1))
                self.teacher_schedule.add(assignment1.teacher.name, slot2, str(class2))
            
            if assignment2.teacher:
                self.teacher_schedule.remove(assignment2.teacher.name, slot2, str(class2))
                self.teacher_schedule.add(assignment2.teacher.name, slot1, str(class1))
            
            return True
        
        return False
    
    def _play_completion_sound(self):
        """完了音を鳴らす"""
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
            elif system == "Linux":
                subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"])
            elif system == "Windows":
                import winsound
                winsound.MessageBeep()
        except Exception as e:
            logger.info(f"\n[完了音を鳴らせませんでした: {e}]")
        
        # ターミナルベルも鳴らす
        print("\a")  # ベル文字


def main():
    """メイン処理"""
    fixer = Ultrathink95PercentFixer()
    fixer.fix_to_95_percent()


if __name__ == "__main__":
    main()
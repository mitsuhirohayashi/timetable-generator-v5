#!/usr/bin/env python3
"""
月曜日の日内重複問題を包括的に修正するスクリプト

主な問題:
1. 5組（1-5, 2-5, 3-5）が月曜日に保健体育(保)を3回も持っている
2. 他のクラスでも日内重複が発生している可能性
3. 空きスロット埋め戦略が日内重複を十分にチェックしていない

解決策:
1. 日内重複の厳格なチェック（1日1回制限）
2. 5組の同期を維持しながら修正
3. より賢い空きスロット埋め戦略の実装
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import csv
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set
import logging

from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer import CSVScheduleWriter
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.repositories.config_repository import ConfigRepository

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class MondayDuplicateFixer:
    """月曜日の日内重複を修正するクラス"""
    
    def __init__(self):
        self.csv_reader = CSVScheduleReader()
        self.csv_writer = CSVScheduleWriter()
        self.csv_repo = CSVScheduleRepository()
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        self.exchange_pairs = {
            "1年6組": "1年1組",
            "1年7組": "1年2組", 
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        self.fixed_subjects = {"欠", "YT", "学", "学活", "総", "総合", "道", "道徳", "学総", "行", "行事", "テスト", "技家"}
        
    def analyze_daily_duplicates(self, schedule: Schedule, school: School) -> Dict[str, List[Tuple[str, str, int]]]:
        """日内重複を分析"""
        duplicates = defaultdict(list)
        
        for class_ref in school.get_all_classes():
            for day in ["月", "火", "水", "木", "金"]:
                subject_counts = defaultdict(int)
                
                # Count subjects for the day
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subject_counts[assignment.subject.name] += 1
                
                # Find duplicates
                for subject, count in subject_counts.items():
                    if count > 1:
                        duplicates[class_ref.full_name].append((day, subject, count))
        
        return duplicates
    
    def find_monday_pe_slots(self, schedule: Schedule, class_ref: ClassReference) -> List[int]:
        """Find all PE slots on Monday for a class"""
        pe_slots = []
        for period in range(1, 7):
            time_slot = TimeSlot("月", period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == "保":
                pe_slots.append(period)
        return pe_slots
    
    def find_alternative_subjects(self, schedule: Schedule, school: School, class_ref: ClassReference, day: str) -> List[str]:
        """Find subjects that can be placed without causing duplicates"""
        # Get subjects already placed on this day
        placed_subjects = set()
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                placed_subjects.add(assignment.subject.name)
        
        # Get all available subjects for this class
        available_subjects = []
        for subject in school.subjects.values():
            if (subject.name not in self.fixed_subjects and 
                subject.name not in placed_subjects and
                school.get_subject_teachers(subject)):
                available_subjects.append(subject.name)
        
        # Prioritize main subjects
        priority_subjects = ["数", "国", "英", "理", "社", "算"]
        prioritized = []
        
        # Add priority subjects first
        for subj in priority_subjects:
            if subj in available_subjects:
                prioritized.append(subj)
        
        # Add remaining subjects
        for subj in available_subjects:
            if subj not in prioritized:
                prioritized.append(subj)
        
        return prioritized
    
    def fix_grade5_monday_pe(self, schedule: Schedule, school: School) -> int:
        """Fix Grade 5 Monday PE duplicates while maintaining synchronization"""
        changes = 0
        
        # Find PE slots for Grade 5 on Monday
        grade5_pe_slots = {}
        for class_name in self.grade5_classes:
            class_ref = ClassReference.from_string(class_name)
            pe_slots = self.find_monday_pe_slots(schedule, class_ref)
            grade5_pe_slots[class_name] = pe_slots
        
        logger.info(f"Grade 5 Monday PE slots: {grade5_pe_slots}")
        
        # Keep only the first PE slot (period 2), replace others
        if all(len(slots) > 1 for slots in grade5_pe_slots.values()):
            # Get alternative subjects that won't cause duplicates
            alternative_subjects = self.find_alternative_subjects(
                schedule, school, ClassReference.from_string("1年5組"), "月"
            )
            
            if len(alternative_subjects) >= 2:
                # Replace PE in periods 3 and 5 with different subjects
                replacements = {
                    3: alternative_subjects[0],
                    5: alternative_subjects[1] if len(alternative_subjects) > 1 else alternative_subjects[0]
                }
                
                for period, new_subject in replacements.items():
                    if period != 5 or new_subject != replacements.get(3):  # Avoid same subject if possible
                        # Find a teacher for the new subject
                        subject_obj = school.subjects.get(new_subject)
                        if subject_obj:
                            teachers = list(school.get_subject_teachers(subject_obj))
                            if teachers:
                                # Select teacher that can teach all Grade 5 classes
                                selected_teacher = None
                                for teacher in teachers:
                                    can_teach_all = True
                                    for class_name in self.grade5_classes:
                                        class_ref = ClassReference.from_string(class_name)
                                        if not self._can_teacher_teach_at_time(schedule, teacher, TimeSlot("月", period), class_ref):
                                            can_teach_all = False
                                            break
                                    if can_teach_all:
                                        selected_teacher = teacher
                                        break
                                
                                if selected_teacher:
                                    # Replace PE with new subject for all Grade 5 classes
                                    for class_name in self.grade5_classes:
                                        class_ref = ClassReference.from_string(class_name)
                                        time_slot = TimeSlot("月", period)
                                        new_assignment = Assignment(class_ref, subject_obj, selected_teacher)
                                        
                                        if schedule.assign(time_slot, new_assignment):
                                            changes += 1
                                            logger.info(f"Replaced PE with {new_subject} for {class_name} at Monday period {period}")
        
        return changes
    
    def _can_teacher_teach_at_time(self, schedule: Schedule, teacher, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """Check if teacher is available at the given time"""
        # Check if teacher is already assigned elsewhere
        for other_class in schedule.get_all_classes():
            if other_class != class_ref:
                assignment = schedule.get_assignment(time_slot, other_class)
                if assignment and assignment.teacher == teacher:
                    # Allow if it's a Grade 5 synchronization
                    if not (other_class.full_name in self.grade5_classes and 
                           class_ref.full_name in self.grade5_classes):
                        return False
        return True
    
    def fix_other_daily_duplicates(self, schedule: Schedule, school: School) -> int:
        """Fix daily duplicates for non-Grade 5 classes"""
        changes = 0
        duplicates = self.analyze_daily_duplicates(schedule, school)
        
        for class_name, dup_list in duplicates.items():
            # Skip Grade 5 classes (handled separately)
            if class_name in self.grade5_classes:
                continue
                
            class_ref = ClassReference.from_string(class_name)
            
            for day, subject, count in dup_list:
                if count > 1:
                    # Find all slots with this subject
                    subject_slots = []
                    for period in range(1, 7):
                        time_slot = TimeSlot(day, period)
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.subject.name == subject:
                            subject_slots.append((period, assignment))
                    
                    # Keep the first occurrence, replace others
                    for i in range(1, len(subject_slots)):
                        period, old_assignment = subject_slots[i]
                        time_slot = TimeSlot(day, period)
                        
                        # Find alternative subject
                        alternatives = self.find_alternative_subjects(schedule, school, class_ref, day)
                        
                        for alt_subject_name in alternatives:
                            alt_subject = school.subjects.get(alt_subject_name)
                            if alt_subject:
                                teachers = list(school.get_subject_teachers(alt_subject))
                                for teacher in teachers:
                                    if self._can_teacher_teach_at_time(schedule, teacher, time_slot, class_ref):
                                        new_assignment = Assignment(class_ref, alt_subject, teacher)
                                        if schedule.assign(time_slot, new_assignment):
                                            changes += 1
                                            logger.info(f"Replaced duplicate {subject} with {alt_subject_name} for {class_name} at {day} period {period}")
                                            
                                            # Handle exchange class sync if needed
                                            if class_name in self.exchange_pairs:
                                                parent_class = self.exchange_pairs[class_name]
                                                parent_ref = ClassReference.from_string(parent_class)
                                                parent_assignment = Assignment(parent_ref, alt_subject, teacher)
                                                schedule.assign(time_slot, parent_assignment)
                                                logger.info(f"Synced parent class {parent_class}")
                                            
                                            break
                                if changes > 0:
                                    break
        
        return changes
    
    def validate_no_daily_duplicates(self, schedule: Schedule, school: School) -> bool:
        """Validate that there are no daily duplicates"""
        duplicates = self.analyze_daily_duplicates(schedule, school)
        
        if not duplicates:
            return True
        
        # Report remaining duplicates
        for class_name, dup_list in duplicates.items():
            for day, subject, count in dup_list:
                logger.warning(f"{class_name}: {subject} appears {count} times on {day}")
        
        return False
    
    def fix_schedule(self, input_path: str, output_path: str):
        """Main method to fix the schedule"""
        logger.info("=== Starting Monday Daily Duplicate Fix ===")
        
        # Load school and schedule
        school = self._load_school()
        schedule = self.csv_reader.read_schedule(input_path, school)
        
        # Analyze current duplicates
        logger.info("\n=== Analyzing Current Daily Duplicates ===")
        duplicates = self.analyze_daily_duplicates(schedule, school)
        
        total_duplicates = sum(len(dup_list) for dup_list in duplicates.values())
        logger.info(f"Found {total_duplicates} daily duplicate issues")
        
        # Fix Grade 5 Monday PE duplicates first
        logger.info("\n=== Fixing Grade 5 Monday PE Duplicates ===")
        grade5_changes = self.fix_grade5_monday_pe(schedule, school)
        logger.info(f"Made {grade5_changes} changes to Grade 5 schedule")
        
        # Fix other daily duplicates
        logger.info("\n=== Fixing Other Daily Duplicates ===")
        other_changes = self.fix_other_daily_duplicates(schedule, school)
        logger.info(f"Made {other_changes} changes to other classes")
        
        # Validate results
        logger.info("\n=== Validating Results ===")
        if self.validate_no_daily_duplicates(schedule, school):
            logger.info("✓ All daily duplicates have been resolved!")
        else:
            logger.warning("⚠ Some daily duplicates remain")
        
        # Save the fixed schedule
        self.csv_writer.write_schedule(schedule, output_path)
        logger.info(f"\nFixed schedule saved to: {output_path}")
        
        return grade5_changes + other_changes
    
    def _load_school(self) -> School:
        """Load school data using ConfigRepository"""
        config_repo = ConfigRepository()
        return config_repo.load_school()


def main():
    """Main execution function"""
    fixer = MondayDuplicateFixer()
    
    input_file = project_root / "data" / "output" / "output.csv"
    output_file = project_root / "data" / "output" / "output_fixed_monday_duplicates.csv"
    
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        return
    
    changes = fixer.fix_schedule(str(input_file), str(output_file))
    logger.info(f"\nTotal changes made: {changes}")


if __name__ == "__main__":
    main()
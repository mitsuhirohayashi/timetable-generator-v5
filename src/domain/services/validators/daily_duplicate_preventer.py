"""Daily duplicate prevention service

This service provides pre-checks before placing subjects to prevent daily duplicates,
especially for Grade 5 synchronized classes.
"""

from typing import Dict, Set, Optional, List
from collections import defaultdict
import logging

from ...entities.schedule import Schedule
from ...entities.school import School, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ...constants import FIXED_SUBJECTS


class DailyDuplicatePreventer:
    """Service to prevent daily duplicates proactively"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.grade5_classes = {"1年5組", "2年5組", "3年5組"}
        
        # Cache for daily subject counts
        self._daily_counts_cache = {}
        self._cache_version = 0
    
    def clear_cache(self):
        """Clear the cache when schedule changes"""
        self._daily_counts_cache.clear()
        self._cache_version += 1
    
    def can_place_subject(
        self, 
        schedule: Schedule, 
        time_slot: TimeSlot,
        class_ref: ClassReference,
        subject: Subject,
        check_level: str = 'strict'
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a subject can be placed without causing daily duplicates
        
        Args:
            schedule: Current schedule
            time_slot: Time slot to check
            class_ref: Class reference
            subject: Subject to place
            check_level: 'strict' (1 per day), 'normal' (flexible), 'relaxed' (very flexible)
            
        Returns:
            (can_place, reason)
        """
        # Fixed subjects are always allowed
        if subject.name in FIXED_SUBJECTS:
            return True, None
        
        # Get current count for this subject on this day
        current_count = self.get_subject_count_for_day(
            schedule, class_ref, time_slot.day, subject
        )
        
        # Determine max allowed based on check level
        max_allowed = self._get_max_allowed(subject, check_level)
        
        if current_count >= max_allowed:
            return False, f"{subject.name}は{time_slot.day}曜日に既に{current_count}回配置されています（最大{max_allowed}回）"
        
        # Additional check for Grade 5 synchronization
        if class_ref.full_name in self.grade5_classes:
            # Check all Grade 5 classes
            for grade5_class in self.grade5_classes:
                if grade5_class != class_ref.full_name:
                    other_ref = ClassReference.from_string(grade5_class)
                    other_count = self.get_subject_count_for_day(
                        schedule, other_ref, time_slot.day, subject
                    )
                    if other_count >= max_allowed:
                        return False, f"5組同期制約: {grade5_class}が{time_slot.day}曜日に{subject.name}を{other_count}回持っています"
        
        return True, None
    
    def get_subject_count_for_day(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        day: str,
        subject: Subject
    ) -> int:
        """Get the number of times a subject appears on a specific day"""
        cache_key = (class_ref.full_name, day, subject.name, self._cache_version)
        
        if cache_key in self._daily_counts_cache:
            return self._daily_counts_cache[cache_key]
        
        count = 0
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == subject.name:
                count += 1
        
        self._daily_counts_cache[cache_key] = count
        return count
    
    def get_daily_subject_summary(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        day: str
    ) -> Dict[str, int]:
        """Get a summary of all subjects and their counts for a day"""
        subject_counts = defaultdict(int)
        
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name not in FIXED_SUBJECTS:
                subject_counts[assignment.subject.name] += 1
        
        return dict(subject_counts)
    
    def find_safe_subjects_for_slot(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        check_level: str = 'strict'
    ) -> List[Subject]:
        """Find subjects that can be safely placed without causing duplicates"""
        safe_subjects = []
        
        for subject in school.subjects.values():
            if subject.name in FIXED_SUBJECTS:
                continue
                
            can_place, _ = self.can_place_subject(
                schedule, time_slot, class_ref, subject, check_level
            )
            
            if can_place:
                safe_subjects.append(subject)
        
        # Sort by standard hours (prioritize subjects with more hours)
        base_hours = school.get_all_standard_hours(class_ref)
        safe_subjects.sort(
            key=lambda s: base_hours.get(s, 0),
            reverse=True
        )
        
        return safe_subjects
    
    def _get_max_allowed(self, subject: Subject, check_level: str) -> int:
        """Get maximum allowed occurrences per day based on check level"""
        if check_level == 'strict':
            return 1  # Strict: 1 per day for all subjects
        elif check_level == 'normal':
            # Normal: Allow 2 for main subjects
            if subject.name in {"数", "国", "英", "理", "社", "算"}:
                return 2
            return 1
        else:  # relaxed
            # Relaxed: Allow up to 3 for main subjects
            if subject.name in {"数", "国", "英", "理", "社", "算"}:
                return 3
            return 2
    
    def get_daily_duplicate_report(
        self,
        schedule: Schedule,
        school: School
    ) -> str:
        """Generate a report of all daily duplicates"""
        report_lines = ["=== Daily Duplicate Report ==="]
        total_duplicates = 0
        
        for class_ref in school.get_all_classes():
            class_duplicates = []
            
            for day in ["月", "火", "水", "木", "金"]:
                subject_summary = self.get_daily_subject_summary(schedule, class_ref, day)
                
                for subject_name, count in subject_summary.items():
                    if count > 1:
                        class_duplicates.append(f"  {day}曜日: {subject_name} x{count}")
                        total_duplicates += 1
            
            if class_duplicates:
                report_lines.append(f"\n{class_ref.full_name}:")
                report_lines.extend(class_duplicates)
        
        report_lines.append(f"\nTotal duplicates: {total_duplicates}")
        return "\n".join(report_lines)
    
    def suggest_replacement_for_duplicate(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        duplicate_subject: Subject
    ) -> Optional[Subject]:
        """Suggest a replacement subject for a duplicate"""
        # Find safe subjects that won't cause duplicates
        safe_subjects = self.find_safe_subjects_for_slot(
            schedule, school, time_slot, class_ref, 'strict'
        )
        
        # Filter out the duplicate subject
        safe_subjects = [s for s in safe_subjects if s.name != duplicate_subject.name]
        
        if safe_subjects:
            return safe_subjects[0]  # Return the highest priority safe subject
        
        return None
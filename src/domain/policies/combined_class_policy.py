"""Combined Class Policy for team-taught integrated subjects

This policy handles subjects like 学総 (integrated learning) where multiple
teachers collaborate to teach combined classes, particularly in Grade 2.
"""
import logging
from typing import Optional, Set, Dict
from pathlib import Path
import csv

from .team_teaching_policy import TeamTeachingPolicy, TeamTeachingArrangement
from ..value_objects.time_slot import Teacher, ClassReference, Subject


class CombinedClassPolicy(TeamTeachingPolicy):
    """Policy for combined/integrated classes that are team-taught
    
    Handles subjects like:
    - 学総 (総合学習): Integrated learning typically in Grade 2
    - Other team-taught general subjects
    """
    
    def __init__(self):
        """Initialize combined class policy"""
        self.logger = logging.getLogger(__name__)
        
        # Subjects that are designed for team teaching
        self.combined_subjects = {"学総", "総合", "総"}
        
        # Grade-specific combined class configurations
        # Grade 2 often has 学総 as a combined class
        self.grade_combined_subjects = {
            2: {"学総"}  # Grade 2 has integrated learning
        }
        
        # Teachers who can participate in combined classes
        self.combined_class_teachers = self._load_combined_class_teachers()
        
        self.logger.info(f"Combined class policy initialized with subjects: {self.combined_subjects}")
    
    def _load_combined_class_teachers(self) -> Dict[str, Set[str]]:
        """Load teachers assigned to combined classes from configuration
        
        Returns:
            Dict mapping subject names to sets of teacher names
        """
        combined_teachers = {}
        
        try:
            # Load from teacher_subject_mapping.csv
            config_path = Path(__file__).parent.parent.parent.parent / "data" / "config" / "teacher_subject_mapping.csv"
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        subject = row.get('教科', '').strip()
                        teacher = row.get('教師名', '').strip()
                        
                        if subject in self.combined_subjects and teacher:
                            if subject not in combined_teachers:
                                combined_teachers[subject] = set()
                            combined_teachers[subject].add(teacher)
                
                self.logger.info(f"Loaded combined class teachers: {combined_teachers}")
            
            # Add default configuration for 学総 if not loaded
            if "学総" not in combined_teachers:
                # Based on the mapping data, these teachers handle Grade 2 学総
                combined_teachers["学総"] = {
                    "塚本", "野口", "永山",  # Grade 2 regular classes
                    "金子み"  # Grade 2-5 special support
                }
                self.logger.info("Using default Grade 2 学総 teacher configuration")
                
        except Exception as e:
            self.logger.error(f"Error loading combined class teachers: {e}")
            # Use defaults
            combined_teachers["学総"] = {"塚本", "野口", "永山", "金子み"}
        
        return combined_teachers
    
    def is_team_teaching_allowed(self, 
                                teacher: Teacher,
                                class1: ClassReference,
                                class2: ClassReference,
                                subject: Optional[Subject] = None) -> bool:
        """Check if team-teaching is allowed for combined classes
        
        For combined subjects like 学総:
        - Multiple teachers can be in different classes of the same grade simultaneously
        - This represents coordinated/parallel teaching rather than one teacher in multiple places
        """
        # Must have a subject to check
        if not subject:
            return False
        
        # Check if it's a combined subject
        if subject.name not in self.combined_subjects:
            return False
        
        # Check if both classes are in the same grade
        if class1.grade != class2.grade:
            return False
        
        # Check if this grade has combined classes for this subject
        grade = class1.grade
        if grade in self.grade_combined_subjects:
            if subject.name in self.grade_combined_subjects[grade]:
                # Check if the teacher is authorized for this combined subject
                if subject.name in self.combined_class_teachers:
                    if teacher.name in self.combined_class_teachers[subject.name]:
                        self.logger.debug(
                            f"Allowing team teaching for {teacher.name} "
                            f"in Grade {grade} {subject.name} classes"
                        )
                        return True
        
        return False
    
    def get_team_teaching_arrangements(self) -> list[TeamTeachingArrangement]:
        """Get all combined class team-teaching arrangements"""
        arrangements = []
        
        # Create arrangements for each combined subject
        for subject_name, teachers in self.combined_class_teachers.items():
            # For each grade that has this combined subject
            for grade, grade_subjects in self.grade_combined_subjects.items():
                if subject_name in grade_subjects:
                    # Create arrangement for this grade's combined classes
                    # Note: In actual practice, teachers teach their own classes
                    # but coordinate the curriculum
                    for teacher_name in teachers:
                        teacher = Teacher(teacher_name)
                        subject = Subject(subject_name)
                        
                        # This is more about coordination than actual simultaneous teaching
                        arrangement = TeamTeachingArrangement(
                            teacher=teacher,
                            classes=set(),  # Empty as they teach their assigned classes
                            subjects={subject},
                            description=f"Grade {grade} {subject_name} coordinated teaching"
                        )
                        arrangements.append(arrangement)
        
        return arrangements
    
    def get_description(self) -> str:
        """Get policy description"""
        desc = "Combined Class Policy:\n"
        desc += f"- Combined subjects: {', '.join(sorted(self.combined_subjects))}\n"
        desc += "- Grade configurations:\n"
        
        for grade, subjects in self.grade_combined_subjects.items():
            desc += f"  - Grade {grade}: {', '.join(sorted(subjects))}\n"
        
        desc += "- Combined class teachers:\n"
        for subject, teachers in self.combined_class_teachers.items():
            desc += f"  - {subject}: {', '.join(sorted(teachers))}\n"
        
        desc += "\nNote: Combined classes involve coordinated teaching where multiple "
        desc += "teachers handle different sections of the same grade simultaneously.\n"
        
        return desc
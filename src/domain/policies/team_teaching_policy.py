"""Team Teaching Policy abstraction

This module provides a clean abstraction for handling special teaching arrangements
where teachers can teach multiple classes simultaneously.
"""
from abc import ABC, abstractmethod
from typing import Set, List, Tuple, Optional
from dataclasses import dataclass

from ..value_objects.time_slot import Teacher, ClassReference, Subject


@dataclass
class TeamTeachingArrangement:
    """Represents a team-teaching arrangement"""
    teacher: Teacher
    classes: Set[ClassReference]
    subjects: Optional[Set[Subject]] = None  # None means all subjects
    description: str = ""


class TeamTeachingPolicy(ABC):
    """Abstract base class for team-teaching policies"""
    
    @abstractmethod
    def is_team_teaching_allowed(self, 
                                teacher: Teacher,
                                class1: ClassReference,
                                class2: ClassReference,
                                subject: Optional[Subject] = None) -> bool:
        """Check if team-teaching is allowed for the given scenario
        
        Args:
            teacher: The teacher in question
            class1: First class
            class2: Second class
            subject: Subject being taught (optional)
            
        Returns:
            True if team-teaching is allowed, False otherwise
        """
        pass
    
    @abstractmethod
    def get_team_teaching_arrangements(self) -> List[TeamTeachingArrangement]:
        """Get all team-teaching arrangements defined by this policy"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get a human-readable description of this policy"""
        pass


class CompositeTeamTeachingPolicy(TeamTeachingPolicy):
    """Composite policy that combines multiple team-teaching policies"""
    
    def __init__(self, policies: List[TeamTeachingPolicy]):
        self.policies = policies
    
    def is_team_teaching_allowed(self, 
                                teacher: Teacher,
                                class1: ClassReference,
                                class2: ClassReference,
                                subject: Optional[Subject] = None) -> bool:
        """Check if any policy allows team-teaching"""
        return any(policy.is_team_teaching_allowed(teacher, class1, class2, subject) 
                  for policy in self.policies)
    
    def get_team_teaching_arrangements(self) -> List[TeamTeachingArrangement]:
        """Get all arrangements from all policies"""
        arrangements = []
        for policy in self.policies:
            arrangements.extend(policy.get_team_teaching_arrangements())
        return arrangements
    
    def get_description(self) -> str:
        """Get combined description"""
        descriptions = [policy.get_description() for policy in self.policies]
        return "\n".join(descriptions)


class Grade5TeamTeachingPolicy(TeamTeachingPolicy):
    """Team-teaching policy for Grade 5 classes
    
    In Grade 5, teachers can teach multiple Grade 5 classes (1-5, 2-5, 3-5)
    simultaneously as they use a team-teaching approach.
    """
    
    def __init__(self, team_teaching_teachers: Set[str], 
                 flexible_subject_teachers: Optional[dict] = None):
        """Initialize Grade 5 team-teaching policy
        
        Args:
            team_teaching_teachers: Set of teacher names who do team-teaching
            flexible_subject_teachers: Dict mapping subjects to sets of flexible teachers
                                     e.g., {"国": {"寺田", "金子み"}}
        """
        self.team_teaching_teachers = team_teaching_teachers
        self.flexible_subject_teachers = flexible_subject_teachers or {}
        self.grade5_class_numbers = {5}  # Grade 5 classes have class_number 5
    
    def is_team_teaching_allowed(self, 
                                teacher: Teacher,
                                class1: ClassReference,
                                class2: ClassReference,
                                subject: Optional[Subject] = None) -> bool:
        """Check if team-teaching is allowed between two classes"""
        # Both classes must be Grade 5
        if (class1.class_number not in self.grade5_class_numbers or 
            class2.class_number not in self.grade5_class_numbers):
            return False
        
        # Teacher must be a team-teaching teacher
        if teacher.name not in self.team_teaching_teachers:
            return False
        
        # If subject is specified, check flexible subject rules
        if subject and subject.name in self.flexible_subject_teachers:
            flexible_teachers = self.flexible_subject_teachers[subject.name]
            return teacher.name in flexible_teachers
        
        return True
    
    def get_team_teaching_arrangements(self) -> List[TeamTeachingArrangement]:
        """Get all Grade 5 team-teaching arrangements"""
        arrangements = []
        
        # Create arrangements for each team-teaching teacher
        for teacher_name in self.team_teaching_teachers:
            teacher = Teacher(teacher_name)
            # Grade 5 classes: 1-5, 2-5, 3-5
            grade5_classes = {
                ClassReference(1, 5),
                ClassReference(2, 5), 
                ClassReference(3, 5)
            }
            
            # Check if this teacher has subject-specific rules
            teacher_subjects = None
            for subject, teachers in self.flexible_subject_teachers.items():
                if teacher_name in teachers:
                    if teacher_subjects is None:
                        teacher_subjects = set()
                    teacher_subjects.add(Subject(subject))
            
            arrangement = TeamTeachingArrangement(
                teacher=teacher,
                classes=grade5_classes,
                subjects=teacher_subjects,
                description=f"Grade 5 team-teaching for {teacher_name}"
            )
            arrangements.append(arrangement)
        
        return arrangements
    
    def get_description(self) -> str:
        """Get policy description"""
        desc = "Grade 5 Team-Teaching Policy:\n"
        desc += f"- Team-teaching teachers: {', '.join(sorted(self.team_teaching_teachers))}\n"
        
        if self.flexible_subject_teachers:
            desc += "- Flexible subject assignments:\n"
            for subject, teachers in self.flexible_subject_teachers.items():
                desc += f"  - {subject}: {', '.join(sorted(teachers))}\n"
        
        return desc


class SimultaneousClassPolicy(TeamTeachingPolicy):
    """Policy for classes that occur simultaneously across all classes
    
    Examples: YT (朝読書), 道徳 (moral education)
    """
    
    def __init__(self, simultaneous_teachers: Set[str]):
        """Initialize with teachers who conduct simultaneous classes
        
        Args:
            simultaneous_teachers: Set of teacher names (e.g., {"YT担当", "道担当"})
        """
        self.simultaneous_teachers = simultaneous_teachers
    
    def is_team_teaching_allowed(self, 
                                teacher: Teacher,
                                class1: ClassReference,
                                class2: ClassReference,
                                subject: Optional[Subject] = None) -> bool:
        """Simultaneous class teachers can teach any classes at the same time"""
        return teacher.name in self.simultaneous_teachers
    
    def get_team_teaching_arrangements(self) -> List[TeamTeachingArrangement]:
        """Get arrangements for simultaneous classes"""
        arrangements = []
        
        for teacher_name in self.simultaneous_teachers:
            teacher = Teacher(teacher_name)
            # These teachers can teach all classes simultaneously
            # We don't specify exact classes as it applies to all
            arrangement = TeamTeachingArrangement(
                teacher=teacher,
                classes=set(),  # Empty set means all classes
                subjects=None,  # All subjects they teach
                description=f"Simultaneous class arrangement for {teacher_name}"
            )
            arrangements.append(arrangement)
        
        return arrangements
    
    def get_description(self) -> str:
        """Get policy description"""
        return f"Simultaneous Class Policy for: {', '.join(sorted(self.simultaneous_teachers))}"
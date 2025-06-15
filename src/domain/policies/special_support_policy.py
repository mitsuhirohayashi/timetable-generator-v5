"""Special Support Classes Team Teaching Policy

Handles team-teaching arrangements for special support classes (5組, 6組, 7組).
"""
from typing import Optional, Set
from .team_teaching_policy import TeamTeachingPolicy, TeamTeachingArrangement
from ..value_objects.time_slot import Teacher, ClassReference, Subject


class SpecialSupportTeamTeachingPolicy(TeamTeachingPolicy):
    """Team-teaching policy for special support classes (5組, 6組, 7組)
    
    Special rules:
    - Each homeroom teacher can teach jiritsu (自立) for 1-3 classes of their group
    - Class 5: 金子み teacher (1-5, 2-5, 3-5)
    - Class 6: 財津 teacher (1-6, 2-6, 3-6) 
    - Class 7: 智田 teacher (1-7, 2-7, 3-7)
    - PE for class 5 is always done together (1-5, 2-5, 3-5)
    """
    
    def __init__(self):
        """Initialize special support team-teaching policy"""
        # Homeroom teachers for each special support class
        self.homeroom_teachers = {
            5: "金子み",
            6: "財津",
            7: "智田"
        }
        
        # Classes that each homeroom teacher can handle
        self.teacher_classes = {
            "金子み": {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)},
            "財津": {ClassReference(1, 6), ClassReference(2, 6), ClassReference(3, 6)},
            "智田": {ClassReference(1, 7), ClassReference(2, 7), ClassReference(3, 7)}
        }
        
        # Subjects that allow team-teaching
        self.team_teaching_subjects = {"自立", "日生", "作業"}  # jiritsu, daily life, work
        
        # PE is always together for class 5
        self.pe_together_classes = {5}
    
    def is_team_teaching_allowed(self, 
                                teacher: Teacher,
                                class1: ClassReference,
                                class2: ClassReference,
                                subject: Optional[Subject] = None) -> bool:
        """Check if team-teaching is allowed between two classes"""
        # Check if teacher is a homeroom teacher for special support
        if teacher.name not in self.teacher_classes:
            return False
        
        # Get allowed classes for this teacher
        allowed_classes = self.teacher_classes[teacher.name]
        
        # Both classes must be in the teacher's allowed set
        if class1 not in allowed_classes or class2 not in allowed_classes:
            return False
        
        # If subject is specified, check if it's allowed
        if subject:
            # For jiritsu activities
            if subject.name in self.team_teaching_subjects:
                return True
            
            # For PE in class 5
            if (subject.name == "保" and 
                class1.class_number == 5 and class2.class_number == 5):
                return True
            
            # For regular subjects in class 5 (existing team-teaching)
            if class1.class_number == 5 and class2.class_number == 5:
                return True
            
            return False
        
        return True
    
    def get_team_teaching_arrangements(self) -> list[TeamTeachingArrangement]:
        """Get all special support team-teaching arrangements"""
        arrangements = []
        
        # Create arrangements for each homeroom teacher
        for class_num, teacher_name in self.homeroom_teachers.items():
            teacher = Teacher(teacher_name)
            classes = self.teacher_classes[teacher_name]
            
            # Jiritsu activities arrangement
            jiritsu_arrangement = TeamTeachingArrangement(
                teacher=teacher,
                classes=classes,
                subjects={Subject(s) for s in self.team_teaching_subjects},
                description=f"Special support class {class_num} jiritsu activities"
            )
            arrangements.append(jiritsu_arrangement)
            
            # PE arrangement for class 5
            if class_num == 5:
                pe_arrangement = TeamTeachingArrangement(
                    teacher=teacher,
                    classes=classes,
                    subjects={Subject("保")},
                    description="Grade 5 joint PE classes"
                )
                arrangements.append(pe_arrangement)
        
        return arrangements
    
    def get_description(self) -> str:
        """Get policy description"""
        desc = "Special Support Classes Team-Teaching Policy:\n"
        desc += "- Homeroom teachers:\n"
        for class_num, teacher in self.homeroom_teachers.items():
            desc += f"  - Class {class_num}: {teacher}\n"
        desc += "- Each teacher can handle 1-3 classes of their group for jiritsu activities\n"
        desc += "- Class 5 has joint PE sessions\n"
        desc += "- Preferably distribute classes rather than always grouping them\n"
        
        return desc
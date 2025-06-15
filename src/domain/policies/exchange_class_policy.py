"""Exchange Class Policy

Handles the special rules for exchange classes (交流学級).
When exchange class students join their parent class, only one teacher is needed.
"""
from typing import Optional
from .team_teaching_policy import TeamTeachingPolicy, TeamTeachingArrangement
from ..value_objects.time_slot import Teacher, ClassReference, Subject


class ExchangeClassPolicy(TeamTeachingPolicy):
    """Policy for exchange classes (交流学級)
    
    When exchange class students join their parent class for non-jiritsu activities,
    the parent class teacher handles both groups. This is not a teacher conflict.
    
    Example:
    - 3年3組 has 社会 (taught by 北先生)
    - 3年6組 student joins 3年3組 for 社会
    - Only 北先生 is needed (not a conflict)
    """
    
    def __init__(self):
        """Initialize exchange class policy"""
        # Exchange class mappings (grade, exchange_class) -> (grade, parent_class)
        self.exchange_mappings = {
            (1, 6): (1, 1),  # 1年6組 -> 1年1組
            (1, 7): (1, 2),  # 1年7組 -> 1年2組
            (2, 6): (2, 3),  # 2年6組 -> 2年3組
            (2, 7): (2, 2),  # 2年7組 -> 2年2組
            (3, 6): (3, 3),  # 3年6組 -> 3年3組
            (3, 7): (3, 2),  # 3年7組 -> 3年2組
        }
    
    def is_team_teaching_allowed(self, 
                                teacher: Teacher,
                                class1: ClassReference,
                                class2: ClassReference,
                                subject: Optional[Subject] = None) -> bool:
        """Check if this is an exchange class situation"""
        # Check if one is parent and one is exchange class
        class1_key = (class1.grade, class1.class_number)
        class2_key = (class2.grade, class2.class_number)
        
        # Check if class1 is exchange and class2 is its parent
        if class1_key in self.exchange_mappings:
            parent_key = self.exchange_mappings[class1_key]
            if class2_key == parent_key:
                # Exchange students joining parent class
                # OK if not jiritsu activity
                if subject and subject.name != "自立":
                    return True
        
        # Check if class2 is exchange and class1 is its parent
        if class2_key in self.exchange_mappings:
            parent_key = self.exchange_mappings[class2_key]
            if class1_key == parent_key:
                # Exchange students joining parent class
                # OK if not jiritsu activity
                if subject and subject.name != "自立":
                    return True
        
        return False
    
    def get_team_teaching_arrangements(self) -> list[TeamTeachingArrangement]:
        """Get all exchange class arrangements"""
        arrangements = []
        
        # Create arrangements for each exchange-parent pair
        for (ex_grade, ex_class), (par_grade, par_class) in self.exchange_mappings.items():
            exchange_class = ClassReference(ex_grade, ex_class)
            parent_class = ClassReference(par_grade, par_class)
            
            # For non-jiritsu subjects, exchange students join parent class
            arrangement = TeamTeachingArrangement(
                teacher=Teacher("各教科担当"),  # Placeholder - actual teacher depends on subject
                classes={exchange_class, parent_class},
                subjects=None,  # All subjects except jiritsu
                description=f"Exchange class {exchange_class} joins parent {parent_class}"
            )
            arrangements.append(arrangement)
        
        return arrangements
    
    def get_description(self) -> str:
        """Get policy description"""
        desc = "Exchange Class Policy:\n"
        desc += "When exchange class students join parent class:\n"
        for (ex_grade, ex_class), (par_grade, par_class) in self.exchange_mappings.items():
            desc += f"  - {ex_grade}年{ex_class}組 → {par_grade}年{par_class}組\n"
        desc += "Only the parent class teacher is needed (not a conflict)\n"
        
        return desc
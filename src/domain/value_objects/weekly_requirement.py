"""週次要望を表現する値オブジェクト"""
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from .time_slot import TimeSlot, ClassReference, Subject, Teacher


class RequirementType(Enum):
    """要望タイプ"""
    TEACHER_UNAVAILABLE = "教員不在"    # 教員が利用不可
    TEACHER_UNAVAILABLE_ALT = "教員利用不可"  # 教員が利用不可（別表記）
    SUBJECT_FIXED = "教科固定"          # 特定時間に特定教科を固定
    TIME_FIXED = "時間固定"             # 特定時間を変更不可
    TIME_ADJUSTABLE = "時間調整可"       # 特定時間の調整可能
    SUBJECT_AVOID = "教科回避"          # 特定教科を特定時間に配置しない
    SUBJECT_PRIORITY = "教科優先"        # 特定教科を優先的に配置
    HOURS_ADJUSTMENT = "時間増減"        # 標準時数の増減
    EXCHANGE_ADJUSTMENT = "交流調整"     # 交流学級の特別調整
    SPECIAL_NOTE = "特記事項"           # その他の特記事項


class Priority(Enum):
    """優先度"""
    HIGH = "高"
    MEDIUM = "中" 
    LOW = "低"


@dataclass
class WeeklyRequirement:
    """週次要望"""
    requirement_type: RequirementType
    target: str              # 対象（クラス名、教員名、学年など）
    condition: str           # 条件（時間、曜日など）
    content: str             # 内容（教科名、利用不可など）
    priority: Priority       # 優先度
    note: str = ""          # 備考
    
    def applies_to_class(self, class_ref: ClassReference) -> bool:
        """指定クラスに適用されるかどうか判定"""
        if "全クラス" in self.target:
            return True
        elif "全組" in self.target:
            # "1年全組", "3年全組" など
            if self.target.startswith("全"):
                return True
            target_grade = self.target.replace("年全組", "")
            if target_grade.isdigit():
                return class_ref.grade == int(target_grade)
        elif "全学年" in self.target or "全体" in self.target:
            return True
        else:
            # 具体的なクラス名
            return class_ref.full_name == self.target
        
        return False
    
    def applies_to_teacher(self, teacher: Teacher) -> bool:
        """指定教員に適用されるかどうか判定"""
        return self.target == teacher.name
    
    def applies_to_time(self, time_slot: TimeSlot) -> bool:
        """指定時間に適用されるかどうか判定"""
        condition = self.condition.lower()
        
        # 曜日指定
        if time_slot.day in condition:
            if "午後" in condition:
                return time_slot.period >= 4
            elif "午前" in condition:
                return time_slot.period <= 3
            elif "校時" in condition:
                # "火曜3校時", "金曜5-6校時" など
                return self._parse_period_condition(condition, time_slot)
            else:
                return True
        
        # 全日指定
        if "全日" in condition or "今週" in condition:
            return True
            
        return False
    
    def _parse_period_condition(self, condition: str, time_slot: TimeSlot) -> bool:
        """校時条件の解析"""
        try:
            if "-" in condition:
                # "5-6校時" の形式
                periods_part = condition.split("校時")[0]
                if time_slot.day in periods_part:
                    periods_part = periods_part.split(time_slot.day)[1]
                start_end = periods_part.split("-")
                if len(start_end) == 2:
                    start = int(start_end[0])
                    end = int(start_end[1])
                    return start <= time_slot.period <= end
            else:
                # "3校時" の形式
                period_str = condition.split("校時")[0]
                if time_slot.day in period_str:
                    period_str = period_str.split(time_slot.day)[1]
                if period_str.isdigit():
                    return time_slot.period == int(period_str)
        except (ValueError, IndexError):
            pass
        
        return False
    
    def get_hours_adjustment(self, subject: Subject) -> int:
        """時間増減要望の場合の調整時間数を取得"""
        if self.requirement_type != RequirementType.HOURS_ADJUSTMENT:
            return 0
            
        content = self.content
        subject_name = subject.name
        
        if subject_name in content:
            try:
                # "音楽+1", "英語+2", "数学-1" などの形式
                if "+" in content:
                    adjustment_str = content.split("+")[1]
                    return int(adjustment_str)
                elif "-" in content:
                    adjustment_str = content.split("-")[1] 
                    return -int(adjustment_str)
            except (ValueError, IndexError):
                pass
                
        return 0
    
    def __str__(self) -> str:
        return f"{self.requirement_type.value}:{self.target}({self.condition})={self.content}[{self.priority.value}]"
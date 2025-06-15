"""時間割ドメインモデル - 集約ルート"""
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import copy


@dataclass(frozen=True)
class TimeSlot:
    """時間スロット（不変オブジェクト）"""
    day: str  # 月, 火, 水, 木, 金
    period: int  # 1-6
    
    def __post_init__(self):
        if self.day not in ["月", "火", "水", "木", "金"]:
            raise ValueError(f"Invalid day: {self.day}")
        if not 1 <= self.period <= 6:
            raise ValueError(f"Invalid period: {self.period}")
    
    def __str__(self):
        return f"{self.day}{self.period}限"
    
    @property
    def is_monday_6th(self) -> bool:
        """月曜6限かチェック"""
        return self.day == "月" and self.period == 6
    
    @property
    def is_fixed_yt(self) -> bool:
        """YT固定時間かチェック"""
        return (self.day in ["火", "水", "金"] and self.period == 6)


@dataclass(frozen=True)
class ClassReference:
    """クラス参照（不変オブジェクト）"""
    grade: int  # 1-3
    number: int  # 1-7
    
    def __post_init__(self):
        if not 1 <= self.grade <= 3:
            raise ValueError(f"Invalid grade: {self.grade}")
        if not 1 <= self.number <= 7:
            raise ValueError(f"Invalid class number: {self.number}")
    
    def __str__(self):
        return f"{self.grade}年{self.number}組"
    
    @property
    def is_grade5(self) -> bool:
        """5組（特別支援学級）かチェック"""
        return self.number == 5
    
    @property
    def is_exchange_class(self) -> bool:
        """交流学級（6,7組）かチェック"""
        return self.number in [6, 7]


@dataclass(frozen=True)
class Subject:
    """教科（不変オブジェクト）"""
    name: str
    
    def __post_init__(self):
        # 有効な教科名のバリデーション
        valid_subjects = {
            "国", "社", "数", "理", "音", "美", "保", "技", "家", "英",
            "道", "道徳", "学", "学活", "学総", "総", "総合", "YT", "欠",
            "自立", "日生", "生単", "作業", "行"
        }
        if self.name and self.name not in valid_subjects:
            raise ValueError(f"Invalid subject: {self.name}")
    
    def __str__(self):
        return self.name
    
    @property
    def is_protected(self) -> bool:
        """保護された教科（移動不可）かチェック"""
        return self.name in ["欠", "YT", "道", "道徳", "行"]
    
    @property
    def is_special_needs(self) -> bool:
        """特別支援教育の教科かチェック"""
        return self.name in ["自立", "日生", "生単", "作業"]


@dataclass(frozen=True)
class Teacher:
    """教員（不変オブジェクト）"""
    name: str
    id: Optional[str] = None
    
    def __str__(self):
        return self.name


@dataclass
class Cell:
    """時間割のセル"""
    time_slot: TimeSlot
    class_ref: ClassReference
    subject: Optional[Subject] = None
    teacher: Optional[Teacher] = None
    is_locked: bool = False
    metadata: Dict[str, any] = field(default_factory=dict)
    
    @property
    def is_empty(self) -> bool:
        """空きコマかチェック"""
        return self.subject is None
    
    @property
    def is_assigned(self) -> bool:
        """割り当て済みかチェック"""
        return self.subject is not None


class Timetable:
    """時間割（集約ルート）"""
    
    def __init__(self):
        self._cells: Dict[Tuple[TimeSlot, ClassReference], Cell] = {}
        self._version: int = 0
        self._created_at: datetime = datetime.now()
        self._modified_at: datetime = datetime.now()
        self._history: List[Dict] = []
    
    def assign(self, time_slot: TimeSlot, class_ref: ClassReference, 
               subject: Subject, teacher: Optional[Teacher] = None,
               lock: bool = False) -> bool:
        """授業を割り当て"""
        cell_key = (time_slot, class_ref)
        
        # 既存のセルをチェック
        if cell_key in self._cells:
            cell = self._cells[cell_key]
            if cell.is_locked:
                return False
        
        # 新しいセルを作成または更新
        cell = Cell(
            time_slot=time_slot,
            class_ref=class_ref,
            subject=subject,
            teacher=teacher,
            is_locked=lock
        )
        
        # 履歴を記録
        self._record_change('assign', cell_key, self._cells.get(cell_key), cell)
        
        # セルを更新
        self._cells[cell_key] = cell
        self._version += 1
        self._modified_at = datetime.now()
        
        return True
    
    def remove(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """割り当てを削除"""
        cell_key = (time_slot, class_ref)
        
        if cell_key not in self._cells:
            return False
        
        cell = self._cells[cell_key]
        if cell.is_locked:
            return False
        
        # 履歴を記録
        self._record_change('remove', cell_key, cell, None)
        
        # セルを削除
        del self._cells[cell_key]
        self._version += 1
        self._modified_at = datetime.now()
        
        return True
    
    def get_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional[Cell]:
        """セルを取得"""
        return self._cells.get((time_slot, class_ref))
    
    def get_assignment(self, time_slot: TimeSlot, class_ref: ClassReference) -> Optional['Assignment']:
        """割り当てを取得"""
        cell = self.get_cell(time_slot, class_ref)
        if cell and cell.is_assigned:
            from ..core.constraint_engine import Assignment
            return Assignment(
                time_slot=time_slot,
                class_ref=class_ref,
                subject=cell.subject,
                teacher=cell.teacher
            )
        return None
    
    def get_assignments_at(self, time_slot: TimeSlot) -> List['Assignment']:
        """指定時間のすべての割り当てを取得"""
        assignments = []
        for (ts, cr), cell in self._cells.items():
            if ts == time_slot and cell.is_assigned:
                from ..core.constraint_engine import Assignment
                assignments.append(Assignment(
                    time_slot=ts,
                    class_ref=cr,
                    subject=cell.subject,
                    teacher=cell.teacher
                ))
        return assignments
    
    def get_all_assignments(self) -> List['Assignment']:
        """すべての割り当てを取得"""
        assignments = []
        for (ts, cr), cell in self._cells.items():
            if cell.is_assigned:
                from ..core.constraint_engine import Assignment
                assignments.append(Assignment(
                    time_slot=ts,
                    class_ref=cr,
                    subject=cell.subject,
                    teacher=cell.teacher
                ))
        return assignments
    
    def get_teacher_schedule(self, teacher: Teacher) -> List[Tuple[TimeSlot, ClassReference, Subject]]:
        """教員のスケジュールを取得"""
        schedule = []
        for (ts, cr), cell in self._cells.items():
            if cell.teacher == teacher and cell.is_assigned:
                schedule.append((ts, cr, cell.subject))
        return sorted(schedule, key=lambda x: (x[0].day, x[0].period))
    
    def get_class_schedule(self, class_ref: ClassReference) -> List[Tuple[TimeSlot, Subject, Teacher]]:
        """クラスのスケジュールを取得"""
        schedule = []
        for (ts, cr), cell in self._cells.items():
            if cr == class_ref and cell.is_assigned:
                schedule.append((ts, cell.subject, cell.teacher))
        return sorted(schedule, key=lambda x: (x[0].day, x[0].period))
    
    def lock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """セルをロック"""
        cell = self.get_cell(time_slot, class_ref)
        if cell:
            cell.is_locked = True
            self._version += 1
            return True
        return False
    
    def unlock_cell(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """セルのロックを解除"""
        cell = self.get_cell(time_slot, class_ref)
        if cell:
            cell.is_locked = False
            self._version += 1
            return True
        return False
    
    def is_locked(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """セルがロックされているかチェック"""
        cell = self.get_cell(time_slot, class_ref)
        return cell.is_locked if cell else False
    
    def clone(self) -> 'Timetable':
        """時間割の複製を作成"""
        new_timetable = Timetable()
        new_timetable._cells = copy.deepcopy(self._cells)
        new_timetable._version = self._version
        new_timetable._created_at = self._created_at
        new_timetable._modified_at = datetime.now()
        return new_timetable
    
    def get_empty_slots(self, class_ref: ClassReference) -> List[TimeSlot]:
        """クラスの空きスロットを取得"""
        empty_slots = []
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                cell = self.get_cell(time_slot, class_ref)
                if not cell or cell.is_empty:
                    empty_slots.append(time_slot)
        return empty_slots
    
    def get_statistics(self) -> Dict[str, any]:
        """統計情報を取得"""
        total_slots = 0
        assigned_slots = 0
        locked_slots = 0
        empty_slots = 0
        
        class_stats = {}
        subject_stats = {}
        teacher_stats = {}
        
        for (ts, cr), cell in self._cells.items():
            total_slots += 1
            
            if cell.is_locked:
                locked_slots += 1
            
            if cell.is_assigned:
                assigned_slots += 1
                
                # クラス別統計
                if cr not in class_stats:
                    class_stats[cr] = {'total': 0, 'assigned': 0, 'empty': 0}
                class_stats[cr]['assigned'] += 1
                
                # 教科別統計
                if cell.subject not in subject_stats:
                    subject_stats[cell.subject] = 0
                subject_stats[cell.subject] += 1
                
                # 教員別統計
                if cell.teacher:
                    if cell.teacher not in teacher_stats:
                        teacher_stats[cell.teacher] = 0
                    teacher_stats[cell.teacher] += 1
            else:
                empty_slots += 1
                if cr not in class_stats:
                    class_stats[cr] = {'total': 0, 'assigned': 0, 'empty': 0}
                class_stats[cr]['empty'] += 1
        
        return {
            'version': self._version,
            'created_at': self._created_at,
            'modified_at': self._modified_at,
            'total_slots': total_slots,
            'assigned_slots': assigned_slots,
            'empty_slots': empty_slots,
            'locked_slots': locked_slots,
            'fill_rate': assigned_slots / total_slots if total_slots > 0 else 0,
            'class_statistics': class_stats,
            'subject_statistics': subject_stats,
            'teacher_statistics': teacher_stats
        }
    
    def _record_change(self, action: str, cell_key: Tuple, old_value: any, new_value: any):
        """変更履歴を記録"""
        self._history.append({
            'version': self._version,
            'timestamp': datetime.now(),
            'action': action,
            'cell_key': cell_key,
            'old_value': old_value,
            'new_value': new_value
        })
        
        # 履歴が大きくなりすぎないように制限
        if len(self._history) > 1000:
            self._history = self._history[-500:]
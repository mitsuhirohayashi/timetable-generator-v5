"""教師不在情報のアダプター実装"""

from typing import Dict, List, Set
from ...domain.interfaces.teacher_absence_repository import ITeacherAbsenceRepository
from ...domain.value_objects import TimeSlot
from ..repositories.teacher_absence_loader import TeacherAbsenceLoader


class TeacherAbsenceAdapter(ITeacherAbsenceRepository):
    """既存のTeacherAbsenceLoaderをITeacherAbsenceRepositoryに適合させるアダプター"""
    
    def __init__(self, loader: TeacherAbsenceLoader = None):
        self._loader = loader or TeacherAbsenceLoader()
        self._cached_absences = None
    
    def get_absences(self) -> Dict[str, List[TimeSlot]]:
        """すべての教師の不在情報を取得"""
        if self._cached_absences is None:
            self._build_absence_cache()
        return self._cached_absences
    
    def is_teacher_absent(self, teacher_name: str, time_slot: TimeSlot) -> bool:
        """指定された教師が指定された時間に不在かどうかを判定"""
        return self._loader.is_teacher_absent(teacher_name, time_slot.day, time_slot.period)
    
    def get_absent_teachers_at(self, time_slot: TimeSlot) -> Set[str]:
        """指定された時間に不在の教師のセットを取得"""
        absent_teachers = set()
        
        if time_slot.day not in self._loader.absences:
            return absent_teachers
        
        day_absences = self._loader.absences[time_slot.day]
        
        # 終日不在の教師を追加
        absent_teachers.update(day_absences.get('all_day', []))
        
        # 時限別不在の教師を追加
        if time_slot.period in day_absences.get('periods', {}):
            absent_teachers.update(day_absences['periods'][time_slot.period])
        
        return absent_teachers
    
    def get_teacher_absence_slots(self, teacher_name: str) -> List[TimeSlot]:
        """指定された教師の不在時間のリストを取得"""
        if self._cached_absences is None:
            self._build_absence_cache()
        return self._cached_absences.get(teacher_name, [])
    
    def reload(self) -> None:
        """不在情報を再読み込み"""
        self._loader = TeacherAbsenceLoader()
        self._cached_absences = None
    
    def _build_absence_cache(self) -> None:
        """不在情報のキャッシュを構築"""
        self._cached_absences = {}
        
        for day, day_absences in self._loader.absences.items():
            # 終日不在の教師
            for teacher in day_absences.get('all_day', []):
                if teacher not in self._cached_absences:
                    self._cached_absences[teacher] = []
                # 1日で6コマ分を追加
                for period in range(1, 7):
                    self._cached_absences[teacher].append(TimeSlot(day, period))
            
            # 時限別不在の教師
            for period, teachers in day_absences.get('periods', {}).items():
                for teacher in teachers:
                    if teacher not in self._cached_absences:
                        self._cached_absences[teacher] = []
                    self._cached_absences[teacher].append(TimeSlot(day, period))
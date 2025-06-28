"""スケジュールのシリアライゼーション

並列処理でプロセス間通信のためにスケジュールと学校データをシリアライズ/デシリアライズします。
"""
import pickle
from typing import Dict, List, Any

from .....domain.entities.schedule import Schedule
from .....domain.entities.school import School, Teacher, Subject
from .....domain.value_objects.time_slot import TimeSlot, ClassReference
from .....domain.value_objects.assignment import Assignment


class ScheduleSerializer:
    """スケジュールシリアライザー"""
    
    @staticmethod
    def serialize_schedule(schedule: Schedule) -> bytes:
        """スケジュールをシリアライズ
        
        Args:
            schedule: シリアライズするスケジュール
            
        Returns:
            シリアライズされたバイト列
        """
        data = {
            'assignments': [],
            'locked_cells': []
        }
        
        for time_slot, assignment in schedule.get_all_assignments():
            data['assignments'].append({
                'day': time_slot.day,
                'period': time_slot.period,
                'grade': assignment.class_ref.grade,
                'class_number': assignment.class_ref.class_number,
                'subject': assignment.subject.name,
                'teacher': assignment.teacher.name if assignment.teacher else None
            })
        
        # TODO: ロックされたセルも記録
        
        return pickle.dumps(data)
    
    @staticmethod
    def deserialize_schedule(data: bytes) -> Schedule:
        """スケジュールをデシリアライズ
        
        Args:
            data: シリアライズされたバイト列
            
        Returns:
            復元されたスケジュール
        """
        schedule = Schedule()
        schedule_data = pickle.loads(data)
        
        for item in schedule_data['assignments']:
            time_slot = TimeSlot(item['day'], item['period'])
            class_ref = ClassReference(item['grade'], item['class_number'])
            subject = Subject(item['subject'])
            teacher = Teacher(item['teacher']) if item['teacher'] else None
            assignment = Assignment(class_ref, subject, teacher)
            
            try:
                schedule.assign(time_slot, assignment)
            except:
                # エラーは無視（ログに記録すべきだが簡略化）
                pass
        
        return schedule
    
    @staticmethod
    def serialize_school(school: School) -> bytes:
        """学校データをシリアライズ
        
        Args:
            school: シリアライズする学校データ
            
        Returns:
            シリアライズされたバイト列
        """
        # 必要最小限のデータのみシリアライズ
        data = {
            'classes': [(c.grade, c.class_number) for c in school.get_all_classes()],
            # TODO: その他必要なデータ（教師、科目、制約など）
        }
        return pickle.dumps(data)
    
    @staticmethod
    def deserialize_school(data: bytes) -> School:
        """学校データをデシリアライズ
        
        Args:
            data: シリアライズされたバイト列
            
        Returns:
            復元された学校データ（簡易版）
        """
        # 簡易的な復元（実際は適切な実装が必要）
        school = School()
        school_data = pickle.loads(data)
        
        # TODO: 最小限の情報のみ復元
        return school
    
    @staticmethod
    def copy_schedule(schedule: Schedule) -> Schedule:
        """スケジュールのディープコピー
        
        Args:
            schedule: コピー元のスケジュール
            
        Returns:
            コピーされたスケジュール
        """
        copy = Schedule()
        for time_slot, assignment in schedule.get_all_assignments():
            copy.assign(time_slot, assignment)
        
        # TODO: ロック情報もコピー
        
        return copy
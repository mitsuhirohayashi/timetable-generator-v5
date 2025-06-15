"""統合制約システムのテスト"""
import pytest
from pathlib import Path
import sys

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.domain.constraints.consolidated import (
    ConstraintValidator,
    ProtectedSlotConstraint,
    TeacherSchedulingConstraint,
    ClassSynchronizationConstraint,
    ResourceUsageConstraint,
    SchedulingRuleConstraint,
    SubjectValidationConstraint,
    ValidationContext
)
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.config.consolidated_constraint_loader import ConsolidatedConstraintLoader


def create_test_school():
    """テスト用の学校を作成"""
    school = School()
    
    # クラスを追加
    for grade in range(1, 4):
        for class_num in range(1, 8):
            school.add_class(ClassReference(grade, class_num))
    
    # 教師を追加
    teachers = ["山田", "田中", "鈴木", "佐藤", "青井"]
    for teacher_name in teachers:
        school.add_teacher(Teacher(teacher_name))
    
    # 教科を追加
    subjects = ["国語", "数学", "英語", "理科", "社会", "体育", "音楽", "美術", "自立", "欠", "YT"]
    for subject_name in subjects:
        school.add_subject(Subject(subject_name))
    
    return school


def create_test_schedule(school):
    """テスト用のスケジュールを作成"""
    schedule = Schedule()
    
    # いくつかの割り当てを追加
    # 月曜6限は全クラス欠課
    for grade in range(1, 4):
        for class_num in range(1, 8):
            time_slot = TimeSlot(day="月", period=6)
            class_ref = ClassReference(grade, class_num)
            assignment = Assignment(
                time_slot=time_slot,
                class_ref=class_ref,
                subject=Subject("欠"),
                teacher=Teacher("欠課")
            )
            schedule.add_assignment(assignment)
    
    # 5組に同じ教科を配置
    time_slot = TimeSlot(day="火", period=1)
    for grade in range(1, 4):
        class_ref = ClassReference(grade, 5)
        assignment = Assignment(
            time_slot=time_slot,
            class_ref=class_ref,
            subject=Subject("国語"),
            teacher=Teacher("山田")
        )
        schedule.add_assignment(assignment)
    
    return schedule


class TestProtectedSlotConstraint:
    """保護スロット制約のテスト"""
    
    def test_monday_sixth_period_protection(self):
        """月曜6限の欠課保護"""
        school = create_test_school()
        schedule = create_test_schedule(school)
        
        constraint = ProtectedSlotConstraint()
        context = ValidationContext(schedule=schedule, school=school)
        result = constraint.validate(context)
        
        # 月曜6限は欠課で違反なし
        assert result.is_valid
        
        # 月曜6限に他の教科を配置
        time_slot = TimeSlot(day="月", period=6)
        class_ref = ClassReference(1, 1)
        assignment = Assignment(
            time_slot=time_slot,
            class_ref=class_ref,
            subject=Subject("国語"),
            teacher=Teacher("田中")
        )
        schedule.add_assignment(assignment)
        
        result = constraint.validate(context)
        assert not result.is_valid
        assert len(result.violations) > 0
        

class TestTeacherSchedulingConstraint:
    """教師スケジューリング制約のテスト"""
    
    def test_teacher_conflict_detection(self):
        """教師の重複検出"""
        school = create_test_school()
        schedule = create_test_schedule(school)
        
        # 同じ教師を同じ時間に複数クラスに配置
        time_slot = TimeSlot(day="火", period=2)
        
        assignment1 = Assignment(
            time_slot=time_slot,
            class_ref=ClassReference(1, 1),
            subject=Subject("数学"),
            teacher=Teacher("田中")
        )
        schedule.add_assignment(assignment1)
        
        assignment2 = Assignment(
            time_slot=time_slot,
            class_ref=ClassReference(1, 2),
            subject=Subject("数学"),
            teacher=Teacher("田中")
        )
        schedule.add_assignment(assignment2)
        
        constraint = TeacherSchedulingConstraint()
        context = ValidationContext(schedule=schedule, school=school)
        result = constraint.validate(context)
        
        # 教師の重複で違反
        assert not result.is_valid
        assert any("複数クラス" in v.message for v in result.violations)


class TestClassSynchronizationConstraint:
    """クラス同期制約のテスト"""
    
    def test_grade5_synchronization(self):
        """5組の同期"""
        school = create_test_school()
        schedule = Schedule()
        
        # 5組に異なる教科を配置
        time_slot = TimeSlot(day="水", period=1)
        
        schedule.add_assignment(Assignment(
            time_slot=time_slot,
            class_ref=ClassReference(1, 5),
            subject=Subject("国語"),
            teacher=Teacher("山田")
        ))
        
        schedule.add_assignment(Assignment(
            time_slot=time_slot,
            class_ref=ClassReference(2, 5),
            subject=Subject("数学"),  # 異なる教科
            teacher=Teacher("田中")
        ))
        
        schedule.add_assignment(Assignment(
            time_slot=time_slot,
            class_ref=ClassReference(3, 5),
            subject=Subject("国語"),
            teacher=Teacher("鈴木")
        ))
        
        constraint = ClassSynchronizationConstraint()
        context = ValidationContext(schedule=schedule, school=school)
        result = constraint.validate(context)
        
        # 5組の教科が異なるので違反
        assert not result.is_valid
        assert any("5組" in v.message and "異なります" in v.message for v in result.violations)


class TestResourceUsageConstraint:
    """リソース使用制約のテスト"""
    
    def test_gym_usage_limit(self):
        """体育館使用制限"""
        school = create_test_school()
        schedule = Schedule()
        
        # 同じ時間に複数クラスで体育
        time_slot = TimeSlot(day="木", period=1)
        
        schedule.add_assignment(Assignment(
            time_slot=time_slot,
            class_ref=ClassReference(1, 1),
            subject=Subject("体育"),
            teacher=Teacher("佐藤")
        ))
        
        schedule.add_assignment(Assignment(
            time_slot=time_slot,
            class_ref=ClassReference(2, 1),
            subject=Subject("体育"),
            teacher=Teacher("鈴木")
        ))
        
        constraint = ResourceUsageConstraint()
        context = ValidationContext(schedule=schedule, school=school)
        result = constraint.validate(context)
        
        # 体育館の同時使用で違反
        assert not result.is_valid
        assert any("体育館" in v.message for v in result.violations)


class TestSchedulingRuleConstraint:
    """スケジューリングルール制約のテスト"""
    
    def test_daily_duplicate_limit(self):
        """日内重複制限"""
        school = create_test_school()
        schedule = Schedule()
        
        # 同じ日に国語を3回配置
        class_ref = ClassReference(1, 1)
        day = "金"
        
        for period in [1, 3, 5]:
            schedule.add_assignment(Assignment(
                time_slot=TimeSlot(day=day, period=period),
                class_ref=class_ref,
                subject=Subject("国語"),
                teacher=Teacher("山田")
            ))
        
        constraint = SchedulingRuleConstraint()
        context = ValidationContext(schedule=schedule, school=school)
        result = constraint.validate(context)
        
        # 国語が1日3回で違反
        assert not result.is_valid
        assert any("国語" in v.message and "3回" in v.message for v in result.violations)


class TestSubjectValidationConstraint:
    """教科検証制約のテスト"""
    
    def test_special_needs_subject_placement(self):
        """特別支援教科の配置"""
        school = create_test_school()
        schedule = Schedule()
        
        # 通常学級に自立活動を配置
        schedule.add_assignment(Assignment(
            time_slot=TimeSlot(day="月", period=1),
            class_ref=ClassReference(1, 1),  # 通常学級
            subject=Subject("自立"),  # 特別支援教科
            teacher=Teacher("田中")
        ))
        
        constraint = SubjectValidationConstraint()
        context = ValidationContext(schedule=schedule, school=school)
        result = constraint.validate(context)
        
        # 通常学級に特別支援教科で違反
        assert not result.is_valid
        assert any("配置できません" in v.message for v in result.violations)


class TestConsolidatedConstraintLoader:
    """統合制約ローダーのテスト"""
    
    def test_load_all_constraints(self):
        """全制約の読み込み"""
        loader = ConsolidatedConstraintLoader()
        constraints = loader.load_all_constraints()
        
        # 6つの統合制約が読み込まれる
        assert len(constraints) == 6
        
        # 各制約の存在確認
        constraint_names = [c.name for c in constraints]
        assert "保護スロット制約" in constraint_names
        assert "教師スケジューリング制約" in constraint_names
        assert "クラス同期制約" in constraint_names
        assert "リソース使用制約" in constraint_names
        assert "スケジューリングルール制約" in constraint_names
        assert "教科検証制約" in constraint_names
        
    def test_create_validator(self):
        """バリデーターの作成"""
        loader = ConsolidatedConstraintLoader()
        validator = loader.create_validator()
        
        assert isinstance(validator, ConstraintValidator)
        assert len(validator.constraints) == 6
        
    def test_constraint_priority_order(self):
        """制約の優先度順"""
        loader = ConsolidatedConstraintLoader()
        constraints = loader.load_all_constraints()
        
        # 優先度順にソートされている
        priorities = [c.priority.value for c in constraints]
        assert priorities == sorted(priorities, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
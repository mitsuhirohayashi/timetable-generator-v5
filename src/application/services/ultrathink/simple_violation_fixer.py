"""シンプルで効果的な違反修正器

Ultrathinkフレームワーク内で動作する、制約違反を確実に修正するモジュール。
複雑な最適化ではなく、確実な違反修正に焦点を当てる。
"""
import logging
from typing import List, Optional, Tuple, Dict, Set
from collections import defaultdict

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School, Teacher
from ....domain.value_objects.time_slot import TimeSlot
from ....domain.value_objects.time_slot import ClassReference
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.base import ConstraintViolation, ConstraintPriority


class SimpleViolationFixer:
    """シンプルな違反修正器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.fixed_subjects = {'欠', '欠課', 'YT', '学', '学活', '道', '道徳', 
                               '総', '総合', '学総', '行', '行事', 'テスト', '技家'}
        
        # 交流学級マッピング
        self.exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        # 5組クラス
        self.grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
    
    def fix_violations(
        self,
        schedule: Schedule,
        school: School,
        violations: List[ConstraintViolation]
    ) -> Tuple[Schedule, int]:
        """違反を修正
        
        Returns:
            修正されたスケジュールと修正した違反数
        """
        self.logger.info(f"違反修正を開始: {len(violations)}件の違反")
        
        # 違反を優先度でソート（CRITICALから修正）
        sorted_violations = sorted(
            violations,
            key=lambda v: (v.priority.value, v.type),
            reverse=True
        )
        
        fixed_count = 0
        
        # 違反タイプ別にグループ化
        violation_groups = defaultdict(list)
        for violation in sorted_violations:
            violation_groups[violation.type].append(violation)
        
        # 1. 教師重複を修正（最重要）
        if 'TEACHER_CONFLICT' in violation_groups:
            count = self._fix_teacher_conflicts(
                schedule, school, violation_groups['TEACHER_CONFLICT']
            )
            fixed_count += count
            self.logger.info(f"  教師重複: {count}件修正")
        
        # 2. 日内重複を修正
        if 'DAILY_DUPLICATE' in violation_groups:
            count = self._fix_daily_duplicates(
                schedule, school, violation_groups['DAILY_DUPLICATE']
            )
            fixed_count += count
            self.logger.info(f"  日内重複: {count}件修正")
        
        # 3. 月曜6限を修正
        if 'MONDAY_SIXTH' in violation_groups:
            count = self._fix_monday_sixth(
                schedule, school, violation_groups['MONDAY_SIXTH']
            )
            fixed_count += count
            self.logger.info(f"  月曜6限: {count}件修正")
        
        # 4. 交流学級の自立活動を修正
        if 'JIRITSU_CONSTRAINT' in violation_groups:
            count = self._fix_jiritsu_violations(
                schedule, school, violation_groups['JIRITSU_CONSTRAINT']
            )
            fixed_count += count
            self.logger.info(f"  自立活動: {count}件修正")
        
        # 5. 5組同期を修正
        count = self._fix_grade5_sync(schedule, school)
        if count > 0:
            fixed_count += count
            self.logger.info(f"  5組同期: {count}件修正")
        
        self.logger.info(f"違反修正完了: {fixed_count}件を修正")
        
        return schedule, fixed_count
    
    def _fix_teacher_conflicts(
        self,
        schedule: Schedule,
        school: School,
        violations: List[ConstraintViolation]
    ) -> int:
        """教師重複を修正"""
        fixed_count = 0
        
        for violation in violations:
            time_slot = violation.time_slot
            teacher_name = violation.details.get('teacher')
            
            if not time_slot or not teacher_name:
                continue
            
            # この時間の教師の全割り当てを取得
            teacher_assignments = []
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                    teacher_assignments.append((class_ref, assignment))
            
            # 5組の合同授業は除外
            non_grade5 = [(c, a) for c, a in teacher_assignments if c.class_number != 5]
            if non_grade5:
                teacher_assignments = non_grade5
            
            # 最初のクラス以外の教師を変更
            for class_ref, assignment in teacher_assignments[1:]:
                # 代替教師を探す
                alt_teacher = self._find_alternative_teacher(
                    school, assignment.subject, time_slot, schedule, teacher_name
                )
                
                if alt_teacher:
                    new_assignment = Assignment(
                        class_ref=class_ref,
                        subject=assignment.subject,
                        teacher=alt_teacher
                    )
                    
                    try:
                        schedule.assign(time_slot, new_assignment)
                        fixed_count += 1
                    except:
                        pass
        
        return fixed_count
    
    def _fix_daily_duplicates(
        self,
        schedule: Schedule,
        school: School,
        violations: List[ConstraintViolation]
    ) -> int:
        """日内重複を修正"""
        fixed_count = 0
        
        # クラスと日付でグループ化
        class_day_violations = defaultdict(list)
        for violation in violations:
            if violation.time_slot and violation.class_ref:
                key = (violation.class_ref, violation.time_slot.day)
                class_day_violations[key].append(violation)
        
        for (class_ref, day), day_violations in class_day_violations.items():
            # その日の全授業を取得
            day_assignments = []
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    day_assignments.append((time_slot, assignment))
            
            # 重複している教科を特定
            subject_slots = defaultdict(list)
            for time_slot, assignment in day_assignments:
                if assignment.subject.name not in self.fixed_subjects:
                    subject_slots[assignment.subject.name].append(time_slot)
            
            # 重複を修正
            for subject, slots in subject_slots.items():
                if len(slots) > 1:
                    # 最初の時限以外を変更
                    for time_slot in slots[1:]:
                        # 不足している教科を探す
                        needed_subject = self._find_needed_subject(
                            schedule, school, class_ref, day
                        )
                        
                        if needed_subject:
                            teacher = self._find_teacher_for_subject(
                                school, needed_subject, class_ref
                            )
                            
                            if teacher and self._is_teacher_available(
                                schedule, teacher, time_slot
                            ):
                                new_assignment = Assignment(
                                    class_ref=class_ref,
                                    subject=school.get_subject(needed_subject),
                                    teacher=teacher
                                )
                                
                                try:
                                    schedule.assign(time_slot, new_assignment)
                                    fixed_count += 1
                                except:
                                    pass
        
        return fixed_count
    
    def _fix_monday_sixth(
        self,
        schedule: Schedule,
        school: School,
        violations: List[ConstraintViolation]
    ) -> int:
        """月曜6限を修正"""
        fixed_count = 0
        
        for violation in violations:
            if violation.class_ref:
                time_slot = TimeSlot('月', 6)
                
                # 担任を取得
                teacher = self._get_homeroom_teacher(school, violation.class_ref)
                
                assignment = Assignment(
                    class_ref=violation.class_ref,
                    subject=school.get_subject('欠'),
                    teacher=teacher
                )
                
                try:
                    schedule.assign(time_slot, assignment)
                    fixed_count += 1
                except:
                    pass
        
        return fixed_count
    
    def _fix_jiritsu_violations(
        self,
        schedule: Schedule,
        school: School,
        violations: List[ConstraintViolation]
    ) -> int:
        """自立活動違反を修正"""
        fixed_count = 0
        
        for violation in violations:
            if not violation.time_slot or not violation.class_ref:
                continue
            
            # 交流学級の場合
            if violation.class_ref in self.exchange_mappings:
                parent_class = self.exchange_mappings[violation.class_ref]
                parent_assignment = schedule.get_assignment(
                    violation.time_slot, parent_class
                )
                
                if parent_assignment and parent_assignment.subject.name not in ['数', '英']:
                    # 親学級を数学に変更
                    teacher = self._find_teacher_for_subject(school, '数', parent_class)
                    
                    if teacher and self._is_teacher_available(
                        schedule, teacher, violation.time_slot
                    ):
                        new_assignment = Assignment(
                            class_ref=parent_class,
                            subject=school.get_subject('数'),
                            teacher=teacher
                        )
                        
                        try:
                            schedule.assign(violation.time_slot, new_assignment)
                            fixed_count += 1
                        except:
                            pass
        
        return fixed_count
    
    def _fix_grade5_sync(self, schedule: Schedule, school: School) -> int:
        """5組同期を修正"""
        fixed_count = 0
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各5組の割り当てを取得
                assignments = []
                for class_ref in self.grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments.append((class_ref, assignment))
                
                if len(assignments) >= 2:
                    # 最も多い教科を選択
                    subject_counts = defaultdict(int)
                    teacher_map = {}
                    
                    for class_ref, assignment in assignments:
                        subject_counts[assignment.subject.name] += 1
                        if assignment.subject.name not in teacher_map:
                            teacher_map[assignment.subject.name] = assignment.teacher
                    
                    if len(set(a[1].subject.name for a in assignments)) > 1:
                        # 不一致がある場合、最も多い教科に統一
                        most_common = max(subject_counts, key=subject_counts.get)
                        teacher = teacher_map[most_common]
                        
                        for class_ref in self.grade5_classes:
                            current = schedule.get_assignment(time_slot, class_ref)
                            if not current or current.subject.name != most_common:
                                new_assignment = Assignment(
                                    class_ref=class_ref,
                                    subject=school.get_subject(most_common),
                                    teacher=teacher
                                )
                                
                                try:
                                    schedule.assign(time_slot, new_assignment)
                                    fixed_count += 1
                                except:
                                    pass
        
        return fixed_count
    
    # ヘルパーメソッド
    def _find_alternative_teacher(
        self,
        school: School,
        subject,
        time_slot: TimeSlot,
        schedule: Schedule,
        exclude_teacher: str
    ) -> Optional[Teacher]:
        """代替教師を探す"""
        for teacher in school.get_all_teachers():
            if teacher.name == exclude_teacher:
                continue
            
            # 教科を教えられるかチェック（簡易実装）
            if self._can_teach_subject(teacher, subject.name):
                if self._is_teacher_available(schedule, teacher, time_slot):
                    return teacher
        
        return None
    
    def _is_teacher_available(
        self,
        schedule: Schedule,
        teacher: Teacher,
        time_slot: TimeSlot
    ) -> bool:
        """教師が利用可能か確認"""
        for class_ref in schedule.school.get_all_classes() if hasattr(schedule, 'school') else []:
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher == teacher:
                return False
        return True
    
    def _can_teach_subject(self, teacher: Teacher, subject: str) -> bool:
        """教師が教科を教えられるか（簡易実装）"""
        # 実際の実装では、教師の担当教科情報を参照
        return True
    
    def _find_needed_subject(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        day: str
    ) -> Optional[str]:
        """不足している教科を探す"""
        # その日の教科を収集
        day_subjects = set()
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # 主要教科で未配置のものを優先
        main_subjects = ['国', '数', '英', '理', '社']
        for subject in main_subjects:
            if subject not in day_subjects:
                return subject
        
        # 技能教科
        skill_subjects = ['音', '美', '体', '技', '家']
        for subject in skill_subjects:
            if subject not in day_subjects:
                return subject
        
        return None
    
    def _find_teacher_for_subject(
        self,
        school: School,
        subject: str,
        class_ref: ClassReference
    ) -> Optional[Teacher]:
        """教科の教師を探す"""
        # 実際の実装では、教師割り当て情報を参照
        for teacher in school.get_all_teachers():
            if self._can_teach_subject(teacher, subject):
                return teacher
        return None
    
    def _get_homeroom_teacher(
        self,
        school: School,
        class_ref: ClassReference
    ) -> Optional[Teacher]:
        """担任教師を取得"""
        # 実際の実装では、担任情報を参照
        homeroom_map = {
            (1, 1): '金子ひ先生',
            (1, 2): '井野口先生',
            (1, 3): '梶永先生',
            (2, 1): '塚本先生',
            (2, 2): '野口先生',
            (2, 3): '永山先生',
            (3, 1): '白石先生',
            (3, 2): '森山先生',
            (3, 3): '北先生',
            (1, 5): '金子み先生',
            (2, 5): '金子み先生',
            (3, 5): '金子み先生',
        }
        
        teacher_name = homeroom_map.get((class_ref.grade, class_ref.class_number))
        if teacher_name:
            return school.get_teacher(teacher_name)
        return None
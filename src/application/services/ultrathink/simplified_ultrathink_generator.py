"""簡略化されたUltrathink生成器

複雑な最適化を避け、確実に違反を減らすことに焦点を当てた実装。
"""
import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, ClassReference
from ....domain.value_objects.assignment import Assignment
from ....domain.services.validators.constraint_validator import ConstraintValidator
from ....domain.services.synchronizers.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
from ....domain.services.synchronizers.exchange_class_synchronizer import ExchangeClassSynchronizer
from .test_period_protector import TestPeriodProtector
from .simple_violation_fixer import SimpleViolationFixer


@dataclass
class SimplifiedOptimizationResult:
    """簡略化された最適化結果"""
    schedule: Schedule
    violations: int
    teacher_conflicts: int
    execution_time: float
    improvements: List[str]
    is_successful: bool = False
    
    def __post_init__(self):
        self.is_successful = self.violations == 0


class SimplifiedUltrathinkGenerator:
    """簡略化されたUltrathink生成器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.constraint_validator = ConstraintValidator()
        self.grade5_synchronizer = RefactoredGrade5Synchronizer(self.constraint_validator)
        self.exchange_synchronizer = ExchangeClassSynchronizer()
        self.test_period_protector = TestPeriodProtector()
        self.violation_fixer = SimpleViolationFixer()
        
        # 固定科目
        self.fixed_subjects = {'欠', '欠課', 'YT', '学', '学活', '道', '道徳', 
                               '総', '総合', '学総', '行', '行事', 'テスト', '技家'}
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        followup_data: Optional[Dict[str, Any]] = None
    ) -> SimplifiedOptimizationResult:
        """スケジュールを生成"""
        start_time = time.time()
        
        self.logger.info("=== 簡略化されたUltrathink生成を開始 ===")
        
        # 初期スケジュールを準備
        if initial_schedule is None:
            initial_schedule = Schedule()
        
        schedule = initial_schedule.copy()
        improvements = []
        
        try:
            # Phase 1: テスト期間保護
            self.logger.info("Phase 1: テスト期間保護")
            if followup_data:
                self.test_period_protector.load_followup_data(followup_data)
                protected_count = self._protect_test_periods(schedule, school)
                if protected_count > 0:
                    improvements.append(f"テスト期間を{protected_count}スロット保護")
            
            # Phase 2: 5組同期
            self.logger.info("Phase 2: 5組同期")
            sync_count = self._sync_grade5(schedule, school)
            if sync_count > 0:
                improvements.append(f"5組を{sync_count}コマ同期")
            
            # Phase 3: 交流学級同期
            self.logger.info("Phase 3: 交流学級同期")
            exchange_count = self._sync_exchange_classes(schedule, school)
            if exchange_count > 0:
                improvements.append(f"交流学級を{exchange_count}コマ同期")
            
            # Phase 4: 月曜6限修正
            self.logger.info("Phase 4: 月曜6限修正")
            monday_count = self._fix_monday_6th(schedule, school)
            if monday_count > 0:
                improvements.append(f"月曜6限を{monday_count}クラス修正")
            
            # Phase 5: 違反修正
            violations = self.constraint_validator.validate_all(schedule)
            initial_violation_count = len(violations)
            
            if violations:
                self.logger.info(f"Phase 5: {len(violations)}件の違反を修正")
                schedule, fixed_count = self.violation_fixer.fix_violations(
                    schedule, school, violations
                )
                if fixed_count > 0:
                    improvements.append(f"{fixed_count}件の違反を修正")
                
                # 再検証
                violations = self.constraint_validator.validate_all(schedule)
            
            # Phase 6: 空きコマ埋め
            self.logger.info("Phase 6: 空きコマ埋め")
            filled_count = self._fill_empty_slots(schedule, school)
            if filled_count > 0:
                improvements.append(f"{filled_count}個の空きコマを埋めた")
            
            # 最終検証
            final_violations = self.constraint_validator.validate_all(schedule)
            teacher_conflicts = self._count_teacher_conflicts(final_violations)
            
            # 結果を作成
            result = SimplifiedOptimizationResult(
                schedule=schedule,
                violations=len(final_violations),
                teacher_conflicts=teacher_conflicts,
                execution_time=time.time() - start_time,
                improvements=improvements
            )
            
            # 改善度を記録
            if initial_violation_count > result.violations:
                improvement_rate = (initial_violation_count - result.violations) / initial_violation_count * 100
                result.improvements.append(f"違反を{improvement_rate:.1f}%削減")
            
            self._print_summary(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"生成中にエラー: {e}")
            return SimplifiedOptimizationResult(
                schedule=schedule,
                violations=-1,
                teacher_conflicts=-1,
                execution_time=time.time() - start_time,
                improvements=[]
            )
    
    def _protect_test_periods(self, schedule: Schedule, school: School) -> int:
        """テスト期間を保護"""
        protected_count = 0
        
        if hasattr(self.test_period_protector, 'test_periods'):
            for (day, period) in self.test_period_protector.test_periods:
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and assignment.subject.name not in ['行', '行事', 'テスト']:
                        # テスト期間は行事のみ
                        try:
                            test_assignment = Assignment(
                                class_ref=class_ref,
                                subject=school.get_subject('行'),
                                teacher=assignment.teacher
                            )
                            schedule.assign(time_slot, test_assignment)
                            protected_count += 1
                        except:
                            pass
        
        return protected_count
    
    def _sync_grade5(self, schedule: Schedule, school: School) -> int:
        """5組を同期"""
        synced_count = 0
        grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各5組の現在の割り当てを取得
                assignments = []
                for class_ref in grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments.append((class_ref, assignment))
                
                if len(assignments) >= 2:
                    # 最初の割り当てに統一
                    base_assignment = assignments[0][1]
                    
                    for class_ref, current in assignments[1:]:
                        if (current.subject.name != base_assignment.subject.name or
                            current.teacher != base_assignment.teacher):
                            
                            new_assignment = Assignment(
                                class_ref=class_ref,
                                subject=base_assignment.subject,
                                teacher=base_assignment.teacher
                            )
                            
                            try:
                                schedule.assign(time_slot, new_assignment)
                                synced_count += 1
                            except:
                                pass
        
        return synced_count
    
    def _sync_exchange_classes(self, schedule: Schedule, school: School) -> int:
        """交流学級を同期"""
        synced_count = 0
        
        exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        for exchange_class, parent_class in exchange_mappings.items():
            for day in ['月', '火', '水', '木', '金']:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if exchange_assignment and parent_assignment:
                        # 自立活動・日生・作業以外は同期
                        if exchange_assignment.subject.name not in ['自立', '日生', '作業']:
                            if (exchange_assignment.subject.name != parent_assignment.subject.name or
                                exchange_assignment.teacher != parent_assignment.teacher):
                                
                                new_assignment = Assignment(
                                    class_ref=exchange_class,
                                    subject=parent_assignment.subject,
                                    teacher=parent_assignment.teacher
                                )
                                
                                try:
                                    schedule.assign(time_slot, new_assignment)
                                    synced_count += 1
                                except:
                                    pass
        
        return synced_count
    
    def _fix_monday_6th(self, schedule: Schedule, school: School) -> int:
        """月曜6限を修正"""
        fixed_count = 0
        
        for class_ref in school.get_all_classes():
            time_slot = TimeSlot('月', 6)
            current = schedule.get_assignment(time_slot, class_ref)
            
            if not current or current.subject.name != '欠':
                # 担任を取得
                teacher = self._get_homeroom_teacher(school, class_ref)
                
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=school.get_subject('欠'),
                    teacher=teacher
                )
                
                try:
                    schedule.assign(time_slot, assignment)
                    fixed_count += 1
                except:
                    pass
        
        return fixed_count
    
    def _fill_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きコマを埋める"""
        filled_count = 0
        
        # 主要教科の標準時数
        standard_hours = {
            '国': 4.0, '数': 4.0, '英': 4.0, '理': 3.0, '社': 3.0,
            '音': 1.5, '美': 1.5, '技': 1.0, '家': 1.0, '体': 3.0
        }
        
        for class_ref in school.get_all_classes():
            # 現在の時数を計算
            current_hours = {}
            for day in ['月', '火', '水', '木', '金']:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subject = assignment.subject.name
                        if subject not in self.fixed_subjects:
                            current_hours[subject] = current_hours.get(subject, 0) + 1
            
            # 空きコマを埋める
            for day in ['月', '火', '水', '木', '金']:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    if not schedule.get_assignment(time_slot, class_ref):
                        # 不足している教科を選択
                        best_subject = None
                        max_shortage = 0
                        
                        for subject, target in standard_hours.items():
                            current = current_hours.get(subject, 0)
                            shortage = target - current
                            
                            if shortage > max_shortage:
                                # その日にまだ配置されていないか確認
                                already_today = False
                                for p in range(1, 7):
                                    ts = TimeSlot(day, p)
                                    a = schedule.get_assignment(ts, class_ref)
                                    if a and a.subject.name == subject:
                                        already_today = True
                                        break
                                
                                if not already_today:
                                    # 教師が利用可能か確認
                                    teacher = self._get_teacher_for_subject(school, subject)
                                    if teacher and self._is_teacher_available(schedule, teacher, time_slot):
                                        best_subject = subject
                                        max_shortage = shortage
                        
                        if best_subject:
                            teacher = self._get_teacher_for_subject(school, best_subject)
                            assignment = Assignment(
                                class_ref=class_ref,
                                subject=school.get_subject(best_subject),
                                teacher=teacher
                            )
                            
                            try:
                                schedule.assign(time_slot, assignment)
                                current_hours[best_subject] = current_hours.get(best_subject, 0) + 1
                                filled_count += 1
                            except:
                                pass
        
        return filled_count
    
    def _count_teacher_conflicts(self, violations) -> int:
        """教師重複をカウント"""
        return sum(1 for v in violations if 'TEACHER_CONFLICT' in str(v.type))
    
    def _get_homeroom_teacher(self, school: School, class_ref: ClassReference):
        """担任教師を取得"""
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
        return school.get_teacher(teacher_name) if teacher_name else None
    
    def _get_teacher_for_subject(self, school: School, subject: str):
        """教科の教師を取得"""
        teacher_map = {
            '国': '智田先生',
            '数': '井上先生',
            '英': '蒲地先生',
            '理': '梶永先生',
            '社': '神田先生',
            '音': '今先生',
            '美': '平野先生',
            '体': '野田先生',
            '技': '國本先生',
            '家': '石原先生',
        }
        
        teacher_name = teacher_map.get(subject)
        return school.get_teacher(teacher_name) if teacher_name else None
    
    def _is_teacher_available(self, schedule: Schedule, teacher, time_slot: TimeSlot) -> bool:
        """教師が利用可能か確認"""
        # 簡易実装：他のクラスを担当していないか
        for assignment in schedule.get_all_assignments():
            if (assignment[0] == time_slot and 
                assignment[1].teacher == teacher):
                return False
        return True
    
    def _print_summary(self, result: SimplifiedOptimizationResult):
        """結果サマリーを出力"""
        self.logger.info("\n=== 簡略化Ultrathink生成結果 ===")
        self.logger.info(f"実行時間: {result.execution_time:.2f}秒")
        self.logger.info(f"制約違反: {result.violations}件")
        self.logger.info(f"教師重複: {result.teacher_conflicts}件")
        
        if result.improvements:
            self.logger.info("\n改善内容:")
            for improvement in result.improvements:
                self.logger.info(f"  ✓ {improvement}")
        
        if result.is_successful:
            self.logger.info("\n✅ 全ての制約を満たす完璧な時間割を生成しました！")
        else:
            self.logger.info(f"\n⚠️ {result.violations}件の違反が残っています")
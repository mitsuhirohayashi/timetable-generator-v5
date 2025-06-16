"""スケジュール検証サービス - 制約違反の検証と修正"""
import logging
from typing import List, Optional, Dict, Set, Tuple

from ...domain.entities.schedule import Schedule
from ...domain.entities.school import School
from ...domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ...domain.value_objects.assignment import Assignment
from ..repositories.teacher_absence_loader import TeacherAbsenceLoader
from ...domain.services.test_period_protector import TestPeriodProtector


class ScheduleValidationService:
    """スケジュールの制約違反を検証・修正するサービス"""
    
    def __init__(self, absence_loader: Optional[TeacherAbsenceLoader] = None):
        self.logger = logging.getLogger(__name__)
        self.absence_loader = absence_loader or TeacherAbsenceLoader()
        self.test_period_protector = TestPeriodProtector()
    
    def validate_and_fix_schedule(
        self,
        schedule: Schedule,
        school: School,
        forbidden_cells: Optional[Dict[Tuple[TimeSlot, ClassReference], Set[str]]] = None
    ) -> Dict[str, int]:
        """スケジュールの制約違反を検証し修正する
        
        Returns:
            修正結果の統計情報
        """
        # テスト期間情報をログ出力
        if self.test_period_protector.test_periods:
            self.logger.info(
                f"テスト期間を検出: {len(self.test_period_protector.test_periods)}スロット - "
                f"{sorted(self.test_period_protector.test_periods)}"
            )
        
        stats = {
            'teacher_absence_removed': 0,
            'teacher_absence_moved': 0,
            'gym_violations_removed': 0,
            'forbidden_cells_fixed': 0
        }
        
        # 教員不在違反を処理
        removed, moved = self._fix_teacher_absence_violations(schedule, school)
        stats['teacher_absence_removed'] = removed
        stats['teacher_absence_moved'] = moved
        
        # 体育館使用制約違反を処理
        stats['gym_violations_removed'] = self._fix_gym_violations(schedule, school)
        
        # セル配置禁止違反を処理
        if forbidden_cells:
            stats['forbidden_cells_fixed'] = self._fix_forbidden_cell_violations(
                schedule, school, forbidden_cells
            )
        
        self._log_validation_stats(stats)
        return stats
    
    def _fix_teacher_absence_violations(
        self,
        schedule: Schedule,
        school: School
    ) -> Tuple[int, int]:
        """教員不在違反を修正"""
        removed_count = 0
        moved_count = 0
        assignments_to_move = []
        
        # 違反を検出
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if not assignment:
                        continue
                    
                    teacher = assignment.teacher or school.get_assigned_teacher(
                        assignment.subject, class_ref
                    )
                    
                    if teacher and self.absence_loader.is_teacher_absent(
                        teacher.name, day, period
                    ):
                        if not schedule.is_locked(time_slot, class_ref):
                            # テスト期間の場合は移動をスキップ
                            if self.test_period_protector.is_test_period(time_slot):
                                self.logger.info(
                                    f"テスト期間のため教員不在違反を無視: {time_slot} {class_ref} "
                                    f"{assignment.subject.name}({teacher.name})"
                                )
                                continue
                            
                            assignments_to_move.append(
                                (time_slot, class_ref, assignment)
                            )
        
        # 移動を試みる
        for time_slot, class_ref, assignment in assignments_to_move:
            schedule.remove_assignment(time_slot, class_ref)
            
            if self._try_move_assignment(
                schedule, school, class_ref, assignment
            ):
                moved_count += 1
            else:
                removed_count += 1
                self.logger.warning(
                    f"教員不在授業を削除: {time_slot} {class_ref} "
                    f"{assignment.subject}({assignment.teacher})"
                )
        
        return removed_count, moved_count
    
    def _try_move_assignment(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        assignment: Assignment
    ) -> bool:
        """割り当てを別の時間枠に移動を試みる"""
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 利用可能性チェック
                if not self._is_slot_available_for_move(
                    schedule, school, time_slot, class_ref, assignment
                ):
                    continue
                
                # 移動実行
                schedule.assign(time_slot, assignment)
                self.logger.info(
                    f"教員不在授業を移動: {class_ref} {assignment.subject} → "
                    f"{time_slot}"
                )
                return True
        
        return False
    
    def _is_slot_available_for_move(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        assignment: Assignment
    ) -> bool:
        """スロットが移動先として利用可能かチェック"""
        # 特別な時間枠はスキップ
        if (time_slot.day == "月" and time_slot.period == 6) or \
           (time_slot.day in ["火", "水", "金"] and time_slot.period == 6):
            return False
        
        # 既に授業がある場合はスキップ
        if schedule.get_assignment(time_slot, class_ref):
            return False
        
        # ロックされている場合はスキップ
        if schedule.is_locked(time_slot, class_ref):
            return False
        
        # 教員が利用可能かチェック
        if assignment.teacher:
            if self.absence_loader.is_teacher_absent(
                assignment.teacher.name, time_slot.day, time_slot.period
            ):
                return False
            
            # 教員の重複チェック
            for other_class in school.get_all_classes():
                if other_class != class_ref:
                    other_assignment = schedule.get_assignment(time_slot, other_class)
                    if other_assignment and \
                       other_assignment.teacher == assignment.teacher:
                        return False
        
        return True
    
    def _fix_gym_violations(self, schedule: Schedule, school: School) -> int:
        """体育館使用制約違反を修正"""
        removed_count = 0
        
        # 交流学級と親学級のマッピング
        exchange_parent_map = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # PEクラスを収集
                pe_classes = []
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        pe_classes.append(
                            (class_ref, assignment, 
                             schedule.is_locked(time_slot, class_ref))
                        )
                
                # PEグループをカウント（交流学級と親学級は1グループとして数える）
                pe_groups = []
                counted_classes = set()
                
                for class_ref, assignment, is_locked in pe_classes:
                    if class_ref in counted_classes:
                        continue
                    
                    # 交流学級の場合
                    if class_ref in exchange_parent_map:
                        parent_class = exchange_parent_map[class_ref]
                        # 親学級も保健体育をしているか確認
                        parent_has_pe = any(c == parent_class for c, _, _ in pe_classes)
                        if parent_has_pe:
                            # 交流学級と親学級を同じグループとして追加
                            group_classes = [class_ref, parent_class]
                            group_assignments = [(c, a, l) for c, a, l in pe_classes if c in group_classes]
                            pe_groups.append(group_assignments)
                            counted_classes.update(group_classes)
                        else:
                            # 親学級が保健体育でない場合は別グループ
                            pe_groups.append([(class_ref, assignment, is_locked)])
                            counted_classes.add(class_ref)
                    # 親学級の場合
                    elif class_ref in exchange_parent_map.values():
                        # 対応する交流学級を探す
                        exchange_class = None
                        for exc, par in exchange_parent_map.items():
                            if par == class_ref:
                                exchange_class = exc
                                break
                        
                        if exchange_class and exchange_class not in counted_classes:
                            # 交流学級も保健体育をしているか確認
                            exchange_has_pe = any(c == exchange_class for c, _, _ in pe_classes)
                            if exchange_has_pe:
                                # 交流学級と親学級を同じグループとして追加
                                group_classes = [class_ref, exchange_class]
                                group_assignments = [(c, a, l) for c, a, l in pe_classes if c in group_classes]
                                pe_groups.append(group_assignments)
                                counted_classes.update(group_classes)
                            else:
                                # 交流学級が保健体育でない場合は別グループ
                                pe_groups.append([(class_ref, assignment, is_locked)])
                                counted_classes.add(class_ref)
                        elif class_ref not in counted_classes:
                            pe_groups.append([(class_ref, assignment, is_locked)])
                            counted_classes.add(class_ref)
                    # 通常クラスの場合
                    else:
                        pe_groups.append([(class_ref, assignment, is_locked)])
                        counted_classes.add(class_ref)
                
                if len(pe_groups) <= 1:
                    continue
                
                # テスト期間中の体育を検出
                if self.test_period_protector.is_test_period(time_slot) and len(pe_groups) > 1:
                    self.logger.info(
                        f"テスト期間中の体育を保護: {day}曜{period}限に{len(pe_groups)}グループの体育"
                    )
                
                # 5組の合同体育かチェック
                grade5_classes = [c for group in pe_groups for c, _, _ in group if c.class_number == 5]
                non_grade5_classes = [c for group in pe_groups for c, _, _ in group if c.class_number != 5]
                
                if len(grade5_classes) == 3 and len(non_grade5_classes) == 0:
                    self.logger.info(
                        f"{day}曜{period}校時: 5組合同体育を検出（制約違反なし）"
                    )
                    continue
                
                # 制約違反を処理
                self.logger.warning(
                    f"体育館使用制約違反を検出: {day}曜{period}校時に"
                    f"{len(pe_groups)}グループが保健体育"
                )
                
                # ロックされているグループを優先的に残す
                # グループ内に1つでもロックされたクラスがあればそのグループを優先
                pe_groups.sort(key=lambda group: (not any(l for _, _, l in group), str(group[0][0])))
                
                # 2つ目以降のグループを削除
                for i in range(1, len(pe_groups)):
                    for class_ref, _, is_locked in pe_groups[i]:
                        if not is_locked:
                            # テスト期間の場合は削除をスキップ
                            if self.test_period_protector.is_test_period(time_slot):
                                self.logger.info(
                                    f"テスト期間のため体育館制約違反を無視: {day}曜{period}校時 "
                                    f"{class_ref} 保健体育"
                                )
                                continue
                            
                            schedule.remove_assignment(time_slot, class_ref)
                            removed_count += 1
                            self.logger.info(
                                f"体育館制約違反を削除: {day}曜{period}校時 "
                                f"{class_ref} 保健体育"
                            )
        
        return removed_count
    
    def _fix_forbidden_cell_violations(
        self,
        schedule: Schedule,
        school: School,
        forbidden_cells: Dict[Tuple[TimeSlot, ClassReference], Set[str]]
    ) -> int:
        """セル配置禁止違反を修正"""
        fixed_count = 0
        
        for (time_slot, class_ref), forbidden_subjects in forbidden_cells.items():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name in forbidden_subjects:
                # 制約違反を検出
                self.logger.warning(
                    f"セル配置禁止違反を検出: {class_ref}の{time_slot}に"
                    f"{assignment.subject.name}（非{assignment.subject.name}指定）"
                )
                
                # ロックされていない場合のみ修正
                if not schedule.is_locked(time_slot, class_ref):
                    # テスト期間の場合は削除をスキップ
                    if self.test_period_protector.is_test_period(time_slot):
                        self.logger.info(
                            f"テスト期間のためセル配置禁止違反を無視: {class_ref}の{time_slot}に"
                            f"{assignment.subject.name}（非{assignment.subject.name}指定）"
                        )
                        continue
                    
                    schedule.remove_assignment(time_slot, class_ref)
                    
                    # 代替教科を探して配置
                    alternative = self._find_alternative_subject(
                        schedule, school, time_slot, class_ref,
                        assignment.subject.name
                    )
                    
                    if alternative:
                        schedule.assign(time_slot, alternative)
                        self.logger.info(
                            f"セル配置禁止違反を修正: {class_ref}の{time_slot} "
                            f"{assignment.subject.name} → {alternative.subject.name}"
                        )
                        fixed_count += 1
        
        return fixed_count
    
    def _find_alternative_subject(
        self,
        schedule: Schedule,
        school: School,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        forbidden_subject: str
    ) -> Optional[Assignment]:
        """代替教科を探す"""
        # 主要5教科を優先
        core_subjects = ["国", "数", "理", "社", "英"]
        
        for subject_name in core_subjects:
            if subject_name == forbidden_subject:
                continue
            
            try:
                subject = Subject(subject_name)
                if not subject.is_valid_for_class(class_ref):
                    continue
                
                teacher = school.get_assigned_teacher(subject, class_ref)
                if not teacher:
                    continue
                
                # 教員の利用可能性チェック
                if self.absence_loader.is_teacher_absent(
                    teacher.name, time_slot.day, time_slot.period
                ):
                    continue
                
                # 教員の重複チェック
                conflicting = False
                for other_class in school.get_all_classes():
                    if other_class != class_ref:
                        other_assignment = schedule.get_assignment(
                            time_slot, other_class
                        )
                        if other_assignment and \
                           other_assignment.teacher == teacher:
                            conflicting = True
                            break
                
                if not conflicting:
                    return Assignment(class_ref, subject, teacher)
                    
            except Exception:
                continue
        
        return None
    
    def _log_validation_stats(self, stats: Dict[str, int]) -> None:
        """検証結果の統計をログ出力"""
        total_fixes = sum(stats.values())
        if total_fixes > 0:
            self.logger.info(
                f"スケジュール検証完了: "
                f"教員不在削除{stats['teacher_absence_removed']}件、"
                f"教員不在移動{stats['teacher_absence_moved']}件、"
                f"体育館違反{stats['gym_violations_removed']}件、"
                f"セル禁止違反{stats['forbidden_cells_fixed']}件"
            )
"""改善版CSP生成器 - 5組優先配置と教師追跡を統合"""
import logging
import time
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

from ....domain.entities.schedule import Schedule
from ....domain.entities.school import School
from ....domain.value_objects.time_slot import TimeSlot, Subject
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.base import ConstraintPriority
from ....domain.services.core.unified_constraint_system import UnifiedConstraintSystem, AssignmentContext
from ..grade5_priority_placement_service import Grade5PriorityPlacementService
from ..exchange_class_synchronizer import ExchangeClassSynchronizer
from ....domain.utils import parse_class_reference


class ImprovedCSPGenerator:
    """
    改善版CSP時間割生成器
    
    特徴：
    1. 5組を最優先で一括配置
    2. 教師スケジュールのリアルタイム追跡
    3. 段階的な配置戦略
    4. バックトラッキングによる競合解決
    """
    
    def __init__(self, constraint_system: UnifiedConstraintSystem):
        self.logger = logging.getLogger(__name__)
        self.constraint_system = constraint_system
        self.grade5_service = Grade5PriorityPlacementService()
        self.exchange_sync = ExchangeClassSynchronizer()
        
        # 教師スケジュール追跡
        self.teacher_schedule: Dict[str, Dict[Tuple[str, int], str]] = defaultdict(dict)
        self.teacher_conflicts = []
        
        # 統計情報
        self.stats = {
            'phase1_placed': 0,  # 5組配置数
            'phase2_placed': 0,  # 交流学級配置数
            'phase3_placed': 0,  # 通常クラス配置数
            'conflicts_resolved': 0,
            'backtracks': 0
        }
    
    def generate(self, school: School, initial_schedule: Optional[Schedule] = None,
                followup_constraints: Optional[dict] = None) -> Schedule:
        """時間割を生成"""
        start_time = time.time()
        self.logger.info("=== 改善版CSP生成器による時間割生成開始 ===")
        
        # 初期スケジュールの準備
        schedule = initial_schedule if initial_schedule else Schedule()
        
        # Phase 1: 5組優先配置
        self.logger.info("Phase 1: 5組優先配置")
        self._phase1_grade5_priority(schedule, school)
        
        # Phase 2: 交流学級の自立活動配置
        self.logger.info("Phase 2: 交流学級配置")
        self._phase2_exchange_classes(schedule, school)
        
        # Phase 3: 通常クラスの配置
        self.logger.info("Phase 3: 通常クラス配置")
        self._phase3_regular_classes(schedule, school)
        
        # Phase 4: 最適化と競合解決
        self.logger.info("Phase 4: 最適化")
        self._phase4_optimization(schedule, school)
        
        # 統計情報出力
        elapsed = time.time() - start_time
        self._print_statistics(elapsed)
        
        return schedule
    
    def _phase1_grade5_priority(self, schedule: Schedule, school: School):
        """Phase 1: 5組を最優先で配置"""
        # 5組優先配置サービスを使用
        success = self.grade5_service.place_grade5_first(schedule, school)
        
        if success:
            # 配置された授業数をカウント
            count = self._count_grade5_assignments(schedule)
            self.stats['phase1_placed'] = count
            self.logger.info(f"5組に{count}個の授業を配置しました")
            
            # 教師スケジュールを更新
            self._update_teacher_schedule(schedule, ['1年5組', '2年5組', '3年5組'])
        else:
            self.logger.warning("5組の配置に一部問題がありました")
    
    def _phase2_exchange_classes(self, schedule: Schedule, school: School):
        """Phase 2: 交流学級の自立活動を配置"""
        exchange_pairs = {
            '1年6組': '1年1組',
            '1年7組': '1年2組',
            '2年6組': '2年3組',
            '2年7組': '2年2組',
            '3年6組': '3年3組',
            '3年7組': '3年2組'
        }
        
        placed_count = 0
        
        for exchange_class, parent_class in exchange_pairs.items():
            # 週2時間の自立活動を配置
            for _ in range(2):
                slot = self._find_jiritsu_slot(schedule, school, exchange_class, parent_class)
                if slot:
                    success = self._place_jiritsu(schedule, school, slot, exchange_class, parent_class)
                    if success:
                        placed_count += 1
        
        self.stats['phase2_placed'] = placed_count
        self.logger.info(f"交流学級に{placed_count}個の自立活動を配置しました")
    
    def _phase3_regular_classes(self, schedule: Schedule, school: School):
        """Phase 3: 通常クラスの配置"""
        regular_classes = []
        
        # 通常クラスのリストを作成（5組と交流学級以外）
        for class_ref in school.get_all_classes():
            class_name = str(class_ref)
            if not (class_name.endswith('5組') or class_name.endswith('6組') or class_name.endswith('7組')):
                regular_classes.append(class_name)
        
        placed_count = 0
        
        # 各クラスの必要授業を配置
        for class_name in regular_classes:
            # 必要な授業をリストアップ
            required_subjects = self._get_required_subjects(school, class_name, schedule)
            
            # 優先順位順に配置
            for subject_name, hours in required_subjects:
                for _ in range(hours):
                    slot = self._find_best_slot(schedule, school, class_name, subject_name)
                    if slot:
                        success = self._place_assignment(
                            schedule, school, slot, class_name, subject_name
                        )
                        if success:
                            placed_count += 1
        
        self.stats['phase3_placed'] = placed_count
        self.logger.info(f"通常クラスに{placed_count}個の授業を配置しました")
    
    def _phase4_optimization(self, schedule: Schedule, school: School):
        """Phase 4: 最適化と競合解決"""
        # 教師重複の検出と解決
        conflicts = self._detect_teacher_conflicts(schedule, school)
        
        if conflicts:
            self.logger.info(f"{len(conflicts)}個の教師重複を検出しました")
            resolved = self._resolve_conflicts(schedule, school, conflicts)
            self.stats['conflicts_resolved'] = resolved
            self.logger.info(f"{resolved}個の競合を解決しました")
    
    def _count_grade5_assignments(self, schedule: Schedule) -> int:
        """5組の配置数をカウント"""
        count = 0
        grade5_classes = ['1年5組', '2年5組', '3年5組']
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組のいずれかに授業があるかチェック
                for class_name in grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_name)
                    if assignment and assignment.subject:
                        count += 1
                        break
        
        return count
    
    def _update_teacher_schedule(self, schedule: Schedule, classes: List[str]):
        """教師スケジュールを更新"""
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_name in classes:
                    class_ref = parse_class_reference(class_name)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        key = (day, period)
                        teacher_name = assignment.teacher.name
                        if key in self.teacher_schedule[teacher_name]:
                            # 既存の割り当てがある場合
                            existing = self.teacher_schedule[teacher_name][key]
                            if existing != class_name:
                                # 5組の合同授業でない限り競合
                                if not (class_name.endswith('5組') and existing.endswith('5組')):
                                    self.teacher_conflicts.append({
                                        'teacher': teacher_name,
                                        'time': time_slot,
                                        'classes': [existing, class_name]
                                    })
                        else:
                            self.teacher_schedule[teacher_name][key] = class_name
    
    def _find_jiritsu_slot(self, schedule: Schedule, school: School,
                          exchange_class: str, parent_class: str) -> Optional[TimeSlot]:
        """自立活動に適したスロットを探す"""
        best_slots = []
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 6):  # 6限は除外
                time_slot = TimeSlot(day, period)
                
                # 親学級の授業を確認
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                if parent_assignment and parent_assignment.subject:
                    # 数学または英語の時のみ
                    if parent_assignment.subject.name in ['数', '英']:
                        # 交流学級が空いているか確認
                        exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                        if not exchange_assignment or not exchange_assignment.subject:
                            # 教師の可用性チェック
                            if self._is_teacher_available(time_slot, '財津') or \
                               self._is_teacher_available(time_slot, '智田'):
                                best_slots.append((time_slot, self._calculate_slot_score(time_slot, schedule)))
        
        # スコアの高い順にソート
        best_slots.sort(key=lambda x: x[1], reverse=True)
        
        return best_slots[0][0] if best_slots else None
    
    def _is_teacher_available(self, time_slot: TimeSlot, teacher_name: str) -> bool:
        """教師が利用可能かチェック"""
        key = (time_slot.day, time_slot.period)
        return key not in self.teacher_schedule.get(teacher_name, {})
    
    def _place_jiritsu(self, schedule: Schedule, school: School,
                      time_slot: TimeSlot, exchange_class: str, parent_class: str) -> bool:
        """自立活動を配置"""
        try:
            # 適切な教師を選択
            teacher_name = '財津' if exchange_class.endswith('6組') else '智田'
            
            class_ref = parse_class_reference(exchange_class)
            subject = Subject('自立')
            teacher = None
            # 教師を探す
            for t in school.get_all_teachers():
                if t.name == teacher_name:
                    teacher = t
                    break
            
            assignment = Assignment(
                class_ref=class_ref,
                subject=subject,
                teacher=teacher
            )
            
            # 配置
            schedule.assign(time_slot, assignment)
            
            # 教師スケジュール更新
            key = (time_slot.day, time_slot.period)
            self.teacher_schedule[teacher_name][key] = exchange_class
            
            return True
            
        except Exception as e:
            self.logger.debug(f"自立活動配置失敗: {e}")
            return False
    
    def _get_required_subjects(self, school: School, class_name: str, 
                              schedule: Schedule) -> List[Tuple[str, int]]:
        """必要な授業をリストアップ（既配置分を除く）"""
        required = []
        
        # クラスを取得
        class_ref = None
        for c in school.get_all_classes():
            if str(c) == class_name:
                class_ref = c
                break
        
        if not class_ref:
            return required
        
        # 標準時数を取得
        standard_hours = school.get_all_standard_hours(class_ref)
        
        # 既に配置された時数をカウント
        placed_hours = defaultdict(int)
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_name)
                if assignment and assignment.subject:
                    placed_hours[assignment.subject.name] += 1
        
        # 必要な残り時数を計算
        for subject, hours in standard_hours.items():
            if subject.name not in ['欠', 'YT', '学活', '学', '道', '道徳', '総', '総合', '学総']:
                remaining = int(hours) - placed_hours[subject.name]
                if remaining > 0:
                    required.append((subject.name, remaining))
        
        # 優先順位でソート（主要教科優先）
        priority_order = ['国', '数', '英', '理', '社']
        required.sort(key=lambda x: priority_order.index(x[0]) if x[0] in priority_order else 100)
        
        return required
    
    def _find_best_slot(self, schedule: Schedule, school: School,
                       class_name: str, subject_name: str) -> Optional[TimeSlot]:
        """最適なスロットを探す"""
        candidates = []
        
        for day in ['月', '火', '水', '木', '金']:
            # 同じ日に同じ科目がないかチェック
            if self._has_subject_on_day(schedule, class_name, day, subject_name):
                continue
                
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # スロットが空いているか確認
                assignment = schedule.get_assignment(time_slot, class_name)
                if assignment and assignment.subject:
                    continue
                
                # 教師の可用性確認
                subject = Subject(subject_name)
                teachers = school.get_subject_teachers(subject)
                available_teacher = None
                
                for teacher in teachers:
                    if self._is_teacher_available(time_slot, teacher.name):
                        available_teacher = teacher
                        break
                
                if available_teacher:
                    score = self._calculate_slot_score(time_slot, schedule)
                    candidates.append((time_slot, score, available_teacher))
        
        # スコアの高い順にソート
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[0][0] if candidates else None
    
    def _has_subject_on_day(self, schedule: Schedule, class_name: str,
                           day: str, subject_name: str) -> bool:
        """特定の日に科目が既に配置されているか"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_name)
            if assignment and assignment.subject and assignment.subject.name == subject_name:
                return True
        return False
    
    def _calculate_slot_score(self, time_slot: TimeSlot, schedule: Schedule) -> float:
        """スロットのスコアを計算"""
        score = 100.0
        
        # 午前中優遇
        if time_slot.period <= 3:
            score += 20.0
        
        # 月曜1限と金曜6限は避ける
        if (time_slot.day == '月' and time_slot.period == 1):
            score -= 30.0
        if (time_slot.day == '金' and time_slot.period == 6):
            score -= 20.0
            
        return score
    
    def _place_assignment(self, schedule: Schedule, school: School,
                         time_slot: TimeSlot, class_name: str, subject_name: str) -> bool:
        """授業を配置"""
        try:
            # 利用可能な教師を探す
            subject = Subject(subject_name)
            teachers = school.get_subject_teachers(subject)
            
            for teacher in teachers:
                if self._is_teacher_available(time_slot, teacher.name):
                    class_ref = parse_class_reference(class_name)
                    assignment = Assignment(
                        class_ref=class_ref,
                        subject=subject,
                        teacher=teacher
                    )
                    
                    # 配置
                    schedule.assign(time_slot, assignment)
                    
                    # 教師スケジュール更新
                    key = (time_slot.day, time_slot.period)
                    self.teacher_schedule[teacher.name][key] = class_name
                    
                    # 交流学級の同期
                    self.exchange_sync.sync_if_needed(schedule, time_slot, class_name)
                    
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.debug(f"配置失敗: {class_name} {subject_name} - {e}")
            return False
    
    def _detect_teacher_conflicts(self, schedule: Schedule, school: School) -> List[Dict]:
        """教師重複を検出"""
        conflicts = []
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                teacher_assignments = defaultdict(list)
                
                # 全クラスの割り当てを確認
                for class_ref in school.get_all_classes():
                    class_name = str(class_ref)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and assignment.teacher:
                        teacher_assignments[assignment.teacher.name].append(class_name)
                
                # 重複を検出
                for teacher, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        if not all(c.endswith('5組') for c in classes):
                            conflicts.append({
                                'teacher': teacher,
                                'time': time_slot,
                                'classes': classes
                            })
        
        return conflicts
    
    def _resolve_conflicts(self, schedule: Schedule, school: School,
                          conflicts: List[Dict]) -> int:
        """競合を解決"""
        resolved = 0
        
        for conflict in conflicts:
            # バックトラッキングによる解決を試みる
            if self._backtrack_resolve(schedule, school, conflict):
                resolved += 1
                self.stats['backtracks'] += 1
        
        return resolved
    
    def _backtrack_resolve(self, schedule: Schedule, school: School,
                          conflict: Dict) -> bool:
        """バックトラッキングで競合を解決"""
        # 簡単な実装：競合するクラスの一つを別のスロットに移動
        time_slot = conflict['time']
        classes = conflict['classes']
        
        # 最初のクラス以外を移動対象とする
        for class_name in classes[1:]:
            class_ref = parse_class_reference(class_name)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                # 一時的に削除
                schedule.remove_assignment(time_slot, class_ref)
                
                # 別のスロットを探す
                new_slot = self._find_best_slot(
                    schedule, school, class_name, assignment.subject.name
                )
                
                if new_slot:
                    # 新しいスロットに配置
                    success = self._place_assignment(
                        schedule, school, new_slot, class_name, assignment.subject.name
                    )
                    if success:
                        return True
                
                # 失敗したら元に戻す
                schedule.assign(time_slot, assignment)
        
        return False
    
    def _print_statistics(self, elapsed_time: float):
        """統計情報を出力"""
        self.logger.info("=== 生成統計 ===")
        self.logger.info(f"Phase 1 (5組): {self.stats['phase1_placed']}個配置")
        self.logger.info(f"Phase 2 (交流学級): {self.stats['phase2_placed']}個配置")
        self.logger.info(f"Phase 3 (通常クラス): {self.stats['phase3_placed']}個配置")
        self.logger.info(f"競合解決: {self.stats['conflicts_resolved']}個")
        self.logger.info(f"バックトラック: {self.stats['backtracks']}回")
        self.logger.info(f"生成時間: {elapsed_time:.2f}秒")
"""配置戦略クラス群

各種科目の配置戦略を個別のクラスとして実装。
単一責任原則に従い、それぞれの戦略は特定の配置ロジックのみを担当。
"""
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict
import logging

from ....domain.entities import School, Schedule
from ....domain.value_objects.time_slot import TimeSlot, ClassReference as ClassRef, Subject, Teacher
from ....domain.value_objects.assignment import Assignment
from ....domain.constraints.base import Constraint
from .schedule_helpers import ScheduleHelpers
from .metadata_collector import MetadataCollector

logger = logging.getLogger(__name__)


class BaseStrategy:
    """配置戦略の基底クラス"""
    
    def __init__(self, helpers: ScheduleHelpers, metadata: MetadataCollector):
        self.helpers = helpers
        self.metadata = metadata
        self.placed_count = 0
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """戦略を実行（サブクラスで実装）"""
        raise NotImplementedError


class TestPeriodProtectionStrategy(BaseStrategy):
    """テスト期間保護戦略"""
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """テスト期間の科目を保護"""
        test_subjects = {
            ("月", "1"): {"1": "英", "2": "数", "3": "国"},
            ("月", "2"): {"1": "保", "2": "技家", "3": "音"},
            ("月", "3"): {"1": "技家", "2": "社", "3": "理"},
            ("火", "1"): {"1": "社", "2": "国", "3": "数"},
            ("火", "2"): {"1": "音", "2": "保", "3": "英"},
            ("火", "3"): {"1": "国", "2": "理", "3": "技家"},
            ("水", "1"): {"1": "理", "2": "英", "3": "保"},
            ("水", "2"): {"1": "数", "2": "音", "3": "社"}
        }
        
        # テスト期間の監督教師マッピング（学年ごとに監督教師を設定）
        test_supervisors = {
            "1": {"英": "井野口", "保": "野口", "技家": "池田", "社": "梶永", "音": "山口", "国": "塚本", "理": "永山", "数": "永山"},
            "2": {"数": "井上", "技家": "池田", "社": "北", "国": "塚本", "保": "野口", "理": "永山", "英": "小野塚", "音": "山口"},
            "3": {"国": "塚本", "音": "山口", "理": "福山", "数": "小野塚", "英": "林", "技家": "池田", "保": "野口", "社": "北"}
        }
        
        self.placed_count = 0
        for (day, period), grade_subjects in test_subjects.items():
            for class_ref in school.get_all_classes():
                # 5組は除外
                if class_ref.class_number == 5:
                    continue
                
                grade_str = str(class_ref.grade)
                if grade_str in grade_subjects:
                    subject = grade_subjects[grade_str]
                    time_slot = TimeSlot(day=day, period=int(period))
                    
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, class_ref):
                        logger.debug(f"スキップ（ロック済み）: {time_slot} - {class_ref}")
                        continue
                    
                    # 既存の割り当てを確認
                    existing = schedule.get_assignment(time_slot, class_ref)
                    if not existing or existing.subject.name != subject:
                        # テスト期間中は同じ学年の同じ科目には同じ教師を配置
                        supervisor_name = test_supervisors.get(grade_str, {}).get(subject)
                        if supervisor_name:
                            # 教師オブジェクトを検索
                            teacher = None
                            for t in school.get_all_teachers():
                                if t.name == supervisor_name:
                                    teacher = t
                                    break
                        else:
                            # 監督教師が指定されていない場合は通常の教師検索
                            teacher = self.helpers.find_teacher_for_subject(
                                school, class_ref, subject, time_slot
                            )
                        
                        if teacher:
                            assignment = Assignment(
                                class_ref=class_ref,
                                subject=Subject(subject),
                                teacher=teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                self.placed_count += 1
                                logger.debug(f"テスト配置: {class_ref} {time_slot} {subject} - {teacher.name}")
                            except Exception as e:
                                logger.warning(f"テスト期間配置エラー: {e}")
        
        logger.info(f"テスト期間保護: {self.placed_count}スロット")
        return self.placed_count


class FixedSubjectPlacementStrategy(BaseStrategy):
    """固定科目配置戦略"""
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """固定科目を配置"""
        self.placed_count = 0
        
        # 月曜6限は全クラス「欠」
        self._place_fixed_subject(schedule, school, "月", 6, "欠")
        
        # 金曜6限も全クラス「欠」
        self._place_fixed_subject(schedule, school, "金", 6, "欠")
        
        logger.info(f"固定科目配置: {self.placed_count}スロット")
        return self.placed_count
    
    def _place_fixed_subject(self, schedule: Schedule, school: School,
                            day: str, period: int, subject: str):
        """特定の時間に固定科目を配置"""
        for class_ref in school.get_all_classes():
            time_slot = TimeSlot(day=day, period=period)
            
            # ロックされている場合はスキップ
            if schedule.is_locked(time_slot, class_ref):
                continue
            
            if not schedule.get_assignment(time_slot, class_ref):
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=Subject(subject),
                    teacher=None
                )
                try:
                    schedule.assign(time_slot, assignment)
                    self.placed_count += 1
                except Exception as e:
                    logger.warning(f"固定科目配置エラー: {e}")


class JiritsuPlacementStrategy(BaseStrategy):
    """自立活動配置戦略"""
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """自立活動を戦略的に配置"""
        jiritsu_requirements = {
            "1-6": 2, "1-7": 2, "2-6": 2, "2-7": 2, "3-6": 2, "3-7": 2
        }
        
        self.placed_count = 0
        for class_name, required_hours in jiritsu_requirements.items():
            class_ref = self.helpers.get_class_ref(school, class_name)
            if not class_ref:
                continue
            
            parent_class_name = self.metadata.exchange_parent_map.get(class_name)
            parent_class_ref = self.helpers.get_class_ref(school, parent_class_name)
            
            # 既存の自立活動をカウント
            existing_jiritsu = self._count_existing_jiritsu(schedule, class_ref)
            
            # 不足分を配置
            needed = required_hours - existing_jiritsu
            if needed > 0:
                suitable_slots = self._find_jiritsu_slots(
                    schedule, school, class_ref, parent_class_ref, needed
                )
                
                for time_slot in suitable_slots[:needed]:
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    teacher = self._find_jiritsu_teacher(school, class_ref)
                    if teacher:
                        assignment = Assignment(
                            class_ref=class_ref,
                            subject=Subject("自立"),
                            teacher=teacher
                        )
                        try:
                            schedule.assign(time_slot, assignment)
                            self.placed_count += 1
                        except Exception as e:
                            logger.warning(f"自立活動配置エラー: {e}")
        
        logger.info(f"自立活動配置: {self.placed_count}スロット")
        return self.placed_count
    
    def _count_existing_jiritsu(self, schedule: Schedule, class_ref: ClassRef) -> int:
        """既存の自立活動をカウント"""
        count = 0
        for time_slot in self.helpers.get_all_time_slots():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == "自立":
                count += 1
        return count
    
    def _find_jiritsu_slots(self, schedule: Schedule, school: School,
                           exchange_class: ClassRef, parent_class: ClassRef,
                           needed: int) -> List[TimeSlot]:
        """自立活動に適したスロットを見つける"""
        suitable_slots = []
        
        for time_slot in self.helpers.get_all_time_slots():
            # テスト期間は除外
            if self.metadata.is_test_period(time_slot.day, str(time_slot.period)):
                continue
            
            # 既に割り当てがある場合は除外
            if schedule.get_assignment(time_slot, exchange_class):
                continue
            
            # 親学級の科目を確認
            parent_assignment = schedule.get_assignment(time_slot, parent_class)
            if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                suitable_slots.append(time_slot)
        
        return suitable_slots
    
    def _find_jiritsu_teacher(self, school: School, class_ref: ClassRef) -> Optional[Teacher]:
        """自立活動の教師を見つける"""
        jiritsu_teachers = {
            "1-6": "財津", "1-7": "智田",
            "2-6": "財津", "2-7": "智田",
            "3-6": "財津", "3-7": "智田"
        }
        class_name = f"{class_ref.grade}-{class_ref.class_number}"
        teacher_name = jiritsu_teachers.get(class_name)
        if teacher_name:
            for teacher in school.get_all_teachers():
                if teacher.name == teacher_name:
                    return teacher
        return None


class Grade5SynchronizationStrategy(BaseStrategy):
    """5組同期配置戦略"""
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """5組の完全同期配置"""
        grade5_classes = [
            self.helpers.get_class_ref(school, "1-5"),
            self.helpers.get_class_ref(school, "2-5"),
            self.helpers.get_class_ref(school, "3-5")
        ]
        
        # 必要時数の定義
        required_hours = {
            "国": 4, "社": 1, "数": 4, "理": 3, "音": 1,
            "美": 1, "保": 2, "技": 1, "家": 1, "英": 2,
            "道": 1, "総": 1, "自立": 3, "日生": 1, "作業": 1
        }
        
        self.placed_count = 0
        for subject, hours in required_hours.items():
            # 既存の配置をカウント
            existing_hours = self._count_existing_grade5_hours(
                schedule, grade5_classes, subject
            )
            
            # 不足分を配置
            needed = hours - existing_hours
            if needed > 0:
                available_slots = self._find_grade5_slots(
                    schedule, school, grade5_classes, subject, needed
                )
                
                for time_slot in available_slots[:needed]:
                    teacher = self._find_grade5_teacher(school, subject)
                    if teacher:
                        # 全ての5組クラスがロックされていないかチェック
                        all_unlocked = all(
                            not schedule.is_locked(time_slot, cls)
                            for cls in grade5_classes if cls
                        )
                        
                        if all_unlocked:
                            for class_ref in grade5_classes:
                                if class_ref:
                                    assignment = Assignment(
                                        class_ref=class_ref,
                                        subject=Subject(subject),
                                        teacher=teacher
                                    )
                                    try:
                                        schedule.assign(time_slot, assignment)
                                        self.placed_count += 1
                                    except Exception as e:
                                        logger.warning(f"5組配置エラー: {e}")
        
        logger.info(f"5組同期配置: {self.placed_count}スロット")
        return self.placed_count
    
    def _count_existing_grade5_hours(self, schedule: Schedule,
                                    grade5_classes: List[ClassRef],
                                    subject: str) -> int:
        """既存の5組時数をカウント"""
        count = 0
        for time_slot in self.helpers.get_all_time_slots():
            if all(schedule.get_assignment(time_slot, cls) and 
                   schedule.get_assignment(time_slot, cls).subject.name == subject
                   for cls in grade5_classes if cls):
                count += 1
        return count
    
    def _find_grade5_slots(self, schedule: Schedule, school: School,
                          grade5_classes: List[ClassRef], subject: str,
                          needed: int) -> List[TimeSlot]:
        """5組に適したスロットを見つける"""
        suitable_slots = []
        
        for time_slot in self.helpers.get_all_time_slots():
            # 全ての5組クラスで空いているかチェック
            if all(not schedule.get_assignment(time_slot, cls) 
                   for cls in grade5_classes if cls):
                
                # 教師が利用可能かチェック
                teacher = self._find_grade5_teacher(school, subject)
                if teacher and not self.metadata.is_teacher_absent(
                    teacher.name, time_slot.day, str(time_slot.period)
                ):
                    suitable_slots.append(time_slot)
                    
                    if len(suitable_slots) >= needed:
                        break
        
        return suitable_slots
    
    def _find_grade5_teacher(self, school: School, subject: str) -> Optional[Teacher]:
        """5組の教科担当教師を見つける"""
        grade5_teachers = {
            "国": "寺田", "社": "蒲地", "数": "梶永", "理": "智田",
            "音": "塚本", "美": "金子み", "保": "野口", "技": "林",
            "家": "金子み", "英": "林田", "道": "金子み", "総": "金子み",
            "自立": "金子み", "日生": "金子み", "作業": "金子み"
        }
        teacher_name = grade5_teachers.get(subject)
        if teacher_name:
            for teacher in school.get_all_teachers():
                if teacher.name == teacher_name:
                    return teacher
        return None


class RegularSubjectPlacementStrategy(BaseStrategy):
    """通常科目配置戦略"""
    
    def __init__(self, helpers: ScheduleHelpers, metadata: MetadataCollector,
                 constraints: List[Constraint]):
        super().__init__(helpers, metadata)
        self.constraints = constraints
        self.critical_constraints = [c for c in constraints 
                                   if hasattr(c, 'priority') and 
                                   c.priority.name == 'CRITICAL']
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """通常科目の配置（制約違反ゼロを目指す）"""
        # 各クラスの必要時数を計算
        placement_tasks = []
        
        for class_ref in school.get_all_classes():
            required_hours = self._get_required_hours(school, class_ref)
            current_hours = self._count_current_hours(schedule, class_ref)
            
            for subject, required in required_hours.items():
                current = current_hours.get(subject, 0)
                if current < required:
                    needed = required - current
                    placement_tasks.append({
                        'class_ref': class_ref,
                        'subject': subject,
                        'needed': needed,
                        'priority': self._get_subject_priority(subject)
                    })
        
        # 優先度順にソート
        placement_tasks.sort(key=lambda x: (-x['priority'], -x['needed']))
        
        # 配置実行
        self.placed_count = 0
        for task in placement_tasks:
            for _ in range(task['needed']):
                time_slot = self._find_best_slot(
                    schedule, school, task['class_ref'], task['subject']
                )
                if time_slot:
                    teacher = self.helpers.find_teacher_for_subject(
                        school, task['class_ref'], task['subject'], time_slot
                    )
                    if teacher:
                        assignment = Assignment(
                            class_ref=task['class_ref'],
                            subject=Subject(task['subject']),
                            teacher=teacher
                        )
                        if self._is_assignment_valid(schedule, school, time_slot, assignment):
                            # ロックされている場合はスキップ
                            if schedule.is_locked(time_slot, task['class_ref']):
                                continue
                            
                            try:
                                schedule.assign(time_slot, assignment)
                                self.placed_count += 1
                                
                                # 交流学級も同期
                                self._sync_if_parent_class(
                                    schedule, school, task['class_ref'], 
                                    time_slot, task['subject'], teacher
                                )
                            except Exception as e:
                                logger.debug(f"配置エラー: {e}")
        
        logger.info(f"通常科目配置: {self.placed_count}スロット")
        return self.placed_count
    
    def _get_required_hours(self, school: School, class_ref: ClassRef) -> Dict[str, int]:
        """クラスの必要時数を取得"""
        if class_ref.class_number == 5:
            return {
                "国": 4, "社": 1, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 2, "技": 1, "家": 1, "英": 2,
                "道": 1, "総": 1, "自立": 3, "日生": 1, "作業": 1
            }
        else:
            base_hours = {
                "国": 4, "社": 3, "数": 4, "理": 3, "音": 1,
                "美": 1, "保": 3, "技": 1, "家": 1, "英": 4,
                "道": 1, "学": 1, "総": 1
            }
            # 学年による調整
            if class_ref.grade == 2:
                base_hours["技家"] = 1
                base_hours["技"] = 0
                base_hours["家"] = 0
                base_hours["総"] = 2
            elif class_ref.grade == 3:
                base_hours["国"] = 3
                base_hours["社"] = 4
                base_hours["技"] = 0
                base_hours["家"] = 0
                base_hours["総"] = 2
                
            return base_hours
    
    def _count_current_hours(self, schedule: Schedule, class_ref: ClassRef) -> Dict[str, int]:
        """現在の配置時数をカウント"""
        hours = defaultdict(int)
        for time_slot in self.helpers.get_all_time_slots():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject:
                hours[assignment.subject.name] += 1
        return dict(hours)
    
    def _get_subject_priority(self, subject: str) -> int:
        """教科の優先度を取得"""
        priority_map = {
            "数": 90, "英": 90, "国": 85, "理": 80, "社": 80,
            "保": 70, "音": 60, "美": 60, "技": 60, "家": 60,
            "道": 50, "総": 50, "学": 50
        }
        return priority_map.get(subject, 40)
    
    def _find_best_slot(self, schedule: Schedule, school: School,
                       class_ref: ClassRef, subject: str) -> Optional[TimeSlot]:
        """最適なスロットを見つける"""
        candidates = []
        
        for time_slot in self.helpers.get_all_time_slots():
            # 既に割り当てがある場合はスキップ
            if schedule.get_assignment(time_slot, class_ref):
                continue
            
            # スコアを計算
            score = self._calculate_slot_score(
                schedule, school, class_ref, time_slot, subject
            )
            
            if score > 0:
                candidates.append((time_slot, score))
        
        # スコアの高い順にソート
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 最高スコアのスロットを返す
        return candidates[0][0] if candidates else None
    
    def _calculate_slot_score(self, schedule: Schedule, school: School,
                             class_ref: ClassRef, time_slot: TimeSlot,
                             subject: str) -> float:
        """スロットのスコアを計算"""
        score = 100.0
        
        # 日内重複チェック
        if self.helpers.would_create_daily_duplicate(schedule, class_ref, time_slot, subject):
            return 0.0
        
        # 教師の可用性チェック
        teacher = self.helpers.find_teacher_for_subject(school, class_ref, subject, time_slot)
        if not teacher:
            return 0.0
        
        # 教師の負荷を考慮
        teacher_load = self.helpers.calculate_teacher_load(schedule, teacher, time_slot)
        score -= teacher_load * 10
        
        # 体育館使用の場合
        if subject == "保":
            gym_usage = self.helpers.count_gym_usage(schedule, time_slot)
            if gym_usage > 0:
                score -= gym_usage * 20
        
        # 連続授業のボーナス
        if self._has_adjacent_same_subject(schedule, class_ref, time_slot, subject):
            score += 5
        
        return max(0, score)
    
    def _has_adjacent_same_subject(self, schedule: Schedule, class_ref: ClassRef,
                                  time_slot: TimeSlot, subject: str) -> bool:
        """隣接する時間に同じ科目があるかチェック"""
        # 前の時間
        if time_slot.period > 1:
            prev_slot = TimeSlot(day=time_slot.day, period=time_slot.period - 1)
            prev_assignment = schedule.get_assignment(prev_slot, class_ref)
            if prev_assignment and prev_assignment.subject.name == subject:
                return True
        
        # 次の時間
        if time_slot.period < 6:
            next_slot = TimeSlot(day=time_slot.day, period=time_slot.period + 1)
            next_assignment = schedule.get_assignment(next_slot, class_ref)
            if next_assignment and next_assignment.subject.name == subject:
                return True
        
        return False
    
    def _is_assignment_valid(self, schedule: Schedule, school: School,
                           time_slot: TimeSlot, assignment: Assignment) -> bool:
        """割り当てが有効かチェック"""
        # CRITICAL制約のみチェック（パフォーマンスのため）
        for constraint in self.critical_constraints:
            if hasattr(constraint, 'check') and not constraint.check(
                schedule, school, time_slot, assignment
            ):
                return False
        return True
    
    def _sync_if_parent_class(self, schedule: Schedule, school: School,
                             class_ref: ClassRef, time_slot: TimeSlot,
                             subject: str, teacher: Teacher):
        """親学級の場合、交流学級も同期"""
        class_name = f"{class_ref.grade}-{class_ref.class_number}"
        exchange_classes = self.metadata.get_exchange_class(class_name)
        
        for exchange_name in exchange_classes:
            exchange_ref = self.helpers.get_class_ref(school, exchange_name)
            if exchange_ref:
                exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                if exchange_assignment and exchange_assignment.subject.name not in ["自立", "日生", "作業"]:
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, exchange_ref):
                        continue
                    new_assignment = Assignment(
                        class_ref=exchange_ref,
                        subject=Subject(subject),
                        teacher=teacher
                    )
                    try:
                        schedule.assign(time_slot, new_assignment)
                    except Exception as e:
                        logger.debug(f"交流学級同期エラー: {e}")


class ExchangeClassSynchronizationStrategy(BaseStrategy):
    """交流学級同期戦略"""
    
    def execute(self, schedule: Schedule, school: School) -> int:
        """交流学級の完全同期"""
        sync_count = 0
        
        for parent_name, exchange_names in self.metadata.parent_exchange_map.items():
            parent_ref = self.helpers.get_class_ref(school, parent_name)
            if not parent_ref:
                continue
            
            for exchange_name in exchange_names:
                exchange_ref = self.helpers.get_class_ref(school, exchange_name)
                if not exchange_ref:
                    continue
                
                for time_slot in self.helpers.get_all_time_slots():
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    
                    if parent_assignment and exchange_assignment:
                        # 交流学級が自立活動等でない場合は同期
                        if exchange_assignment.subject.name not in ["自立", "日生", "作業"]:
                            if (exchange_assignment.subject != parent_assignment.subject or
                                exchange_assignment.teacher != parent_assignment.teacher):
                                # 親学級と同じ内容に更新
                                # ロックされている場合はスキップ
                                if schedule.is_locked(time_slot, exchange_ref):
                                    continue
                                
                                new_assignment = Assignment(
                                    class_ref=exchange_ref,
                                    subject=parent_assignment.subject,
                                    teacher=parent_assignment.teacher
                                )
                                try:
                                    schedule.assign(time_slot, new_assignment)
                                    sync_count += 1
                                except Exception as e:
                                    logger.debug(f"交流学級同期エラー: {e}")
        
        logger.info(f"交流学級同期: {sync_count}件")
        return sync_count
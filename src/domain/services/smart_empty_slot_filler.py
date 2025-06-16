"""スマート空きコマ埋めサービス

交流学級・5組同期・教師負担・連続コマを考慮した高度な空きコマ埋めアルゴリズム。
複数のパスを通じて段階的に制約を緩和しながら、すべての空きコマを埋めることを目指します。
"""
import logging
from typing import List, Set, Tuple, Optional, Dict, TYPE_CHECKING
import random
from collections import defaultdict

from ..entities.schedule import Schedule
from ..entities.school import School
from ..value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from ..value_objects.assignment import Assignment
from ..constraints.base import ConstraintPriority
from .unified_constraint_system import UnifiedConstraintSystem

if TYPE_CHECKING:
    from ...infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader


class SmartEmptySlotFiller:
    """スマート空きコマ埋めサービス
    
    複数パスで段階的に制約を緩和しながら空きコマを埋めるサービス。
    交流学級の同期、5組の同期、教師負担バランス、連続コマ回避などを考慮します。
    
    優先順位:
        1. 交流学級（6組、7組）を親学級と同期
        2. 5組クラス（1年5組、2年5組、3年5組）を同期
        3. 日内重複を避ける
        4. 教師負担のバランスを考慮
        5. 主要教科（国、数、理、社、英）を優先しつつ全教科の時数を確保
        6. 連続コマを避ける
        7. 特別教科（道徳、学活等）は追加しない
        
    Attributes:
        constraint_system: 制約システム
        logger: ロガー
        absence_loader: 教師不在情報ローダー
        exchange_mappings: 交流学級のマッピング情報
        grade5_classes: 5組クラスのリスト
        core_subjects: 主要教科のセット
        excluded_subjects: 除外教科のセット
        stats: 統計情報の辞書
    """
    
    def __init__(self, 
                 constraint_system: UnifiedConstraintSystem, 
                 absence_loader: Optional['TeacherAbsenceLoader'] = None) -> None:
        """SmartEmptySlotFillerを初期化
        
        Args:
            constraint_system: 統一制約システム
            absence_loader: 教師不在情報ローダー（オプション）
        """
        self.constraint_system = constraint_system
        self.logger = logging.getLogger(__name__)
        self.absence_loader = absence_loader
        
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
        self.grade5_classes = [
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        ]
        
        # 主要教科
        self.core_subjects = {"国", "数", "理", "社", "英"}
        
        # 追加しない特別教科
        self.excluded_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行"}
        
        # 禁止セル情報
        self._forbidden_cells = self._extract_forbidden_cells()
        
        # テスト期間情報
        self.test_periods = set()
        self._load_test_periods()
        
        # 統計情報
        self.stats = {
            'exchange_synced': 0,
            'grade5_synced': 0,
            'regular_filled': 0,
            'daily_duplicate_avoided': 0,
            'consecutive_avoided': 0,
            'teacher_balance_considered': 0
        }
    
    def _load_test_periods(self) -> None:
        """テスト期間情報を読み込む"""
        try:
            from ...infrastructure.parsers.natural_followup_parser import NaturalFollowUpParser
            from ...infrastructure.config.path_config import path_config
            
            parser = NaturalFollowUpParser(path_config.input_dir)
            result = parser.parse_file("Follow-up.csv")
            
            if result.get("test_periods"):
                for test_period in result["test_periods"]:
                    day = test_period.day
                    for period in test_period.periods:
                        self.test_periods.add((day, period))
                self.logger.debug(f"テスト期間を{len(self.test_periods)}スロット読み込みました")
        except Exception as e:
            self.logger.warning(f"テスト期間情報の読み込みに失敗: {e}")
    
    def fill_empty_slots_smartly(self, schedule: Schedule, school: School, max_passes: int = 3) -> int:
        """スマートに空きコマを埋める（複数パス）
        
        複数のパスを実行し、各パスで段階的に制約を緩和しながら空きコマを埋めます。
        第1パス: 厳格な制約（strict）
        第2パス: バランス重視（balanced）
        第3パス以降: 緩和モード（relaxed）→極限緩和（ultra_relaxed）→強制（forced）
        
        Args:
            schedule: 対象のスケジュール
            school: 学校情報
            max_passes: 最大パス数（デフォルト: 3）
            
        Returns:
            埋めた空きコマの総数
        """
        total_filled = 0
        
        for pass_num in range(1, max_passes + 1):
            strategy = self._get_strategy_for_pass(pass_num)
            self.logger.info(f"\n=== スマート空きコマ埋め第{pass_num}パス開始（{strategy}モード） ===")
            
            # 残り空きスロット数を確認
            empty_count = self._count_empty_slots(schedule, school)
            self.logger.info(f"残り空きスロット数: {empty_count}")
            
            if empty_count == 0:
                self.logger.info("すべての空きスロットが埋まりました！")
                break
            
            # 各パスで統計をリセット
            self.stats = {key: 0 for key in self.stats}
            
            # 1. 交流学級の同期
            filled = self._fill_exchange_classes(schedule, school)
            total_filled += filled
            
            # 2. 5組の同期
            filled = self._fill_grade5_classes(schedule, school)
            total_filled += filled
            
            # 3. 通常クラスの空きコマ埋め
            filled = self._fill_regular_classes(schedule, school, pass_num)
            total_filled += filled
            
            # 統計ログ
            self._log_statistics()
            
            if filled == 0 and strategy != "forced":
                self.logger.info(f"第{pass_num}パスで埋められるコマがなくなりました。次のパスへ...")
        
        # 最終的な空きスロット数を確認
        final_empty = self._count_empty_slots(schedule, school)
        if final_empty > 0:
            self.logger.warning(f"最終的に{final_empty}個の空きスロットが残りました")
        
        return total_filled
    
    def _fill_exchange_classes(self, schedule: Schedule, school: School) -> int:
        """交流学級の空きコマを親学級と同期して埋める"""
        filled_count = 0
        
        for exchange_class, parent_class in self.exchange_mappings.items():
            if exchange_class not in school.get_all_classes() or parent_class not in school.get_all_classes():
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 特別な時間はスキップ
                    if self._should_skip_slot(time_slot, exchange_class):
                        continue
                    
                    # 交流学級が空きかつ親学級に授業がある場合
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    if not exchange_assignment and parent_assignment:
                        # 交流学級の自立活動はスキップ
                        if parent_assignment.subject.name in ["自立", "日生", "生単", "作業"]:
                            continue
                        
                        # 禁止セルチェック
                        if self._is_forbidden_subject(time_slot, exchange_class, parent_assignment.subject):
                            continue
                        
                        # 日内重複チェック
                        if self._would_cause_daily_duplicate(schedule, exchange_class, time_slot, parent_assignment.subject):
                            self.stats['daily_duplicate_avoided'] += 1
                            continue
                        
                        # 親学級と同じ授業を割り当て
                        new_assignment = Assignment(exchange_class, parent_assignment.subject, parent_assignment.teacher)
                        
                        # 制約チェック
                        if self._check_basic_constraints(schedule, school, time_slot, new_assignment):
                            schedule.assign(time_slot, new_assignment)
                            self.logger.info(f"{time_slot} {exchange_class}: 親学級{parent_class}と同期 - {parent_assignment.subject.name}")
                            filled_count += 1
                            self.stats['exchange_synced'] += 1
        
        return filled_count
    
    def _fill_grade5_classes(self, schedule: Schedule, school: School) -> int:
        """5組クラスの空きコマを同期して埋める"""
        filled_count = 0
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 特別な時間はスキップ
                if self._should_skip_slot(time_slot, self.grade5_classes[0]):
                    continue
                
                # 全ての5組クラスが空きか確認
                empty_classes = []
                for class_ref in self.grade5_classes:
                    if not schedule.get_assignment(time_slot, class_ref):
                        if not schedule.is_locked(time_slot, class_ref):
                            empty_classes.append(class_ref)
                
                # 全クラスが空きでない場合はスキップ
                if len(empty_classes) != len(self.grade5_classes):
                    continue
                
                # 最適な教科を選択
                best_subject, best_teacher = self._find_best_subject_for_grade5(
                    schedule, school, time_slot
                )
                
                if not best_subject or not best_teacher:
                    continue
                
                # 教員不在チェック
                if self._is_teacher_absent(best_teacher, time_slot):
                    continue
                
                # 全クラスで制約チェック
                can_assign_all = True
                for class_ref in self.grade5_classes:
                    assignment = Assignment(class_ref, best_subject, best_teacher)
                    if not self._check_basic_constraints(schedule, school, time_slot, assignment):
                        can_assign_all = False
                        break
                    
                    # 日内重複チェック
                    if self._would_cause_daily_duplicate(schedule, class_ref, time_slot, best_subject):
                        self.logger.debug(f"{class_ref}の{time_slot}への{best_subject.name}配置は日内重複のため不可")
                        can_assign_all = False
                        break
                    
                    # 連続コマチェック
                    if self._would_cause_consecutive_periods(schedule, class_ref, time_slot, best_subject):
                        can_assign_all = False
                        break
                
                # 制約を満たす場合のみ配置
                if can_assign_all:
                    for class_ref in self.grade5_classes:
                        assignment = Assignment(class_ref, best_subject, best_teacher)
                        schedule.assign(time_slot, assignment)
                    
                    self.logger.info(f"{time_slot}: 5組を{best_subject.name}({best_teacher.name})で同期")
                    filled_count += 1
                    self.stats['grade5_synced'] += 1
        
        return filled_count
    
    def _fill_regular_classes(self, schedule: Schedule, school: School, pass_num: int) -> int:
        """通常クラスの空きコマを埋める"""
        filled_count = 0
        empty_slots = self._find_empty_slots(schedule, school)
        
        # パスごとに戦略を変える
        strategy = self._get_strategy_for_pass(pass_num)
        
        # 強制モードではすべての空きスロットを埋める
        if strategy == "forced":
            self.logger.info("強制モード: すべての空きスロットを埋めます")
        
        for time_slot, class_ref in empty_slots:
            # 交流学級は強制モード以外でスキップ、5組は常にスキップ
            if (strategy != "forced" and class_ref in self.exchange_mappings) or class_ref in self.grade5_classes:
                continue
            
            if self._fill_single_slot(schedule, school, time_slot, class_ref, strategy):
                filled_count += 1
                self.stats['regular_filled'] += 1
        
        return filled_count
    
    def _fill_single_slot(self, schedule: Schedule, school: School, 
                         time_slot: TimeSlot, class_ref: ClassReference, 
                         strategy: str) -> bool:
        """単一の空きコマを埋める"""
        # 不足科目を取得
        shortage_subjects = self._get_shortage_subjects_prioritized(schedule, school, class_ref)
        
        # 禁止教科を除外（forcedモードでは除外しない）
        if strategy != "forced":
            shortage_subjects = self._filter_forbidden_subjects(time_slot, class_ref, shortage_subjects)
        
        # 教師負担を考慮した候補リストを作成
        candidates = self._create_balanced_candidates(
            schedule, school, time_slot, class_ref, shortage_subjects, strategy
        )
        
        # 各候補を試す
        for subject, teacher in candidates:
            # 基本的な制約チェック
            assignment = Assignment(class_ref, subject, teacher)
            
            # 戦略に応じた制約チェック
            if strategy == "forced":
                # 強制モード: 教師重複と体育館制約をチェック
                if schedule.get_teacher_at_time(time_slot, assignment.teacher):
                    continue
                # 体育の場合は体育館制約も必須
                if assignment.subject.name == "保":
                    if not self._check_gym_constraint(schedule, school, time_slot, assignment):
                        continue
            else:
                if not self._check_basic_constraints(schedule, school, time_slot, assignment):
                    continue
            
            # 日内重複チェック（すべての戦略で実施）
            if self._would_cause_daily_duplicate(schedule, class_ref, time_slot, subject):
                self.stats['daily_duplicate_avoided'] += 1
                # forcedモードでも基本的な制約は守る
                if strategy != "forced" or self._count_subject_occurrences_on_day(schedule, class_ref, time_slot, subject) >= 2:
                    continue
            
            # 連続コマチェック（戦略による）
            if strategy in ["strict", "balanced"]:
                if self._would_cause_consecutive_periods(schedule, class_ref, time_slot, subject):
                    self.stats['consecutive_avoided'] += 1
                    continue
            
            # 割り当て実行
            schedule.assign(time_slot, assignment)
            self.logger.debug(f"{time_slot} {class_ref}: {subject.name}({teacher.name})を割り当て（{strategy}モード）")
            return True
        
        # 強制モードで候補がない場合、任意の利用可能な教科を割り当て
        if strategy == "forced" and not candidates:
            return self._force_fill_slot(schedule, school, time_slot, class_ref)
        
        return False
    
    def _find_best_subject_for_grade5(self, schedule: Schedule, school: School,
                                     time_slot: TimeSlot) -> Tuple[Optional[Subject], Optional[Teacher]]:
        """5組に最適な教科と教師を選択"""
        # 各クラスの不足時数を計算
        shortage_by_subject = defaultdict(list)
        
        for class_ref in self.grade5_classes:
            shortages = self._get_shortage_subjects(schedule, school, class_ref)
            for subject, shortage in shortages.items():
                if subject.name not in self.excluded_subjects:
                    shortage_by_subject[subject.name].append(shortage)
        
        # 全クラスで不足している教科を優先
        candidates = []
        
        # 主要教科で全クラス不足
        for subject_name, shortages in shortage_by_subject.items():
            if len(shortages) == len(self.grade5_classes) and subject_name in self.core_subjects:
                avg_shortage = sum(shortages) / len(shortages)
                candidates.append((subject_name, avg_shortage, True))  # True = 主要教科
        
        # その他の教科で全クラス不足
        for subject_name, shortages in shortage_by_subject.items():
            if len(shortages) == len(self.grade5_classes) and subject_name not in self.core_subjects:
                avg_shortage = sum(shortages) / len(shortages)
                candidates.append((subject_name, avg_shortage, False))  # False = 非主要教科
        
        # 主要教科を優先し、不足数でソート
        candidates.sort(key=lambda x: (not x[2], -x[1]))  # 主要教科優先、不足数降順
        
        for subject_name, _, _ in candidates:
            subject = Subject(subject_name)
            teacher = self._get_grade5_teacher(school, subject)
            
            if teacher and not self._is_teacher_absent(teacher, time_slot):
                # 全クラスで禁止されていないかチェック
                all_allowed = True
                for class_ref in self.grade5_classes:
                    if self._is_forbidden_subject(time_slot, class_ref, subject):
                        all_allowed = False
                        break
                    # 日内重複チェックも追加
                    if self._would_cause_daily_duplicate(schedule, class_ref, time_slot, subject):
                        all_allowed = False
                        break
                
                if all_allowed:
                    return subject, teacher
        
        return None, None
    
    def _create_balanced_candidates(self, schedule: Schedule, school: School,
                                   time_slot: TimeSlot, class_ref: ClassReference,
                                   shortage_subjects: Dict[Subject, int],
                                   strategy: str) -> List[Tuple[Subject, Teacher]]:
        """教師負担を考慮した候補リストを作成"""
        candidates = []
        
        # 教師の現在の負担を計算
        teacher_loads = self._calculate_teacher_loads(schedule)
        
        for subject, shortage in shortage_subjects.items():
            # この科目を教えられる教師を取得
            teachers = self._find_available_teachers_balanced(
                schedule, school, time_slot, class_ref, subject, teacher_loads
            )
            
            for teacher in teachers:
                # 主要教科と不足数でスコアを計算
                score = shortage
                if subject.name in self.core_subjects:
                    score += 10  # 主要教科ボーナス
                
                # 教師負担の少ない教師を優先
                teacher_load = teacher_loads.get(teacher.name, 0)
                score -= teacher_load * 0.1  # 負担が多い教師はスコアを下げる
                
                candidates.append((subject, teacher, score))
        
        # スコアでソート
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        # タプルから必要な情報だけ返す
        return [(subj, teacher) for subj, teacher, _ in candidates]
    
    def _find_available_teachers_balanced(self, schedule: Schedule, school: School,
                                         time_slot: TimeSlot, class_ref: ClassReference,
                                         subject: Subject, teacher_loads: Dict[str, int]) -> List[Teacher]:
        """負担バランスを考慮して利用可能な教師を探す"""
        teachers = []
        
        # この科目を教えられる教師を取得
        subject_teachers = school.get_subject_teachers(subject)
        
        for teacher in subject_teachers:
            # 教師不在チェック
            if self._is_teacher_absent(teacher, time_slot):
                continue
            
            # 恒久的な不在チェック
            if school.is_teacher_unavailable(time_slot.day, time_slot.period, teacher):
                continue
            
            # 非常勤教師制約チェック（青井先生の美術）
            if self._is_part_time_teacher_unavailable(teacher, subject, time_slot):
                continue
            
            # 5組の合同授業を考慮した教師重複チェック
            assignment = Assignment(class_ref, subject, teacher)
            if not self._check_teacher_conflict_with_grade5(schedule, time_slot, assignment):
                continue
            
            teachers.append(teacher)
        
        # 負担の少ない教師順にソート
        teachers.sort(key=lambda t: teacher_loads.get(t.name, 0))
        
        if len(teachers) > 0:
            self.stats['teacher_balance_considered'] += 1
        
        return teachers
    
    def _calculate_teacher_loads(self, schedule: Schedule) -> Dict[str, int]:
        """全教師の現在の授業数を計算"""
        loads = defaultdict(int)
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                # すべての時間帯の割り当てを取得
                assignments = schedule.get_assignments_by_time_slot(time_slot)
                for assignment in assignments:
                    if assignment and assignment.teacher:
                        loads[assignment.teacher.name] += 1
        
        return dict(loads)
    
    def _would_cause_consecutive_periods(self, schedule: Schedule, class_ref: ClassReference,
                                       time_slot: TimeSlot, subject: Subject) -> bool:
        """連続コマが発生するかチェック"""
        # 前の時間
        if time_slot.period > 1:
            prev_slot = TimeSlot(time_slot.day, time_slot.period - 1)
            prev_assignment = schedule.get_assignment(prev_slot, class_ref)
            if prev_assignment and prev_assignment.subject == subject:
                return True
        
        # 次の時間
        if time_slot.period < 6:
            next_slot = TimeSlot(time_slot.day, time_slot.period + 1)
            next_assignment = schedule.get_assignment(next_slot, class_ref)
            if next_assignment and next_assignment.subject == subject:
                return True
        
        return False
    
    def _would_cause_daily_duplicate(self, schedule: Schedule, class_ref: ClassReference,
                                   time_slot: TimeSlot, subject: Subject) -> bool:
        """日内重複が発生するかチェック"""
        # 保護教科は日内重複を許可
        if subject.name in self.excluded_subjects:
            return False
            
        for period in range(1, 7):
            if period == time_slot.period:
                continue
            
            other_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(other_slot, class_ref)
            
            if assignment and assignment.subject == subject:
                return True
        
        return False
    
    def _count_subject_occurrences_on_day(self, schedule: Schedule, class_ref: ClassReference,
                                       time_slot: TimeSlot, subject: Subject) -> int:
        """その日のその教科の出現回数をカウント"""
        count = 0
        for period in range(1, 7):
            if period == time_slot.period:
                continue
                
            other_slot = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(other_slot, class_ref)
            
            if assignment and assignment.subject == subject:
                count += 1
        
        return count
    
    def _get_shortage_subjects_prioritized(self, schedule: Schedule, school: School,
                                         class_ref: ClassReference) -> Dict[Subject, int]:
        """主要教科を優先した不足科目リストを取得"""
        shortages = self._get_shortage_subjects(schedule, school, class_ref)
        
        # 主要教科と非主要教科に分類
        core_shortages = {}
        other_shortages = {}
        
        for subject, shortage in shortages.items():
            if subject.name in self.core_subjects:
                core_shortages[subject] = shortage
            else:
                other_shortages[subject] = shortage
        
        # 主要教科を先に、その後その他の教科
        result = {}
        
        # 主要教科（不足数降順）
        for subject in sorted(core_shortages.keys(), key=lambda s: core_shortages[s], reverse=True):
            result[subject] = core_shortages[subject]
        
        # その他の教科（不足数降順）
        for subject in sorted(other_shortages.keys(), key=lambda s: other_shortages[s], reverse=True):
            result[subject] = other_shortages[subject]
        
        return result
    
    def _get_shortage_subjects(self, schedule: Schedule, school: School,
                             class_ref: ClassReference) -> Dict[Subject, int]:
        """不足科目とその不足数を取得"""
        # 基本時数を取得
        base_hours = school.get_all_standard_hours(class_ref)
        
        # 現在の割り当て数をカウント
        current_hours = defaultdict(int)
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject:
                    current_hours[assignment.subject] += 1
        
        # 不足数を計算
        shortage = {}
        for subject, required in base_hours.items():
            if subject.name not in self.excluded_subjects:
                current = current_hours.get(subject, 0)
                if current < required:
                    shortage[subject] = required - current
        
        return shortage
    
    def _find_empty_slots(self, schedule: Schedule, school: School) -> List[Tuple[TimeSlot, ClassReference]]:
        """空きコマを見つける"""
        empty_slots = []
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 特別な空きコマはスキップ
                    if self._should_skip_slot(time_slot, class_ref):
                        continue
                    
                    # テスト期間はスキップ
                    if (day, period) in self.test_periods:
                        continue
                    
                    # 既に割り当てがある場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    
                    empty_slots.append((time_slot, class_ref))
        
        # ランダムな順序で処理
        random.shuffle(empty_slots)
        return empty_slots
    
    def _should_skip_slot(self, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """このスロットをスキップすべきか判定"""
        # 月曜6時限は「欠」なのでスキップ（ただし3年生は除外）
        if time_slot.day == "月" and time_slot.period == 6:
            # 3年生は月曜6時限の制約から除外される
            if class_ref.grade == 3:
                return False
            return True
        
        # 火水金の6時限は「YT」なのでスキップ
        if time_slot.day in ["火", "水", "金"] and time_slot.period == 6:
            return True
        
        return False
    
    def _is_forbidden_subject(self, time_slot: TimeSlot, class_ref: ClassReference, 
                            subject: Subject) -> bool:
        """指定の教科が禁止されているかチェック"""
        forbidden_key = (time_slot, class_ref)
        forbidden_subjects = self._forbidden_cells.get(forbidden_key, set())
        return subject.name in forbidden_subjects
    
    def _filter_forbidden_subjects(self, time_slot: TimeSlot, class_ref: ClassReference,
                                 shortage_subjects: Dict[Subject, int]) -> Dict[Subject, int]:
        """禁止教科を除外"""
        forbidden_key = (time_slot, class_ref)
        forbidden_subjects = self._forbidden_cells.get(forbidden_key, set())
        
        if forbidden_subjects:
            return {s: count for s, count in shortage_subjects.items() 
                   if s.name not in forbidden_subjects}
        
        return shortage_subjects
    
    def _check_basic_constraints(self, schedule: Schedule, school: School,
                               time_slot: TimeSlot, assignment: Assignment) -> bool:
        """基本的な制約チェック"""
        # 教師不在チェック
        if self._is_teacher_absent(assignment.teacher, time_slot):
            return False
        
        # 教師重複チェック（5組の合同授業を考慮）
        if not self._check_teacher_conflict_with_grade5(schedule, time_slot, assignment):
            return False
        
        # 体育館使用制約（5組合同・交流ペアを考慮）
        if assignment.subject.name == "保":
            if not self._check_gym_constraint(schedule, school, time_slot, assignment):
                return False
        
        # CRITICALレベルの制約のみチェック
        critical_constraints = self.constraint_system.constraints.get(ConstraintPriority.CRITICAL, [])
        for constraint in critical_constraints:
            if hasattr(constraint, 'check'):
                if not constraint.check(schedule, school, time_slot, assignment):
                    return False
        
        return True
    
    def _check_teacher_conflict_with_grade5(self, schedule: Schedule, time_slot: TimeSlot, 
                                          assignment: Assignment) -> bool:
        """教師重複チェック（5組の合同授業を考慮）"""
        # 5組の場合、他の5組クラスが同じ教師・教科で授業をしているかチェック
        if assignment.class_ref in self.grade5_classes:
            # 他の5組クラスをチェック
            other_grade5_same_subject_teacher = 0
            for other_class in self.grade5_classes:
                if other_class != assignment.class_ref:
                    other_assignment = schedule.get_assignment(time_slot, other_class)
                    if (other_assignment and 
                        other_assignment.subject == assignment.subject and
                        other_assignment.teacher == assignment.teacher):
                        other_grade5_same_subject_teacher += 1
            
            # 他の5組クラスが同じ教師・教科なら合同授業としてOK
            if other_grade5_same_subject_teacher > 0:
                return True
        
        # 通常の教師重複チェック
        teacher_assignments = schedule.get_teacher_at_time(time_slot, assignment.teacher)
        if teacher_assignments:
            # 教師が既に5組の授業を担当している場合
            for existing_assignment in teacher_assignments:
                if existing_assignment.class_ref in self.grade5_classes:
                    # 5組の授業を担当中で、新しい割り当ても5組なら
                    if (assignment.class_ref in self.grade5_classes and
                        existing_assignment.subject == assignment.subject):
                        # 同じ教科なら合同授業としてOK
                        return True
            # それ以外の重複はNG
            return False
        
        return True
    
    def _check_gym_constraint(self, schedule: Schedule, school: School,
                            time_slot: TimeSlot, assignment: Assignment) -> bool:
        """体育館使用制約チェック（5組合同・交流ペアを考慮）"""
        # 体育館を使用するグループをカウント
        gym_groups = []
        pe_classes = []
        
        # 全クラスの体育をチェック
        for class_ref in school.get_all_classes():
            if class_ref == assignment.class_ref:
                continue
            other_assignment = schedule.get_assignment(time_slot, class_ref)
            if other_assignment and other_assignment.subject.name == "保":
                pe_classes.append(class_ref)
        
        # 新しい割り当てを含めてグループ分析
        pe_classes.append(assignment.class_ref)
        
        # 5組合同チェック
        grade5_in_pe = [c for c in pe_classes if c in self.grade5_classes]
        if len(grade5_in_pe) >= 2:  # 5組が2つ以上
            gym_groups.append("5組合同")
            # 5組を処理済みとしてマーク
            pe_classes = [c for c in pe_classes if c not in self.grade5_classes]
        
        # 交流ペアチェック
        processed = set()
        for class_ref in pe_classes:
            if class_ref in processed:
                continue
            
            # 交流学級の場合
            if class_ref in self.exchange_mappings:
                parent = self.exchange_mappings[class_ref]
                if parent in pe_classes:
                    gym_groups.append(f"交流ペア({parent}+{class_ref})")
                    processed.add(class_ref)
                    processed.add(parent)
                else:
                    # 交流学級単独
                    gym_groups.append(f"単独({class_ref})")
                    processed.add(class_ref)
            # 親学級の場合
            else:
                # 対応する交流学級を探す
                exchange_class = None
                for exc, par in self.exchange_mappings.items():
                    if par == class_ref:
                        exchange_class = exc
                        break
                
                if exchange_class and exchange_class in pe_classes:
                    # 既に交流ペアとして処理済み
                    continue
                else:
                    # 親学級単独
                    gym_groups.append(f"単独({class_ref})")
                    processed.add(class_ref)
        
        # 体育館は1グループのみ使用可能
        return len(gym_groups) <= 1
    
    def _is_teacher_absent(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師不在チェック"""
        if self.absence_loader:
            return self.absence_loader.is_teacher_absent(teacher.name, time_slot.day, time_slot.period)
        return False
    
    def _is_part_time_teacher_unavailable(self, teacher: Teacher, subject: Subject, time_slot: TimeSlot) -> bool:
        """非常勤教師が利用不可かチェック"""
        # 青井先生（美術）の制約
        if teacher.name == "青井" and subject.name == "美":
            # 月曜・火曜は全時限不可
            if time_slot.day in ["月", "火"]:
                return True
            # 水曜は2,3,4校時のみ可
            if time_slot.day == "水" and time_slot.period not in [2, 3, 4]:
                return True
            # 木曜は1,2,3校時のみ可
            if time_slot.day == "木" and time_slot.period not in [1, 2, 3]:
                return True
            # 金曜は2,3,4校時のみ可
            if time_slot.day == "金" and time_slot.period not in [2, 3, 4]:
                return True
        
        return False
    
    def _get_grade5_teacher(self, school: School, subject: Subject) -> Optional[Teacher]:
        """5組の特定教科の担当教師を取得"""
        # 各5組クラスから教師を探す
        for class_ref in self.grade5_classes:
            teacher = school.get_assigned_teacher(subject, class_ref)
            if teacher:
                return teacher
        
        # 見つからない場合は、教科担当教師から選択
        teachers = school.get_teachers_for_subject(subject)
        if teachers:
            # 金子み先生を優先
            for teacher in teachers:
                if "金子み" in teacher.name:
                    return teacher
            return teachers[0]
        
        return None
    
    def _get_strategy_for_pass(self, pass_num: int) -> str:
        """パス番号に応じた戦略を取得"""
        if pass_num == 1:
            return "strict"  # 厳格な制約
        elif pass_num == 2:
            return "balanced"  # バランス重視
        elif pass_num == 3:
            return "relaxed"  # 緩い制約
        elif pass_num == 4:
            return "ultra_relaxed"  # 最大限緩い
        else:
            return "forced"  # 強制的に埋める
    
    def _force_fill_slot(self, schedule: Schedule, school: School,
                        time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """強制的に空きスロットを埋める（最後の手段）"""
        # すべての教科から選択（特別教科を除く）
        all_subjects = []
        base_hours = school.get_all_standard_hours(class_ref)
        
        for subject in base_hours.keys():
            if subject.name not in self.excluded_subjects:
                all_subjects.append(subject)
        
        # ランダムな順序で試す
        random.shuffle(all_subjects)
        
        for subject in all_subjects:
            # この教科を教えられる教師を探す
            teachers = list(school.get_subject_teachers(subject))
            random.shuffle(teachers)
            
            for teacher in teachers:
                # 非常勤教師制約チェック
                if self._is_part_time_teacher_unavailable(teacher, subject, time_slot):
                    continue
                    
                assignment = Assignment(class_ref, subject, teacher)
                # 5組の合同授業を考慮した教師重複チェック
                if self._check_teacher_conflict_with_grade5(schedule, time_slot, assignment):
                    # 体育の場合は体育館制約もチェック
                    if subject.name == "保":
                        if not self._check_gym_constraint(schedule, school, time_slot, assignment):
                            continue
                    
                    schedule.assign(time_slot, assignment)
                    self.logger.info(f"{time_slot} {class_ref}: {subject.name}({teacher.name})を強制割り当て")
                    return True
        
        self.logger.warning(f"{time_slot} {class_ref}: 強制モードでも埋められませんでした")
        return False
    
    def _extract_forbidden_cells(self) -> Dict:
        """制約システムから非○○制約情報を抽出"""
        forbidden_cells = {}
        
        from ..constraints.cell_forbidden_subject_constraint import CellForbiddenSubjectConstraint
        
        for priority in ConstraintPriority:
            constraints = self.constraint_system.constraints.get(priority, [])
            for constraint in constraints:
                if isinstance(constraint, CellForbiddenSubjectConstraint):
                    forbidden_cells = constraint.forbidden_cells
                    self.logger.info(f"非○○制約を{len(forbidden_cells)}個抽出しました")
                    return forbidden_cells
        
        return forbidden_cells
    
    def _count_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きスロット数をカウント"""
        count = 0
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    # 特別な空きコマはカウントしない
                    if self._should_skip_slot(time_slot, class_ref):
                        continue
                    # 既に割り当てがある場合はスキップ
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    # ロックされている場合はスキップ
                    if schedule.is_locked(time_slot, class_ref):
                        continue
                    count += 1
        return count
    
    def _log_statistics(self) -> None:
        """統計情報をログ出力"""
        self.logger.info(
            f"スマート空きコマ埋め統計:\n"
            f"  交流学級同期: {self.stats['exchange_synced']}件\n"
            f"  5組同期: {self.stats['grade5_synced']}件\n"
            f"  通常埋め: {self.stats['regular_filled']}件\n"
            f"  日内重複回避: {self.stats['daily_duplicate_avoided']}件\n"
            f"  連続コマ回避: {self.stats['consecutive_avoided']}件\n"
            f"  教師負担考慮: {self.stats['teacher_balance_considered']}件"
        )
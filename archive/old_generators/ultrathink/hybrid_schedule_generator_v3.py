"""
フェーズ5: ハイブリッドアプローチV3（完全最適化版）

V2の改善点に加えて、以下を実装：
1. 月曜6限の欠課保護（3年生も含む）
2. 標準時数の厳密な遵守
3. 空きスロットの最小化
4. より賢い教師配置戦略
"""
import logging
import random
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from ...entities.schedule import Schedule
from ...entities.school import School, Teacher, Subject
from ...value_objects.time_slot import TimeSlot, ClassReference
from ...value_objects.assignment import Assignment
from ..constraint_validator import ConstraintValidator
from ..exchange_class_synchronizer import ExchangeClassSynchronizer
from ..grade5_synchronizer_refactored import RefactoredGrade5Synchronizer
from .test_period_protector import TestPeriodProtector


@dataclass
class OptimizationResult:
    """最適化結果"""
    schedule: Schedule
    violations: int
    teacher_conflicts: int
    statistics: Dict
    improvements: List[str] = field(default_factory=list)


class HybridScheduleGeneratorV3:
    """完全最適化版ハイブリッド時間割生成器"""
    
    def __init__(self, enable_logging: bool = True):
        self.logger = logging.getLogger(__name__)
        if not enable_logging:
            self.logger.setLevel(logging.WARNING)
        
        # 制約検証器
        self.constraint_validator = ConstraintValidator()
        
        # 同期サービス
        self.grade5_synchronizer = RefactoredGrade5Synchronizer(self.constraint_validator)
        self.exchange_synchronizer = ExchangeClassSynchronizer()
        
        # テスト期間の定義
        self.test_periods = {
            ("月", 1), ("月", 2), ("月", 3),
            ("火", 1), ("火", 2), ("火", 3),
            ("水", 1), ("水", 2)
        }
        
        # 固定教師の定義
        self.fixed_teachers = {
            "欠", "欠課先生", "YT担当", "YT担当先生", 
            "道担当", "道担当先生", "学担当", "学担当先生", 
            "総担当", "総担当先生", "学総担当", "学総担当先生", 
            "行担当", "行担当先生", "技家担当", "技家担当先生"
        }
        
        # 5組クラス
        self.grade5_classes = {
            ClassReference(1, 5), 
            ClassReference(2, 5), 
            ClassReference(3, 5)
        }
        
        # 交流学級と親学級のマッピング
        self.exchange_class_mapping = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
        
        # 固定科目
        self.fixed_subjects = {"欠", "YT", "道", "学", "総", "学総", "行", "技家"}
    
    def generate(
        self,
        school: School,
        initial_schedule: Optional[Schedule] = None,
        target_violations: int = 0,
        time_limit: int = 300,
        followup_data: Optional[Dict[str, List[str]]] = None
    ) -> OptimizationResult:
        """スケジュールを生成"""
        start_time = datetime.now()
        
        self.logger.info("=== ハイブリッドV3時間割生成開始 ===")
        
        # テスト期間保護の初期化
        if followup_data:
            self.test_period_protector.load_followup_data(followup_data)
            # test_periodsも更新
            self.test_periods = self.test_period_protector.test_periods.copy()
        
        # 初期スケジュールの準備
        if initial_schedule:
            schedule = self._copy_schedule(initial_schedule)
            # テスト期間の割り当てを保存
            self.test_period_protector.load_initial_schedule(initial_schedule)
        else:
            schedule = Schedule()
        
        # フェーズ0: 固定科目の保護
        self.logger.info("フェーズ0: 固定科目の保護")
        self._protect_fixed_subjects(schedule, school)
        
        # フェーズ1: 事前分析と準備
        self.logger.info("フェーズ1: 事前分析と準備")
        teacher_availability = self._analyze_teacher_availability(school, schedule)
        subject_requirements = self._analyze_subject_requirements(school, schedule)
        
        # フェーズ2: 5組の完全同期配置
        self.logger.info("フェーズ2: 5組の同期配置")
        self._place_grade5_synchronized_v3(schedule, school, teacher_availability, subject_requirements)
        
        # フェーズ3: 交流学級の自立活動配置
        self.logger.info("フェーズ3: 交流学級の自立活動配置")
        self._place_exchange_jiritsu_v3(schedule, school, teacher_availability)
        
        # フェーズ4: 残りの科目を最適配置
        self.logger.info("フェーズ4: 残りの科目を最適配置")
        self._place_remaining_optimized(schedule, school, teacher_availability, subject_requirements)
        
        # フェーズ5: 積極的な最適化
        self.logger.info("フェーズ5: 積極的な最適化")
        best_schedule = self._aggressive_optimize(schedule, school, target_violations, time_limit, start_time)
        
        # フェーズ6: テスト期間保護の適用
        self.logger.info("フェーズ6: テスト期間保護の適用")
        if self.test_period_protector.test_periods:
            changes = self.test_period_protector.protect_test_periods(best_schedule, school)
            if changes > 0:
                self.logger.info(f"テスト期間保護により{changes}個の割り当てを修正しました")
        
        # 結果の評価
        violations = self._count_violations(best_schedule, school)
        teacher_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        # 統計情報の収集
        statistics = {
            'total_assignments': len(best_schedule.get_all_assignments()),
            'violations': violations,
            'teacher_conflicts': teacher_conflicts,
            'elapsed_time': (datetime.now() - start_time).total_seconds(),
            'empty_slots': self._count_empty_slots(best_schedule, school),
            'standard_hours_met': self._check_standard_hours(best_schedule, school)
        }
        
        result = OptimizationResult(
            schedule=best_schedule,
            violations=violations,
            teacher_conflicts=teacher_conflicts,
            statistics=statistics
        )
        
        self._print_summary(result)
        
        return result
    
    def _protect_fixed_subjects(self, schedule: Schedule, school: School):
        """固定科目を保護"""
        # 月曜6限を全クラスに欠課設定
        monday_6th = TimeSlot("月", 6)
        for class_ref in school.get_all_classes():
            if not schedule.get_assignment(monday_6th, class_ref):
                assignment = Assignment(class_ref, Subject("欠"), Teacher("欠課先生"))
                try:
                    schedule.assign(monday_6th, assignment)
                    schedule.lock_cell(monday_6th, class_ref)
                except:
                    pass
        
        # その他の固定科目もロック
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in self.fixed_subjects:
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    schedule.lock_cell(time_slot, assignment.class_ref)
    
    def _analyze_teacher_availability(self, school: School, schedule: Schedule) -> Dict:
        """教師の利用可能性を分析（改良版）"""
        availability = defaultdict(lambda: defaultdict(set))
        
        days = ["月", "火", "水", "木", "金"]
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各教師の利用可能性をチェック
                for teacher in school.get_all_teachers():
                    if school.is_teacher_unavailable(day, period, teacher):
                        continue
                    
                    # 既存の割り当てをチェック
                    is_available = True
                    assigned_classes = []
                    
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                            assigned_classes.append(class_ref)
                            # テスト期間以外は1クラスまで
                            if (day, period) not in self.test_periods and len(assigned_classes) >= 1:
                                is_available = False
                                break
                    
                    if is_available:
                        availability[teacher.name][time_slot].add(time_slot)
        
        return availability
    
    def _analyze_subject_requirements(self, school: School, schedule: Schedule) -> Dict:
        """科目の必要時数を分析（精密版）"""
        requirements = defaultdict(lambda: defaultdict(int))
        
        for class_ref in school.get_all_classes():
            # 標準時数を取得
            for subject, hours in school.get_all_standard_hours(class_ref).items():
                requirements[class_ref][subject.name] = int(hours)
            
            # 既存の配置を差し引く
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        subject_name = assignment.subject.name
                        if subject_name in requirements[class_ref] and subject_name not in self.fixed_subjects:
                            requirements[class_ref][subject_name] -= 1
        
        return requirements
    
    def _place_grade5_synchronized_v3(self, schedule: Schedule, school: School, 
                                     teacher_availability: Dict, subject_requirements: Dict):
        """5組を同期して配置（改良版）"""
        # 5組共通の科目と教師のマッピング
        grade5_subjects = {
            "国": "寺田",
            "社": "蒲地", 
            "数": "梶永",
            "理": "智田",
            "音": "塚本",
            "美": "金子み",
            "保": "野口",
            "技": "林",
            "家": "金子み",
            "英": "林田",
            "道": "金子み",
            "学": "金子み",
            "総": "金子み",
            "自立": "金子み",
            "日生": "金子み",
            "作業": "金子み",
            "YT": "金子み",
            "学総": "金子み"
        }
        
        # 必要時数を計算
        grade5_needs = defaultdict(int)
        for class_ref in self.grade5_classes:
            for subject, hours in subject_requirements[class_ref].items():
                if hours > 0:
                    grade5_needs[subject] = max(grade5_needs[subject], hours)
        
        # 優先度順にソート（必要時数が多い順）
        sorted_subjects = sorted(grade5_needs.items(), key=lambda x: x[1], reverse=True)
        
        days = ["月", "火", "水", "木", "金"]
        for subject_name, needed_hours in sorted_subjects:
            if subject_name in self.fixed_subjects:
                continue
                
            teacher_name = grade5_subjects.get(subject_name)
            if not teacher_name:
                continue
            
            placed_count = 0
            for day in days:
                if placed_count >= needed_hours:
                    break
                    
                for period in range(1, 7):
                    if placed_count >= needed_hours:
                        break
                        
                    time_slot = TimeSlot(day, period)
                    
                    # 全5組が空いているか確認
                    all_empty = True
                    for class_ref in self.grade5_classes:
                        if schedule.get_assignment(time_slot, class_ref):
                            all_empty = False
                            break
                    
                    if not all_empty:
                        continue
                    
                    # 教師が利用可能か確認
                    if time_slot not in teacher_availability.get(teacher_name, {}).get(time_slot, set()):
                        continue
                    
                    # 5組全てに配置
                    subject = Subject(subject_name)
                    teacher = Teacher(teacher_name)
                    
                    placed_all = True
                    for class_ref in self.grade5_classes:
                        assignment = Assignment(class_ref, subject, teacher)
                        try:
                            schedule.assign(time_slot, assignment)
                        except:
                            placed_all = False
                            break
                    
                    if placed_all:
                        placed_count += 1
                        # 教師の利用可能性を更新
                        if teacher_name in teacher_availability:
                            teacher_availability[teacher_name][time_slot].discard(time_slot)
    
    def _place_exchange_jiritsu_v3(self, schedule: Schedule, school: School, teacher_availability: Dict):
        """交流学級の自立活動を配置（改良版）"""
        for exchange_class, parent_class in self.exchange_class_mapping.items():
            # 自立活動の教師を取得
            jiritsu_teacher = self._get_jiritsu_teacher(exchange_class)
            if not jiritsu_teacher:
                continue
            
            # 必要時数を確認
            needed_hours = 3  # 通常3時間必要
            placed_count = 0
            
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                if placed_count >= needed_hours:
                    break
                    
                for period in range(1, 7):
                    if placed_count >= needed_hours:
                        break
                        
                    time_slot = TimeSlot(day, period)
                    
                    # 既に配置済みならスキップ
                    if schedule.get_assignment(time_slot, exchange_class):
                        continue
                    
                    # 親学級の科目を確認
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    if not parent_assignment or parent_assignment.subject.name not in ["数", "英"]:
                        continue
                    
                    # 教師が利用可能か確認
                    if time_slot not in teacher_availability.get(jiritsu_teacher, {}).get(time_slot, set()):
                        continue
                    
                    # 自立活動を配置
                    subject = Subject("自立")
                    teacher = Teacher(jiritsu_teacher)
                    assignment = Assignment(exchange_class, subject, teacher)
                    
                    try:
                        schedule.assign(time_slot, assignment)
                        placed_count += 1
                        # 教師の利用可能性を更新
                        if jiritsu_teacher in teacher_availability:
                            teacher_availability[jiritsu_teacher][time_slot].discard(time_slot)
                    except:
                        pass
    
    def _place_remaining_optimized(self, schedule: Schedule, school: School, 
                                  teacher_availability: Dict, subject_requirements: Dict):
        """残りの科目を最適配置"""
        # 優先度順に配置
        priority_subjects = ["数", "英", "国", "理", "社"]  # 主要5教科を優先
        
        # クラスごとに処理
        for class_ref in school.get_all_classes():
            if class_ref in self.grade5_classes:
                continue  # 5組は既に処理済み
            
            # 必要時数が多い科目から配置
            class_needs = []
            for subject_name, required in subject_requirements[class_ref].items():
                if required > 0 and subject_name not in self.fixed_subjects:
                    priority = 0 if subject_name in priority_subjects else 1
                    class_needs.append((priority, required, subject_name))
            
            # 優先度と必要時数でソート
            class_needs.sort(key=lambda x: (x[0], -x[1]))
            
            for _, required, subject_name in class_needs:
                # この科目の教師を取得
                subject = Subject(subject_name)
                assigned_teacher = school.get_assigned_teacher(subject, class_ref)
                if not assigned_teacher:
                    continue
                
                # 最適なスロットを探して配置
                placed_count = 0
                days = ["月", "火", "水", "木", "金"]
                
                for day in days:
                    if placed_count >= required:
                        break
                    
                    # 同じ日に同じ科目がないかチェック
                    day_has_subject = False
                    for period in range(1, 7):
                        time_slot = TimeSlot(day, period)
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.subject.name == subject_name:
                            day_has_subject = True
                            break
                    
                    if day_has_subject:
                        continue
                    
                    # 最適な時間を探す
                    for period in range(1, 7):
                        if placed_count >= required:
                            break
                        
                        time_slot = TimeSlot(day, period)
                        
                        # 既に配置済みならスキップ
                        if schedule.get_assignment(time_slot, class_ref):
                            continue
                        
                        # テスト期間中はスキップ
                        if self.test_period_protector.is_test_period(time_slot):
                            continue
                        
                        # 教師が利用可能か確認
                        if time_slot not in teacher_availability.get(assigned_teacher.name, {}).get(time_slot, set()):
                            continue
                        
                        # 配置を試みる
                        assignment = Assignment(class_ref, subject, assigned_teacher)
                        try:
                            schedule.assign(time_slot, assignment)
                            placed_count += 1
                            
                            # 教師の利用可能性を更新
                            if assigned_teacher.name in teacher_availability:
                                teacher_availability[assigned_teacher.name][time_slot].discard(time_slot)
                        except:
                            pass
    
    def _aggressive_optimize(self, schedule: Schedule, school: School, 
                           target_violations: int, time_limit: int, start_time: datetime) -> Schedule:
        """積極的な最適化"""
        best_schedule = self._copy_schedule(schedule)
        best_violations = self._count_violations(best_schedule, school)
        best_conflicts = self._count_teacher_conflicts(best_schedule, school)
        
        iteration = 0
        max_iterations = 200  # より多くの試行
        no_improvement_count = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # 時間制限チェック
            if (datetime.now() - start_time).total_seconds() > time_limit:
                break
            
            # 現在の状態
            current_violations = self._count_violations(schedule, school)
            current_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if current_violations <= target_violations and current_conflicts == 0:
                return schedule
            
            # 様々な最適化戦略を試す
            improved = False
            
            # 1. 教師重複の解消
            if current_conflicts > 0:
                improved = self._fix_teacher_conflicts(schedule, school)
            
            # 2. 標準時数の修正
            if not improved:
                improved = self._fix_standard_hours(schedule, school)
            
            # 3. 空きスロットの埋め込み
            if not improved:
                improved = self._fill_empty_slots(schedule, school)
            
            # 4. ランダムな改善
            if not improved:
                improved = self._random_improvement(schedule, school)
            
            # 改善があった場合
            new_violations = self._count_violations(schedule, school)
            new_conflicts = self._count_teacher_conflicts(schedule, school)
            
            if new_violations < best_violations or (new_violations == best_violations and new_conflicts < best_conflicts):
                best_schedule = self._copy_schedule(schedule)
                best_violations = new_violations
                best_conflicts = new_conflicts
                no_improvement_count = 0
                self.logger.debug(f"改善: 違反={best_violations}, 教師重複={best_conflicts}")
            else:
                no_improvement_count += 1
            
            # 改善がない場合は別の戦略
            if no_improvement_count > 10:
                schedule = self._copy_schedule(best_schedule)
                self._perturb_schedule(schedule, school)
                no_improvement_count = 0
        
        return best_schedule
    
    def _fix_teacher_conflicts(self, schedule: Schedule, school: School) -> bool:
        """教師重複を修正"""
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 教師ごとにクラスを収集
                teacher_classes = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        
                        # 固定教師はスキップ
                        if teacher_name in self.fixed_teachers:
                            continue
                        
                        teacher_classes[teacher_name].append((class_ref, assignment))
                
                # 重複を修正
                for teacher_name, assignments in teacher_classes.items():
                    # 5組の合同授業は除外
                    grade5_assignments = [(c, a) for c, a in assignments if c in self.grade5_classes]
                    if len(grade5_assignments) == len(assignments) and len(assignments) > 1:
                        continue  # 5組のみの重複は正常
                    
                    if len(assignments) > 1:
                        # 最初の1つを残して他を削除
                        for class_ref, assignment in assignments[1:]:
                            if not schedule.is_locked(time_slot, class_ref):
                                schedule.remove_assignment(time_slot, class_ref)
                                return True
        
        return False
    
    def _fix_standard_hours(self, schedule: Schedule, school: School) -> bool:
        """標準時数を修正"""
        for class_ref in school.get_all_classes():
            # 現在の時数を計算
            current_hours = defaultdict(int)
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        current_hours[assignment.subject.name] += 1
            
            # 標準時数と比較
            for subject, standard in school.get_all_standard_hours(class_ref).items():
                if subject.name in self.fixed_subjects:
                    continue
                    
                diff = int(standard) - current_hours[subject.name]
                
                # 不足している場合
                if diff > 0:
                    teacher = school.get_assigned_teacher(subject, class_ref)
                    if not teacher:
                        continue
                    
                    # 空きスロットに配置
                    for day in days:
                        if diff <= 0:
                            break
                        for period in range(1, 7):
                            if diff <= 0:
                                break
                            time_slot = TimeSlot(day, period)
                            if not schedule.get_assignment(time_slot, class_ref):
                                assignment = Assignment(class_ref, subject, teacher)
                                try:
                                    schedule.assign(time_slot, assignment)
                                    diff -= 1
                                    return True
                                except:
                                    pass
                
                # 過剰な場合
                elif diff < 0:
                    # 削除可能な授業を探す
                    for day in days:
                        if diff >= 0:
                            break
                        for period in range(1, 7):
                            if diff >= 0:
                                break
                            time_slot = TimeSlot(day, period)
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            if (assignment and assignment.subject.name == subject.name 
                                and not schedule.is_locked(time_slot, class_ref)):
                                schedule.remove_assignment(time_slot, class_ref)
                                diff += 1
                                return True
        
        return False
    
    def _fill_empty_slots(self, schedule: Schedule, school: School) -> bool:
        """空きスロットを埋める"""
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    if not schedule.get_assignment(time_slot, class_ref):
                        # 不足している科目を探す
                        for subject in school.get_all_subjects():
                            if subject.name in self.fixed_subjects:
                                continue
                            
                            teacher = school.get_assigned_teacher(subject, class_ref)
                            if not teacher:
                                continue
                            
                            # 教師が利用可能か確認
                            if not school.is_teacher_unavailable(day, period, teacher):
                                assignment = Assignment(class_ref, subject, teacher)
                                try:
                                    schedule.assign(time_slot, assignment)
                                    return True
                                except:
                                    pass
        
        return False
    
    def _random_improvement(self, schedule: Schedule, school: School) -> bool:
        """ランダムな改善を試みる"""
        # ランダムに2つのスロットを交換
        classes = list(school.get_all_classes())
        if len(classes) < 2:
            return False
        
        days = ["月", "火", "水", "木", "金"]
        
        # 10回試行
        for _ in range(10):
            # ランダムにスロットを選択
            class1 = random.choice(classes)
            class2 = random.choice(classes)
            day1 = random.choice(days)
            day2 = random.choice(days)
            period1 = random.randint(1, 6)
            period2 = random.randint(1, 6)
            
            time_slot1 = TimeSlot(day1, period1)
            time_slot2 = TimeSlot(day2, period2)
            
            # 同じスロットなら無視
            if class1 == class2 and time_slot1 == time_slot2:
                continue
            
            # ロックされていたら無視
            if schedule.is_locked(time_slot1, class1) or schedule.is_locked(time_slot2, class2):
                continue
            
            # 交換前の違反数
            before_violations = self._count_violations(schedule, school)
            
            # 交換
            assignment1 = schedule.get_assignment(time_slot1, class1)
            assignment2 = schedule.get_assignment(time_slot2, class2)
            
            if assignment1:
                schedule.remove_assignment(time_slot1, class1)
            if assignment2:
                schedule.remove_assignment(time_slot2, class2)
            
            success = True
            if assignment2:
                try:
                    schedule.assign(time_slot1, Assignment(class1, assignment2.subject, assignment2.teacher))
                except:
                    success = False
            
            if success and assignment1:
                try:
                    schedule.assign(time_slot2, Assignment(class2, assignment1.subject, assignment1.teacher))
                except:
                    success = False
            
            # 違反数が改善したか確認
            if success:
                after_violations = self._count_violations(schedule, school)
                if after_violations <= before_violations:
                    return True
            
            # 元に戻す
            if assignment2:
                schedule.remove_assignment(time_slot1, class1)
            if assignment1:
                schedule.remove_assignment(time_slot2, class2)
            
            if assignment1:
                try:
                    schedule.assign(time_slot1, assignment1)
                except:
                    pass
            if assignment2:
                try:
                    schedule.assign(time_slot2, assignment2)
                except:
                    pass
        
        return False
    
    def _perturb_schedule(self, schedule: Schedule, school: School):
        """スケジュールに摂動を加える"""
        # ランダムに5個の授業を削除して再配置
        days = ["月", "火", "水", "木", "金"]
        removed = []
        
        for _ in range(5):
            class_ref = random.choice(list(school.get_all_classes()))
            day = random.choice(days)
            period = random.randint(1, 6)
            time_slot = TimeSlot(day, period)
            
            if not schedule.is_locked(time_slot, class_ref):
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name not in self.fixed_subjects:
                    schedule.remove_assignment(time_slot, class_ref)
                    removed.append((class_ref, assignment.subject, assignment.teacher))
        
        # 削除した授業を別の場所に配置
        for class_ref, subject, teacher in removed:
            for _ in range(10):  # 10回試行
                day = random.choice(days)
                period = random.randint(1, 6)
                time_slot = TimeSlot(day, period)
                
                if not schedule.get_assignment(time_slot, class_ref):
                    assignment = Assignment(class_ref, subject, teacher)
                    try:
                        schedule.assign(time_slot, assignment)
                        break
                    except:
                        pass
    
    def _get_jiritsu_teacher(self, exchange_class: ClassReference) -> Optional[str]:
        """交流学級の自立活動担当教師を取得"""
        jiritsu_teachers = {
            (1, 6): "財津",
            (1, 7): "智田",
            (2, 6): "財津",
            (2, 7): "智田",
            (3, 6): "財津",
            (3, 7): "智田"
        }
        return jiritsu_teachers.get((exchange_class.grade, exchange_class.class_number))
    
    def _copy_schedule(self, original: Schedule) -> Schedule:
        """スケジュールのコピーを作成"""
        copy = Schedule()
        for time_slot, assignment in original.get_all_assignments():
            copy.assign(time_slot, assignment)
            if original.is_locked(time_slot, assignment.class_ref):
                copy.lock_cell(time_slot, assignment.class_ref)
        return copy
    
    def _count_violations(self, schedule: Schedule, school: School) -> int:
        """違反数をカウント"""
        violations = self.constraint_validator.validate_all_constraints(schedule, school)
        return len(violations)
    
    def _count_teacher_conflicts(self, schedule: Schedule, school: School) -> int:
        """教師重複をカウント（テスト期間を除く）"""
        from collections import defaultdict
        
        grade5_refs = {ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)}
        
        conflicts = 0
        days = ["月", "火", "水", "木", "金"]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # テスト期間はスキップ
                if (day, period) in self.test_periods:
                    continue
                
                # 教師ごとにクラスを収集
                teacher_classes = defaultdict(list)
                
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_name = assignment.teacher.name
                        
                        # 固定教師はスキップ
                        if teacher_name in self.fixed_teachers:
                            continue
                        
                        teacher_classes[teacher_name].append(class_ref)
                
                # 重複をカウント
                for teacher_name, classes in teacher_classes.items():
                    # 5組の合同授業は除外
                    grade5_count = sum(1 for c in classes if c in grade5_refs)
                    if grade5_count == len(classes) and grade5_count > 1:
                        continue  # 5組のみの重複は正常
                    
                    if len(classes) > 1:
                        conflicts += 1
        
        return conflicts
    
    def _count_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きスロット数をカウント"""
        empty = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref):
                        empty += 1
        
        return empty
    
    def _check_standard_hours(self, schedule: Schedule, school: School) -> Dict:
        """標準時数の達成状況をチェック"""
        result = {
            'total_subjects': 0,
            'met': 0,
            'unmet': 0,
            'details': []
        }
        
        for class_ref in school.get_all_classes():
            # 現在の時数を計算
            current_hours = defaultdict(int)
            days = ["月", "火", "水", "木", "金"]
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        current_hours[assignment.subject.name] += 1
            
            # 標準時数と比較
            for subject, standard in school.get_all_standard_hours(class_ref).items():
                if subject.name in self.fixed_subjects:
                    continue
                
                result['total_subjects'] += 1
                diff = int(standard) - current_hours[subject.name]
                
                if diff == 0:
                    result['met'] += 1
                else:
                    result['unmet'] += 1
                    result['details'].append({
                        'class': str(class_ref),
                        'subject': subject.name,
                        'standard': int(standard),
                        'actual': current_hours[subject.name],
                        'diff': diff
                    })
        
        return result
    
    def _print_summary(self, result: OptimizationResult):
        """結果サマリーを出力"""
        self.logger.info("\n=== ハイブリッドV3生成結果 ===")
        self.logger.info(f"総割り当て数: {result.statistics['total_assignments']}")
        self.logger.info(f"制約違反数: {result.violations}")
        self.logger.info(f"教師重複数: {result.teacher_conflicts}")
        self.logger.info(f"空きスロット数: {result.statistics['empty_slots']}")
        self.logger.info(f"実行時間: {result.statistics['elapsed_time']:.1f}秒")
        
        # 標準時数の達成状況
        hours_info = result.statistics['standard_hours_met']
        self.logger.info(f"\n標準時数達成率: {hours_info['met']}/{hours_info['total_subjects']} "
                        f"({hours_info['met']/hours_info['total_subjects']*100:.1f}%)")
        
        if hours_info['unmet'] > 0:
            self.logger.info(f"未達成: {hours_info['unmet']}件")
            for detail in hours_info['details'][:5]:  # 最初の5件のみ表示
                self.logger.debug(f"  {detail['class']} {detail['subject']}: "
                                f"標準{detail['standard']} vs 実際{detail['actual']} "
                                f"(差分: {detail['diff']})")
        
        if result.improvements:
            self.logger.info("\n改善点:")
            for improvement in result.improvements:
                self.logger.info(f"  - {improvement}")
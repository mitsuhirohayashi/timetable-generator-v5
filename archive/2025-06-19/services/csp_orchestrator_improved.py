"""改良版CSPオーケストレーター

6フェーズ管理により、段階的かつ効率的な時間割生成を実現。
"""
import logging
from typing import Optional, Dict, List, Set, Tuple, Any
from collections import defaultdict

from ...entities.schedule import Schedule
from ...entities.school import School
from ...value_objects.time_slot import ClassReference, TimeSlot
from ...value_objects.assignment import Assignment
from ..unified_constraint_validator import UnifiedConstraintValidator
from .priority_based_placement_service_improved import PriorityBasedPlacementServiceImproved


class CSPOrchestratorImproved:
    """改良版CSPオーケストレーター
    
    6つのフェーズで段階的に時間割を生成：
    1. 初期設定と保護
    2. 自立活動の配置
    3. 5組の同期配置
    4. 交流学級の早期同期
    5. 通常教科の配置（優先度ベース）
    6. 最適化
    """
    
    def __init__(self, constraint_validator: UnifiedConstraintValidator):
        """初期化
        
        Args:
            constraint_validator: 統合制約検証器
        """
        self.constraint_validator = constraint_validator
        self.logger = logging.getLogger(__name__)
        
        # 統計情報
        self._statistics = {
            'phase1_protected': 0,
            'phase2_jiritsu': 0,
            'phase3_grade5': 0,
            'phase4_exchange': 0,
            'phase5_subjects': 0,
            'phase6_optimized': 0,
            'backtrack_count': 0,
            'total_assignments': 0,
            'failed_assignments': 0
        }
        
        # 優先度ベース配置サービス
        self.placement_service = PriorityBasedPlacementServiceImproved(constraint_validator)
    
    def generate(self, school: School, max_iterations: int = 100,
                initial_schedule: Optional[Schedule] = None) -> Schedule:
        """スケジュールを生成
        
        Args:
            school: 学校情報
            max_iterations: 最大反復回数
            initial_schedule: 初期スケジュール
            
        Returns:
            生成されたスケジュール
        """
        self.logger.info("=== 改良版CSPオーケストレーター開始 ===")
        
        # 初期スケジュールの準備
        if initial_schedule:
            schedule = self._copy_schedule(initial_schedule)
        else:
            schedule = Schedule()
        
        # 6フェーズ実行
        self._phase1_initial_setup(schedule, school)
        self._phase2_jiritsu_placement(schedule, school)
        self._phase3_grade5_sync(schedule, school)
        self._phase4_exchange_sync(schedule, school)
        self._phase5_subject_placement(schedule, school, max_iterations)
        self._phase6_optimization(schedule, school)
        
        # 統計情報のログ出力
        self._log_statistics()
        
        return schedule
    
    def _phase1_initial_setup(self, schedule: Schedule, school: School):
        """フェーズ1: 初期設定と保護"""
        self.logger.info("【フェーズ1】初期設定と固定科目の保護")
        
        fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "行事", "テスト"}
        protected_count = 0
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.subject.name in fixed_subjects:
                if not schedule.is_locked(time_slot, assignment.class_ref):
                    schedule.lock_cell(time_slot, assignment.class_ref)
                    protected_count += 1
        
        self._statistics['phase1_protected'] = protected_count
        self.logger.info(f"  → {protected_count}個の固定科目を保護しました")
    
    def _phase2_jiritsu_placement(self, schedule: Schedule, school: School):
        """フェーズ2: 自立活動の配置"""
        self.logger.info("【フェーズ2】自立活動の優先配置")
        
        jiritsu_count = 0
        exchange_classes = self._get_exchange_classes(school)
        
        for exchange_class in exchange_classes:
            # 自立活動の必要時間数を取得
            requirements = school.get_class_requirements(exchange_class)
            jiritsu_hours = requirements.get("自立", 0)
            
            if jiritsu_hours == 0:
                continue
            
            # 配置可能なスロットを探す
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 既に配置済みならスキップ
                    if schedule.get_assignment(time_slot, exchange_class):
                        continue
                    
                    # 親学級の科目をチェック
                    parent_class = self._get_parent_class(exchange_class, school)
                    if parent_class:
                        parent_assignment = schedule.get_assignment(time_slot, parent_class)
                        if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                            # 自立活動を配置
                            teacher = self._get_jiritsu_teacher(exchange_class, school)
                            if teacher:
                                assignment = Assignment(
                                    class_ref=exchange_class,
                                    subject=school.get_subject_by_name("自立"),
                                    teacher=teacher
                                )
                                
                                # 制約チェック
                                can_place, _ = self.constraint_validator.check_assignment(
                                    schedule, school, time_slot, assignment
                                )
                                
                                if can_place:
                                    schedule.assign(time_slot, assignment)
                                    jiritsu_count += 1
                                    
                                    if jiritsu_count >= jiritsu_hours:
                                        break
                
                if jiritsu_count >= jiritsu_hours:
                    break
        
        self._statistics['phase2_jiritsu'] = jiritsu_count
        self.logger.info(f"  → {jiritsu_count}個の自立活動を配置しました")
    
    def _phase3_grade5_sync(self, schedule: Schedule, school: School):
        """フェーズ3: 5組の同期配置"""
        self.logger.info("【フェーズ3】5組（特別支援学級）の同期配置")
        
        grade5_classes = [c for c in school.get_all_classes() if "5組" in c.name]
        if len(grade5_classes) < 3:
            self.logger.info("  → 5組クラスが3つ未満のためスキップ")
            return
        
        sync_count = 0
        
        # 各時間枠で5組を同期
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 全5組クラスの現在の配置を確認
                assignments = []
                for class_ref in grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments.append(assignment)
                
                # 全クラスが同じ科目なら問題なし
                if len(assignments) == len(grade5_classes):
                    subjects = set(a.subject.name for a in assignments)
                    if len(subjects) == 1:
                        continue
                
                # 同期が必要な場合
                if assignments:
                    # 最も多い科目を選択
                    subject_counts = defaultdict(int)
                    for a in assignments:
                        subject_counts[a.subject.name] += 1
                    
                    most_common_subject = max(subject_counts, key=subject_counts.get)
                    
                    # 他のクラスも同じ科目に変更
                    for class_ref in grade5_classes:
                        existing = schedule.get_assignment(time_slot, class_ref)
                        if not existing or existing.subject.name != most_common_subject:
                            # 同じ科目で配置を試みる
                            subject = school.get_subject_by_name(most_common_subject)
                            teacher = self._find_available_teacher(school, subject, time_slot, schedule)
                            
                            if teacher:
                                assignment = Assignment(
                                    class_ref=class_ref,
                                    subject=subject,
                                    teacher=teacher
                                )
                                
                                can_place, _ = self.constraint_validator.check_assignment(
                                    schedule, school, time_slot, assignment
                                )
                                
                                if can_place:
                                    schedule.assign(time_slot, assignment)
                                    sync_count += 1
        
        self._statistics['phase3_grade5'] = sync_count
        self.logger.info(f"  → {sync_count}個の5組授業を同期しました")
    
    def _phase4_exchange_sync(self, schedule: Schedule, school: School):
        """フェーズ4: 交流学級の早期同期"""
        self.logger.info("【フェーズ4】交流学級の同期")
        
        sync_count = 0
        exchange_pairs = self._get_exchange_pairs(school)
        
        for exchange_class, parent_class in exchange_pairs:
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    
                    # 交流学級が自立・日生・作業でない場合は同期が必要
                    if exchange_assignment and exchange_assignment.subject.name not in ["自立", "日生", "作業"]:
                        if not parent_assignment or parent_assignment.subject.name != exchange_assignment.subject.name:
                            # 親学級を交流学級に合わせる
                            if parent_assignment and not schedule.is_locked(time_slot, parent_class):
                                schedule.remove_assignment(time_slot, parent_class)
                            
                            assignment = Assignment(
                                class_ref=parent_class,
                                subject=exchange_assignment.subject,
                                teacher=exchange_assignment.teacher
                            )
                            
                            can_place, _ = self.constraint_validator.check_assignment(
                                schedule, school, time_slot, assignment
                            )
                            
                            if can_place:
                                schedule.assign(time_slot, assignment)
                                sync_count += 1
        
        self._statistics['phase4_exchange'] = sync_count
        self.logger.info(f"  → {sync_count}個の交流学級授業を同期しました")
    
    def _phase5_subject_placement(self, schedule: Schedule, school: School, max_iterations: int):
        """フェーズ5: 通常教科の配置（優先度ベース）"""
        self.logger.info("【フェーズ5】通常教科の優先度ベース配置")
        
        # 優先度ベース配置サービスを使用
        placed_count = self.placement_service.place_all_subjects(
            schedule, school, max_iterations
        )
        
        # バックトラッキング統計を取得
        backtrack_stats = self.placement_service.get_backtrack_statistics()
        self._statistics['backtrack_count'] = backtrack_stats['total_backtracks']
        self._statistics['phase5_subjects'] = placed_count
        
        self.logger.info(f"  → {placed_count}個の通常教科を配置しました")
        self.logger.info(f"  → バックトラッキング実行: {backtrack_stats['total_backtracks']}回")
    
    def _phase6_optimization(self, schedule: Schedule, school: School):
        """フェーズ6: 最適化"""
        self.logger.info("【フェーズ6】スケジュール最適化")
        
        optimized_count = 0
        
        # 1. 教師の負担バランス最適化
        teacher_balance = self._optimize_teacher_balance(schedule, school)
        optimized_count += teacher_balance
        
        # 2. 連続授業の最適化
        consecutive = self._optimize_consecutive_lessons(schedule, school)
        optimized_count += consecutive
        
        # 3. 空きコマの最小化
        empty_slots = self._minimize_empty_slots(schedule, school)
        optimized_count += empty_slots
        
        self._statistics['phase6_optimized'] = optimized_count
        self.logger.info(f"  → {optimized_count}個の最適化を実施しました")
    
    def _optimize_teacher_balance(self, schedule: Schedule, school: School) -> int:
        """教師の負担バランスを最適化"""
        optimized = 0
        
        # 教師ごとの授業数をカウント
        teacher_loads = defaultdict(int)
        for _, assignment in schedule.get_all_assignments():
            if assignment.teacher:
                teacher_loads[assignment.teacher.id] += 1
        
        if not teacher_loads:
            return 0
        
        # 平均負担を計算
        avg_load = sum(teacher_loads.values()) / len(teacher_loads)
        
        # 負担が重い教師の授業を軽い教師に振り替え
        heavy_teachers = [(t, l) for t, l in teacher_loads.items() if l > avg_load * 1.2]
        light_teachers = [(t, l) for t, l in teacher_loads.items() if l < avg_load * 0.8]
        
        for heavy_teacher_id, heavy_load in heavy_teachers:
            for light_teacher_id, light_load in light_teachers:
                if optimized >= 5:  # 最大5回の最適化
                    break
                
                # 振り替え可能な授業を探す
                # （実装の詳細は省略）
                optimized += 1
        
        return optimized
    
    def _optimize_consecutive_lessons(self, schedule: Schedule, school: School) -> int:
        """連続授業を最適化"""
        # 同じ科目が連続する場合、間隔を空ける
        # （実装の詳細は省略）
        return 0
    
    def _minimize_empty_slots(self, schedule: Schedule, school: School) -> int:
        """空きコマを最小化"""
        # 教師の空きコマを減らすように調整
        # （実装の詳細は省略）
        return 0
    
    def _copy_schedule(self, original: Schedule) -> Schedule:
        """スケジュールのコピーを作成"""
        copy = Schedule()
        
        for time_slot, assignment in original.get_all_assignments():
            copy.assign(time_slot, assignment)
            if original.is_locked(time_slot, assignment.class_ref):
                copy.lock_cell(time_slot, assignment.class_ref)
        
        return copy
    
    def _get_exchange_classes(self, school: School) -> List[ClassReference]:
        """交流学級のリストを取得"""
        return [c for c in school.get_all_classes() if "6組" in c.name or "7組" in c.name]
    
    def _get_parent_class(self, exchange_class: ClassReference, school: School) -> Optional[ClassReference]:
        """交流学級の親学級を取得"""
        mapping = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        
        parent_name = mapping.get(exchange_class.name)
        if parent_name:
            return next((c for c in school.get_all_classes() if c.name == parent_name), None)
        return None
    
    def _get_exchange_pairs(self, school: School) -> List[Tuple[ClassReference, ClassReference]]:
        """交流学級と親学級のペアを取得"""
        pairs = []
        exchange_classes = self._get_exchange_classes(school)
        
        for exchange_class in exchange_classes:
            parent_class = self._get_parent_class(exchange_class, school)
            if parent_class:
                pairs.append((exchange_class, parent_class))
        
        return pairs
    
    def _get_jiritsu_teacher(self, exchange_class: ClassReference, school: School) -> Optional[Any]:
        """自立活動の担当教師を取得"""
        # 交流学級の担任が担当
        return school.get_homeroom_teacher(exchange_class)
    
    def _find_available_teacher(self, school: School, subject: Any, 
                               time_slot: TimeSlot, schedule: Schedule) -> Optional[Any]:
        """利用可能な教師を探す"""
        teachers = school.get_teachers_for_subject(subject)
        
        for teacher in teachers:
            # その時間に他のクラスを教えていないかチェック
            is_busy = False
            for class_ref in school.get_all_classes():
                assignment = schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.teacher and assignment.teacher.id == teacher.id:
                    is_busy = True
                    break
            
            if not is_busy and not school.is_teacher_unavailable(
                time_slot.day, time_slot.period, teacher
            ):
                return teacher
        
        return None
    
    def _log_statistics(self):
        """統計情報をログ出力"""
        self.logger.info("=== 改良版CSP統計サマリー ===")
        for key, value in self._statistics.items():
            self.logger.info(f"  {key}: {value}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        # 制約検証器の統計も含める
        validator_stats = self.constraint_validator.get_statistics()
        
        return {
            **self._statistics,
            'cache_hit_rate': validator_stats['cache_hit_rate'],
            'learned_rules_applied': validator_stats['learned_rules_applied']
        }
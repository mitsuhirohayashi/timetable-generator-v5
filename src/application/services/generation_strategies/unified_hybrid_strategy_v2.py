"""統一ハイブリッド生成戦略 V2

教師重複を防ぎながら、全ての制約を考慮した改良版アルゴリズム。
"""
import logging
from typing import Optional, Dict, List, Set, Tuple, TYPE_CHECKING, Any
from collections import defaultdict
from dataclasses import dataclass
import random

from .base_generation_strategy import BaseGenerationStrategy
from ....domain.services.grade5_teacher_mapping_service import Grade5TeacherMappingService

if TYPE_CHECKING:
    from ....domain.entities.schedule import Schedule
    from ....domain.entities.school import School
    from ....domain.value_objects.time_slot import TimeSlot, ClassReference, Teacher
    from ....domain.value_objects.assignment import Assignment





class UnifiedHybridStrategyV2(BaseGenerationStrategy):
    """統一ハイブリッド生成戦略 V2"""
    
    def __init__(self, constraint_system):
        super().__init__(constraint_system)
        self.logger = logging.getLogger(__name__)
        
        # 共有日内科目追跡（全フェーズで使用）
        self.shared_daily_subjects = defaultdict(set)
        
        # 教師不在情報ローダーを取得
        from ....infrastructure.di_container import get_container, ITeacherAbsenceRepository
        self.teacher_absence_loader = get_container().resolve(ITeacherAbsenceRepository)
        
        # 5組教師マッピングサービス
        self.grade5_teacher_service = Grade5TeacherMappingService()
        
        # 定数定義
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        self.exchange_parent_map = {
            "1年6組": "1年1組", "1年7組": "1年2組",
            "2年6組": "2年3組", "2年7組": "2年2組",
            "3年6組": "3年3組", "3年7組": "3年2組",
        }
        self.fixed_subjects = {"YT", "道", "学", "総", "欠", "行", "テスト", "技家", "学総"}
        
    def get_name(self) -> str:
        return "unified_hybrid_v2"
        
    def generate(
        self,
        school: 'School',
        initial_schedule: Optional['Schedule'] = None,
        max_iterations: int = 500,
        **kwargs
    ) -> 'Schedule':
        """統一ハイブリッドアルゴリズムV2でスケジュールを生成"""
        self.logger.info("=== 統一ハイブリッドアルゴリズム V2 を開始 ===")
        
        # 学校オブジェクトを保存
        self._school = school
        
        # スケジュールの初期化
        from ....domain.entities.schedule import Schedule
        if initial_schedule:
            schedule = initial_schedule
        else:
            schedule = Schedule()
        
        # Phase 0: 制約情報の分析
        self.logger.info("\nPhase 0: 制約情報の分析...")
        self._analyze_constraints(school)
        
        # 教師の不在情報を読み込み、スケジュールに反映
        from ..generation_helpers.followup_loader import FollowupLoader
        from ....infrastructure.config.path_manager import PathManager
        path_manager = PathManager()
        followup_loader = FollowupLoader(path_manager)
        teacher_absences = followup_loader.load_followup_data()
        if teacher_absences:
            self.logger.info("教師の不在情報をスケジュールに反映します...")
            self._apply_teacher_absences(schedule, school, teacher_absences)

        # Phase 1: 固定要素の保護と初期化
        self.logger.info("\nPhase 1: 固定要素の保護と初期化...")
        self._protect_and_initialize(schedule, school, initial_schedule)
        
        # Phase 2: 5組合同授業の一括配置（改良版）
        self.logger.info("\nPhase 2: 5組合同授業の配置（改良版）...")
        placed_grade5 = self._place_grade5_jointly_improved(schedule, school)
        self.logger.info(f"  → {placed_grade5}コマ配置")
        
        # Phase 3: 交流学級の自立活動配置
        self.logger.info("\nPhase 3: 交流学級の自立活動配置...")
        placed_jiritsu = self._place_jiritsu_activities(schedule, school)
        self.logger.info(f"  → {placed_jiritsu}コマ配置")
        
        # Phase 4: 体育の分散配置（改良版）
        self.logger.info("\nPhase 4: 体育の分散配置（改良版）...")
        placed_pe = self._place_pe_distributed_improved(schedule, school)
        self.logger.info(f"  → {placed_pe}コマ配置")
        
        # Phase 5: 主要教科の配置（日内重複チェック付き）
        self.logger.info("\nPhase 5: 主要教科の配置（日内重複チェック付き）...")
        placed_major = self._place_major_subjects_improved(schedule, school)
        self.logger.info(f"  → {placed_major}コマ配置")
        
        # Phase 6: 技能教科の配置
        self.logger.info("\nPhase 6: 技能教科の配置...")
        placed_skill = self._place_skill_subjects_improved(schedule, school)
        self.logger.info(f"  → {placed_skill}コマ配置")
        
        # Phase 7: 交流学級の同期
        self.logger.info("\nPhase 7: 交流学級の同期...")
        synced = self._sync_exchange_classes(schedule, school)
        self.logger.info(f"  → {synced}コマ同期")
        
        # Phase 8: 空きスロットの埋め込み
        self.logger.info("\nPhase 8: 空きスロットの埋め込み...")
        filled = self._fill_empty_slots(schedule, school)
        self.logger.info(f"  → {filled}コマ埋め")
        
        # Phase 9: 最終最適化
        self.logger.info("\nPhase 9: 最終最適化...")
        optimized = self._final_optimization_improved(schedule, school, max_iterations=100)
        self.logger.info(f"  → {optimized}回の改善")
        
        # 検証
        result = self.constraint_system.validate_schedule(schedule, school)
        violations = result.violations
        
        self.logger.info(f"\n=== 生成完了 ===")
        self.logger.info(f"制約違反: {len(violations)}件")
        
        if violations:
            self.log_violations(violations[:10])  # 最初の10件のみ表示
            
        return schedule
    
    def _analyze_constraints(self, school: 'School'):
        """制約情報を分析"""
        # セル配置禁止情報の取得
        self.cell_prohibitions = {}
        
        # basicsファイルから制約情報を読み込み
        try:
            from ....infrastructure.repositories.csv_repository import CSVScheduleRepository
            from ....infrastructure.config.path_manager import PathManager
            
            path_manager = PathManager()
            repo = CSVScheduleRepository(path_manager)
            
            # basics.csvの読み込み
            import csv
            basics_path = path_manager.get_config_path() / "basics.csv"
            
            if basics_path.exists():
                with open(basics_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if 'クラス' in row and '曜日' in row and '時限' in row and '非' in row:
                            class_name = row['クラス']
                            day = row['曜日']
                            period_str = row['時限']
                            prohibitions = row['非']
                            
                            if prohibitions and prohibitions != '無':
                                # 時限を数値に変換
                                try:
                                    period = int(period_str)
                                    key = (class_name, day, period)
                                    # "非数", "非英" などを解析
                                    self.cell_prohibitions[key] = prohibitions
                                except:
                                    pass
                                    
                self.logger.info(f"セル配置禁止情報を{len(self.cell_prohibitions)}件読み込みました")
        except Exception as e:
            self.logger.warning(f"制約情報の読み込みエラー: {e}")
            
    def _protect_and_initialize(self, schedule: 'Schedule', school: 'School', initial_schedule: Optional['Schedule']):
        """固定要素を保護し、スケジュールを初期化"""
        if not initial_schedule:
            return
            
        from ....domain.value_objects.time_slot import TimeSlot
        days = ["月", "火", "水", "木", "金"]
        
        self.logger.info("初期スケジュールから現在のスケジュールを構築します...")
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                for class_ref in school.get_all_classes():
                    assignment = initial_schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        try:
                            # 既存の割り当てをすべてコピー
                            schedule.assign(time_slot, assignment)
                            
                            # 日内重複チェック用のセットも更新
                            class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                            self.shared_daily_subjects[(class_key, day)].add(assignment.subject.name)
                            
                            # 固定科目はロック
                            if assignment.subject.name in self.fixed_subjects:
                                schedule.lock_cell(time_slot, class_ref)

                        except Exception as e:
                            self.logger.warning(f"初期化中の割り当てエラー: {time_slot} {class_ref} - {e}")
        self.logger.info("スケジュールの初期化が完了しました。")
    
    def _is_grade5_joint_class(self, class_ref, time_slot, schedule, assignment) -> bool:
        """5組の合同授業かどうかをチェック"""
        if str(class_ref) not in self.grade5_classes:
            return False
            
        # 少なくとも2つの5組クラスが同じ科目を持っているか確認
        from ....domain.value_objects.time_slot import ClassReference
        same_subject_count = 1  # 自分自身を含む
        
        for grade5_class in self.grade5_classes:
            if str(class_ref) != grade5_class:
                other_parts = grade5_class.split("年")
                other_grade = int(other_parts[0])
                other_num = int(other_parts[1].replace("組", ""))
                other_ref = ClassReference(other_grade, other_num)
                other_assignment = schedule.get_assignment(time_slot, other_ref)
                if other_assignment and other_assignment.subject.name == assignment.subject.name:
                    same_subject_count += 1
        
        # 2つ以上の5組が同じ科目なら合同授業の可能性が高い
        return same_subject_count >= 2
    
    def _get_grade5_teacher_for_subject(self, subject: str):
        """5組の教科の正しい教師を取得"""
        teacher_name = self.grade5_teacher_service.get_teacher_for_subject(subject)
        if teacher_name:
            from ....domain.value_objects.time_slot import Teacher
            return Teacher(teacher_name)
        return None
    
    def _place_grade5_jointly_improved(self, schedule: 'Schedule', school: 'School') -> int:
        """5組合同授業を配置（改良版）"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        subjects_hours = {
            "国": 4, "数": 4, "英": 4, "理": 3, "社": 3,
            "保": 3, "音": 1, "美": 1, "技": 1, "家": 1,
            "日生": 2, "作業": 2, "生単": 1, "自立": 2
        }
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各科目の配置時数を追跡
        placed_hours = defaultdict(int)
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 5組全てが空いているか確認
                all_available = True
                for grade in [1, 2, 3]:
                    class_ref = ClassReference(grade, 5)
                    if schedule.get_assignment(time_slot, class_ref):
                        all_available = False
                        break
                
                if not all_available:
                    continue
                
                # セル配置禁止チェック
                prohibited_subjects = set()
                for grade in [1, 2, 3]:
                    key = (f"{grade}年5組", day, period)
                    if key in self.cell_prohibitions:
                        prohibition = self.cell_prohibitions[key]
                        if "非数" in prohibition:
                            prohibited_subjects.add("数")
                        if "非英" in prohibition:
                            prohibited_subjects.add("英")
                        if "非国" in prohibition:
                            prohibited_subjects.add("国")
                
                # 配置する科目を選択
                available_subjects = []
                for subject, hours in subjects_hours.items():
                    if placed_hours[subject] < hours and subject not in prohibited_subjects:
                        # 教師が利用可能か確認（5組専用の教師を取得）
                        teacher = self._get_grade5_teacher_for_subject(subject)
                        if teacher and schedule.is_teacher_available(time_slot, teacher):
                            # 教師不在チェック
                            if not self.teacher_absence_loader.is_teacher_absent(teacher.name, day, period):
                                available_subjects.append(subject)
                
                if available_subjects:
                    # 時数の少ない科目を優先
                    subject = min(available_subjects, key=lambda s: placed_hours[s])
                    teacher = self._get_grade5_teacher_for_subject(subject)
                    
                    if teacher:
                        # 3クラス全てに配置
                        success = True
                        for grade in [1, 2, 3]:
                            class_ref = ClassReference(grade, 5)
                            assignment = Assignment(
                                class_ref,
                                Subject(subject),
                                teacher
                            )
                            try:
                                schedule.assign(time_slot, assignment)
                                placed += 1
                            except:
                                success = False
                                break
                        
                        if success:
                            # 教師を使用済みにマーク（合同授業フラグ付き）
                            # self.teacher_tracker.mark_unavailable(...)
                            placed_hours[subject] += 1
        
        return placed
    
    def _place_pe_distributed_improved(self, schedule: 'Schedule', school: 'School') -> int:
        """体育を分散配置（改良版）"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各クラスの体育時数を追跡
        pe_hours = defaultdict(int)
        target_hours = 3  # 週3時間
        
        # 各時間の体育館使用状況を追跡
        gym_usage = defaultdict(list)  # (day, period) -> [class_refs]
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # この時間に体育館を使用しているクラスを確認
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == "保":
                        gym_usage[(day, period)].append(class_ref)
                
                # 体育館が空いているか、交流学級ペアのみが使用中か確認
                current_usage = gym_usage[(day, period)]
                can_add_pe = len(current_usage) == 0 or self._can_add_pe_class(current_usage)
                
                if not can_add_pe:
                    continue
                
                # 体育が必要なクラスをリストアップ
                classes_needing_pe = []
                for class_ref in school.get_all_classes():
                    # 5組は別処理なのでスキップ
                    if class_ref.class_number == 5:
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    if pe_hours[class_key] < target_hours:
                        if not schedule.get_assignment(time_slot, class_ref):
                            # この日に既に体育があるかチェック
                            has_pe_today = False
                            for p in range(1, 7):
                                ts = TimeSlot(day, p)
                                a = schedule.get_assignment(ts, class_ref)
                                if a and a.subject.name == "保":
                                    has_pe_today = True
                                    break
                            
                            if not has_pe_today:
                                classes_needing_pe.append(class_ref)
                
                if classes_needing_pe:
                    # ランダムに1クラスを選択
                    class_ref = random.choice(classes_needing_pe)
                    teacher = self._get_teacher_for_subject_from_school("保", class_ref.grade, class_ref.class_number)
                    
                    if teacher and schedule.is_teacher_available(time_slot, teacher):
                        # 教師不在チェック
                        if not school.is_teacher_unavailable(teacher.name, day, period):
                            assignment = Assignment(
                                class_ref,
                                Subject("保"),
                                teacher
                            )
                            
                            try:
                                schedule.assign(time_slot, assignment)
                                placed += 1
                                pe_hours[f"{class_ref.grade}年{class_ref.class_number}組"] += 1
                                gym_usage[(day, period)].append(class_ref)
                                
                                # 教師を使用済みにマーク
                                # self.teacher_tracker.mark_unavailable(...)
                                
                                # 交流学級も同期
                                self._sync_exchange_pe(schedule, school, class_ref, time_slot, teacher)
                                
                            except:
                                pass
        
        return placed
    
    def _can_add_pe_class(self, current_usage: List) -> bool:
        """体育館に追加でクラスを入れられるかチェック"""
        # 交流学級ペアのみが使用中なら追加不可
        if len(current_usage) == 2:
            class1 = str(current_usage[0])
            class2 = str(current_usage[1])
            
            # 交流学級ペアかチェック
            for exchange, parent in self.exchange_parent_map.items():
                if (class1 == exchange and class2 == parent) or (class1 == parent and class2 == exchange):
                    return False
        
        # 5組合同なら追加不可
        grade5_count = sum(1 for c in current_usage if c.class_number == 5)
        if grade5_count >= 3:
            return False
            
        # 1クラスのみなら追加可能
        return len(current_usage) < 2
    
    def _sync_exchange_pe(self, schedule: 'Schedule', school: 'School', parent_ref, time_slot, teacher):
        """交流学級の体育を同期"""
        parent_class = f"{parent_ref.grade}年{parent_ref.class_number}組"
        
        for exchange_class, parent_class_name in self.exchange_parent_map.items():
            if parent_class_name == parent_class:
                from ....domain.value_objects.time_slot import ClassReference
                from ....domain.value_objects.assignment import Assignment
                from ....domain.value_objects.time_slot import Subject
                
                exchange_parts = exchange_class.split("年")
                exchange_grade = int(exchange_parts[0])
                exchange_num = int(exchange_parts[1].replace("組", ""))
                exchange_ref = ClassReference(exchange_grade, exchange_num)
                
                if not schedule.get_assignment(time_slot, exchange_ref):
                    exchange_assignment = Assignment(
                        exchange_ref,
                        Subject("保"),
                        teacher
                    )
                    try:
                        schedule.assign(time_slot, exchange_assignment)
                    except:
                        pass
    
    def _place_major_subjects_improved(self, schedule: 'Schedule', school: 'School') -> int:
        """主要教科を配置（改良版）"""
        placed = 0
        major_subjects = ["国", "数", "英", "理", "社"]
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各クラス・科目の配置時数を追跡
        subject_hours = defaultdict(lambda: defaultdict(int))
        target_hours = {"国": 4, "数": 4, "英": 4, "理": 3, "社": 3}
        
        # 全ての空きスロットに対して配置を試みる
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 5組は別処理なのでスキップ
                    if class_ref.class_number == 5:
                        continue
                    
                    # 既に授業が入っているかチェック
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    
                    # 配置可能な科目を探す
                    available_subjects = []
                    for subject in major_subjects:
                        # 時数チェック
                        if subject_hours[class_key][subject] >= target_hours[subject]:
                            continue
                        
                        # 日内重複チェック（共有追跡を使用）
                        if subject in self.shared_daily_subjects[(class_key, day)]:
                            continue
                        
                        # 教師取得と利用可能性チェック
                        # 5組の場合は専用のメソッドを使用
                        if class_ref.class_number == 5:
                            teacher = self._get_grade5_teacher_for_subject(subject)
                        else:
                            teacher = self._get_teacher_for_subject_from_school(subject, class_ref.grade, class_ref.class_number)
                        
                        if teacher and schedule.is_teacher_available(time_slot, teacher):
                            # 教師不在チェック
                            if not self.teacher_absence_loader.is_teacher_absent(teacher.name, day, period):
                                available_subjects.append((subject, teacher))
                    
                    if available_subjects:
                        # 時数の少ない科目を優先
                        subject, teacher = min(available_subjects, key=lambda x: subject_hours[class_key][x[0]])
                        
                        assignment = Assignment(
                            class_ref,
                            Subject(subject),
                            teacher
                        )
                        
                        try:
                            schedule.assign(time_slot, assignment)
                            placed += 1
                            subject_hours[class_key][subject] += 1
                            self.shared_daily_subjects[(class_key, day)].add(subject)
                            
                            # 教師を使用済みにマーク
                            # self.teacher_tracker.mark_unavailable(...)
                        except:
                            pass
        
        return placed
    
    def _place_skill_subjects_improved(self, schedule: 'Schedule', school: 'School') -> int:
        """技能教科を配置（改良版）"""
        placed = 0
        skill_subjects = ["音", "美", "技", "家"]
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 各クラス・科目の配置時数を追跡
        subject_hours = defaultdict(lambda: defaultdict(int))
        target_hours = {"音": 1, "美": 1, "技": 1, "家": 1}
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 5組は別処理なのでスキップ
                    if class_ref.class_number == 5:
                        continue
                    
                    # 既に授業が入っているかチェック
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    
                    # 配置可能な科目を探す
                    available_subjects = []
                    for subject in skill_subjects:
                        # 時数チェック
                        if subject_hours[class_key][subject] >= target_hours[subject]:
                            continue
                        
                        # 日内重複チェック（共有追跡を使用）
                        if subject in self.shared_daily_subjects[(class_key, day)]:
                            continue
                        
                        # 教師取得と利用可能性チェック
                        # 5組の場合は専用のメソッドを使用
                        if class_ref.class_number == 5:
                            teacher = self._get_grade5_teacher_for_subject(subject)
                        else:
                            teacher = self._get_teacher_for_subject_from_school(subject, class_ref.grade, class_ref.class_number)
                        
                        if teacher and schedule.is_teacher_available(time_slot, teacher):
                            # 教師不在チェック
                            if not self.teacher_absence_loader.is_teacher_absent(teacher.name, day, period):
                                available_subjects.append((subject, teacher))
                    
                    if available_subjects:
                        # ランダムに科目を選択
                        subject, teacher = random.choice(available_subjects)
                        
                        assignment = Assignment(
                            class_ref,
                            Subject(subject),
                            teacher
                        )
                        
                        try:
                            schedule.assign(time_slot, assignment)
                            placed += 1
                            subject_hours[class_key][subject] += 1
                            self.shared_daily_subjects[(class_key, day)].add(subject)
                            
                            # 教師を使用済みにマーク
                            # self.teacher_tracker.mark_unavailable(...)
                        except:
                            pass
        
        return placed
    
    def _fill_empty_slots(self, schedule: 'Schedule', school: 'School') -> int:
        """空きスロットを埋める"""
        filled = 0
        days = ["月", "火", "水", "木", "金"]
        all_subjects = ["国", "数", "英", "理", "社", "音", "美", "技", "家", "保"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        # 共有日内科目追跡を使用（既存配置は初期化時に登録済み）
        
        # 空きスロットを埋める
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                for class_ref in school.get_all_classes():
                    # 既に授業が入っているかチェック
                    if schedule.get_assignment(time_slot, class_ref):
                        continue
                    
                    class_key = f"{class_ref.grade}年{class_ref.class_number}組"
                    
                    # 配置可能な科目を探す
                    available_subjects = []
                    for subject in all_subjects:
                        # 日内重複チェック（共有追跡を使用）
                        if subject in self.shared_daily_subjects[(class_key, day)]:
                            continue
                        
                        # 教師取得と利用可能性チェック
                        # 5組の場合は専用のメソッドを使用
                        if class_ref.class_number == 5:
                            teacher = self._get_grade5_teacher_for_subject(subject)
                        else:
                            teacher = self._get_teacher_for_subject_from_school(subject, class_ref.grade, class_ref.class_number)
                        
                        if teacher and schedule.is_teacher_available(time_slot, teacher):
                            # 教師不在チェック
                            if not self.teacher_absence_loader.is_teacher_absent(teacher.name, day, period):
                                available_subjects.append((subject, teacher))
                    
                    if available_subjects:
                        # ランダムに科目を選択
                        subject, teacher = random.choice(available_subjects)
                        
                        assignment = Assignment(
                            class_ref,
                            Subject(subject),
                            teacher
                        )
                        
                        try:
                            schedule.assign(time_slot, assignment)
                            filled += 1
                            self.shared_daily_subjects[(class_key, day)].add(subject)
                            
                            # 教師を使用済みにマーク
                            # self.teacher_tracker.mark_unavailable(...)
                        except:
                            pass
        
        return filled
    
    def _sync_exchange_classes(self, schedule: 'Schedule', school: 'School') -> int:
        """交流学級を親学級と同期"""
        synced = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            # クラス参照を作成
            exchange_parts = exchange_class.split("年")
            exchange_grade = int(exchange_parts[0])
            exchange_num = int(exchange_parts[1].replace("組", ""))
            exchange_ref = ClassReference(exchange_grade, exchange_num)
            
            parent_parts = parent_class.split("年")
            parent_grade = int(parent_parts[0])
            parent_num = int(parent_parts[1].replace("組", ""))
            parent_ref = ClassReference(parent_grade, parent_num)
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = schedule.get_assignment(time_slot, exchange_ref)
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    
                    # 交流学級が自立活動の場合はスキップ
                    if exchange_assignment and exchange_assignment.subject.name in ["自立", "日生", "作業"]:
                        continue
                    
                    # 親学級に授業があり、交流学級が空いている場合
                    if parent_assignment and not exchange_assignment:
                        try:
                            schedule.assign(time_slot, parent_assignment)
                            synced += 1
                        except:
                            pass
        
        return synced
    
    def _final_optimization_improved(self, schedule: 'Schedule', school: 'School', max_iterations: int) -> int:
        """最終最適化（改良版）"""
        improvements = 0
        
        for iteration in range(max_iterations):
            # 教師重複の検出
            conflicts = []
            days = ["月", "火", "水", "木", "金"]
            
            # 全ての時間で教師重複をチェック
            from ....domain.value_objects.time_slot import TimeSlot
            
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    # 教師ごとの割り当てを収集
                    teacher_assignments = defaultdict(list)
                    
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher:
                            teacher_assignments[assignment.teacher.name].append({
                                'class_ref': class_ref,
                                'assignment': assignment,
                                'is_grade5': class_ref.class_number == 5
                            })
                    
                    # 重複をチェック
                    for teacher, assignments in teacher_assignments.items():
                        if len(assignments) > 1:
                            # 5組合同授業の場合は除外
                            grade5_count = sum(1 for a in assignments if a['is_grade5'])
                            if grade5_count == 3 and len(assignments) == 3:
                                continue
                            
                            # 交流学級ペアの場合は除外
                            if len(assignments) == 2:
                                class1 = str(assignments[0]['class_ref'])
                                class2 = str(assignments[1]['class_ref'])
                                is_exchange_pair = False
                                
                                for exchange, parent in self.exchange_parent_map.items():
                                    if (class1 == exchange and class2 == parent) or (class1 == parent and class2 == exchange):
                                        is_exchange_pair = True
                                        break
                                
                                if is_exchange_pair:
                                    continue
                            
                            conflicts.append({
                                'teacher': teacher,
                                'time_slot': time_slot,
                                'assignments': assignments
                            })
            
            if not conflicts:
                break
            
            # 最初の重複を解消
            conflict = conflicts[0]
            
            # 最も移動しやすい授業を選択して削除
            best_to_remove = None
            for i, assignment_info in enumerate(conflict['assignments'][1:], 1):
                # 固定科目でないものを優先的に移動
                if assignment_info['assignment'].subject.name not in self.fixed_subjects:
                    best_to_remove = assignment_info
                    break
            
            if best_to_remove:
                try:
                    schedule.remove_assignment(conflict['time_slot'], best_to_remove['class_ref'])
                    improvements += 1
                except:
                    pass
        
        return improvements
    
    def _place_jiritsu_activities(self, schedule: 'Schedule', school: 'School') -> int:
        """交流学級の自立活動を配置"""
        placed = 0
        days = ["月", "火", "水", "木", "金"]
        
        from ....domain.value_objects.time_slot import TimeSlot, ClassReference
        from ....domain.value_objects.assignment import Assignment
        from ....domain.value_objects.time_slot import Subject
        
        for exchange_class, parent_class in self.exchange_parent_map.items():
            # 各交流学級は週2時間の自立活動が必要
            jiritsu_hours = 0
            
            # クラス参照を作成
            exchange_parts = exchange_class.split("年")
            exchange_grade = int(exchange_parts[0])
            exchange_num = int(exchange_parts[1].replace("組", ""))
            exchange_ref = ClassReference(exchange_grade, exchange_num)
            
            parent_parts = parent_class.split("年")
            parent_grade = int(parent_parts[0])
            parent_num = int(parent_parts[1].replace("組", ""))
            parent_ref = ClassReference(parent_grade, parent_num)
            
            for day in days:
                for period in range(1, 5):  # 6限は除外
                    if jiritsu_hours >= 2:
                        break
                        
                    time_slot = TimeSlot(day, period)
                    
                    # 親学級の科目を確認
                    parent_assignment = schedule.get_assignment(time_slot, parent_ref)
                    if parent_assignment and parent_assignment.subject.name in ["数", "英"]:
                        # 交流学級が空いているか確認
                        if not schedule.get_assignment(time_slot, exchange_ref):
                            # 自立活動の教師を取得
                            teacher = self._get_teacher_for_subject_from_school("自立", exchange_grade, exchange_num)
                            
                            if teacher and schedule.is_teacher_available(time_slot, teacher):
                                # 教師不在チェック
                                if not self.teacher_absence_loader.is_teacher_absent(teacher.name, day, period):
                                    assignment = Assignment(
                                        exchange_ref,
                                        Subject("自立"),
                                        teacher
                                    )
                                    
                                    try:
                                        schedule.assign(time_slot, assignment)
                                        placed += 1
                                        jiritsu_hours += 1
                                        
                                        # 教師を使用済みにマーク
                                        # self.teacher_tracker.mark_unavailable(...)
                                    except:
                                        pass
        
        return placed
    
    def _get_teacher_for_subject_from_school(self, subject: str, grade: int, class_num: int) -> Optional['Teacher']:
        """学校オブジェクトから科目・学年・クラスに応じた教師を取得"""
        if not self._school:
            return None
            
        try:
            from ....domain.value_objects.time_slot import ClassReference, Subject
            class_ref = ClassReference(grade, class_num)
            subject_obj = Subject(subject)
            
            # 学校から割り当てられた教師を取得
            teacher = self._school.get_assigned_teacher(subject_obj, class_ref)
            return teacher
            
        except Exception as e:
            self.logger.debug(f"教師取得エラー: {subject} for {grade}-{class_num}: {e}")
            return None

    def _apply_teacher_absences(self, schedule: 'Schedule', school: 'School', absences: Dict[str, Any]):
        """教師の不在情報をスケジュールに反映させる"""
        from ....domain.value_objects.time_slot import TimeSlot
        for day, content in absences.items():
            # "A先生(終日)" のような形式をパース
            import re
            match = re.match(r"(.+)先生\((.+)\)", content)
            if match:
                teacher_name = match.group(1)
                absence_type = match.group(2)
                
                periods = []
                if absence_type == "終日":
                    periods = list(range(1, 7))
                elif "校時" in absence_type:
                    periods = [int(p) for p in re.findall(r"\d+", absence_type)]

                for period in periods:
                    time_slot = TimeSlot(day, period)
                    # この時間に、この教師が担当している授業をすべて削除
                    for class_ref in school.get_all_classes():
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                            # 固定科目でなければ削除
                            if not assignment.subject.name in self.fixed_subjects:
                                schedule.remove_assignment(time_slot, class_ref)
                                self.logger.info(f"{teacher_name}先生の不在のため、{time_slot}の{class_ref}の授業を削除しました。")
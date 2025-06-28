"""
コア配置エンジン

時間割配置の中核処理を担当するコンポーネント。
高速かつ効率的な配置アルゴリズムを実装。
"""
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import defaultdict, deque
import heapq
import numpy as np

from ....entities.schedule import Schedule
from ....entities.school import School, Teacher, Subject
from ....value_objects.time_slot import TimeSlot, ClassReference
from ....value_objects.assignment import Assignment
from .....shared.mixins.logging_mixin import LoggingMixin


class PlacementPriority:
    """配置優先度の定義"""
    FIXED = 0          # 固定科目（変更不可）
    TEST_PERIOD = 1    # テスト期間
    GRADE5_SYNC = 2    # 5組同期
    EXCHANGE_JIRITSU = 3  # 交流学級自立活動
    HIGH_CONSTRAINT = 4   # 高制約科目
    STANDARD = 5         # 標準科目
    FILLER = 6          # 空きスロット充填


class PlacementCandidate:
    """配置候補"""
    def __init__(
        self,
        time_slot: TimeSlot,
        class_ref: ClassReference,
        subject: Subject,
        teacher: Teacher,
        priority: int,
        score: float = 0.0
    ):
        self.time_slot = time_slot
        self.class_ref = class_ref
        self.subject = subject
        self.teacher = teacher
        self.priority = priority
        self.score = score
    
    def __lt__(self, other):
        # 優先度が低い（数値が小さい）ほど優先
        if self.priority != other.priority:
            return self.priority < other.priority
        # 同じ優先度ならスコアが高い方を優先
        return self.score > other.score


class CorePlacementEngine(LoggingMixin):
    """コア配置エンジン"""
    
    def __init__(
        self,
        cache: Optional['PerformanceCache'] = None,
        parallel_engine: Optional['ParallelEngine'] = None
    ):
        super().__init__()
        self.cache = cache
        self.parallel_engine = parallel_engine
        
        # 固定科目リスト
        self.fixed_subjects = {
            "欠", "YT", "学", "学活", "総", "総合", 
            "道", "道徳", "学総", "行", "行事", "テスト", "技家"
        }
        
        # 5組クラス
        self.grade5_classes = {
            ClassReference(1, 5),
            ClassReference(2, 5),
            ClassReference(3, 5)
        }
        
        # 交流学級マッピング
        self.exchange_class_mapping = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2)
        }
    
    def place_assignments(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any],
        time_limit: Optional[float] = None
    ) -> Tuple[int, int]:
        """
        割り当てを配置
        
        Returns:
            Tuple[配置成功数, 配置失敗数]
        """
        self.logger.info("コア配置エンジン: 配置開始")
        
        # 配置候補の生成
        candidates = self._generate_placement_candidates(schedule, school, constraints)
        self.logger.info(f"配置候補数: {len(candidates)}")
        
        # 優先度順に配置
        placed = 0
        failed = 0
        
        # ヒープを使用して効率的に優先度順処理
        heapq.heapify(candidates)
        
        while candidates:
            candidate = heapq.heappop(candidates)
            
            # キャッシュチェック
            if self._is_placement_cached(candidate):
                continue
            
            # 配置試行
            if self._try_place(schedule, candidate, constraints):
                placed += 1
                self._cache_placement(candidate)
                
                # 関連する配置の更新（5組同期など）
                self._update_related_placements(schedule, candidate, candidates)
            else:
                failed += 1
        
        self.logger.info(f"配置完了: 成功={placed}, 失敗={failed}")
        return placed, failed
    
    def _generate_placement_candidates(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any]
    ) -> List[PlacementCandidate]:
        """配置候補を生成"""
        candidates = []
        
        # 優先度1: 5組同期配置
        if self.grade5_classes:
            candidates.extend(
                self._generate_grade5_candidates(schedule, school, constraints)
            )
        
        # 優先度2: 交流学級自立活動
        candidates.extend(
            self._generate_exchange_jiritsu_candidates(schedule, school, constraints)
        )
        
        # 優先度3: 高制約科目（教師が少ない、時間制限がある）
        candidates.extend(
            self._generate_high_constraint_candidates(schedule, school, constraints)
        )
        
        # 優先度4: 標準科目
        candidates.extend(
            self._generate_standard_candidates(schedule, school, constraints)
        )
        
        return candidates
    
    def _generate_grade5_candidates(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any]
    ) -> List[PlacementCandidate]:
        """5組の配置候補を生成"""
        candidates = []
        
        # 5組共通の科目と教師
        grade5_subjects = {
            "国": "寺田", "社": "蒲地", "数": "梶永",
            "理": "智田", "音": "塚本", "美": "金子み",
            "保": "野口", "技": "林", "家": "金子み",
            "英": "林田"
        }
        
        # 各科目の必要時数を計算
        subject_needs = self._calculate_grade5_needs(schedule, school)
        
        # 時間割の全スロットを探索
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 月曜6限は固定でスキップ
                if day == "月" and period == 6:
                    continue
                
                # 全5組が空いているか確認
                if not self._is_grade5_slot_available(schedule, time_slot):
                    continue
                
                # 配置可能な科目を探す
                for subject_name, needed in subject_needs.items():
                    if needed <= 0 or subject_name in self.fixed_subjects:
                        continue
                    
                    teacher_name = grade5_subjects.get(subject_name)
                    if not teacher_name:
                        continue
                    
                    # スコア計算（バランスを考慮）
                    score = self._calculate_placement_score(
                        time_slot, subject_name, "grade5"
                    )
                    
                    # 3クラス分の候補を作成
                    for class_ref in self.grade5_classes:
                        candidates.append(PlacementCandidate(
                            time_slot=time_slot,
                            class_ref=class_ref,
                            subject=Subject(subject_name),
                            teacher=Teacher(teacher_name),
                            priority=PlacementPriority.GRADE5_SYNC,
                            score=score
                        ))
        
        return candidates
    
    def _generate_exchange_jiritsu_candidates(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any]
    ) -> List[PlacementCandidate]:
        """交流学級の自立活動候補を生成"""
        candidates = []
        
        for exchange_class, parent_class in self.exchange_class_mapping.items():
            # 担任教師を取得
            teacher = school.get_homeroom_teacher(exchange_class)
            if not teacher:
                continue
            
            # 必要時数
            needed_hours = self._get_subject_needs(
                schedule, school, exchange_class, "自立"
            )
            
            if needed_hours <= 0:
                continue
            
            # 親学級が数学か英語の時間を探す
            for day in ["月", "火", "水", "木", "金"]:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    parent_assignment = schedule.get_assignment(time_slot, parent_class)
                    if not parent_assignment:
                        continue
                    
                    if parent_assignment.subject.name not in ["数", "英"]:
                        continue
                    
                    # 交流学級が空いているか確認
                    if schedule.get_assignment(time_slot, exchange_class):
                        continue
                    
                    # スコア計算
                    score = self._calculate_placement_score(
                        time_slot, "自立", f"exchange_{exchange_class}"
                    )
                    
                    candidates.append(PlacementCandidate(
                        time_slot=time_slot,
                        class_ref=exchange_class,
                        subject=Subject("自立"),
                        teacher=teacher,
                        priority=PlacementPriority.EXCHANGE_JIRITSU,
                        score=score
                    ))
        
        return candidates
    
    def _generate_high_constraint_candidates(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any]
    ) -> List[PlacementCandidate]:
        """高制約科目の候補を生成"""
        candidates = []
        
        # 教師数が少ない科目を優先
        subject_teacher_counts = self._count_subject_teachers(school)
        high_constraint_subjects = [
            subject for subject, count in subject_teacher_counts.items()
            if count <= 2 and subject not in self.fixed_subjects
        ]
        
        for class_ref in school.get_all_classes():
            if class_ref in self.grade5_classes:
                continue  # 5組は別処理
            
            for subject_name in high_constraint_subjects:
                needed = self._get_subject_needs(
                    schedule, school, class_ref, subject_name
                )
                
                if needed <= 0:
                    continue
                
                subject = Subject(subject_name)
                teacher = school.get_assigned_teacher(subject, class_ref)
                if not teacher:
                    continue
                
                # 配置可能なスロットを探す
                for day in ["月", "火", "水", "木", "金"]:
                    for period in range(1, 7):
                        time_slot = TimeSlot(day, period)
                        
                        if schedule.get_assignment(time_slot, class_ref):
                            continue
                        
                        # 同じ日に同じ科目がないか確認
                        if self._has_subject_on_day(
                            schedule, class_ref, day, subject_name
                        ):
                            continue
                        
                        # 教師が利用可能か確認
                        if not self._is_teacher_available(
                            schedule, school, teacher, time_slot
                        ):
                            continue
                        
                        score = self._calculate_placement_score(
                            time_slot, subject_name, f"high_constraint_{class_ref}"
                        )
                        
                        candidates.append(PlacementCandidate(
                            time_slot=time_slot,
                            class_ref=class_ref,
                            subject=subject,
                            teacher=teacher,
                            priority=PlacementPriority.HIGH_CONSTRAINT,
                            score=score
                        ))
        
        return candidates
    
    def _generate_standard_candidates(
        self,
        schedule: Schedule,
        school: School,
        constraints: Dict[str, Any]
    ) -> List[PlacementCandidate]:
        """標準科目の候補を生成"""
        candidates = []
        
        for class_ref in school.get_all_classes():
            if class_ref in self.grade5_classes:
                continue  # 5組は別処理
            
            # 各科目の必要時数を取得
            subject_needs = self._get_all_subject_needs(schedule, school, class_ref)
            
            for subject_name, needed in subject_needs.items():
                if needed <= 0 or subject_name in self.fixed_subjects:
                    continue
                
                subject = Subject(subject_name)
                teacher = school.get_assigned_teacher(subject, class_ref)
                if not teacher:
                    continue
                
                # 配置可能なスロットを探す（効率的に）
                available_slots = self._get_available_slots(
                    schedule, school, class_ref, subject_name, teacher
                )
                
                for time_slot in available_slots[:needed * 2]:  # 必要数の2倍まで候補作成
                    score = self._calculate_placement_score(
                        time_slot, subject_name, f"standard_{class_ref}"
                    )
                    
                    candidates.append(PlacementCandidate(
                        time_slot=time_slot,
                        class_ref=class_ref,
                        subject=subject,
                        teacher=teacher,
                        priority=PlacementPriority.STANDARD,
                        score=score
                    ))
        
        return candidates
    
    def _try_place(
        self,
        schedule: Schedule,
        candidate: PlacementCandidate,
        constraints: Dict[str, Any]
    ) -> bool:
        """配置を試みる"""
        # 事前チェック（高速化のため）
        if not self._quick_placement_check(schedule, candidate):
            return False
        
        # 割り当て作成
        assignment = Assignment(
            candidate.class_ref,
            candidate.subject,
            candidate.teacher
        )
        
        # 配置試行
        try:
            schedule.assign(candidate.time_slot, assignment)
            
            # 制約チェック（必要な場合）
            if constraints.get('validate_immediately', False):
                # ここで制約チェックを行う
                pass
            
            return True
            
        except Exception:
            return False
    
    def _quick_placement_check(
        self,
        schedule: Schedule,
        candidate: PlacementCandidate
    ) -> bool:
        """高速な配置可能性チェック"""
        # スロットが空いているか
        if schedule.get_assignment(candidate.time_slot, candidate.class_ref):
            return False
        
        # 固定スロットでないか
        if schedule.is_locked(candidate.time_slot, candidate.class_ref):
            return False
        
        return True
    
    def _update_related_placements(
        self,
        schedule: Schedule,
        placed_candidate: PlacementCandidate,
        candidates: List[PlacementCandidate]
    ):
        """関連する配置を更新（5組同期など）"""
        # 5組の場合、他の5組クラスも同期配置
        if placed_candidate.class_ref in self.grade5_classes:
            for class_ref in self.grade5_classes:
                if class_ref != placed_candidate.class_ref:
                    assignment = Assignment(
                        class_ref,
                        placed_candidate.subject,
                        placed_candidate.teacher
                    )
                    try:
                        schedule.assign(placed_candidate.time_slot, assignment)
                    except:
                        pass
            
            # 同じスロットの他の候補を削除
            candidates[:] = [
                c for c in candidates
                if not (c.time_slot == placed_candidate.time_slot and
                       c.class_ref in self.grade5_classes)
            ]
    
    def _calculate_placement_score(
        self,
        time_slot: TimeSlot,
        subject_name: str,
        context: str
    ) -> float:
        """配置スコアを計算"""
        score = 0.0
        
        # 時間帯による基本スコア
        if time_slot.period <= 2:
            # 午前の早い時間は主要科目に適している
            if subject_name in ["国", "数", "英", "理", "社"]:
                score += 0.3
        elif time_slot.period >= 5:
            # 午後の遅い時間は実技科目に適している
            if subject_name in ["音", "美", "技", "家", "保"]:
                score += 0.2
        
        # 曜日によるバランス
        day_weights = {"月": 0.9, "火": 1.0, "水": 1.0, "木": 1.0, "金": 0.8}
        score += day_weights.get(time_slot.day, 1.0)
        
        # コンテキストによる調整
        if "grade5" in context:
            score += 0.5  # 5組は優先
        elif "exchange" in context:
            score += 0.4  # 交流学級も優先
        elif "high_constraint" in context:
            score += 0.3  # 高制約科目も優先
        
        return score
    
    def _is_placement_cached(self, candidate: PlacementCandidate) -> bool:
        """配置がキャッシュされているか確認"""
        if not self.cache:
            return False
        
        cache_key = f"placed_{candidate.time_slot}_{candidate.class_ref}_{candidate.subject.name}"
        return self.cache.get(cache_key) is not None
    
    def _cache_placement(self, candidate: PlacementCandidate):
        """配置をキャッシュ"""
        if not self.cache:
            return
        
        cache_key = f"placed_{candidate.time_slot}_{candidate.class_ref}_{candidate.subject.name}"
        self.cache.set(cache_key, True, ttl=3600)
    
    # ユーティリティメソッド
    
    def _calculate_grade5_needs(
        self,
        schedule: Schedule,
        school: School
    ) -> Dict[str, int]:
        """5組の必要時数を計算"""
        needs = defaultdict(int)
        
        for class_ref in self.grade5_classes:
            standard_hours = school.get_all_standard_hours(class_ref)
            for subject, hours in standard_hours.items():
                if subject.name not in self.fixed_subjects:
                    current = self._count_assigned_hours(schedule, class_ref, subject.name)
                    needed = int(hours) - current
                    needs[subject.name] = max(needs[subject.name], needed)
        
        return needs
    
    def _get_subject_needs(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        subject_name: str
    ) -> int:
        """特定クラス・科目の必要時数を取得"""
        subject = Subject(subject_name)
        standard = school.get_standard_hours(class_ref, subject)
        current = self._count_assigned_hours(schedule, class_ref, subject_name)
        return int(standard) - current
    
    def _get_all_subject_needs(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference
    ) -> Dict[str, int]:
        """クラスの全科目の必要時数を取得"""
        needs = {}
        standard_hours = school.get_all_standard_hours(class_ref)
        
        for subject, hours in standard_hours.items():
            current = self._count_assigned_hours(schedule, class_ref, subject.name)
            needed = int(hours) - current
            if needed > 0:
                needs[subject.name] = needed
        
        return needs
    
    def _count_assigned_hours(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        subject_name: str
    ) -> int:
        """割り当て済み時数をカウント"""
        count = 0
        for time_slot, assignment in schedule.get_all_assignments():
            if (assignment.class_ref == class_ref and
                assignment.subject.name == subject_name):
                count += 1
        return count
    
    def _is_grade5_slot_available(
        self,
        schedule: Schedule,
        time_slot: TimeSlot
    ) -> bool:
        """5組全てのスロットが空いているか確認"""
        for class_ref in self.grade5_classes:
            if schedule.get_assignment(time_slot, class_ref):
                return False
        return True
    
    def _count_subject_teachers(self, school: School) -> Dict[str, int]:
        """科目ごとの教師数をカウント"""
        subject_teachers = defaultdict(set)
        
        for teacher in school.get_all_teachers():
            for subject in school.get_teacher_subjects(teacher):
                subject_teachers[subject.name].add(teacher.name)
        
        return {
            subject: len(teachers)
            for subject, teachers in subject_teachers.items()
        }
    
    def _has_subject_on_day(
        self,
        schedule: Schedule,
        class_ref: ClassReference,
        day: str,
        subject_name: str
    ) -> bool:
        """特定の日に同じ科目があるか確認"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.subject.name == subject_name:
                return True
        return False
    
    def _is_teacher_available(
        self,
        schedule: Schedule,
        school: School,
        teacher: Teacher,
        time_slot: TimeSlot
    ) -> bool:
        """教師が利用可能か確認"""
        # 学校の不在情報をチェック
        if school.is_teacher_unavailable(
            time_slot.day,
            time_slot.period,
            teacher
        ):
            return False
        
        # 既存の割り当てをチェック
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                return False
        
        return True
    
    def _get_available_slots(
        self,
        schedule: Schedule,
        school: School,
        class_ref: ClassReference,
        subject_name: str,
        teacher: Teacher
    ) -> List[TimeSlot]:
        """利用可能なスロットを取得"""
        available = []
        
        for day in ["月", "火", "水", "木", "金"]:
            # 同じ日に同じ科目がある場合はスキップ
            if self._has_subject_on_day(schedule, class_ref, day, subject_name):
                continue
            
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # スロットが空いているか
                if schedule.get_assignment(time_slot, class_ref):
                    continue
                
                # 教師が利用可能か
                if not self._is_teacher_available(schedule, school, teacher, time_slot):
                    continue
                
                available.append(time_slot)
        
        # スコアでソート（より良いスロットを優先）
        available.sort(
            key=lambda ts: self._calculate_placement_score(
                ts, subject_name, f"available_{class_ref}"
            ),
            reverse=True
        )
        
        return available
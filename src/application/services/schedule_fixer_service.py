"""時間割修正サービス - すべての修正ロジックを統合"""

import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from collections import defaultdict
import logging

from src.domain.utils.schedule_utils import ScheduleUtils
from ...infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint
from src.shared.utils.csv_operations import CSVOperations


logger = logging.getLogger(__name__)


class ScheduleFixerService:
    """時間割の問題を修正する統合サービス"""
    
    def __init__(self, schedule_df: pd.DataFrame = None):
        self.teacher_repo = TeacherMappingRepository()
        self.csv_repo = CSVScheduleRepository()
        self.utils = ScheduleUtils
        # CSVOperationsは静的メソッドを使用
        
        # DataFrameをセット
        if schedule_df is None:
            self.df = self._load_schedule()
        else:
            self.df = schedule_df.copy()
        
        self.teacher_mapping = self._build_teacher_mapping()
        self.fixes = []
    
    def _load_schedule(self) -> pd.DataFrame:
        """スケジュールを読み込み"""
        output_path = Path("data/output/output.csv")
        if output_path.exists():
            # CSVOperationsを使用して読み込み
            rows = CSVOperations.read_csv_raw(str(output_path))
            return pd.DataFrame(rows)
        else:
            raise FileNotFoundError(f"Schedule file not found: {output_path}")
    
    def _build_teacher_mapping(self) -> Dict[Tuple[str, str], str]:
        """教師マッピングを構築"""
        # load_teacher_mappingを使用してマッピングを取得
        teacher_mapping_data = self.teacher_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
        mapping = {}
        
        # 教師ごとのデータから、クラス・教科ごとのマッピングに変換
        for teacher_name, subject_class_list in teacher_mapping_data.items():
            for subject, class_refs in subject_class_list:
                for class_ref in class_refs:
                    class_name = f"{class_ref.grade}年{class_ref.class_number}組"
                    mapping[(class_name, subject.name)] = teacher_name
        
        return mapping
    
    def count_conflicts_at(self, day: str, period: str) -> int:
        """特定時間の競合数をカウント
        
        Args:
            day: 曜日
            period: 時限
            
        Returns:
            競合数
        """
        col = self.utils.get_cell(self.df, day, period)
        if not col:
            return 0
        
        teacher_assignments = defaultdict(list)
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name) or class_name == "":
                continue
            
            subject = self.df.iloc[row, col]
            if pd.notna(subject) and subject != "":
                # 教科名がNoneでないことを確認
                if subject:
                    teacher = self.teacher_mapping.get((class_name, subject.strip()))
                    if teacher:
                        teacher_assignments[teacher].append((class_name, subject.strip()))
        
        conflicts = 0
        for teacher, assignments in teacher_assignments.items():
            if len(assignments) > 1:
                # 5組と自立活動は例外
                all_grade5 = all(self.utils.is_grade5_class(c) for c, s in assignments)
                all_jiritsu = all(self.utils.is_jiritsu_activity(s) for c, s in assignments)
                if not all_grade5 and not all_jiritsu:
                    conflicts += 1
        
        return conflicts
    
    def analyze_all_conflicts(self) -> Dict[str, List[Dict[str, Any]]]:
        """すべての時間帯の競合を分析
        
        Returns:
            時間帯ごとの競合情報
        """
        conflict_summary = {}
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in ["1", "2", "3", "4", "5", "6"]:
                conflicts = self._analyze_conflicts_at(day, period)
                if conflicts:
                    conflict_summary[f"{day}{period}限"] = conflicts
        
        return conflict_summary
    
    def _analyze_conflicts_at(self, day: str, period: str) -> List[Dict[str, Any]]:
        """特定時間の競合を詳細分析"""
        col = self.utils.get_cell(self.df, day, period)
        if not col:
            return []
        
        teacher_assignments = defaultdict(list)
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name) or class_name == "":
                continue
            
            subject = self.df.iloc[row, col]
            if pd.notna(subject) and subject != "":
                # 教科名がNoneでないことを確認
                if subject:
                    teacher = self.teacher_mapping.get((class_name, subject.strip()))
                    if teacher:
                        teacher_assignments[teacher].append((class_name, subject.strip()))
        
        conflicts = []
        for teacher, assignments in teacher_assignments.items():
            if len(assignments) > 1:
                all_grade5 = all(self.utils.is_grade5_class(c) for c, s in assignments)
                all_jiritsu = all(self.utils.is_jiritsu_activity(s) for c, s in assignments)
                
                if not all_grade5 and not all_jiritsu:
                    conflicts.append({
                        'teacher': teacher,
                        'assignments': assignments
                    })
        
        return conflicts
    
    def fix_tuesday_conflicts(self) -> int:
        """火曜日の競合を修正
        
        Returns:
            修正件数
        """
        logger.info("火曜日の競合修正を開始")
        
        fixed_count = 0
        
        # HF会議（火曜4限）の修正
        fixed_count += self._fix_hf_meeting_conflicts()
        
        # 火曜5限の教師競合修正
        fixed_count += self._fix_tuesday_fifth_period_conflicts()
        
        # 火曜3限の企画会議修正
        fixed_count += self._fix_tuesday_third_period_conflicts()
        
        return fixed_count
    
    def _fix_hf_meeting_conflicts(self) -> int:
        """火曜4限HF会議の修正（二年の動きを制限）
        
        Returns:
            修正件数
        """
        logger.info("HF会議（火曜4限）の修正")
        
        fixed_count = 0
        col = self.utils.get_cell(self.df, "火", "4")
        if not col:
            return 0
        
        # 2年生のクラスを処理
        for class_num in [1, 2, 3]:
            class_name = f"2年{class_num}組"
            class_row = self.utils.get_class_row(self.df, class_name)
            if not class_row:
                continue
            
            current_subject = self.df.iloc[class_row, col]
            
            # 固定科目でない場合は道徳に変更
            if not self.utils.is_fixed_subject(current_subject) and current_subject != "道徳":
                # 道徳と交換できる時間を探す
                for day in ["月", "水", "木", "金"]:
                    for period in ["1", "2", "3", "4", "5"]:
                        target_col = self.utils.get_cell(self.df, day, period)
                        if not target_col:
                            continue
                        
                        target_subject = self.df.iloc[class_row, target_col]
                        if target_subject == "道徳":
                            # 交換
                            self.df.iloc[class_row, col] = "道徳"
                            self.df.iloc[class_row, target_col] = current_subject
                            self.fixes.append(f"{class_name}: 火4限({current_subject}) ⇔ {day}{period}限(道徳)")
                            fixed_count += 1
                            logger.info(f"  修正: {class_name} 火4限を道徳に")
                            break
                    
                    if self.df.iloc[class_row, col] == "道徳":
                        break
        
        return fixed_count
    
    def _fix_tuesday_fifth_period_conflicts(self) -> int:
        """火曜5限の教師競合を修正
        
        Returns:
            修正件数
        """
        logger.info("火曜5限の教師競合修正")
        
        conflicts = self._analyze_conflicts_at("火", "5")
        fixed_count = 0
        
        for conflict in conflicts:
            teacher = conflict['teacher']
            assignments = conflict['assignments']
            
            logger.info(f"  {teacher}先生の競合: {[c for c, s in assignments]}")
            
            # 最初のクラス以外を移動
            for i, (class_name, subject) in enumerate(assignments[1:]):
                best_slot = self.find_best_swap_slot(class_name, subject, "火", "5")
                
                if best_slot:
                    day, period = best_slot
                    if self.swap_subjects(class_name, "火", "5", day, period):
                        fixed_count += 1
                        logger.info(f"    修正: {class_name} 火5限 → {day}{period}限")
        
        return fixed_count
    
    def _fix_tuesday_third_period_conflicts(self) -> int:
        """火曜3限の企画会議競合を修正
        
        Returns:
            修正件数
        """
        # 企画会議参加者の授業を移動
        # TODO: 企画会議参加者の情報を取得して実装
        return 0
    
    def find_best_swap_slot(self, class_name: str, subject: str, exclude_day: str, exclude_period: str) -> Optional[Tuple[str, str]]:
        """最適な交換先を探す
        
        Args:
            class_name: クラス名
            subject: 科目名
            exclude_day: 除外する曜日
            exclude_period: 除外する時限
            
        Returns:
            (曜日, 時限)のタプルまたはNone
        """
        class_row = self.utils.get_class_row(self.df, class_name)
        if not class_row:
            return None
        
        teacher = self.teacher_mapping.get((class_name, subject))
        if not teacher:
            return None
        
        best_slot = None
        min_conflicts = float('inf')
        
        for day in ["月", "火", "水", "木", "金"]:
            for period in ["1", "2", "3", "4", "5"]:
                if day == exclude_day and period == exclude_period:
                    continue
                
                col = self.utils.get_cell(self.df, day, period)
                if not col:
                    continue
                
                current_subject = self.df.iloc[class_row, col]
                
                # 固定科目は交換不可
                if self.utils.is_fixed_subject(current_subject):
                    continue
                
                # 日内重複チェック
                if self.utils.would_cause_daily_duplicate(self.df, class_name, subject, day):
                    continue
                
                # 教師の空き状況を確認
                if self._is_teacher_available_at(teacher, day, period):
                    conflicts = self.count_conflicts_at(day, period)
                    if conflicts < min_conflicts:
                        min_conflicts = conflicts
                        best_slot = (day, period)
        
        return best_slot
    
    def _is_teacher_available_at(self, teacher: str, day: str, period: str) -> bool:
        """指定教師が指定時間に空いているか確認"""
        col = self.utils.get_cell(self.df, day, period)
        if not col:
            return False
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name):
                continue
            
            subject = self.df.iloc[row, col]
            if pd.notna(subject) and subject != "":
                assigned_teacher = self.teacher_mapping.get((class_name, subject))
                if assigned_teacher == teacher:
                    # 5組と自立活動は例外
                    if not (self.utils.is_grade5_class(class_name) or self.utils.is_jiritsu_activity(subject)):
                        return False
        
        return True
    
    def swap_subjects(self, class_name: str, day1: str, period1: str, day2: str, period2: str) -> bool:
        """指定クラスの2つの時間の科目を交換
        
        Args:
            class_name: クラス名
            day1, period1: 交換元
            day2, period2: 交換先
            
        Returns:
            成功した場合True
        """
        class_row = self.utils.get_class_row(self.df, class_name)
        col1 = self.utils.get_cell(self.df, day1, period1)
        col2 = self.utils.get_cell(self.df, day2, period2)
        
        if not (class_row and col1 and col2):
            return False
        
        subject1 = self.df.iloc[class_row, col1]
        subject2 = self.df.iloc[class_row, col2]
        
        # 両方が固定科目でないことを確認
        if self.utils.is_fixed_subject(subject1) or self.utils.is_fixed_subject(subject2):
            return False
        
        # 交換
        self.df.iloc[class_row, col1] = subject2
        self.df.iloc[class_row, col2] = subject1
        
        self.fixes.append(f"{class_name}: {day1}{period1}限({subject1}) ⇔ {day2}{period2}限({subject2})")
        
        return True
    
    def fix_daily_duplicates(self) -> int:
        """日内重複を修正
        
        Returns:
            修正件数
        """
        logger.info("日内重複の修正を開始")
        
        fixed_count = 0
        
        for row in range(2, len(self.df)):
            class_name = self.df.iloc[row, 0]
            if pd.isna(class_name):
                continue
            
            for day in ["月", "火", "水", "木", "金"]:
                subjects = defaultdict(list)
                
                # 同じ曜日の科目を集計
                for period in range(1, 7):
                    col = self.utils.get_cell(self.df, day, str(period))
                    if col:
                        subject = self.df.iloc[row, col]
                        if pd.notna(subject) and subject != "" and not self.utils.is_fixed_subject(subject):
                            subjects[subject].append((period, col))
                
                # 重複を修正
                for subject, occurrences in subjects.items():
                    if len(occurrences) > 1:
                        logger.warning(f"{class_name}の{day}曜日に{subject}が{len(occurrences)}回")
                        
                        # 2回目以降を他の曜日に移動
                        for period, col in occurrences[1:]:
                            moved = False
                            
                            for other_day in ["月", "火", "水", "木", "金"]:
                                if other_day == day:
                                    continue
                                
                                if not self.utils.would_cause_daily_duplicate(self.df, class_name, subject, other_day):
                                    other_col = self.utils.get_cell(self.df, other_day, str(period))
                                    if other_col:
                                        other_subject = self.df.iloc[row, other_col]
                                        
                                        if (pd.notna(other_subject) and 
                                            not self.utils.is_fixed_subject(other_subject) and
                                            not self.utils.would_cause_daily_duplicate(self.df, class_name, other_subject, day)):
                                            
                                            # 交換
                                            self.df.iloc[row, col] = other_subject
                                            self.df.iloc[row, other_col] = subject
                                            self.fixes.append(f"{class_name}: 日内重複解消")
                                            fixed_count += 1
                                            moved = True
                                            logger.info(f"  修正: {class_name} {day}{period}限({subject}) → {other_day}{period}限")
                                            break
                            
                            if not moved:
                                logger.warning(f"  {class_name}の{day}{period}限({subject})の移動先が見つかりません")
        
        return fixed_count
    
    def fix_exchange_class_sync(self) -> int:
        """交流学級の同期を修正
        
        Returns:
            修正件数
        """
        logger.info("交流学級の同期修正を開始")
        
        sync_count = 0
        exchange_pairs = self.utils.get_exchange_class_pairs()
        
        for exchange_class, parent_class in exchange_pairs:
            exchange_row = self.utils.get_class_row(self.df, exchange_class)
            parent_row = self.utils.get_class_row(self.df, parent_class)
            
            if not (exchange_row and parent_row):
                continue
            
            for col in range(1, len(self.df.columns)):
                exchange_subject = self.df.iloc[exchange_row, col]
                parent_subject = self.df.iloc[parent_row, col]
                
                # 自立活動の時は特別処理
                if self.utils.is_jiritsu_activity(exchange_subject):
                    if parent_subject not in ["数", "英"]:
                        # 親学級を数学か英語に変更する必要がある
                        continue
                elif exchange_subject != parent_subject and not self.utils.is_fixed_subject(exchange_subject):
                    # 同期が必要
                    self.df.iloc[exchange_row, col] = parent_subject
                    sync_count += 1
                    logger.info(f"  同期: {exchange_class} ← {parent_class} ({parent_subject})")
        
        return sync_count
    
    def fix_all_conflicts(self) -> Tuple[pd.DataFrame, List[str]]:
        """すべての競合を修正する統合メソッド
        
        Returns:
            (修正後のDataFrame, 修正内容のリスト)
        """
        logger.info("=== 統合修正処理を開始 ===")
        
        # 初期状態の分析
        initial_conflicts = self.analyze_all_conflicts()
        initial_count = sum(len(conflicts) for conflicts in initial_conflicts.values())
        logger.info(f"初期競合数: {initial_count}件")
        
        # 各種修正を順番に実行
        fix_count = 0
        
        # 1. 火曜日問題の修正
        fix_count += self.fix_tuesday_conflicts()
        
        # 2. 日内重複の修正
        fix_count += self.fix_daily_duplicates()
        
        # 3. 交流学級の同期
        fix_count += self.fix_exchange_class_sync()
        
        # 最終状態の分析
        final_conflicts = self.analyze_all_conflicts()
        final_count = sum(len(conflicts) for conflicts in final_conflicts.values())
        logger.info(f"\n最終競合数: {final_count}件")
        logger.info(f"改善率: {((initial_count - final_count) / initial_count * 100):.1f}%")
        logger.info(f"総修正件数: {len(self.fixes)}件")
        
        return self.df, self.fixes
    
    def save_to_file(self, output_path: Optional[Path] = None):
        """修正結果をファイルに保存
        
        Args:
            output_path: 出力パス（指定しない場合はデフォルト）
        """
        if output_path is None:
            output_path = Path("data/output/output_fixed.csv")
        
        # CSVOperationsを使用して書き込み
        rows = self.df.values.tolist()
        CSVOperations.write_csv_raw(str(output_path), rows)
        logger.info(f"\n修正結果を保存: {output_path}")
        
        # 修正内容をログファイルに保存
        fix_log_path = output_path.with_suffix('.log')
        with open(fix_log_path, 'w', encoding='utf-8') as f:
            f.write("=== 修正内容 ===\n")
            for fix in self.fixes:
                f.write(f"{fix}\n")
        
        logger.info(f"修正ログを保存: {fix_log_path}")
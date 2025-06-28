#!/usr/bin/env python3
"""Ultrathink制約システムを使用した時間割修正スクリプト"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, Teacher, Subject, ClassReference
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository, CSVScheduleRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
from src.domain.services.core.unified_constraint_system import UnifiedConstraintSystem
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.infrastructure.config.path_config import path_config

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkConstraintSystemFixer:
    """制約システムを使用した時間割修正クラス"""
    
    def __init__(self):
        self.schedule_repo = CSVScheduleRepository(path_config.data_dir)
        self.school_repo = CSVSchoolRepository(path_config.data_dir)
        
        # 交流学級と親学級のマッピング
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組",
        }
        
        # 5組クラス
        self.grade5_classes = ["1年5組", "2年5組", "3年5組"]
        
        # 固定科目
        self.fixed_subjects = {
            "YT", "道", "学", "総", "欠", "行", "テスト", "技家",
            "日生", "作業", "生単", "学総"
        }
        
        # 教科別教師マッピング
        self.subject_teacher_map = {
            "国": ["寺田", "小野塚", "金子み"],
            "社": ["蒲地", "北"],
            "数": ["梶永", "井上", "森山"],
            "理": ["金子ひ", "智田", "白石"],
            "英": ["井野口", "箱崎", "林田"],
            "音": ["塚本"],
            "美": ["青井", "金子み"],
            "保": ["永山", "野口", "財津"],
            "技": ["林"],
            "家": ["金子み"]
        }
    
    def fix_all_violations(self):
        """全ての違反を修正"""
        logger.info("=== Ultrathink制約システムベース修正を開始 ===\n")
        
        # 学校データ読み込み
        logger.info("学校データを読み込み中...")
        school = self.school_repo.load_school_data("config/base_timetable.csv")
        
        # 時間割読み込み
        logger.info(f"時間割を読み込み中: {path_config.default_output_csv}")
        schedule = self.schedule_repo.load_desired_schedule(
            str(path_config.default_output_csv),
            school
        )
        
        # 修正前に保護を無効化
        schedule.disable_fixed_subject_protection()
        schedule.disable_grade5_sync()
        
        # 制約システム初期化
        constraint_system = UnifiedConstraintSystem()
        constraint_system.school = school
        
        # 制約登録
        constraint_registration_service = ConstraintRegistrationService()
        constraint_registration_service.register_all_constraints(
            constraint_system,
            path_config.data_dir,
            teacher_absences=None
        )
        
        # 現在の違反を検出
        logger.info("\n=== 現在の違反を検出 ===")
        violations = self.detect_violations(constraint_system, schedule, school)
        
        # 違反を種類別に分類
        teacher_violations = []
        gym_violations = []
        daily_violations = []
        sync_violations = []
        other_violations = []
        
        for violation in violations:
            if "教師重複違反" in violation.description:
                teacher_violations.append(violation)
            elif "体育館使用制約" in violation.description:
                gym_violations.append(violation)
            elif "日内重複" in violation.description:
                daily_violations.append(violation)
            elif "交流学級" in violation.description:
                sync_violations.append(violation)
            else:
                other_violations.append(violation)
        
        logger.info(f"総違反数: {len(violations)}件")
        logger.info(f"  - 教師重複: {len(teacher_violations)}件")
        logger.info(f"  - 体育館使用: {len(gym_violations)}件")
        logger.info(f"  - 日内重複: {len(daily_violations)}件")
        logger.info(f"  - 交流学級同期: {len(sync_violations)}件")
        logger.info(f"  - その他: {len(other_violations)}件")
        
        # Phase 1: 教師重複の修正
        if teacher_violations:
            logger.info("\nPhase 1: 教師重複の修正")
            fixed = self.fix_teacher_conflicts(schedule, school, teacher_violations)
            logger.info(f"  → {fixed}件修正")
        
        # Phase 2: 体育館使用の修正
        if gym_violations:
            logger.info("\nPhase 2: 体育館使用の修正")
            fixed = self.fix_gym_conflicts(schedule, school, gym_violations)
            logger.info(f"  → {fixed}件修正")
        
        # Phase 3: 日内重複の修正
        if daily_violations:
            logger.info("\nPhase 3: 日内重複の修正")
            fixed = self.fix_daily_duplicates(schedule, school, daily_violations)
            logger.info(f"  → {fixed}件修正")
        
        # Phase 4: 交流学級同期の修正
        if sync_violations:
            logger.info("\nPhase 4: 交流学級同期の修正")
            fixed = self.fix_exchange_sync(schedule, school, sync_violations)
            logger.info(f"  → {fixed}件修正")
        
        # 結果保存
        self.save_results(schedule)
        
        # 修正後の違反を再検出
        logger.info("\n=== 修正後の違反を再検出 ===")
        final_violations = self.detect_violations(constraint_system, schedule, school)
        logger.info(f"残存違反数: {len(final_violations)}件")
    
    def detect_violations(self, constraint_system, schedule, school):
        """制約システムを使用して違反を検出"""
        all_violations = []
        
        # 各制約の validate メソッドを使用
        constraints = []
        for priority_constraints in constraint_system.constraints.values():
            constraints.extend(priority_constraints)
        
        for constraint in constraints:
            result = constraint.validate(schedule, school)
            if result.violations:
                all_violations.extend(result.violations)
        
        return all_violations
    
    def fix_teacher_conflicts(self, schedule: Schedule, school: School, violations) -> int:
        """教師重複を修正"""
        fixed_count = 0
        
        # 違反から情報を抽出して修正
        for violation in violations:
            # 違反の説明から情報を抽出
            # 例: "教師重複違反: 寺田先生が月曜2校時に1年2組と1年5組, 2年5組, 3年5組を同時に担当"
            desc = violation.description
            if "が" in desc and "に" in desc and "を同時に担当" in desc:
                parts = desc.split("が")
                teacher_name = parts[0].split(":")[-1].strip()
                
                time_info = parts[1].split("に")[0].strip()
                classes_info = parts[1].split("に")[1].split("を同時に担当")[0].strip()
                
                # 時間情報を解析
                day = time_info[0]
                period = int(time_info[1])
                time_slot = TimeSlot(day, period)
                
                # クラス情報を解析
                classes = [c.strip() for c in classes_info.replace("と", ",").split(",")]
                
                # 5組の合同授業は除外
                grade5 = [c for c in classes if c in self.grade5_classes]
                if len(grade5) == 3 and len(classes) == 3:
                    continue
                
                # 最初のクラス以外を修正
                for class_str in classes[1:]:
                    if self.reassign_teacher(schedule, school, time_slot, class_str, teacher_name):
                        fixed_count += 1
                        logger.info(f"  - {time_slot} {class_str}: {teacher_name}の重複を解消")
        
        return fixed_count
    
    def fix_gym_conflicts(self, schedule: Schedule, school: School, violations) -> int:
        """体育館使用の修正"""
        fixed_count = 0
        
        for violation in violations:
            # 違反の説明から情報を抽出
            # 例: "体育館使用制約違反: 月曜5校時に3クラスが同時に保健体育を実施 (合同体育グループではない) - 1年3組, 2年3組, 2年6組"
            desc = violation.description
            if "に" in desc and "クラスが同時に保健体育を実施" in desc:
                time_info = desc.split("に")[0].split(":")[-1].strip()
                classes_info = desc.split("-")[-1].strip()
                
                # 時間情報を解析
                day = time_info[0]
                period = int(time_info[1])
                time_slot = TimeSlot(day, period)
                
                # クラス情報を解析
                classes = [c.strip() for c in classes_info.split(",")]
                
                # 正常なケースを除外
                remaining = list(classes)
                
                # 5組合同
                grade5_pe = [c for c in classes if c in self.grade5_classes]
                if len(grade5_pe) == 3:
                    for c in grade5_pe:
                        if c in remaining:
                            remaining.remove(c)
                
                # 親・交流ペア
                for exchange, parent in self.exchange_parent_map.items():
                    if exchange in remaining and parent in remaining:
                        remaining.remove(exchange)
                        remaining.remove(parent)
                
                # 残りを他の時間に移動
                for class_str in remaining[1:]:
                    if self.move_pe_to_available_slot(schedule, school, time_slot, class_str):
                        fixed_count += 1
                        logger.info(f"  - {time_slot} {class_str}: 体育を他の時間に移動")
        
        return fixed_count
    
    def fix_daily_duplicates(self, schedule: Schedule, school: School, violations) -> int:
        """日内重複を修正"""
        fixed_count = 0
        
        # 違反をクラス・日・科目でグループ化
        duplicate_map = defaultdict(list)
        
        for violation in violations:
            # 例: "日内重複制約違反: 1年1組 木曜日 国"
            desc = violation.description
            parts = desc.split(":")[-1].strip().split()
            if len(parts) >= 3:
                class_str = parts[0]
                day = parts[1][0]  # "木曜日" -> "木"
                subject = parts[2]
                duplicate_map[(class_str, day, subject)].append(violation)
        
        for (class_str, day, subject), _ in duplicate_map.items():
            # その日の該当科目の時限を探す
            periods_with_subject = []
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = schedule.get_assignment(time_slot, class_str)
                if assignment and assignment.subject.name == subject:
                    periods_with_subject.append(period)
            
            # 2つ目以降を変更
            if len(periods_with_subject) > 1:
                for period in periods_with_subject[1:]:
                    time_slot = TimeSlot(day, period)
                    
                    # 他の必要な科目を探す
                    new_subject = self.find_needed_subject_for_day(schedule, school, class_str, day)
                    
                    if new_subject:
                        if self.change_subject(schedule, school, time_slot, class_str, new_subject):
                            fixed_count += 1
                            logger.info(f"  - {class_str} {time_slot}: {subject} → {new_subject}")
        
        return fixed_count
    
    def fix_exchange_sync(self, schedule: Schedule, school: School, violations) -> int:
        """交流学級同期を修正"""
        fixed_count = 0
        
        for violation in violations:
            # 違反から情報を抽出
            desc = violation.description
            
            # 交流学級と親学級を特定
            for exchange, parent in self.exchange_parent_map.items():
                if exchange in desc and parent in desc:
                    # 時間情報を探す
                    days = ["月", "火", "水", "木", "金"]
                    for day in days:
                        if day in desc:
                            for period in range(1, 7):
                                if str(period) in desc:
                                    time_slot = TimeSlot(day, period)
                                    
                                    # 親学級に合わせる
                                    parent_assignment = schedule.get_assignment(time_slot, parent)
                                    if parent_assignment:
                                        exchange_assignment = schedule.get_assignment(time_slot, exchange)
                                        
                                        if exchange_assignment and exchange_assignment.subject.name != "自立":
                                            schedule.remove_assignment(time_slot, exchange)
                                            
                                            # ClassReferenceオブジェクトを作成
                                            parts = exchange.split("年")
                                            grade = int(parts[0])
                                            class_num = int(parts[1].replace("組", ""))
                                            class_ref = ClassReference(grade, class_num)
                                            
                                            new_assignment = Assignment(
                                                class_ref,
                                                parent_assignment.subject,
                                                parent_assignment.teacher
                                            )
                                            schedule.assign(time_slot, new_assignment)
                                            fixed_count += 1
                                            logger.info(f"  - {exchange} {time_slot}: {parent_assignment.subject.name}に同期")
        
        return fixed_count
    
    def reassign_teacher(self, schedule: Schedule, school: School,
                        time_slot: TimeSlot, class_str: str, avoid_teacher: str) -> bool:
        """教師を再割り当て"""
        assignment = schedule.get_assignment(time_slot, class_str)
        if not assignment:
            return False
        
        # 他の教師を探す
        subject_name = assignment.subject.name
        if subject_name in self.subject_teacher_map:
            for teacher_name in self.subject_teacher_map[subject_name]:
                if teacher_name != avoid_teacher:
                    # その時間に空いているか確認
                    if self.is_teacher_available(schedule, school, time_slot, teacher_name):
                        # 教師オブジェクトを探す
                        for teacher in school.get_all_teachers():
                            if teacher.name == teacher_name:
                                schedule.remove_assignment(time_slot, class_str)
                                
                                # ClassReferenceオブジェクトを作成
                                parts = class_str.split("年")
                                grade = int(parts[0])
                                class_num = int(parts[1].replace("組", ""))
                                class_ref = ClassReference(grade, class_num)
                                
                                new_assignment = Assignment(
                                    class_ref,
                                    assignment.subject,
                                    teacher
                                )
                                schedule.assign(time_slot, new_assignment)
                                return True
        
        return False
    
    def move_pe_to_available_slot(self, schedule: Schedule, school: School,
                                 current_slot: TimeSlot, class_str: str) -> bool:
        """体育を利用可能な時間に移動"""
        days = ["月", "火", "水", "木", "金"]
        
        current_assignment = schedule.get_assignment(current_slot, class_str)
        if not current_assignment:
            return False
        
        for day in days:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                if time_slot == current_slot:
                    continue
                
                # その時間の体育館使用状況を確認
                gym_count = 0
                for class_ref in school.get_all_classes():
                    assignment = schedule.get_assignment(time_slot, str(class_ref))
                    if assignment and assignment.subject.name == "保":
                        gym_count += 1
                
                # 体育館が空いている場合
                if gym_count == 0:
                    target_assignment = schedule.get_assignment(time_slot, class_str)
                    
                    if target_assignment and target_assignment.subject.name not in self.fixed_subjects:
                        # 同じ日に同じ科目がないか確認
                        if not self.has_subject_on_day(schedule, class_str, day, target_assignment.subject.name):
                            # 交換実行
                            schedule.remove_assignment(current_slot, class_str)
                            schedule.remove_assignment(time_slot, class_str)
                            
                            # ClassReferenceオブジェクトを作成
                            parts = class_str.split("年")
                            grade = int(parts[0])
                            class_num = int(parts[1].replace("組", ""))
                            class_ref = ClassReference(grade, class_num)
                            
                            new_pe = Assignment(class_ref, current_assignment.subject, current_assignment.teacher)
                            new_other = Assignment(class_ref, target_assignment.subject, target_assignment.teacher)
                            
                            schedule.assign(time_slot, new_pe)
                            schedule.assign(current_slot, new_other)
                            
                            return True
        
        return False
    
    def change_subject(self, schedule: Schedule, school: School,
                      time_slot: TimeSlot, class_str: str, new_subject: str) -> bool:
        """科目を変更"""
        # 新しい科目の教師を探す
        teacher = self.find_teacher_for_subject(school, new_subject, time_slot, schedule)
        
        if teacher:
            schedule.remove_assignment(time_slot, class_str)
            
            # ClassReferenceオブジェクトを作成
            parts = class_str.split("年")
            grade = int(parts[0])
            class_num = int(parts[1].replace("組", ""))
            class_ref = ClassReference(grade, class_num)
            
            new_assignment = Assignment(
                class_ref,
                Subject(new_subject),
                teacher
            )
            schedule.assign(time_slot, new_assignment)
            return True
        
        return False
    
    def find_needed_subject_for_day(self, schedule: Schedule, school: School,
                                  class_str: str, day: str) -> Optional[str]:
        """その日に必要な科目を探す"""
        # その日の配置済み科目を収集
        day_subjects = set()
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_str)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # 主要5教科を優先
        for subject in ["国", "数", "英", "理", "社"]:
            if subject not in day_subjects:
                return subject
        
        # 技能教科
        for subject in ["音", "美", "保", "技", "家"]:
            if subject not in day_subjects:
                return subject
        
        return None
    
    def has_subject_on_day(self, schedule: Schedule, class_str: str, day: str, subject: str) -> bool:
        """その日に指定科目があるか確認"""
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_str)
            if assignment and assignment.subject.name == subject:
                return True
        return False
    
    def find_teacher_for_subject(self, school: School, subject: str,
                               time_slot: TimeSlot, schedule: Schedule) -> Optional[Teacher]:
        """科目の教師を探す"""
        if subject in self.subject_teacher_map:
            for teacher_name in self.subject_teacher_map[subject]:
                if self.is_teacher_available(schedule, school, time_slot, teacher_name):
                    # 教師オブジェクトを探す
                    for teacher in school.get_all_teachers():
                        if teacher.name == teacher_name:
                            return teacher
        
        return None
    
    def is_teacher_available(self, schedule: Schedule, school: School,
                           time_slot: TimeSlot, teacher_name: str) -> bool:
        """教師が利用可能かチェック"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, str(class_ref))
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                return False
        return True
    
    def save_results(self, schedule: Schedule):
        """結果を保存"""
        output_path = project_root / "data" / "output" / "output.csv"
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        logger.info(f"\n修正済み時間割を保存: {output_path}")


def main():
    """メイン処理"""
    fixer = UltrathinkConstraintSystemFixer()
    fixer.fix_all_violations()


if __name__ == "__main__":
    main()
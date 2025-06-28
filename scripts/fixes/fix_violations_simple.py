#!/usr/bin/env python3
"""
シンプルな時間割修正スクリプト

既存の出力を読み込んで、主要な違反を修正します。
"""
import os
import sys
import csv
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set

# プロジェクトルートのパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.config.path_config import path_config
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
# School data loading will be done differently
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class SimpleViolationFixer:
    """シンプルな違反修正クラス"""
    
    def __init__(self):
        self.repository = CSVScheduleRepository()
        self.reader = CSVScheduleReader()
        self.parser = SchoolDataParser()
        self.followup_parser = EnhancedFollowUpParser()
        
        # 固定科目
        self.fixed_subjects = {'欠', '欠課', 'YT', '学', '学活', '道', '道徳', 
                              '総', '総合', '学総', '行', '行事', 'テスト', '技家'}
        
        # 交流学級マッピング
        self.exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        # 担任マッピング
        self.homeroom_teachers = {
            (1, 1): '金子ひ先生',
            (1, 2): '井野口先生',
            (1, 3): '梶永先生',
            (2, 1): '塚本先生',
            (2, 2): '野口先生',
            (2, 3): '永山先生',
            (3, 1): '白石先生',
            (3, 2): '森山先生',
            (3, 3): '北先生',
            (1, 5): '金子み先生',
            (2, 5): '金子み先生',
            (3, 5): '金子み先生',
        }
        
        # 教科と教師のマッピング
        self.subject_teacher_mapping = {
            '国': '智田先生',
            '数': '井上先生',
            '英': '蒲地先生',
            '理': '梶永先生',
            '社': '神田先生',
            '音': '今先生',
            '美': '平野先生',
            '体': '野田先生',
            '技': '國本先生',
            '家': '石原先生',
        }
    
    def fix_violations(self):
        """違反を修正"""
        logger.info("=== シンプルな時間割修正を開始 ===\n")
        
        # 1. データを読み込み
        logger.info("1. データを読み込み中...")
        output_path = path_config.get_output_path('output.csv')
        
        # 学校データを読み込み
        school = self._load_school_data()
        
        # スケジュールを読み込み
        schedule = self.reader.read_schedule(str(output_path), school)
        
        if not schedule:
            logger.error("スケジュールの読み込みに失敗しました")
            return
        
        # 2. 主要な修正を実行
        self._fix_critical_violations(schedule, school)
        
        # 3. 結果を保存
        logger.info("\n修正結果を保存中...")
        self.repository.save_schedule(schedule, str(output_path))
        
        logger.info(f"\n修正完了！")
        logger.info(f"出力ファイル: {output_path}")
    
    def _load_school_data(self) -> School:
        """学校データを読み込み"""
        # 基本データを読み込み
        base_timetable_path = path_config.get_config_path('base_timetable.csv')
        school = self.parser.parse_base_timetable(str(base_timetable_path))
        
        # Follow-upデータを読み込み
        followup_path = path_config.get_input_path('Follow-up.csv')
        absences, meetings, test_periods = self.followup_parser.parse(str(followup_path))
        
        return school
    
    def _fix_critical_violations(self, schedule: Schedule, school: School):
        """重要な違反を修正"""
        
        # 月曜6限の欠課を修正
        self._fix_monday_6th(schedule, school)
        
        # 教師重複を修正
        self._fix_teacher_conflicts(schedule, school)
        
        # 日内重複を修正
        self._fix_daily_duplicates(schedule, school)
        
        # 空きコマを埋める
        self._fill_empty_slots(schedule, school)
        
        # 5組を同期
        self._sync_grade5(schedule, school)
    
    def _fix_monday_6th(self, schedule: Schedule, school: School):
        """月曜6限の欠課を修正"""
        logger.info("\n2. 月曜6限の欠課を修正中...")
        
        fixed_count = 0
        for grade in range(1, 4):
            for class_num in range(1, 8):
                class_ref = ClassReference(grade, class_num)
                
                # クラスが存在するか確認
                if not self._class_exists(school, class_ref):
                    continue
                
                time_slot = TimeSlot('月', 6)
                current = schedule.get_assignment(time_slot, class_ref)
                
                if not current or current.subject.name != '欠':
                    # 欠課を設定
                    teacher_name = self.homeroom_teachers.get((grade, class_num))
                    teacher = school.get_teacher(teacher_name) if teacher_name else None
                    
                    assignment = Assignment(
                        class_ref=class_ref,
                        subject=school.get_subject('欠'),
                        teacher=teacher
                    )
                    
                    try:
                        schedule.assign(time_slot, assignment)
                        fixed_count += 1
                    except Exception as e:
                        logger.warning(f"  {class_ref}の月曜6限設定エラー: {e}")
        
        logger.info(f"  → {fixed_count}クラスの月曜6限を修正")
    
    def _fix_teacher_conflicts(self, schedule: Schedule, school: School):
        """教師重複を修正"""
        logger.info("\n3. 教師重複を修正中...")
        
        fixed_count = 0
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 教師別の担当クラスを収集
                teacher_assignments = defaultdict(list)
                
                for grade in range(1, 4):
                    for class_num in range(1, 8):
                        class_ref = ClassReference(grade, class_num)
                        
                        if not self._class_exists(school, class_ref):
                            continue
                        
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        if assignment and assignment.teacher:
                            teacher_assignments[assignment.teacher.name].append(
                                (class_ref, assignment)
                            )
                
                # 重複を修正
                for teacher_name, assignments in teacher_assignments.items():
                    if len(assignments) > 1:
                        # 5組の合同授業は除外
                        grade5_count = sum(1 for c, _ in assignments if c.class_number == 5)
                        if grade5_count == len(assignments):
                            continue
                        
                        # 最初のクラス以外を修正
                        for class_ref, assignment in assignments[1:]:
                            # 代替教師を探す
                            alt_teacher = self._find_alternative_teacher(
                                school, assignment.subject.name, time_slot, schedule
                            )
                            
                            if alt_teacher:
                                new_assignment = Assignment(
                                    class_ref=class_ref,
                                    subject=assignment.subject,
                                    teacher=alt_teacher
                                )
                                
                                schedule.assign(time_slot, new_assignment)
                                fixed_count += 1
                                logger.info(f"  {time_slot} {class_ref}: {teacher_name} → {alt_teacher.name}")
        
        logger.info(f"  → {fixed_count}件の教師重複を修正")
    
    def _fix_daily_duplicates(self, schedule: Schedule, school: School):
        """日内重複を修正"""
        logger.info("\n4. 日内重複を修正中...")
        
        fixed_count = 0
        
        for grade in range(1, 4):
            for class_num in range(1, 8):
                class_ref = ClassReference(grade, class_num)
                
                if not self._class_exists(school, class_ref):
                    continue
                
                for day in ['月', '火', '水', '木', '金']:
                    # その日の教科をカウント
                    subject_periods = defaultdict(list)
                    
                    for period in range(1, 7):
                        time_slot = TimeSlot(day, period)
                        assignment = schedule.get_assignment(time_slot, class_ref)
                        
                        if assignment and assignment.subject.name not in self.fixed_subjects:
                            subject_periods[assignment.subject.name].append(period)
                    
                    # 重複を修正
                    for subject, periods in subject_periods.items():
                        if len(periods) > 1:
                            # 最初の時限以外を変更
                            for period in periods[1:]:
                                time_slot = TimeSlot(day, period)
                                
                                # 他の必要な教科を探す
                                alt_subject = self._find_needed_subject(
                                    schedule, school, class_ref, day
                                )
                                
                                if alt_subject:
                                    teacher = self._get_teacher_for_subject(
                                        school, alt_subject
                                    )
                                    
                                    if teacher and self._is_teacher_available(
                                        schedule, teacher, time_slot
                                    ):
                                        new_assignment = Assignment(
                                            class_ref=class_ref,
                                            subject=school.get_subject(alt_subject),
                                            teacher=teacher
                                        )
                                        
                                        schedule.assign(time_slot, new_assignment)
                                        fixed_count += 1
                                        logger.info(f"  {class_ref} {day}{period}限: {subject} → {alt_subject}")
        
        logger.info(f"  → {fixed_count}件の日内重複を修正")
    
    def _fill_empty_slots(self, schedule: Schedule, school: School):
        """空きコマを埋める"""
        logger.info("\n5. 空きコマを埋める...")
        
        filled_count = 0
        
        for grade in range(1, 4):
            for class_num in range(1, 8):
                class_ref = ClassReference(grade, class_num)
                
                if not self._class_exists(school, class_ref):
                    continue
                
                for day in ['月', '火', '水', '木', '金']:
                    for period in range(1, 7):
                        time_slot = TimeSlot(day, period)
                        
                        if not schedule.get_assignment(time_slot, class_ref):
                            # 適切な教科を選択
                            subject = self._select_subject_for_slot(
                                schedule, school, class_ref, time_slot
                            )
                            
                            if subject:
                                teacher = self._get_teacher_for_subject(school, subject)
                                
                                if teacher and self._is_teacher_available(
                                    schedule, teacher, time_slot
                                ):
                                    assignment = Assignment(
                                        class_ref=class_ref,
                                        subject=school.get_subject(subject),
                                        teacher=teacher
                                    )
                                    
                                    schedule.assign(time_slot, assignment)
                                    filled_count += 1
        
        logger.info(f"  → {filled_count}コマを埋めました")
    
    def _sync_grade5(self, schedule: Schedule, school: School):
        """5組を同期"""
        logger.info("\n6. 5組を同期中...")
        
        synced_count = 0
        grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各5組の割り当てを取得
                assignments = []
                for class_ref in grade5_classes:
                    assignment = schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments.append((class_ref, assignment.subject.name))
                
                if len(assignments) >= 2:
                    # 最も多い教科を選択
                    subject_counts = defaultdict(int)
                    for _, subject in assignments:
                        subject_counts[subject] += 1
                    
                    most_common = max(subject_counts, key=subject_counts.get)
                    
                    # 全5組を統一
                    for class_ref in grade5_classes:
                        current = schedule.get_assignment(time_slot, class_ref)
                        if not current or current.subject.name != most_common:
                            teacher = self._get_teacher_for_subject(school, most_common)
                            
                            if teacher:
                                assignment = Assignment(
                                    class_ref=class_ref,
                                    subject=school.get_subject(most_common),
                                    teacher=teacher
                                )
                                
                                schedule.assign(time_slot, assignment)
                                synced_count += 1
        
        logger.info(f"  → {synced_count}コマを同期")
    
    # ヘルパーメソッド
    def _class_exists(self, school: School, class_ref: ClassReference) -> bool:
        """クラスが存在するか確認"""
        try:
            return class_ref in [c for c in school.get_all_classes()]
        except:
            return False
    
    def _find_alternative_teacher(self, school: School, subject: str, 
                                 time_slot: TimeSlot, schedule: Schedule):
        """代替教師を探す"""
        # 同じ教科を教えられる他の教師を探す
        possible_teachers = []
        
        # 教科マッピングから探す
        if subject in self.subject_teacher_mapping:
            teacher_name = self.subject_teacher_mapping[subject]
            teacher = school.get_teacher(teacher_name)
            if teacher and self._is_teacher_available(schedule, teacher, time_slot):
                return teacher
        
        # 他の可能な教師を探す（簡易実装）
        return None
    
    def _is_teacher_available(self, schedule: Schedule, teacher, time_slot: TimeSlot) -> bool:
        """教師が利用可能か確認"""
        # 既に他のクラスを担当していないか
        for grade in range(1, 4):
            for class_num in range(1, 8):
                class_ref = ClassReference(grade, class_num)
                assignment = schedule.get_assignment(time_slot, class_ref)
                
                if assignment and assignment.teacher and assignment.teacher.name == teacher.name:
                    # 5組の合同授業は許可
                    if class_num == 5:
                        continue
                    return False
        
        return True
    
    def _find_needed_subject(self, schedule: Schedule, school: School, 
                           class_ref: ClassReference, day: str) -> Optional[str]:
        """必要な教科を探す"""
        # その日にまだ配置されていない主要教科を優先
        main_subjects = ['国', '数', '英', '理', '社']
        
        day_subjects = set()
        for period in range(1, 7):
            time_slot = TimeSlot(day, period)
            assignment = schedule.get_assignment(time_slot, class_ref)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # まだその日に配置されていない主要教科
        for subject in main_subjects:
            if subject not in day_subjects:
                return subject
        
        # 技能教科
        skill_subjects = ['音', '美', '体', '技', '家']
        for subject in skill_subjects:
            if subject not in day_subjects:
                return subject
        
        return None
    
    def _get_teacher_for_subject(self, school: School, subject: str):
        """教科の教師を取得"""
        if subject in self.subject_teacher_mapping:
            teacher_name = self.subject_teacher_mapping[subject]
            return school.get_teacher(teacher_name)
        
        # 担任が担当する教科
        if subject in ['道', '学', '総', '学総']:
            # 適当な担任を返す（簡易実装）
            return school.get_teacher('金子ひ先生')
        
        return None
    
    def _select_subject_for_slot(self, schedule: Schedule, school: School,
                               class_ref: ClassReference, time_slot: TimeSlot) -> Optional[str]:
        """スロットに配置する教科を選択"""
        # その日にまだ配置されていない教科を優先
        return self._find_needed_subject(schedule, school, class_ref, time_slot.day)


def main():
    """メイン処理"""
    try:
        fixer = SimpleViolationFixer()
        fixer.fix_violations()
        
        # 違反チェックを実行
        logger.info("\n=== 修正後の違反チェック ===")
        os.system("python3 scripts/analysis/check_violations.py")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
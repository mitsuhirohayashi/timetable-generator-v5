#!/usr/bin/env python3
"""
包括的な時間割修正スクリプト

全ての制約違反を系統的に修正します。
"""
import os
import sys
import csv
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set

# プロジェクトルートのパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School, Teacher
from src.domain.value_objects.time_slot import TimeSlot, ClassReference
from src.domain.value_objects.assignment import Assignment
from src.domain.services.constraint_validator import ConstraintValidator
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.config.advanced_csp_config_loader import AdvancedCSPConfigLoader
from src.domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint
from src.domain.constraints.daily_duplicate_constraint import DailyDuplicateConstraint
from src.domain.constraints.basic_constraints import StandardHoursConstraint
from src.domain.constraints.monday_sixth_period_constraint import MondaySixthPeriodConstraint
from src.domain.constraints.meeting_lock_constraint import MeetingLockConstraint
from src.domain.constraints.teacher_absence_constraint import TeacherAbsenceConstraint
from src.application.services.constraint_registration_service import ConstraintRegistrationService
from src.infrastructure.config.path_config import path_config

# Path constants
DATA_DIR = str(path_config.data_dir)
CONFIG_DIR = str(path_config.config_dir)
INPUT_DIR = str(path_config.input_dir)
OUTPUT_DIR = str(path_config.output_dir)

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class ComprehensiveScheduleFixer:
    """包括的な時間割修正クラス"""
    
    def __init__(self, schedule: Schedule, school: School):
        self.schedule = schedule
        self.school = school
        self.validator = ConstraintValidator()
        self.fixed_subjects = {'欠', '欠課', 'YT', '学', '学活', '道', '道徳', 
                               '総', '総合', '学総', '行', '行事', 'テスト', '技家'}
        
        # 制約を登録
        self._register_constraints()
        
        # 交流学級マッピング
        self.exchange_mappings = {
            ClassReference(1, 6): ClassReference(1, 1),
            ClassReference(1, 7): ClassReference(1, 2),
            ClassReference(2, 6): ClassReference(2, 3),
            ClassReference(2, 7): ClassReference(2, 2),
            ClassReference(3, 6): ClassReference(3, 3),
            ClassReference(3, 7): ClassReference(3, 2),
        }
        
        # 標準時数を読み込み
        self.standard_hours = self._load_standard_hours()
        
        # 会議時間を取得
        self.meeting_slots = self._get_meeting_slots()
    
    def _register_constraints(self):
        """制約を登録"""
        service = ConstraintRegistrationService(self.school, self.validator)
        
        # Follow-up.csvから教師不在情報を読み込み
        followup_path = os.path.join(INPUT_DIR, 'Follow-up.csv')
        parser = EnhancedFollowUpParser()
        absences, _, _ = parser.parse(followup_path)
        
        # 基本制約を登録
        service.register_basic_constraints()
        
        # 教師不在制約を登録
        if absences:
            service.register_teacher_absence_constraints(absences)
    
    def _load_standard_hours(self) -> Dict[ClassReference, Dict[str, float]]:
        """標準時数を読み込み"""
        standard_hours = {}
        base_timetable_path = os.path.join(CONFIG_DIR, 'base_timetable.csv')
        
        try:
            with open(base_timetable_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not row.get('学年') or not row.get('組'):
                        continue
                    
                    grade = int(row['学年'])
                    class_num = int(row['組'])
                    class_ref = ClassReference(grade, class_num)
                    
                    hours = {}
                    for subject, value in row.items():
                        if subject not in ['学年', '組'] and value and value.strip():
                            try:
                                hours[subject] = float(value)
                            except ValueError:
                                pass
                    
                    if hours:
                        standard_hours[class_ref] = hours
        except Exception as e:
            logger.error(f"標準時数の読み込みエラー: {e}")
        
        return standard_hours
    
    def _get_meeting_slots(self) -> Set[TimeSlot]:
        """会議時間を取得"""
        meeting_slots = set()
        
        # デフォルトの会議時間
        default_meetings = {
            ('火', 3): 'HF',
            ('火', 4): '企画',
            ('水', 2): '特会',
            ('木', 3): '生指'
        }
        
        for (day, period), _ in default_meetings.items():
            meeting_slots.add(TimeSlot(day, period))
        
        return meeting_slots
    
    def fix_all_violations(self):
        """全ての違反を修正"""
        logger.info("=== 包括的な時間割修正を開始 ===\n")
        
        # 1. 月曜6限の欠課を修正
        self._fix_monday_6th_period()
        
        # 2. 教師重複を修正
        self._fix_teacher_conflicts()
        
        # 3. 日内重複を修正
        self._fix_daily_duplicates()
        
        # 4. 標準時数を調整
        self._fix_standard_hours()
        
        # 5. 空きコマを埋める
        self._fill_empty_slots()
        
        # 6. 交流学級を同期
        self._sync_exchange_classes()
        
        # 7. 5組を同期
        self._sync_grade5_classes()
        
        # 最終検証
        violations = self.validator.validate(self.schedule)
        logger.info(f"\n修正完了: {len(violations)}件の違反が残っています")
    
    def _fix_monday_6th_period(self):
        """月曜6限の欠課を修正"""
        logger.info("1. 月曜6限の欠課を修正中...")
        
        fixed_count = 0
        for class_ref in self.school.get_all_classes():
            time_slot = TimeSlot('月', 6)
            current = self.schedule.get_assignment(time_slot, class_ref)
            
            if not current or current.subject.name != '欠':
                # 欠課を設定
                teacher_name = self._get_homeroom_teacher(class_ref)
                teacher = self.school.get_teacher(teacher_name) if teacher_name else None
                
                assignment = Assignment(
                    class_ref=class_ref,
                    subject=self.school.get_subject('欠'),
                    teacher=teacher
                )
                
                try:
                    self.schedule.assign(time_slot, assignment)
                    fixed_count += 1
                except Exception as e:
                    logger.warning(f"  {class_ref}の月曜6限設定エラー: {e}")
        
        logger.info(f"  → {fixed_count}クラスの月曜6限を修正")
    
    def _fix_teacher_conflicts(self):
        """教師重複を修正"""
        logger.info("\n2. 教師重複を修正中...")
        
        conflicts = self._find_teacher_conflicts()
        fixed_count = 0
        
        for time_slot, teacher, conflicting_classes in conflicts:
            logger.info(f"  {teacher.name}の{time_slot}の重複を修正")
            
            # 最初のクラスは残し、他のクラスの教師を変更
            for i, class_ref in enumerate(conflicting_classes[1:]):
                assignment = self.schedule.get_assignment(time_slot, class_ref)
                if assignment:
                    # 代替教師を探す
                    alt_teacher = self._find_alternative_teacher(
                        assignment.subject, time_slot, teacher
                    )
                    
                    if alt_teacher:
                        new_assignment = Assignment(
                            class_ref=class_ref,
                            subject=assignment.subject,
                            teacher=alt_teacher
                        )
                        
                        try:
                            self.schedule.assign(time_slot, new_assignment)
                            fixed_count += 1
                            logger.info(f"    {class_ref}: {teacher.name} → {alt_teacher.name}")
                        except Exception as e:
                            logger.warning(f"    {class_ref}の修正エラー: {e}")
        
        logger.info(f"  → {fixed_count}件の教師重複を修正")
    
    def _fix_daily_duplicates(self):
        """日内重複を修正"""
        logger.info("\n3. 日内重複を修正中...")
        
        duplicates = self._find_daily_duplicates()
        fixed_count = 0
        
        for class_ref, day, subject in duplicates:
            logger.info(f"  {class_ref}の{day}曜日の{subject}重複を修正")
            
            # 重複している時限を取得
            periods = []
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = self.schedule.get_assignment(time_slot, class_ref)
                if assignment and assignment.subject.name == subject:
                    periods.append(period)
            
            # 最初の時限以外を他の教科に変更
            for period in periods[1:]:
                time_slot = TimeSlot(day, period)
                
                # 不足している教科を探す
                needed_subject = self._find_needed_subject(class_ref, day)
                if needed_subject:
                    teacher = self._find_teacher_for_subject(needed_subject, class_ref)
                    
                    if teacher and self._is_teacher_available(teacher, time_slot):
                        new_assignment = Assignment(
                            class_ref=class_ref,
                            subject=self.school.get_subject(needed_subject),
                            teacher=teacher
                        )
                        
                        try:
                            self.schedule.assign(time_slot, new_assignment)
                            fixed_count += 1
                            logger.info(f"    {day}{period}限: {subject} → {needed_subject}")
                        except Exception as e:
                            logger.warning(f"    修正エラー: {e}")
        
        logger.info(f"  → {fixed_count}件の日内重複を修正")
    
    def _fix_standard_hours(self):
        """標準時数を調整"""
        logger.info("\n4. 標準時数を調整中...")
        
        adjusted_count = 0
        
        for class_ref in self.school.get_all_classes():
            if class_ref not in self.standard_hours:
                continue
            
            current_hours = self._calculate_current_hours(class_ref)
            standard = self.standard_hours[class_ref]
            
            # 不足している教科
            for subject, target_hours in standard.items():
                if subject in self.fixed_subjects:
                    continue
                
                current = current_hours.get(subject, 0)
                difference = target_hours - current
                
                if difference > 0.5:  # 0.5時間以上不足
                    # 空きコマまたは過剰な教科と交換
                    for _ in range(int(difference)):
                        if self._add_subject_hour(class_ref, subject):
                            adjusted_count += 1
        
        logger.info(f"  → {adjusted_count}コマの時数を調整")
    
    def _fill_empty_slots(self):
        """空きコマを埋める"""
        logger.info("\n5. 空きコマを埋める...")
        
        filled_count = 0
        
        for time_slot, class_ref in self._find_empty_slots():
            # 不足している教科を優先的に配置
            subject = self._find_most_needed_subject(class_ref)
            
            if subject:
                teacher = self._find_teacher_for_subject(subject, class_ref)
                
                if teacher and self._is_teacher_available(teacher, time_slot):
                    assignment = Assignment(
                        class_ref=class_ref,
                        subject=self.school.get_subject(subject),
                        teacher=teacher
                    )
                    
                    try:
                        self.schedule.assign(time_slot, assignment)
                        filled_count += 1
                        logger.info(f"  {class_ref}の{time_slot}に{subject}を配置")
                    except Exception as e:
                        logger.warning(f"  配置エラー: {e}")
        
        logger.info(f"  → {filled_count}コマを埋めました")
    
    def _sync_exchange_classes(self):
        """交流学級を同期"""
        logger.info("\n6. 交流学級を同期中...")
        
        synced_count = 0
        
        for exchange_class, parent_class in self.exchange_mappings.items():
            for day in ['月', '火', '水', '木', '金']:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    exchange_assignment = self.schedule.get_assignment(time_slot, exchange_class)
                    parent_assignment = self.schedule.get_assignment(time_slot, parent_class)
                    
                    if exchange_assignment and parent_assignment:
                        # 自立活動・日生・作業以外は同期
                        if exchange_assignment.subject.name not in ['自立', '日生', '作業']:
                            if (exchange_assignment.subject.name != parent_assignment.subject.name or
                                exchange_assignment.teacher != parent_assignment.teacher):
                                
                                # 親学級に合わせる
                                new_assignment = Assignment(
                                    class_ref=exchange_class,
                                    subject=parent_assignment.subject,
                                    teacher=parent_assignment.teacher
                                )
                                
                                try:
                                    self.schedule.assign(time_slot, new_assignment)
                                    synced_count += 1
                                except Exception:
                                    pass
        
        logger.info(f"  → {synced_count}コマを同期")
    
    def _sync_grade5_classes(self):
        """5組を同期"""
        logger.info("\n7. 5組を同期中...")
        
        synced_count = 0
        grade5_classes = [ClassReference(1, 5), ClassReference(2, 5), ClassReference(3, 5)]
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                
                # 各5組の現在の割り当てを取得
                assignments = []
                for class_ref in grade5_classes:
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment:
                        assignments.append((class_ref, assignment))
                
                if len(assignments) >= 2:
                    # 最も多い教科を選択
                    subject_counts = defaultdict(int)
                    for _, assignment in assignments:
                        subject_counts[assignment.subject.name] += 1
                    
                    most_common_subject = max(subject_counts, key=subject_counts.get)
                    
                    # 全ての5組を同じ教科に統一
                    for class_ref in grade5_classes:
                        current = self.schedule.get_assignment(time_slot, class_ref)
                        if not current or current.subject.name != most_common_subject:
                            teacher = self._find_teacher_for_subject(most_common_subject, class_ref)
                            
                            if teacher:
                                new_assignment = Assignment(
                                    class_ref=class_ref,
                                    subject=self.school.get_subject(most_common_subject),
                                    teacher=teacher
                                )
                                
                                try:
                                    self.schedule.assign(time_slot, new_assignment)
                                    synced_count += 1
                                except Exception:
                                    pass
        
        logger.info(f"  → {synced_count}コマを同期")
    
    # ヘルパーメソッド
    def _find_teacher_conflicts(self) -> List[Tuple[TimeSlot, Teacher, List[ClassReference]]]:
        """教師重複を検出"""
        conflicts = []
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                teacher_assignments = defaultdict(list)
                
                for class_ref in self.school.get_all_classes():
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.teacher:
                        teacher_assignments[assignment.teacher].append(class_ref)
                
                for teacher, classes in teacher_assignments.items():
                    if len(classes) > 1:
                        # 5組の合同授業は除外
                        grade5_classes = [c for c in classes if c.class_number == 5]
                        if len(grade5_classes) == len(classes):
                            continue
                        
                        conflicts.append((time_slot, teacher, classes))
        
        return conflicts
    
    def _find_daily_duplicates(self) -> List[Tuple[ClassReference, str, str]]:
        """日内重複を検出"""
        duplicates = []
        
        for class_ref in self.school.get_all_classes():
            for day in ['月', '火', '水', '木', '金']:
                subject_counts = defaultdict(int)
                
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    
                    if assignment and assignment.subject.name not in self.fixed_subjects:
                        subject_counts[assignment.subject.name] += 1
                
                for subject, count in subject_counts.items():
                    if count > 1:
                        duplicates.append((class_ref, day, subject))
        
        return duplicates
    
    def _find_empty_slots(self) -> List[Tuple[TimeSlot, ClassReference]]:
        """空きコマを検出"""
        empty_slots = []
        
        for class_ref in self.school.get_all_classes():
            for day in ['月', '火', '水', '木', '金']:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    
                    if not self.schedule.get_assignment(time_slot, class_ref):
                        empty_slots.append((time_slot, class_ref))
        
        return empty_slots
    
    def _calculate_current_hours(self, class_ref: ClassReference) -> Dict[str, float]:
        """現在の時数を計算"""
        hours = defaultdict(float)
        
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                assignment = self.schedule.get_assignment(time_slot, class_ref)
                
                if assignment:
                    hours[assignment.subject.name] += 1.0
        
        return dict(hours)
    
    def _find_alternative_teacher(self, subject, time_slot: TimeSlot, 
                                 exclude_teacher: Teacher) -> Optional[Teacher]:
        """代替教師を探す"""
        # 教科を教えられる他の教師を探す
        for teacher in self.school.get_all_teachers():
            if teacher == exclude_teacher:
                continue
            
            if (self._can_teach_subject(teacher, subject.name) and
                self._is_teacher_available(teacher, time_slot)):
                return teacher
        
        return None
    
    def _is_teacher_available(self, teacher: Teacher, time_slot: TimeSlot) -> bool:
        """教師が利用可能か確認"""
        # 既に他のクラスを担当していないか確認
        for class_ref in self.school.get_all_classes():
            assignment = self.schedule.get_assignment(time_slot, class_ref)
            if assignment and assignment.teacher == teacher:
                return False
        
        # 会議時間でないか確認
        if time_slot in self.meeting_slots:
            # 会議参加者かチェック（簡易的に全教師が参加と仮定）
            return False
        
        return True
    
    def _find_needed_subject(self, class_ref: ClassReference, day: str) -> Optional[str]:
        """その日に不足している教科を探す"""
        if class_ref not in self.standard_hours:
            return None
        
        current_hours = self._calculate_current_hours(class_ref)
        standard = self.standard_hours[class_ref]
        
        # 不足している教科をリストアップ
        needed_subjects = []
        for subject, target_hours in standard.items():
            if subject in self.fixed_subjects:
                continue
            
            current = current_hours.get(subject, 0)
            if current < target_hours:
                # その日にまだ配置されていない教科を優先
                already_today = False
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    assignment = self.schedule.get_assignment(time_slot, class_ref)
                    if assignment and assignment.subject.name == subject:
                        already_today = True
                        break
                
                if not already_today:
                    needed_subjects.append((subject, target_hours - current))
        
        # 最も不足している教科を返す
        if needed_subjects:
            needed_subjects.sort(key=lambda x: x[1], reverse=True)
            return needed_subjects[0][0]
        
        return None
    
    def _find_most_needed_subject(self, class_ref: ClassReference) -> Optional[str]:
        """最も不足している教科を探す"""
        if class_ref not in self.standard_hours:
            return None
        
        current_hours = self._calculate_current_hours(class_ref)
        standard = self.standard_hours[class_ref]
        
        max_shortage = 0
        most_needed = None
        
        for subject, target_hours in standard.items():
            if subject in self.fixed_subjects:
                continue
            
            current = current_hours.get(subject, 0)
            shortage = target_hours - current
            
            if shortage > max_shortage:
                max_shortage = shortage
                most_needed = subject
        
        return most_needed
    
    def _add_subject_hour(self, class_ref: ClassReference, subject: str) -> bool:
        """教科の時間を追加"""
        # 空きコマまたは過剰な教科を探す
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_slot = TimeSlot(day, period)
                current = self.schedule.get_assignment(time_slot, class_ref)
                
                # 空きコマの場合
                if not current:
                    teacher = self._find_teacher_for_subject(subject, class_ref)
                    if teacher and self._is_teacher_available(teacher, time_slot):
                        assignment = Assignment(
                            class_ref=class_ref,
                            subject=self.school.get_subject(subject),
                            teacher=teacher
                        )
                        
                        try:
                            self.schedule.assign(time_slot, assignment)
                            return True
                        except Exception:
                            pass
                
                # 過剰な教科と交換
                elif current.subject.name not in self.fixed_subjects:
                    current_hours = self._calculate_current_hours(class_ref)
                    standard = self.standard_hours.get(class_ref, {})
                    
                    current_subject_hours = current_hours.get(current.subject.name, 0)
                    target_hours = standard.get(current.subject.name, 0)
                    
                    # 過剰な場合
                    if current_subject_hours > target_hours + 0.5:
                        teacher = self._find_teacher_for_subject(subject, class_ref)
                        if teacher and self._is_teacher_available(teacher, time_slot):
                            assignment = Assignment(
                                class_ref=class_ref,
                                subject=self.school.get_subject(subject),
                                teacher=teacher
                            )
                            
                            try:
                                self.schedule.assign(time_slot, assignment)
                                return True
                            except Exception:
                                pass
        
        return False
    
    def _find_teacher_for_subject(self, subject: str, class_ref: ClassReference) -> Optional[Teacher]:
        """教科の教師を探す"""
        # デフォルトマッピングから探す（実装は簡略化）
        teacher_mappings = {
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
        
        teacher_name = teacher_mappings.get(subject)
        if teacher_name:
            return self.school.get_teacher(teacher_name)
        
        # 担任が担当する教科
        if subject in ['道', '学', '総', '学総']:
            homeroom_teacher = self._get_homeroom_teacher(class_ref)
            if homeroom_teacher:
                return self.school.get_teacher(homeroom_teacher)
        
        return None
    
    def _can_teach_subject(self, teacher: Teacher, subject: str) -> bool:
        """教師が教科を教えられるか確認"""
        # 簡易実装：教師名と教科の対応をチェック
        teacher_subjects = {
            '智田先生': ['国'],
            '井上先生': ['数'],
            '蒲地先生': ['英'],
            '梶永先生': ['理'],
            '神田先生': ['社'],
            '今先生': ['音'],
            '平野先生': ['美'],
            '野田先生': ['体'],
            '國本先生': ['技'],
            '石原先生': ['家'],
        }
        
        return subject in teacher_subjects.get(teacher.name, [])
    
    def _get_homeroom_teacher(self, class_ref: ClassReference) -> Optional[str]:
        """担任教師を取得"""
        homeroom_teachers = {
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
        
        return homeroom_teachers.get((class_ref.grade, class_ref.class_number))


def main():
    """メイン処理"""
    try:
        # リポジトリとローダーを初期化
        repository = CSVScheduleRepository()
        loader = AdvancedCSPConfigLoader(repository)
        
        # データを読み込み
        logger.info("データを読み込み中...")
        input_path = os.path.join(OUTPUT_DIR, 'output.csv')
        school, initial_schedule, constraints = loader.load_from_csv(input_path)
        
        # 修正を実行
        fixer = ComprehensiveScheduleFixer(initial_schedule, school)
        fixer.fix_all_violations()
        
        # 結果を保存
        logger.info("\n修正結果を保存中...")
        output_path = os.path.join(OUTPUT_DIR, 'output_fixed.csv')
        repository.save_schedule(initial_schedule, output_path)
        
        # 元のファイルも更新
        repository.save_schedule(initial_schedule, input_path)
        
        logger.info(f"\n修正完了！")
        logger.info(f"出力ファイル: {output_path}")
        
        # 違反チェックスクリプトを実行
        logger.info("\n=== 最終違反チェック ===")
        os.system("python3 scripts/analysis/check_violations.py")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
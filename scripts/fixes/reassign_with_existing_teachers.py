#!/usr/bin/env python3
"""
教師不在違反を既存教師で自動的に修正するスクリプト
"""
import sys
from pathlib import Path

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import csv
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import shutil
from datetime import datetime

from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.infrastructure.repositories.teacher_absence_loader import TeacherAbsenceLoader
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.domain.entities.schedule import Schedule
from src.domain.entities.school import School
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject, Teacher
from src.domain.value_objects.assignment import Assignment


class TeacherReassignmentService:
    """教師再配置サービス"""
    
    def __init__(self):
        self.data_dir = project_root / "data"
        self.teacher_mapping_repo = TeacherMappingRepository(self.data_dir)
        self.teacher_mapping = self.teacher_mapping_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
        self.csv_reader = CSVScheduleReader()
        
        # 教科別の教師リストを作成
        self.subject_teachers = self._build_subject_teacher_mapping()
        
        # 教師の時間割を追跡
        self.teacher_schedule = defaultdict(list)  # teacher -> List[(day, period, class)]
        
    def _build_subject_teacher_mapping(self) -> Dict[str, List[str]]:
        """教科別の教師リストを構築"""
        subject_teachers = defaultdict(list)
        
        # teacher_subject_mapping.csvから教科別教師リストを作成
        for teacher_name, subject_list in self.teacher_mapping.items():
            if teacher_name in ["欠課", "未定", "TBA"]:
                continue
            for subject, class_refs in subject_list:
                subject_name = subject.name
                if teacher_name not in subject_teachers[subject_name]:
                    subject_teachers[subject_name].append(teacher_name)
        
        # CLAUDE.mdの情報で補完
        known_mappings = {
            "国": ["寺田", "小野塚"],
            "数": ["梶永", "井上", "森山"],
            "英": ["井野口", "箱崎", "林田"],
            "社": ["蒲地", "北"],
            "理": ["金子ひ", "智田", "白石"],
            "音": ["塚本"],
            "美": ["青井", "金子み"],
            "保": ["永山", "野口", "財津"],
            "技": ["林"],
            "家": ["金子み"],
        }
        
        for subject, teachers in known_mappings.items():
            for teacher in teachers:
                if teacher not in subject_teachers[subject]:
                    subject_teachers[subject].append(teacher)
        
        return dict(subject_teachers)
    
    def _get_homeroom_teachers(self) -> Dict[Tuple[int, int], str]:
        """担任教師のマッピング"""
        return {
            (1, 1): "金子ひ", (1, 2): "井野口", (1, 3): "梶永",
            (2, 1): "塚本", (2, 2): "野口", (2, 3): "永山",
            (3, 1): "白石", (3, 2): "森山", (3, 3): "北",
            (1, 5): "金子み", (2, 5): "金子み", (3, 5): "金子み",
            (1, 6): "財津", (2, 6): "財津", (3, 6): "財津",
            (1, 7): "智田", (2, 7): "智田", (3, 7): "智田",
        }
    
    def load_violations(self) -> List[Dict]:
        """違反情報を読み込み"""
        violations_file = self.data_dir / "output" / "teacher_absence_violations.json"
        if not violations_file.exists():
            print("❌ 違反情報ファイルが見つかりません。")
            print("   先に check_and_fix_teacher_absences.py を実行してください。")
            return []
        
        with open(violations_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_current_schedule(self) -> Schedule:
        """現在のスケジュールを読み込み"""
        input_path = self.data_dir / "input" / "input.csv"
        
        # CSVReaderはschoolなしでも動作する
        schedule = self.csv_reader.read(input_path, None)
        
        # 教師の時間割を構築
        self._build_teacher_schedule(schedule)
        
        return schedule
    
    def _build_teacher_schedule(self, schedule: Schedule):
        """教師の時間割を構築"""
        self.teacher_schedule.clear()
        
        for time_slot, assignment in schedule.get_all_assignments():
            if assignment.teacher and assignment.teacher.name not in ["欠課", "未定", "TBA"]:
                self.teacher_schedule[assignment.teacher.name].append(
                    (time_slot.day, time_slot.period, assignment.class_ref)
                )
    
    def is_teacher_available(self, teacher: str, day: str, period: int) -> bool:
        """教師がその時間に空いているかチェック"""
        for t_day, t_period, _ in self.teacher_schedule[teacher]:
            if t_day == day and t_period == period:
                return False
        return True
    
    def find_best_replacement(self, subject: str, day: str, period: int, 
                            absent_teacher: str, class_ref: ClassReference) -> Optional[str]:
        """最適な代替教師を見つける"""
        # 担任科目の場合
        if subject in ["道", "学", "総", "学総", "YT"]:
            # 担任教師を取得
            homeroom_teachers = self._get_homeroom_teachers()
            homeroom_teacher = homeroom_teachers.get((class_ref.grade, class_ref.class_number))
            
            # 担任が不在の場合は削除を推奨
            if homeroom_teacher == absent_teacher:
                return None
            
            # 他の担任で空いている人を探す
            for teacher in homeroom_teachers.values():
                if teacher != absent_teacher and self.is_teacher_available(teacher, day, period):
                    return teacher
            return None
        
        # 通常教科の場合
        if subject not in self.subject_teachers:
            return None
        
        # 同じ教科を教えられる教師を優先度順に評価
        candidates = []
        for teacher in self.subject_teachers[subject]:
            if teacher == absent_teacher:
                continue
                
            if self.is_teacher_available(teacher, day, period):
                # 教師の負担を計算（現在の授業数）
                workload = len(self.teacher_schedule[teacher])
                candidates.append((teacher, workload))
        
        # 負担が少ない教師を優先
        candidates.sort(key=lambda x: x[1])
        
        if candidates:
            return candidates[0][0]
        
        return None
    
    def reassign_teachers(self, schedule: Schedule, violations: List[Dict]) -> Tuple[Schedule, List[Dict]]:
        """教師を再配置"""
        results = []
        
        # 固定科目保護を一時的に無効化
        schedule.disable_fixed_subject_protection()
        
        try:
            for violation in violations:
                class_name = violation["class"]
                # time_slotは文字列として保存されているので、パースする
                time_slot_str = violation["time_slot"]
                # "水曜3校時" のような形式からTimeSlotを作成
                import re
                ts_match = re.match(r'([月火水木金])曜(\d+)校時', time_slot_str)
                if ts_match:
                    time_slot = TimeSlot(ts_match.group(1), int(ts_match.group(2)))
                else:
                    continue
                
                subject = violation["subject"]
                absent_teacher = violation["teacher"]
                
                # クラス参照を取得
                import re
                match = re.match(r'(\d+)年(\d+)組', class_name)
                if not match:
                    continue
                class_ref = ClassReference(int(match.group(1)), int(match.group(2)))
                
                # 代替教師を探す
                replacement = self.find_best_replacement(
                    subject, time_slot.day, time_slot.period, absent_teacher, class_ref
                )
                
                if replacement:
                    # 新しい割り当てを作成
                    new_assignment = Assignment(
                        class_ref,
                        Subject(subject),
                        Teacher(replacement)
                    )
                    
                    # スケジュールを更新
                    try:
                        # 既存の割り当てを削除
                        schedule.unlock_cell(time_slot, class_ref)
                        schedule.remove_assignment(time_slot, class_ref)
                        
                        # 新しい割り当てを追加
                        schedule.assign(time_slot, new_assignment)
                        
                        # 教師スケジュールを更新
                        self.teacher_schedule[replacement].append(
                            (time_slot.day, time_slot.period, class_ref)
                        )
                        
                        results.append({
                            "class": class_name,
                            "time_slot": time_slot,
                            "subject": subject,
                            "original_teacher": absent_teacher,
                            "replacement_teacher": replacement,
                            "status": "replaced"
                        })
                    except Exception as e:
                        results.append({
                            "class": class_name,
                            "time_slot": time_slot,
                            "subject": subject,
                            "original_teacher": absent_teacher,
                            "replacement_teacher": None,
                            "status": f"error: {str(e)}"
                        })
                else:
                    # 代替教師が見つからない場合は削除
                    try:
                        schedule.unlock_cell(time_slot, class_ref)
                        schedule.remove_assignment(time_slot, class_ref)
                        
                        results.append({
                            "class": class_name,
                            "time_slot": time_slot,
                            "subject": subject,
                            "original_teacher": absent_teacher,
                            "replacement_teacher": None,
                            "status": "removed"
                        })
                    except Exception as e:
                        results.append({
                            "class": class_name,
                            "time_slot": time_slot,
                            "subject": subject,
                            "original_teacher": absent_teacher,
                            "replacement_teacher": None,
                            "status": f"error: {str(e)}"
                        })
        finally:
            # 固定科目保護を再有効化
            schedule.enable_fixed_subject_protection()
        
        return schedule, results
    
    def save_corrected_schedule(self, schedule: Schedule, output_file: str = "output/input_corrected.csv"):
        """修正済みスケジュールを保存"""
        output_path = self.data_dir / output_file
        output_path.parent.mkdir(exist_ok=True)
        
        # バックアップを作成
        input_path = self.data_dir / "input" / "input.csv"
        backup_path = self.data_dir / "input" / f"input_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        shutil.copy(input_path, backup_path)
        
        # 修正済みスケジュールを手動で保存
        self._write_schedule_to_csv(schedule, output_path)
        
        return output_path, backup_path
    
    def _write_schedule_to_csv(self, schedule: Schedule, output_path: Path):
        """スケジュールをCSVに書き込み"""
        # 元のinput.csvを読み込んで形式を保持
        input_path = self.data_dir / "input" / "input.csv"
        
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = list(csv.reader(f))
        
        # 各クラスの時間割を更新
        days = ["月", "火", "水", "木", "金"]
        for row_idx, row in enumerate(lines[2:], 2):
            if not row or not row[0]:
                continue
                
            class_name = row[0]
            try:
                # クラス参照を取得
                import re
                match = re.match(r'(\d+)年(\d+)組', class_name)
                if not match:
                    continue
                class_ref = ClassReference(int(match.group(1)), int(match.group(2)))
                
                # 各時限の授業を更新
                col_idx = 1
                for day in days:
                    for period in range(1, 7):
                        if col_idx < len(row):
                            time_slot = TimeSlot(day, period)
                            assignment = schedule.get_assignment(time_slot, class_ref)
                            
                            if assignment:
                                lines[row_idx][col_idx] = assignment.subject.name
                            else:
                                lines[row_idx][col_idx] = ""
                        col_idx += 1
            except:
                continue
        
        # CSVに書き込み
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(lines)
    
    def print_results(self, results: List[Dict], output_path: Path, backup_path: Path):
        """結果を表示"""
        print("\n" + "="*80)
        print("教師再配置結果")
        print("="*80)
        
        replaced = [r for r in results if r["status"] == "replaced"]
        removed = [r for r in results if r["status"] == "removed"]
        errors = [r for r in results if r["status"].startswith("error")]
        
        if replaced:
            print(f"\n✅ {len(replaced)}件の再配置に成功:")
            for r in replaced:
                print(f"  - {r['time_slot']} {r['class']} {r['subject']}: "
                      f"{r['original_teacher']} → {r['replacement_teacher']}")
        
        if removed:
            print(f"\n⚠️  {len(removed)}件を削除（代替教師なし）:")
            for r in removed:
                print(f"  - {r['time_slot']} {r['class']} {r['subject']} ({r['original_teacher']})")
        
        if errors:
            print(f"\n❌ {len(errors)}件のエラー:")
            for r in errors:
                print(f"  - {r['time_slot']} {r['class']} {r['subject']}: {r['status']}")
        
        print("\n" + "-"*80)
        print(f"✅ 修正済みファイル: {output_path}")
        print(f"📁 バックアップ: {backup_path}")
        print("\n使用方法:")
        print("1. 修正済みファイルを確認")
        print("2. 問題なければ input.csv を置き換え")
        print("3. python3 main.py generate で時間割を再生成")
        print("="*80)


def main():
    """メイン処理"""
    print("教師再配置処理を開始します...")
    
    service = TeacherReassignmentService()
    
    # 違反情報を読み込み
    violations = service.load_violations()
    if not violations:
        return
    
    print(f"\n{len(violations)}件の違反を処理します...")
    
    # 現在のスケジュールを読み込み
    schedule = service.load_current_schedule()
    
    # 教師を再配置
    corrected_schedule, results = service.reassign_teachers(schedule, violations)
    
    # 結果を保存
    output_path, backup_path = service.save_corrected_schedule(corrected_schedule)
    
    # 結果を表示
    service.print_results(results, output_path, backup_path)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Ultrathink空きスロット埋めスクリプト - 画像から特定された25個の空きスロットを埋める"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Union
from collections import defaultdict
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.domain.value_objects.time_slot import TimeSlot, Teacher, Subject
from src.domain.entities.school import School
from src.domain.entities.schedule import Schedule
from src.domain.value_objects.assignment import Assignment
from src.infrastructure.repositories.csv_repository import CSVSchoolRepository
from src.infrastructure.repositories.schedule_io.csv_reader import CSVScheduleReader
from src.infrastructure.repositories.schedule_io.csv_writer import CSVScheduleWriter

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class UltrathinkEmptySlotFiller:
    """空きスロットを埋める専用クラス"""
    
    def parse_class_ref(self, class_ref_str: str) -> Tuple[int, int]:
        """クラス名文字列をパースして学年と組を返す"""
        # 例: "1年6組" -> (1, 6)
        import re
        match = re.match(r'(\d)年(\d)組', class_ref_str)
        if match:
            return int(match.group(1)), int(match.group(2))
        else:
            raise ValueError(f"無効なクラス名: {class_ref_str}")
    
    def __init__(self):
        # 交流学級と親学級のマッピング
        self.exchange_parent_map = {
            "1年6組": "1年1組",
            "1年7組": "1年2組",
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        
        # 画像から特定された空きスロット（25個）
        self.empty_slots = [
            # 1年6組（3個）
            ("1年6組", "月", 5),
            ("1年6組", "木", 6),
            ("1年6組", "金", 5),
            
            # 1年7組（4個）
            ("1年7組", "月", 4),
            ("1年7組", "木", 6),
            ("1年7組", "金", 4),
            ("1年7組", "金", 6),
            
            # 2年6組（4個）
            ("2年6組", "水", 2),
            ("2年6組", "木", 4),
            ("2年6組", "木", 6),
            ("2年6組", "金", 6),
            
            # 2年7組（6個）
            ("2年7組", "火", 3),
            ("2年7組", "木", 6),
            ("2年7組", "金", 1),
            ("2年7組", "金", 4),
            ("2年7組", "金", 5),
            ("2年7組", "金", 6),
            
            # 3年6組（5個）
            ("3年6組", "水", 5),
            ("3年6組", "木", 5),
            ("3年6組", "金", 2),
            ("3年6組", "金", 4),
            ("3年6組", "金", 6),
            
            # 3年7組（3個）
            ("3年7組", "水", 4),
            ("3年7組", "金", 4),
            ("3年7組", "金", 6)
        ]
        
        # 教師と教科のマッピング（主要教科）
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
        
        # 標準時数（週あたり）
        self.standard_hours = {
            "国": 4, "社": 3, "数": 4, "理": 3, "英": 4,
            "音": 1.3, "美": 1.3, "保": 3, "技": 2, "家": 2
        }
    
    def fill_empty_slots(self):
        """空きスロットを埋める"""
        logger.info("=== Ultrathink空きスロット埋めを開始 ===\n")
        
        # データ読み込み
        school, schedule = self.load_data()
        
        # 教師名を確認
        logger.info("\n利用可能な教師:")
        for teacher in school.get_all_teachers():
            logger.info(f"  - {teacher.name}")
        
        # 空きスロットを埋める
        filled_count = 0
        for class_ref_str, day, period in self.empty_slots:
            time_slot = TimeSlot(day, period)
            
            # 既に埋まっている場合はスキップ
            if schedule.get_assignment(time_slot, class_ref_str):
                logger.info(f"✓ {class_ref_str} {day}{period}限は既に埋まっています")
                continue
            
            # 交流学級の場合は親学級に合わせる
            if class_ref_str in self.exchange_parent_map:
                parent_class = self.exchange_parent_map[class_ref_str]
                parent_assignment = schedule.get_assignment(time_slot, parent_class)
                
                if parent_assignment:
                    schedule.assign(time_slot, class_ref_str,
                                  parent_assignment.subject, parent_assignment.teacher)
                    filled_count += 1
                    logger.info(f"✓ {class_ref_str} {day}{period}限: {parent_assignment.subject.name}（親学級に同期）")
                    continue
            
            # 通常の空きスロット埋め
            subject = self.select_subject_for_slot(schedule, school, class_ref_str, time_slot)
            if subject:
                teacher = self.find_available_teacher(school, subject, time_slot, schedule)
                if teacher:
                    try:
                        subject_obj = Subject(subject)
                        schedule.assign(time_slot, class_ref_str, subject_obj, teacher)
                        filled_count += 1
                        logger.info(f"✓ {class_ref_str} {day}{period}限: {subject} - {teacher.name}")
                    except Exception as e:
                        logger.warning(f"✗ {class_ref_str} {day}{period}限: エラー - {e}")
                else:
                    logger.warning(f"✗ {class_ref_str} {day}{period}限: {subject}の教師が見つかりません")
            else:
                logger.warning(f"✗ {class_ref_str} {day}{period}限: 適切な科目が見つかりません")
        
        logger.info(f"\n合計 {filled_count}個の空きスロットを埋めました")
        
        # 結果保存
        self.save_results(schedule)
        
        # 統計情報
        self.print_statistics(schedule, school)
    
    def load_data(self) -> Tuple[School, Schedule]:
        """データを読み込む"""
        logger.info("データを読み込み中...")
        
        # School data
        school_repo = CSVSchoolRepository(str(project_root / "data" / "config"))
        school = school_repo.load_school_data()
        
        # Schedule
        reader = CSVScheduleReader()
        schedule = reader.read(Path(project_root / "data" / "output" / "output.csv"), school)
        
        return school, schedule
    
    def select_subject_for_slot(self, schedule: Schedule, school: School,
                              class_ref: str, time_slot: TimeSlot) -> Optional[str]:
        """スロットに配置する科目を選択"""
        # その日の配置済み科目を収集
        day_subjects = set()
        for period in range(1, 7):
            ts = TimeSlot(time_slot.day, period)
            assignment = schedule.get_assignment(ts, class_ref)
            if assignment:
                day_subjects.add(assignment.subject.name)
        
        # クラスの週間時数をカウント
        week_subjects = defaultdict(int)
        for day in ["月", "火", "水", "木", "金"]:
            for period in range(1, 7):
                ts = TimeSlot(day, period)
                assignment = schedule.get_assignment(ts, class_ref)
                if assignment:
                    week_subjects[assignment.subject.name] += 1
        
        # 標準時数と比較して不足している科目を優先
        candidates = []
        
        # 主要5教科を最優先
        for subject in ["国", "数", "英", "理", "社"]:
            if subject not in day_subjects:  # その日にまだない
                current = week_subjects.get(subject, 0)
                standard = self.standard_hours.get(subject, 0)
                if current < standard:
                    candidates.append((subject, standard - current))
        
        # 技能教科
        for subject in ["音", "美", "保", "技", "家"]:
            if subject not in day_subjects:  # その日にまだない
                current = week_subjects.get(subject, 0)
                standard = self.standard_hours.get(subject, 0)
                if current < standard:
                    candidates.append((subject, standard - current))
        
        # 不足数が多い順にソート
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 最も不足している科目を返す
        if candidates:
            return candidates[0][0]
        
        # すべて標準時数を満たしている場合は主要5教科から選択
        for subject in ["国", "数", "英", "理", "社"]:
            if subject not in day_subjects and week_subjects.get(subject, 0) < 5:  # 週5時間まで許容
                return subject
        
        return None
    
    def find_available_teacher(self, school: School, subject: str,
                             time_slot: TimeSlot, schedule: Schedule):
        """利用可能な教師を探す"""
        # 教師リストから名前で検索するヘルパー関数
        def find_teacher_by_name(name: str) -> Optional[Teacher]:
            for teacher in school.get_all_teachers():
                if teacher.name == name:
                    return teacher
            return None
        
        if subject in self.subject_teacher_map:
            for teacher_name in self.subject_teacher_map[subject]:
                teacher = find_teacher_by_name(teacher_name)
                if teacher and self.is_teacher_available(schedule, school, time_slot, teacher_name):
                    return teacher
        
        # 担任が担当する科目の場合
        if subject in ["道", "学", "総", "学総"]:
            # 適当な担任を探す
            for teacher_name in ["金子ひ", "井野口", "梶永", "塚本",
                               "野口", "永山", "白石", "森山", "北"]:
                teacher = find_teacher_by_name(teacher_name)
                if teacher and self.is_teacher_available(schedule, school, time_slot, teacher_name):
                    return teacher
        
        return None
    
    def is_teacher_available(self, schedule: Schedule, school: School, 
                           time_slot: TimeSlot, teacher_name: str) -> bool:
        """教師が利用可能かチェック"""
        for class_ref in school.get_all_classes():
            assignment = schedule.get_assignment(time_slot, str(class_ref))
            if assignment and assignment.teacher and assignment.teacher.name == teacher_name:
                # 5組の合同授業は除外
                if "5組" in str(class_ref):
                    continue
                return False
        return True
    
    def save_results(self, schedule: Schedule):
        """結果を保存"""
        output_path = project_root / "data" / "output" / "output.csv"
        # Use CSVScheduleWriterImproved instead
        from src.infrastructure.repositories.schedule_io.csv_writer_improved import CSVScheduleWriterImproved
        writer = CSVScheduleWriterImproved()
        writer.write(schedule, output_path)
        logger.info(f"\n修正済み時間割を保存: {output_path}")
    
    def print_statistics(self, schedule: Schedule, school: School):
        """統計情報を表示"""
        logger.info("\n=== 最終統計 ===")
        
        # 空きスロット数を再カウント
        empty_count = 0
        days = ["月", "火", "水", "木", "金"]
        
        for class_ref in school.get_all_classes():
            class_ref_str = str(class_ref)
            for day in days:
                for period in range(1, 7):
                    time_slot = TimeSlot(day, period)
                    if not schedule.get_assignment(time_slot, class_ref_str):
                        empty_count += 1
        
        logger.info(f"残りの空きスロット数: {empty_count}個")


def main():
    """メイン処理"""
    filler = UltrathinkEmptySlotFiller()
    filler.fill_empty_slots()


if __name__ == "__main__":
    main()
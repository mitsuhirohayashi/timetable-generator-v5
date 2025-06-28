#!/usr/bin/env python3
"""
空きスロットを交流学級の同期を考慮して埋めるスクリプト
"""
import sys
import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.parsers.basics_parser import BasicsParser
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference, Subject

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmptySlotFiller:
    """空きスロット埋めクラス"""
    
    def __init__(self):
        self.data_dir = project_root / "data"
        
        # パーサーとリポジトリの初期化
        self.basics_parser = BasicsParser()
        self.teacher_mapping_repo = TeacherMappingRepository(self.data_dir)
        
        # 教師マッピングを読み込み
        self.teacher_mapping = self.teacher_mapping_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
        
        # 交流学級マッピング
        self.exchange_class_pairs = {
            "1年6組": "1年1組",
            "1年7組": "1年2組", 
            "2年6組": "2年3組",
            "2年7組": "2年2組",
            "3年6組": "3年3組",
            "3年7組": "3年2組"
        }
        
        # 逆引きマッピング
        self.parent_to_exchange = {v: k for k, v in self.exchange_class_pairs.items()}
        
        # 固定科目（配置しない）
        self.fixed_subjects = {"欠", "YT", "道", "道徳", "学", "学活", "学総", "総", "総合", "行", "テスト", "技家"}
    
    def fill_empty_slots(self, input_file: str = "output/output.csv", output_file: str = "output/output_filled.csv"):
        """空きスロットを埋める"""
        logger.info("=== 空きスロット埋め開始 ===")
        
        # スケジュールを読み込み
        schedule_data = self._read_schedule(input_file)
        
        # 空きスロットを検出
        empty_slots = self._find_empty_slots(schedule_data)
        logger.info(f"空きスロット数: {len(empty_slots)}")
        
        # 標準時数を読み込み
        standard_hours = self._load_standard_hours()
        
        # 現在の時数をカウント
        current_hours = self._count_current_hours(schedule_data)
        
        # 空きスロットを埋める
        filled_schedule = self._fill_slots(schedule_data, empty_slots, standard_hours, current_hours)
        
        # 結果を出力
        self._write_schedule(filled_schedule, output_file)
        
        logger.info(f"=== 空きスロット埋め完了: {output_file} ===")
        
        return len(empty_slots)
    
    def _read_schedule(self, file_path: str) -> Dict:
        """スケジュールを読み込み"""
        full_path = self.data_dir / file_path
        
        with open(full_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            lines = list(reader)
        
        # タイムスロットを解析
        time_slots = []
        days = ["月", "火", "水", "木", "金"]
        period_row = lines[1]
        
        for i, period_str in enumerate(period_row[1:]):
            if period_str.isdigit():
                day_index = i // 6
                period = int(period_str)
                if day_index < len(days):
                    time_slots.append((days[day_index], period))
        
        # クラスごとのデータを読み込み
        schedule = {}
        for line in lines[2:]:
            if not line or not line[0].strip():
                continue
            
            class_name = line[0].strip()
            assignments = line[1:]
            
            schedule[class_name] = {
                'assignments': assignments,
                'time_slots': time_slots
            }
        
        return schedule
    
    def _find_empty_slots(self, schedule_data: Dict) -> List[Dict]:
        """空きスロットを検出"""
        empty_slots = []
        
        for class_name, data in schedule_data.items():
            assignments = data['assignments']
            time_slots = data['time_slots']
            
            for i, subject in enumerate(assignments):
                if i >= len(time_slots):
                    break
                
                if not subject.strip():
                    day, period = time_slots[i]
                    empty_slots.append({
                        'class': class_name,
                        'day': day,
                        'period': period,
                        'index': i
                    })
        
        for slot in empty_slots:
            logger.info(f"  - {slot['class']} {slot['day']}曜{slot['period']}限")
        
        return empty_slots
    
    def _load_standard_hours(self) -> Dict[str, Dict[str, int]]:
        """標準時数を読み込み"""
        standard_hours = {}
        
        # base_timetable.csvから読み込み
        base_timetable_path = self.data_dir / "config" / "base_timetable.csv"
        
        try:
            with open(base_timetable_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    class_name = row['クラス']
                    hours = {}
                    for subject, count in row.items():
                        if subject != 'クラス' and count.isdigit():
                            hours[subject] = int(count)
                    standard_hours[class_name] = hours
        except Exception as e:
            logger.error(f"標準時数の読み込みエラー: {e}")
            # デフォルト値を使用
            default_hours = {
                "国": 4, "数": 4, "英": 4, "理": 3, "社": 3,
                "音": 1, "美": 1, "保": 3, "技": 2, "家": 2
            }
            for class_name in ["1年1組", "1年2組", "1年3組", "2年1組", "2年2組", "2年3組", 
                              "3年1組", "3年2組", "3年3組"]:
                standard_hours[class_name] = default_hours.copy()
        
        return standard_hours
    
    def _count_current_hours(self, schedule_data: Dict) -> Dict[str, Dict[str, int]]:
        """現在の時数をカウント"""
        current_hours = {}
        
        for class_name, data in schedule_data.items():
            hours = {}
            assignments = data['assignments']
            
            for subject in assignments:
                subject = subject.strip()
                if subject and subject not in self.fixed_subjects:
                    hours[subject] = hours.get(subject, 0) + 1
            
            current_hours[class_name] = hours
        
        return current_hours
    
    def _fill_slots(self, schedule_data: Dict, empty_slots: List[Dict], 
                   standard_hours: Dict, current_hours: Dict) -> Dict:
        """空きスロットを埋める"""
        import copy
        filled_schedule = copy.deepcopy(schedule_data)
        
        for slot in empty_slots:
            class_name = slot['class']
            day = slot['day']
            period = slot['period']
            index = slot['index']
            
            # 交流学級の場合、親学級との同期を考慮
            if class_name in self.exchange_class_pairs:
                parent_class = self.exchange_class_pairs[class_name]
                if parent_class in filled_schedule:
                    parent_assignments = filled_schedule[parent_class]['assignments']
                    if index < len(parent_assignments) and parent_assignments[index].strip():
                        # 親学級と同じ科目を配置
                        subject = parent_assignments[index].strip()
                        if subject not in ["自立", "日生", "作業"]:
                            filled_schedule[class_name]['assignments'][index] = subject
                            logger.info(f"  → {class_name} {day}曜{period}限: {subject} (親学級と同期)")
                            continue
            
            # 親学級の場合、交流学級も同時に埋める
            if class_name in self.parent_to_exchange:
                exchange_class = self.parent_to_exchange[class_name]
                
                # 適切な科目を選択
                subject = self._select_subject(class_name, day, period, standard_hours.get(class_name, {}), 
                                             current_hours.get(class_name, {}), filled_schedule)
                
                if subject:
                    # 親学級に配置
                    filled_schedule[class_name]['assignments'][index] = subject
                    logger.info(f"  → {class_name} {day}曜{period}限: {subject}")
                    
                    # 交流学級にも配置（自立活動でなければ）
                    if exchange_class in filled_schedule:
                        exchange_assignments = filled_schedule[exchange_class]['assignments']
                        if index < len(exchange_assignments) and not exchange_assignments[index].strip():
                            filled_schedule[exchange_class]['assignments'][index] = subject
                            logger.info(f"  → {exchange_class} {day}曜{period}限: {subject} (交流学級も同期)")
            else:
                # 通常クラスまたは5組
                subject = self._select_subject(class_name, day, period, standard_hours.get(class_name, {}), 
                                             current_hours.get(class_name, {}), filled_schedule)
                
                if subject:
                    filled_schedule[class_name]['assignments'][index] = subject
                    logger.info(f"  → {class_name} {day}曜{period}限: {subject}")
        
        return filled_schedule
    
    def _select_subject(self, class_name: str, day: str, period: int, 
                       standard: Dict[str, int], current: Dict[str, int],
                       schedule_data: Dict) -> Optional[str]:
        """配置する科目を選択"""
        # 不足している科目を優先
        needed_subjects = []
        
        # 主要5教科を優先
        priority_subjects = ["国", "数", "英", "理", "社"]
        other_subjects = ["音", "美", "保", "技", "家"]
        
        # 優先科目から選択
        for subject in priority_subjects:
            if subject in standard:
                needed = standard[subject] - current.get(subject, 0)
                if needed > 0:
                    # その日にまだ配置されていないかチェック
                    if not self._has_subject_on_day(schedule_data, class_name, day, subject):
                        needed_subjects.append((subject, needed))
        
        # その他の科目
        for subject in other_subjects:
            if subject in standard:
                needed = standard[subject] - current.get(subject, 0)
                if needed > 0:
                    if not self._has_subject_on_day(schedule_data, class_name, day, subject):
                        needed_subjects.append((subject, needed))
        
        # 最も不足している科目を選択
        if needed_subjects:
            needed_subjects.sort(key=lambda x: x[1], reverse=True)
            return needed_subjects[0][0]
        
        # 標準時数を超えても配置（主要5教科優先）
        for subject in priority_subjects:
            if not self._has_subject_on_day(schedule_data, class_name, day, subject):
                return subject
        
        return None
    
    def _has_subject_on_day(self, schedule_data: Dict, class_name: str, day: str, subject: str) -> bool:
        """その日に既に科目が配置されているかチェック"""
        if class_name not in schedule_data:
            return False
        
        data = schedule_data[class_name]
        assignments = data['assignments']
        time_slots = data['time_slots']
        
        for i, (slot_day, _) in enumerate(time_slots):
            if slot_day == day and i < len(assignments):
                if assignments[i].strip() == subject:
                    return True
        
        return False
    
    def _write_schedule(self, schedule_data: Dict, output_file: str):
        """スケジュールを出力"""
        output_path = self.data_dir / output_file
        
        # 標準的なクラス順序
        standard_order = [
            "1年1組", "1年2組", "1年3組", "1年5組", "1年6組", "1年7組",
            "2年1組", "2年2組", "2年3組", "2年5組", "2年6組", "2年7組",
            "",  # 空白行
            "3年1組", "3年2組", "3年3組", "3年5組", "3年6組", "3年7組"
        ]
        
        # ヘッダーを作成
        days = ["月", "火", "水", "木", "金"]
        periods = ["1", "2", "3", "4", "5", "6"]
        
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # ヘッダー行
            header = ["基本時間割"]
            for day in days:
                header.extend([day] * 6)
            writer.writerow(header)
            
            # 期間行
            period_row = [""]
            for _ in days:
                period_row.extend(periods)
            writer.writerow(period_row)
            
            # クラスごとのデータ
            for class_name in standard_order:
                if class_name == "":
                    writer.writerow([])
                    continue
                
                if class_name in schedule_data:
                    row = [class_name]
                    row.extend(schedule_data[class_name]['assignments'])
                    writer.writerow(row)
                else:
                    # クラスが存在しない場合は空行
                    writer.writerow([class_name] + [""] * 30)
            
            # 最後に空行
            writer.writerow([])


def main():
    """メイン処理"""
    filler = EmptySlotFiller()
    
    # 空きスロットを埋める
    empty_count = filler.fill_empty_slots()
    
    print(f"\n空きスロット埋め完了")
    print(f"埋めたスロット数: {empty_count}")
    print("\n次のステップ:")
    print("1. output_filled.csvを確認")
    print("2. 制約違反をチェック")
    print("3. 必要に応じて手動調整")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""テスト期間保護スクリプト

Follow-up.csvからテスト期間の指示を読み取り、input.csvに「テスト」として記入します。
これにより、時間割生成時にテスト期間が保護されます。
"""
import re
import csv
import logging
from pathlib import Path
from typing import List, Dict, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestPeriodProtector:
    """テスト期間を保護するクラス"""
    
    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.followup_path = data_dir / "input" / "Follow-up.csv"
        self.input_path = data_dir / "input" / "input.csv"
        self.output_path = data_dir / "input" / "input_with_tests.csv"
        
        # 曜日マッピング
        self.day_map = {
            '月曜': '月', '月曜日': '月',
            '火曜': '火', '火曜日': '火', 
            '水曜': '水', '水曜日': '水',
            '木曜': '木', '木曜日': '木',
            '金曜': '金', '金曜日': '金'
        }
        
        # クラスリスト（5組は除外）
        self.classes = []
        for grade in range(1, 4):
            for class_num in range(1, 8):
                if class_num != 5:  # 5組（特別支援学級）は除外
                    self.classes.append(f"{grade}-{class_num}")
    
    def parse_test_periods(self) -> List[Tuple[str, List[int]]]:
        """Follow-up.csvからテスト期間を抽出"""
        test_periods = []
        current_day = None
        
        if not self.followup_path.exists():
            logger.warning(f"Follow-up.csv not found: {self.followup_path}")
            return test_periods
        
        with open(self.followup_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 曜日の検出
            for day_text, day_code in self.day_map.items():
                if line.startswith(day_text):
                    current_day = day_code
                    break
            
            # テスト期間の指示を検出
            if current_day and 'テストなので時間割の変更をしないでください' in line:
                # 時限を抽出（例：１・２・３校時）
                period_match = re.findall(r'(\d+)[・,、]?(\d+)?[・,、]?(\d+)?校?時', line)
                if period_match:
                    periods = []
                    for match in period_match:
                        for p in match:
                            if p:
                                periods.append(int(p))
                    
                    if periods:
                        test_periods.append((current_day, periods))
                        logger.info(f"テスト期間を検出: {current_day}曜日 {periods}時限")
        
        return test_periods
    
    def load_input_csv(self) -> Dict[str, Dict[str, str]]:
        """input.csvを読み込む"""
        timetable = {}
        
        if not self.input_path.exists():
            logger.warning(f"input.csv not found: {self.input_path}")
            return timetable
        
        with open(self.input_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                time_key = f"{row['曜日']}{row['時限']}"
                if time_key not in timetable:
                    timetable[time_key] = {}
                
                # 各クラスの情報を読み込む
                for class_name in self.classes:
                    if class_name in row:
                        timetable[time_key][class_name] = row[class_name]
        
        return timetable
    
    def protect_test_periods(self, timetable: Dict[str, Dict[str, str]], 
                           test_periods: List[Tuple[str, List[int]]]) -> Dict[str, Dict[str, str]]:
        """テスト期間に「テスト」を設定"""
        for day, periods in test_periods:
            for period in periods:
                time_key = f"{day}{period}"
                
                if time_key not in timetable:
                    timetable[time_key] = {}
                
                # 5組以外の全クラスに「テスト」を設定
                for class_name in self.classes:
                    if '5' not in class_name:  # 5組は除外
                        timetable[time_key][class_name] = 'テスト'
                        logger.debug(f"{time_key} {class_name} に「テスト」を設定")
        
        return timetable
    
    def save_protected_timetable(self, timetable: Dict[str, Dict[str, str]]):
        """保護された時間割を保存"""
        # ヘッダー行の作成
        headers = ['曜日', '時限'] + self.classes
        
        # データ行の作成
        rows = []
        for day in ['月', '火', '水', '木', '金']:
            for period in range(1, 7):
                time_key = f"{day}{period}"
                row = {'曜日': day, '時限': str(period)}
                
                if time_key in timetable:
                    for class_name in self.classes:
                        row[class_name] = timetable[time_key].get(class_name, '')
                else:
                    for class_name in self.classes:
                        row[class_name] = ''
                
                rows.append(row)
        
        # CSVに書き込み
        with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        
        logger.info(f"テスト期間を保護した時間割を保存: {self.output_path}")
    
    def run(self):
        """メイン処理"""
        logger.info("テスト期間保護処理を開始します")
        
        # 1. Follow-up.csvからテスト期間を抽出
        test_periods = self.parse_test_periods()
        if not test_periods:
            logger.warning("テスト期間の指示が見つかりませんでした")
            return
        
        # 2. input.csvを読み込む
        timetable = self.load_input_csv()
        
        # 3. テスト期間を保護
        protected_timetable = self.protect_test_periods(timetable, test_periods)
        
        # 4. 保護された時間割を保存
        self.save_protected_timetable(protected_timetable)
        
        logger.info("テスト期間保護処理が完了しました")
        logger.info(f"時間割生成時は {self.output_path} を使用してください")


def main():
    """メインエントリーポイント"""
    import sys
    
    # データディレクトリの指定（オプション）
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    
    protector = TestPeriodProtector(data_dir)
    protector.run()


if __name__ == "__main__":
    main()
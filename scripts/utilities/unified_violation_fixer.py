#!/usr/bin/env python3
"""統一違反修正スクリプト - 全バージョンの最良の機能を統合"""
import csv
import logging
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path
import sys

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.domain.value_objects.time_slot import TimeSlot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class UnifiedViolationFixer:
    """全ての違反修正機能を統合した統一修正クラス"""
    
    def __init__(self):
        """初期化"""
        # 交流学級のマッピング
        self.exchange_mappings = {
            "1-6": ("1-1", ["数", "英"]),
            "1-7": ("1-2", ["数", "英"]),
            "2-6": ("2-3", ["数", "英"]),
            "2-7": ("2-2", ["数", "英"]),
            "3-6": ("3-3", ["数", "英"]),
            "3-7": ("3-2", ["数", "英"]),
        }
        
        # 体育館使用可能な教科
        self.gym_subjects = {"保"}
        
        # 5組クラス
        self.grade5_classes = ["1-5", "2-5", "3-5"]
        
        # 交流学級一覧
        self.exchange_classes = set(self.exchange_mappings.keys())
        
        # 自立活動関連教科
        self.jiritsu_subjects = {"自立", "日生", "生単", "作業"}
        
        # 曜日と時限の定義
        self.days = ["月", "火", "水", "木", "金"]
        self.periods = list(range(1, 7))
        
    def fix_all_violations(self, input_file: str, output_file: str) -> int:
        """全ての違反を修正"""
        logger.info(f"違反修正を開始: {input_file} → {output_file}")
        
        # データ読み込み
        timetable = self._load_timetable(input_file)
        
        # 各種違反を優先順位順に修正
        total_fixes = 0
        
        # 1. 交流学級の同期を修正
        fixes = self._fix_exchange_class_sync(timetable)
        logger.info(f"交流学級同期修正: {fixes}件")
        total_fixes += fixes
        
        # 2. 自立活動制約を修正
        fixes = self._fix_jiritsu_constraints(timetable)
        logger.info(f"自立活動制約修正: {fixes}件")
        total_fixes += fixes
        
        # 3. 体育館使用の競合を修正
        fixes = self._fix_gym_conflicts(timetable)
        logger.info(f"体育館競合修正: {fixes}件")
        total_fixes += fixes
        
        # 4. 日内重複を修正
        fixes = self._fix_daily_duplicates(timetable)
        logger.info(f"日内重複修正: {fixes}件")
        total_fixes += fixes
        
        # 5. 5組の同期を確認
        fixes = self._ensure_grade5_sync(timetable)
        logger.info(f"5組同期修正: {fixes}件")
        total_fixes += fixes
        
        # 6. 空きコマを埋める
        fixes = self._fill_empty_slots(timetable)
        logger.info(f"空きコマ埋め: {fixes}件")
        total_fixes += fixes
        
        # 結果を保存
        self._save_timetable(timetable, output_file)
        
        # 最終検証
        remaining_violations = self._validate_all_constraints(timetable)
        if remaining_violations > 0:
            logger.warning(f"修正後も{remaining_violations}件の違反が残っています")
        else:
            logger.info("全ての違反が修正されました")
        
        logger.info(f"修正完了: 合計{total_fixes}件の修正を実行")
        return total_fixes
    
    def _load_timetable(self, filename: str) -> Dict[Tuple[str, int, str], str]:
        """時間割を読み込む"""
        timetable = {}
        
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            class_names = header[1:]
            
            for row in reader:
                parts = row[0].split()
                if len(parts) == 2:
                    day, period = parts[0], int(parts[1])
                    for i, subject in enumerate(row[1:]):
                        if i < len(class_names):
                            class_name = class_names[i]
                            timetable[(day, period, class_name)] = subject.strip()
        
        return timetable
    
    def _save_timetable(self, timetable: Dict[Tuple[str, int, str], str], filename: str):
        """時間割を保存"""
        # クラス名を抽出してソート
        class_names = sorted(set(key[2] for key in timetable.keys()), 
                           key=lambda x: (int(x.split('-')[0]), int(x.split('-')[1])))
        
        with open(filename, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow(['時限'] + class_names)
            
            # 各時限のデータ
            for day in self.days:
                for period in self.periods:
                    row = [f"{day} {period}"]
                    for class_name in class_names:
                        subject = timetable.get((day, period, class_name), "")
                        row.append(subject)
                    writer.writerow(row)
    
    def _fix_exchange_class_sync(self, timetable: Dict) -> int:
        """交流学級の同期を修正"""
        fixes = 0
        
        for day in self.days:
            for period in self.periods:
                for exchange_class, (parent_class, _) in self.exchange_mappings.items():
                    exchange_key = (day, period, exchange_class)
                    parent_key = (day, period, parent_class)
                    
                    exchange_subject = timetable.get(exchange_key, "")
                    parent_subject = timetable.get(parent_key, "")
                    
                    # 自立活動以外の教科で不一致の場合
                    if (exchange_subject not in self.jiritsu_subjects and 
                        parent_subject not in self.jiritsu_subjects and
                        exchange_subject != parent_subject and
                        exchange_subject != "" and parent_subject != ""):
                        
                        # 親学級に合わせる
                        timetable[exchange_key] = parent_subject
                        fixes += 1
                        logger.debug(f"交流学級同期修正: {day}{period}限 {exchange_class} → {parent_subject}")
        
        return fixes
    
    def _fix_jiritsu_constraints(self, timetable: Dict) -> int:
        """自立活動制約を修正"""
        fixes = 0
        
        for day in self.days:
            for period in self.periods:
                # 各交流学級をチェック
                for exchange_class, (parent_class, required_subjects) in self.exchange_mappings.items():
                    exchange_key = (day, period, exchange_class)
                    parent_key = (day, period, parent_class)
                    
                    exchange_subject = timetable.get(exchange_key, "")
                    parent_subject = timetable.get(parent_key, "")
                    
                    # 交流学級が自立活動の場合
                    if exchange_subject in self.jiritsu_subjects:
                        # 親学級が数学または英語でない場合
                        if parent_subject not in required_subjects:
                            # 同じ日の他の時限から数学または英語を探して交換
                            for other_period in self.periods:
                                if other_period != period:
                                    other_key = (day, other_period, parent_class)
                                    other_subject = timetable.get(other_key, "")
                                    
                                    if other_subject in required_subjects:
                                        # 交換実行
                                        timetable[parent_key] = other_subject
                                        timetable[other_key] = parent_subject
                                        fixes += 1
                                        logger.debug(f"自立制約修正: {parent_class} {day}{period}限↔{other_period}限")
                                        break
        
        return fixes
    
    def _fix_gym_conflicts(self, timetable: Dict) -> int:
        """体育館使用の競合を修正"""
        fixes = 0
        
        for day in self.days:
            for period in self.periods:
                # その時限の体育授業をカウント
                gym_classes = []
                for class_name in set(key[2] for key in timetable.keys()):
                    subject = timetable.get((day, period, class_name), "")
                    if subject in self.gym_subjects:
                        gym_classes.append(class_name)
                
                # 2つ以上の体育授業がある場合
                if len(gym_classes) > 1:
                    # 最初の1つを残して、他は別の時限に移動
                    for class_name in gym_classes[1:]:
                        # 空いている時限を探す
                        moved = False
                        for other_day in self.days:
                            for other_period in self.periods:
                                if self._can_place_gym(timetable, other_day, other_period):
                                    # 現在の体育授業と交換
                                    current_key = (day, period, class_name)
                                    other_key = (other_day, other_period, class_name)
                                    
                                    timetable[other_key] = timetable[current_key]
                                    timetable[current_key] = timetable.get(other_key, "")
                                    
                                    fixes += 1
                                    moved = True
                                    logger.debug(f"体育競合修正: {class_name} {day}{period}限→{other_day}{other_period}限")
                                    break
                            if moved:
                                break
        
        return fixes
    
    def _fix_daily_duplicates(self, timetable: Dict) -> int:
        """日内重複を修正"""
        fixes = 0
        
        for class_name in set(key[2] for key in timetable.keys()):
            for day in self.days:
                # その日の教科をカウント
                daily_subjects = {}
                for period in self.periods:
                    subject = timetable.get((day, period, class_name), "")
                    if subject and subject not in ["", "欠", "YT", "行", "道", "総", "学活"]:
                        if subject not in daily_subjects:
                            daily_subjects[subject] = []
                        daily_subjects[subject].append(period)
                
                # 重複がある教科を修正
                for subject, periods in daily_subjects.items():
                    if len(periods) > 1:
                        # 最初の1つを残して他を変更
                        for period in periods[1:]:
                            # 他の日から不足している教科を探す
                            replacement = self._find_replacement_subject(timetable, class_name, day, subject)
                            if replacement:
                                timetable[(day, period, class_name)] = replacement
                                fixes += 1
                                logger.debug(f"日内重複修正: {class_name} {day}{period}限 {subject}→{replacement}")
        
        return fixes
    
    def _ensure_grade5_sync(self, timetable: Dict) -> int:
        """5組の同期を確保"""
        fixes = 0
        
        for day in self.days:
            for period in self.periods:
                # 5組の教科を取得
                subjects = []
                for grade5_class in self.grade5_classes:
                    subject = timetable.get((day, period, grade5_class), "")
                    subjects.append((grade5_class, subject))
                
                # 最も多い教科を特定
                subject_counts = {}
                for _, subject in subjects:
                    if subject:
                        subject_counts[subject] = subject_counts.get(subject, 0) + 1
                
                if subject_counts:
                    most_common = max(subject_counts.items(), key=lambda x: x[1])[0]
                    
                    # 全ての5組を最も多い教科に統一
                    for grade5_class, subject in subjects:
                        if subject != most_common:
                            timetable[(day, period, grade5_class)] = most_common
                            fixes += 1
                            logger.debug(f"5組同期修正: {grade5_class} {day}{period}限 → {most_common}")
        
        return fixes
    
    def _fill_empty_slots(self, timetable: Dict) -> int:
        """空きコマを埋める"""
        fixes = 0
        
        # 各クラスの不足教科を計算
        for class_name in set(key[2] for key in timetable.keys()):
            # 現在の教科カウント
            subject_counts = {}
            empty_slots = []
            
            for day in self.days:
                for period in self.periods:
                    subject = timetable.get((day, period, class_name), "")
                    if subject == "":
                        empty_slots.append((day, period))
                    elif subject not in ["欠", "YT", "行"]:
                        subject_counts[subject] = subject_counts.get(subject, 0) + 1
            
            # 必要時数（簡易版）
            required_hours = {
                "国": 4, "社": 3, "数": 4, "理": 3, "英": 4,
                "音": 1, "美": 1, "技": 1, "家": 1, "保": 3,
                "道": 1, "総": 2, "学活": 1
            }
            
            # 不足教科を空きコマに配置
            for day, period in empty_slots:
                # 最も不足している教科を選択
                most_needed = None
                max_shortage = 0
                
                for subject, required in required_hours.items():
                    current = subject_counts.get(subject, 0)
                    shortage = required - current
                    if shortage > max_shortage:
                        most_needed = subject
                        max_shortage = shortage
                
                if most_needed:
                    timetable[(day, period, class_name)] = most_needed
                    subject_counts[most_needed] = subject_counts.get(most_needed, 0) + 1
                    fixes += 1
                    logger.debug(f"空きコマ埋め: {class_name} {day}{period}限 → {most_needed}")
        
        return fixes
    
    def _can_place_gym(self, timetable: Dict, day: str, period: int) -> bool:
        """指定時限に体育を配置可能か確認"""
        for class_name in set(key[2] for key in timetable.keys()):
            subject = timetable.get((day, period, class_name), "")
            if subject in self.gym_subjects:
                return False
        return True
    
    def _find_replacement_subject(self, timetable: Dict, class_name: str, 
                                 day: str, duplicate_subject: str) -> Optional[str]:
        """重複教科の代替を探す"""
        # 週全体の教科カウント
        weekly_counts = {}
        for d in self.days:
            for p in self.periods:
                subject = timetable.get((d, p, class_name), "")
                if subject and subject not in ["", "欠", "YT", "行"]:
                    weekly_counts[subject] = weekly_counts.get(subject, 0) + 1
        
        # 不足している教科を返す
        required_subjects = ["国", "社", "数", "理", "英", "音", "美", "技", "家", "保"]
        for subject in required_subjects:
            if weekly_counts.get(subject, 0) < 1 and subject != duplicate_subject:
                return subject
        
        return None
    
    def _validate_all_constraints(self, timetable: Dict) -> int:
        """全ての制約を検証"""
        violations = 0
        
        # 交流学級同期チェック
        for day in self.days:
            for period in self.periods:
                for exchange_class, (parent_class, _) in self.exchange_mappings.items():
                    exchange_subject = timetable.get((day, period, exchange_class), "")
                    parent_subject = timetable.get((day, period, parent_class), "")
                    
                    if (exchange_subject not in self.jiritsu_subjects and 
                        parent_subject not in self.jiritsu_subjects and
                        exchange_subject != parent_subject and
                        exchange_subject != "" and parent_subject != ""):
                        violations += 1
        
        # 自立活動制約チェック
        for day in self.days:
            for period in self.periods:
                for exchange_class, (parent_class, required_subjects) in self.exchange_mappings.items():
                    exchange_subject = timetable.get((day, period, exchange_class), "")
                    parent_subject = timetable.get((day, period, parent_class), "")
                    
                    if exchange_subject in self.jiritsu_subjects and parent_subject not in required_subjects:
                        violations += 1
        
        return violations


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='統一違反修正スクリプト')
    parser.add_argument('input_file', help='入力CSVファイル')
    parser.add_argument('output_file', help='出力CSVファイル')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細ログを表示')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    fixer = UnifiedViolationFixer()
    total_fixes = fixer.fix_all_violations(args.input_file, args.output_file)
    
    print(f"修正完了: {total_fixes}件の修正を実行しました")
    print(f"結果は {args.output_file} に保存されました")


if __name__ == '__main__':
    main()
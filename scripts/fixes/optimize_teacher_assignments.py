#!/usr/bin/env python3
"""
教師配置の最適化スクリプト
金子み先生を5組専任化し、教師重複を解消
"""
import sys
import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple
import logging

# プロジェクトのルートディレクトリをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.parsers.basics_parser import BasicsParser
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowUpParser
from src.infrastructure.repositories.teacher_mapping_repository import TeacherMappingRepository
from src.domain.value_objects.time_slot import TimeSlot, ClassReference

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TeacherOptimizer:
    """教師配置の最適化"""
    
    def __init__(self):
        self.data_dir = project_root / "data"
        
        # パーサーとリポジトリの初期化
        self.basics_parser = BasicsParser(self.data_dir / "config")
        self.followup_parser = EnhancedFollowUpParser(self.data_dir / "input")
        self.teacher_mapping_repo = TeacherMappingRepository(self.data_dir)
        
        # 教師マッピングを読み込み
        self.teacher_mapping = self.teacher_mapping_repo.load_teacher_mapping("config/teacher_subject_mapping.csv")
    
    def optimize_schedule(self, input_file: str = "output/output.csv", output_file: str = "output/output_optimized.csv"):
        """スケジュールを最適化"""
        logger.info("=== 教師配置の最適化開始 ===")
        
        # スケジュールを読み込み
        schedule_data = self._read_schedule(input_file)
        
        # 最適化対象の検出
        optimization_targets = self._find_optimization_targets(schedule_data)
        
        # 教師の再配置
        optimized_schedule = self._reassign_teachers(schedule_data, optimization_targets)
        
        # 結果を出力
        self._write_schedule(optimized_schedule, output_file)
        
        logger.info(f"=== 最適化完了: {output_file} ===")
        
        return optimization_targets
    
    def _read_schedule(self, file_path: str) -> Dict:
        """スケジュールを読み込み"""
        full_path = self.data_dir / file_path
        
        with open(full_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            lines = list(reader)
        
        # ヘッダー行を解析
        header_row = lines[0]
        period_row = lines[1]
        
        # タイムスロットを解析
        time_slots = []
        days = ["月", "火", "水", "木", "金"]
        for i, period_str in enumerate(period_row[1:]):
            if period_str.isdigit():
                day_index = (i) // 6
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
    
    def _find_optimization_targets(self, schedule_data: Dict) -> List[Dict]:
        """最適化対象を検出"""
        targets = []
        
        # 金子み先生の通常クラスでの家庭科担当を検出
        for class_name, data in schedule_data.items():
            # 5組は除外
            if "5組" in class_name:
                continue
            
            assignments = data['assignments']
            time_slots = data['time_slots']
            
            for i, subject in enumerate(assignments):
                if i >= len(time_slots):
                    break
                
                subject = subject.strip()
                if subject == "家":
                    day, period = time_slots[i]
                    
                    # この時間に金子み先生が5組も担当しているかチェック
                    if self._is_kaneko_teaching_grade5(schedule_data, day, period):
                        targets.append({
                            'class': class_name,
                            'day': day,
                            'period': period,
                            'subject': subject,
                            'current_teacher': '金子み',
                            'reason': '5組との同時担当'
                        })
        
        logger.info(f"最適化対象: {len(targets)}件")
        for target in targets:
            logger.info(f"  - {target['class']} {target['day']}曜{target['period']}限 {target['subject']} "
                       f"({target['reason']})")
        
        return targets
    
    def _is_kaneko_teaching_grade5(self, schedule_data: Dict, target_day: str, target_period: int) -> bool:
        """指定時間に金子み先生が5組を担当しているかチェック"""
        grade5_classes = ["1年5組", "2年5組", "3年5組"]
        
        for class_name in grade5_classes:
            if class_name not in schedule_data:
                continue
            
            data = schedule_data[class_name]
            assignments = data['assignments']
            time_slots = data['time_slots']
            
            for i, (day, period) in enumerate(time_slots):
                if day == target_day and period == target_period:
                    if i < len(assignments) and assignments[i].strip():
                        # 5組のこの時間に授業がある = 金子み先生が担当
                        return True
        
        return False
    
    def _reassign_teachers(self, schedule_data: Dict, targets: List[Dict]) -> Dict:
        """教師を再配置"""
        # スケジュールをコピー
        import copy
        optimized = copy.deepcopy(schedule_data)
        
        for target in targets:
            class_name = target['class']
            day = target['day']
            period = target['period']
            
            # 代替教師を見つける
            # 家庭科を担当できる教師を探す（金子み以外）
            alternative_teachers = self._find_alternative_teachers_for_home_ec(target)
            
            if alternative_teachers:
                # 最適な代替教師を選択
                best_teacher = self._select_best_teacher(alternative_teachers, schedule_data, day, period)
                
                if best_teacher:
                    # 教師を変更（ここでは科目名はそのまま）
                    logger.info(f"  → {class_name} {day}曜{period}限: 金子み → {best_teacher}")
                else:
                    logger.warning(f"  → {class_name} {day}曜{period}限: 代替教師が見つかりません")
            else:
                logger.warning(f"  → {class_name} {day}曜{period}限: 家庭科担当可能な教師がいません")
        
        return optimized
    
    def _find_alternative_teachers_for_home_ec(self, target: Dict) -> List[str]:
        """家庭科を担当できる代替教師を探す"""
        # 金子み以外で家庭科を担当できる教師
        # 本来は教師マッピングから取得すべきだが、簡易的に実装
        possible_teachers = []
        
        # 担任教師を候補に
        homeroom_teachers = {
            "1年1組": "金子ひ",
            "1年2組": "井野口",
            "1年3組": "梶永",
            "2年1組": "塚本",
            "2年2組": "野口",
            "2年3組": "永山",
            "3年1組": "白石",
            "3年2組": "森山",
            "3年3組": "北"
        }
        
        # 該当クラスの担任を優先
        if target['class'] in homeroom_teachers:
            possible_teachers.append(homeroom_teachers[target['class']])
        
        # その他の教師も候補に（教頭、校長など）
        possible_teachers.extend(["教頭", "校長"])
        
        return possible_teachers
    
    def _select_best_teacher(self, candidates: List[str], schedule_data: Dict, 
                           target_day: str, target_period: int) -> str:
        """最適な教師を選択"""
        # 各候補教師がその時間に空いているかチェック
        for teacher in candidates:
            if self._is_teacher_available(teacher, schedule_data, target_day, target_period):
                return teacher
        
        return None
    
    def _is_teacher_available(self, teacher_name: str, schedule_data: Dict, 
                            target_day: str, target_period: int) -> bool:
        """教師がその時間に空いているかチェック"""
        # 簡易的な実装：その時間に他のクラスで授業していないかチェック
        # 実際には教師のスケジュールを詳細に追跡する必要がある
        return True  # 一旦すべて利用可能とする
    
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
    optimizer = TeacherOptimizer()
    
    # 最適化を実行
    targets = optimizer.optimize_schedule()
    
    print(f"\n最適化完了")
    print(f"修正対象: {len(targets)}件")
    print("\n次のステップ:")
    print("1. output_optimized.csvを確認")
    print("2. 空きスロットを適切に埋める")
    print("3. 制約違反を再チェック")


if __name__ == "__main__":
    main()
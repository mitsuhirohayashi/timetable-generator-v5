#!/usr/bin/env python3
"""テスト期間保護の改善版修正スクリプト

HybridScheduleGeneratorV6/V7の配置ロジックに
テスト期間チェックを追加し、テスト期間中の授業変更を防ぐ
"""

import logging
from pathlib import Path
import shutil
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_test_period_check_to_generator():
    """ジェネレーターにテスト期間チェックを追加"""
    
    # バックアップ作成
    backup_dir = Path("src/domain/services/ultrathink/backup")
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # V6とV7の修正
    generators = [
        "hybrid_schedule_generator_v6.py",
        "hybrid_schedule_generator_v7.py"
    ]
    
    for generator_file in generators:
        file_path = Path(f"src/domain/services/ultrathink/{generator_file}")
        if not file_path.exists():
            logger.warning(f"{generator_file}が見つかりません")
            continue
            
        # バックアップ
        backup_path = backup_dir / f"{generator_file}.backup_{timestamp}"
        shutil.copy2(file_path, backup_path)
        logger.info(f"バックアップ作成: {backup_path}")
        
        # ファイル読み込み
        content = file_path.read_text(encoding='utf-8')
        
        # schedule.assignの前にテスト期間チェックを追加
        # パターン1: 通常のassign
        old_pattern1 = """                try:
                    schedule.assign(time_slot, assignment)"""
        
        new_pattern1 = """                try:
                    # テスト期間チェック
                    if self.test_period_protector.is_test_period(time_slot):
                        continue  # テスト期間はスキップ
                    schedule.assign(time_slot, assignment)"""
        
        # パターン2: 新規配置時のチェック
        old_pattern2 = """            if not schedule.get_assignment(time_slot, class_ref):"""
        
        new_pattern2 = """            if not schedule.get_assignment(time_slot, class_ref):
                # テスト期間チェック
                if self.test_period_protector.is_test_period(time_slot):
                    continue  # テスト期間はスキップ"""
        
        # パターン3: 配置可能性チェック
        old_pattern3 = """                if not self._is_slot_available(schedule, time_slot, class_ref):
                    continue"""
        
        new_pattern3 = """                # テスト期間チェック
                if self.test_period_protector.is_test_period(time_slot):
                    continue  # テスト期間はスキップ
                    
                if not self._is_slot_available(schedule, time_slot, class_ref):
                    continue"""
        
        # 置換実行
        modified = False
        
        # より具体的な置換を実行
        # FlexibleStandardHoursGuaranteeSystemのguarantee_flexible_hours内での配置をスキップ
        if "_guarantee_hours_with_learning" in content:
            # この関数の中で配置処理があれば、その前にテスト期間チェックを追加
            lines = content.split('\n')
            new_lines = []
            in_guarantee_hours = False
            indent_level = 0
            
            for i, line in enumerate(lines):
                # 関数の開始を検出
                if "_guarantee_hours_with_learning" in line and "def " in line:
                    in_guarantee_hours = True
                    indent_level = len(line) - len(line.lstrip())
                
                # 関数の終了を検出
                if in_guarantee_hours and line.strip() and not line.startswith(' '):
                    in_guarantee_hours = False
                
                # schedule.assignの前にチェックを追加
                if in_guarantee_hours and "schedule.assign(" in line and "test_period" not in lines[i-1]:
                    # インデントを合わせる
                    current_indent = len(line) - len(line.lstrip())
                    check_line = " " * current_indent + "# テスト期間チェック"
                    skip_line = " " * current_indent + "if self.test_period_protector.is_test_period(time_slot):"
                    continue_line = " " * (current_indent + 4) + "continue  # テスト期間はスキップ"
                    
                    new_lines.extend([check_line, skip_line, continue_line])
                    modified = True
                
                new_lines.append(line)
            
            if modified:
                content = '\n'.join(new_lines)
        
        # _is_slot_availableメソッドを追加（存在しない場合）
        if "_is_slot_available" not in content and "class HybridScheduleGeneratorV" in content:
            # クラスの最後に追加
            insert_pos = content.rfind("\n\n") # 最後の空行の前
            if insert_pos > 0:
                new_method = '''
    def _is_slot_available(self, schedule: Schedule, time_slot: TimeSlot, class_ref: ClassReference) -> bool:
        """スロットが利用可能かチェック（テスト期間を含む）"""
        # テスト期間チェック
        if self.test_period_protector.is_test_period(time_slot):
            return False
        
        # 既存の割り当てチェック
        return schedule.get_assignment(time_slot, class_ref) is None
'''
                content = content[:insert_pos] + new_method + content[insert_pos:]
                modified = True
        
        if modified:
            # ファイル書き込み
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"{generator_file}を修正しました")
        else:
            logger.info(f"{generator_file}は既に修正済みか、修正箇所が見つかりませんでした")

def add_early_test_period_loading():
    """テスト期間の早期読み込みを追加"""
    
    file_path = Path("src/domain/services/ultrathink/hybrid_schedule_generator_v6.py")
    if not file_path.exists():
        logger.error("hybrid_schedule_generator_v6.pyが見つかりません")
        return
    
    content = file_path.read_text(encoding='utf-8')
    
    # generateメソッドの最初の方でテスト期間を読み込むように修正
    old_init_schedule = """        # 初期スケジュールの準備
        if initial_schedule:
            schedule = self._copy_schedule(initial_schedule)
        else:
            schedule = Schedule()"""
    
    new_init_schedule = """        # 初期スケジュールの準備とテスト期間の読み込み
        if initial_schedule:
            schedule = self._copy_schedule(initial_schedule)
            # テスト期間の割り当てを早期に保存
            self.test_period_protector.load_initial_schedule(initial_schedule)
        else:
            schedule = Schedule()
            # 空のスケジュールでも初期データがあれば読み込む
            if followup_data and hasattr(self, '_load_initial_from_csv'):
                initial_from_csv = self._load_initial_from_csv()
                if initial_from_csv:
                    self.test_period_protector.load_initial_schedule(initial_from_csv)"""
    
    if old_init_schedule in content:
        content = content.replace(old_init_schedule, new_init_schedule)
        file_path.write_text(content, encoding='utf-8')
        logger.info("早期テスト期間読み込みを追加しました")

def main():
    logger.info("=== テスト期間保護の改善 ===")
    
    # 1. ジェネレーターにテスト期間チェックを追加
    add_test_period_check_to_generator()
    
    # 2. 早期テスト期間読み込みを追加
    add_early_test_period_loading()
    
    logger.info("\n修正が完了しました。")
    logger.info("次のステップ:")
    logger.info("1. python3 main.py generate を実行して新しい時間割を生成")
    logger.info("2. python3 analyze_test_period_issue.py を実行して改善を確認")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""テスト期間保護の直接的な修正

Scheduleクラスのassignメソッドにテスト期間チェックを追加する
最もシンプルで確実な方法
"""

import logging
from pathlib import Path
import shutil
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_schedule_assign_method():
    """Schedule.assignメソッドにテスト期間チェックを追加"""
    
    schedule_file = Path("src/domain/entities/schedule.py")
    if not schedule_file.exists():
        logger.error("schedule.pyが見つかりません")
        return False
        
    # バックアップ作成
    backup_dir = Path("src/domain/entities/backup")
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"schedule.py.backup_{timestamp}"
    shutil.copy2(schedule_file, backup_path)
    logger.info(f"バックアップ作成: {backup_path}")
    
    # ファイル読み込み
    content = schedule_file.read_text(encoding='utf-8')
    
    # assignメソッドを見つけて修正
    lines = content.split('\n')
    new_lines = []
    in_assign_method = False
    method_indent = 0
    modified = False
    
    for i, line in enumerate(lines):
        # assignメソッドの開始を検出
        if "def assign(" in line and "self" in line:
            in_assign_method = True
            method_indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            
            # 次の行がdocstringの場合はそれも追加
            if i + 1 < len(lines) and '"""' in lines[i + 1]:
                j = i + 1
                while j < len(lines) and not (j > i + 1 and '"""' in lines[j]):
                    new_lines.append(lines[j])
                    j += 1
                if j < len(lines):
                    new_lines.append(lines[j])
                    i = j
                
                # テスト期間チェックを追加
                indent = " " * (method_indent + 4)
                new_lines.extend([
                    f"{indent}# テスト期間チェック",
                    f"{indent}if hasattr(self, '_test_periods') and (time_slot.day, time_slot.period) in self._test_periods:",
                    f"{indent}    # テスト期間中は新しい割り当てを拒否",
                    f"{indent}    existing = self.get_assignment(time_slot, assignment.class_ref)",
                    f"{indent}    if existing:",
                    f"{indent}        # 既存の割り当てがある場合は変更を拒否",
                    f"{indent}        return",
                    f"{indent}    # 既存の割り当てがない場合も、テスト期間なので新規配置を拒否",
                    f"{indent}    return",
                    ""
                ])
                modified = True
                
                # 元のメソッドの残りの行をスキップ位置を調整
                for k in range(i + 1, j + 1):
                    if k < len(lines):
                        lines[k] = None  # 処理済みマーク
            continue
            
        # 処理済みの行はスキップ
        if line is None:
            continue
            
        # メソッドの終了を検出
        if in_assign_method and line.strip() and not line.startswith(' ' * method_indent) and not line.startswith('\t'):
            in_assign_method = False
            
        new_lines.append(line)
    
    if modified:
        # ファイル書き込み
        new_content = '\n'.join(new_lines)
        schedule_file.write_text(new_content, encoding='utf-8')
        logger.info("Schedule.assignメソッドを修正しました")
        return True
    else:
        logger.warning("assignメソッドの修正箇所が見つかりませんでした")
        return False

def add_test_period_setter():
    """Scheduleクラスにテスト期間設定メソッドを追加"""
    
    schedule_file = Path("src/domain/entities/schedule.py")
    if not schedule_file.exists():
        return False
        
    content = schedule_file.read_text(encoding='utf-8')
    
    # set_test_periodsメソッドがない場合は追加
    if "set_test_periods" not in content:
        # クラスの最後に追加
        class_end = content.rfind("\n\n")
        if class_end > 0:
            new_method = '''
    def set_test_periods(self, test_periods: Set[Tuple[str, int]]):
        """テスト期間を設定"""
        self._test_periods = test_periods
        
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたタイムスロットがテスト期間かどうか"""
        if not hasattr(self, '_test_periods'):
            return False
        return (time_slot.day, time_slot.period) in self._test_periods
'''
            # インポートにSetとTupleを追加
            import_line_idx = content.find("from typing import")
            if import_line_idx >= 0:
                import_end = content.find("\n", import_line_idx)
                old_import = content[import_line_idx:import_end]
                if "Set" not in old_import:
                    new_import = old_import.rstrip() + ", Set, Tuple"
                    content = content[:import_line_idx] + new_import + content[import_end:]
            
            content = content[:class_end] + new_method + content[class_end:]
            schedule_file.write_text(content, encoding='utf-8')
            logger.info("set_test_periodsメソッドを追加しました")
            return True
    return False

def update_generator_to_set_test_periods():
    """ジェネレーターでテスト期間を設定するように修正"""
    
    generators = [
        "src/domain/services/ultrathink/hybrid_schedule_generator_v6.py",
        "src/domain/services/ultrathink/hybrid_schedule_generator_v7.py"
    ]
    
    for gen_path in generators:
        file_path = Path(gen_path)
        if not file_path.exists():
            continue
            
        content = file_path.read_text(encoding='utf-8')
        
        # generateメソッドの中でスケジュールにテスト期間を設定
        old_schedule_init = """        else:
            schedule = Schedule()"""
            
        new_schedule_init = """        else:
            schedule = Schedule()
        
        # テスト期間をスケジュールに設定
        if self.test_period_protector.test_periods:
            schedule.set_test_periods(self.test_period_protector.test_periods)"""
        
        if old_schedule_init in content:
            content = content.replace(old_schedule_init, new_schedule_init)
            
            # _copy_scheduleメソッドも修正してテスト期間をコピー
            if "_copy_schedule" in content:
                old_copy = """        new_schedule = Schedule()
        for time_slot, assignment in schedule.get_all_assignments():
            new_schedule.assign(time_slot, assignment)
        return new_schedule"""
                
                new_copy = """        new_schedule = Schedule()
        # テスト期間をコピー
        if hasattr(schedule, '_test_periods'):
            new_schedule.set_test_periods(schedule._test_periods)
        for time_slot, assignment in schedule.get_all_assignments():
            new_schedule.assign(time_slot, assignment)
        return new_schedule"""
                
                if old_copy in content:
                    content = content.replace(old_copy, new_copy)
            
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"{gen_path}を修正しました")

def main():
    logger.info("=== テスト期間保護の直接修正 ===")
    
    # 1. Schedule.assignメソッドの修正
    if not fix_schedule_assign_method():
        logger.error("Schedule.assignメソッドの修正に失敗しました")
        return
        
    # 2. テスト期間設定メソッドの追加
    add_test_period_setter()
    
    # 3. ジェネレーターでテスト期間を設定
    update_generator_to_set_test_periods()
    
    logger.info("\n修正が完了しました。")
    logger.info("この修正により、テスト期間中は一切の新規配置・変更ができなくなります。")
    logger.info("\n次のステップ:")
    logger.info("1. python3 main.py generate を実行して新しい時間割を生成")
    logger.info("2. python3 analyze_test_period_issue.py を実行して改善を確認")

if __name__ == "__main__":
    main()
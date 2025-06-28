#!/usr/bin/env python3
"""Scheduleクラスにテスト期間保護を追加する修正スクリプト"""

import logging
from pathlib import Path
import shutil
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_test_period_protection():
    """Schedule.assignメソッドにテスト期間保護を追加"""
    
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
    
    # assignメソッドを見つけて、その冒頭にテスト期間チェックを追加
    # 既存のis_lockedチェックの後に追加
    old_pattern = r'''    def assign\(self, time_slot: TimeSlot, assignment: Assignment\) -> None:
        """指定された時間枠にクラスの割り当てを設定"""
        if self\.is_locked\(time_slot, assignment\.class_ref\):
            raise InvalidAssignmentException\(f"セルがロックされています: \{time_slot\} - \{assignment\.class_ref\}"\)'''
    
    new_pattern = '''    def assign(self, time_slot: TimeSlot, assignment: Assignment) -> None:
        """指定された時間枠にクラスの割り当てを設定"""
        if self.is_locked(time_slot, assignment.class_ref):
            raise InvalidAssignmentException(f"セルがロックされています: {time_slot} - {assignment.class_ref}")
        
        # テスト期間保護チェック
        if self.is_test_period(time_slot):
            # テスト期間中は既存の割り当てを保護
            existing = self.get_assignment(time_slot, assignment.class_ref)
            if existing:
                # 既存の割り当てと同じ場合は許可（再設定）
                if (existing.subject.name == assignment.subject.name and
                    (not existing.teacher or not assignment.teacher or 
                     existing.teacher.name == assignment.teacher.name)):
                    # 同じ内容なので処理を続行
                    pass
                else:
                    # 異なる内容への変更は拒否
                    raise InvalidAssignmentException(
                        f"テスト期間中は変更できません: {time_slot} - {assignment.class_ref} "
                        f"(現在: {existing.subject.name}, 変更先: {assignment.subject.name})"
                    )'''
    
    # 正規表現で置換
    content_new = re.sub(old_pattern, new_pattern, content, flags=re.DOTALL)
    
    if content_new == content:
        logger.warning("assignメソッドの修正箇所が見つかりませんでした")
        return False
    
    # is_test_periodメソッドを追加（存在しない場合）
    if "def is_test_period" not in content_new:
        # get_all_assignmentsメソッドの後に追加
        insert_pattern = r'(    def get_all_assignments\(self\) -> List\[tuple\[TimeSlot, Assignment\]\]:.*?return result)'
        
        test_period_method = '''
    
    def is_test_period(self, time_slot: TimeSlot) -> bool:
        """指定されたタイムスロットがテスト期間かどうか"""
        if time_slot.day in self.test_periods:
            return time_slot.period in self.test_periods[time_slot.day]
        return False
    
    def set_test_periods(self, test_periods: Set[tuple[str, int]]) -> None:
        """テスト期間を設定"""
        self.test_periods.clear()
        for day, period in test_periods:
            if day not in self.test_periods:
                self.test_periods[day] = []
            self.test_periods[day].append(period)'''
        
        # 正規表現で挿入位置を見つけて追加
        content_new = re.sub(insert_pattern, r'\1' + test_period_method, content_new, flags=re.DOTALL)
    
    # インポートにSetを追加（必要な場合）
    if "from typing import" in content_new and ", Set" not in content_new:
        content_new = content_new.replace(
            "from typing import Dict, List, Optional",
            "from typing import Dict, List, Optional, Set"
        )
    
    # ファイル書き込み
    schedule_file.write_text(content_new, encoding='utf-8')
    logger.info("schedule.pyを修正しました")
    return True

def update_generators():
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
        modified = False
        
        # スケジュール作成直後にテスト期間を設定
        if "schedule = Schedule()" in content and "schedule.set_test_periods" not in content:
            # パターン1: else節でのSchedule作成
            old1 = """        else:
            schedule = Schedule()"""
            new1 = """        else:
            schedule = Schedule()
        
        # テスト期間をスケジュールに設定
        if self.test_period_protector.test_periods:
            schedule.set_test_periods(self.test_period_protector.test_periods)"""
            
            if old1 in content:
                content = content.replace(old1, new1)
                modified = True
            
            # パターン2: _copy_scheduleでのSchedule作成
            if "_copy_schedule" in content:
                old2 = """        new_schedule = Schedule()
        for time_slot, assignment in schedule.get_all_assignments():
            new_schedule.assign(time_slot, assignment)"""
                new2 = """        new_schedule = Schedule()
        # テスト期間をコピー
        if hasattr(schedule, 'test_periods') and schedule.test_periods:
            new_schedule.test_periods = schedule.test_periods.copy()
        for time_slot, assignment in schedule.get_all_assignments():
            new_schedule.assign(time_slot, assignment)"""
                
                if old2 in content:
                    content = content.replace(old2, new2)
                    modified = True
        
        if modified:
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"{gen_path}を修正しました")

def main():
    logger.info("=== Scheduleクラスへのテスト期間保護追加 ===")
    
    # 1. Schedule.assignメソッドの修正
    if not add_test_period_protection():
        logger.error("Schedule.assignメソッドの修正に失敗しました")
        return
    
    # 2. ジェネレーターでテスト期間を設定
    update_generators()
    
    logger.info("\n修正が完了しました。")
    logger.info("この修正により、テスト期間中の授業変更が防止されます。")
    logger.info("\n次のステップ:")
    logger.info("1. python3 main.py generate を実行して新しい時間割を生成")
    logger.info("2. python3 analyze_test_period_issue.py を実行して改善を確認")

if __name__ == "__main__":
    main()
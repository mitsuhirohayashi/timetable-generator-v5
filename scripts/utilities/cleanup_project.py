#!/usr/bin/env python3
"""プロジェクトのクリーンアップスクリプト

不要なファイル（バックアップ、未使用のアルゴリズム）を削除
"""
import os
import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent

# 削除対象のパターン
BACKUP_PATTERNS = [
    "*.backup*",
    "*.bak",
    "*_backup*",
    "*.temp",
    "*.tmp",
    "*.old",
    "*_old*"
]

# 削除対象の未使用アルゴリズムファイル
UNUSED_ALGORITHMS = [
    "src/domain/services/unified_schedule_generator.py",
    "src/domain/services/csp_schedule_generator.py",
    "src/domain/services/schedule_generator.py",
    "src/domain/services/advanced_schedule_generator.py",
    "src/domain/services/special_classes_schedule_generator.py",
    "src/domain/services/grade5_basic_schedule_generator.py",
    "src/domain/services/constraint_aware_scheduler.py",
    "src/domain/services/randomized_unified_schedule_generator.py",
    "src/domain/services/human_like_scheduler_v2.py",
    "src/domain/services/unified_schedule_generator_fixed.py",
    "src/domain/services/grade5_synchronizer.py",  # refactored版を使用
    "src/domain/services/empty_slot_filler.py",    # enhanced版を使用
]

# 削除対象の出力ファイル（最新のものを除く）
OUTPUT_FILES_TO_KEEP = [
    "output.csv"
]

# 削除対象のテンポラリファイル
TEMP_FILES = [
    "analyze_filled_timetable.py",
    "fix_filled_jiritsu.py"
]

def find_files_to_delete():
    """削除対象ファイルを検索"""
    files_to_delete = []
    
    # バックアップファイルを検索
    logger.info("バックアップファイルを検索中...")
    for pattern in BACKUP_PATTERNS:
        for file_path in PROJECT_ROOT.rglob(pattern):
            if file_path.is_file():
                files_to_delete.append(file_path)
    
    # 未使用アルゴリズムファイル
    logger.info("未使用アルゴリズムファイルを確認中...")
    for algo_file in UNUSED_ALGORITHMS:
        file_path = PROJECT_ROOT / algo_file
        if file_path.exists():
            files_to_delete.append(file_path)
    
    # 出力ファイルの整理
    logger.info("出力ファイルを整理中...")
    output_dir = PROJECT_ROOT / "data" / "output"
    if output_dir.exists():
        for file_path in output_dir.glob("*.csv"):
            if file_path.name not in OUTPUT_FILES_TO_KEEP:
                files_to_delete.append(file_path)
    
    # テンポラリファイル
    logger.info("テンポラリファイルを確認中...")
    for temp_file in TEMP_FILES:
        file_path = PROJECT_ROOT / temp_file
        if file_path.exists():
            files_to_delete.append(file_path)
    
    # 空のtempディレクトリ
    temp_dir = PROJECT_ROOT / "temp"
    if temp_dir.exists() and not any(temp_dir.iterdir()):
        files_to_delete.append(temp_dir)
    
    return sorted(set(files_to_delete))

def show_files_to_delete(files):
    """削除対象ファイルを表示"""
    logger.info(f"\n削除対象ファイル数: {len(files)}")
    
    # カテゴリ別に分類
    backups = []
    algorithms = []
    outputs = []
    others = []
    
    for file_path in files:
        if any(pattern.replace("*", "") in str(file_path) for pattern in BACKUP_PATTERNS):
            backups.append(file_path)
        elif "src/domain/services" in str(file_path):
            algorithms.append(file_path)
        elif "data/output" in str(file_path):
            outputs.append(file_path)
        else:
            others.append(file_path)
    
    if backups:
        logger.info(f"\nバックアップファイル ({len(backups)}件):")
        for f in backups[:10]:  # 最初の10件を表示
            logger.info(f"  - {f.relative_to(PROJECT_ROOT)}")
        if len(backups) > 10:
            logger.info(f"  ... 他 {len(backups) - 10}件")
    
    if algorithms:
        logger.info(f"\n未使用アルゴリズム ({len(algorithms)}件):")
        for f in algorithms:
            logger.info(f"  - {f.relative_to(PROJECT_ROOT)}")
    
    if outputs:
        logger.info(f"\n古い出力ファイル ({len(outputs)}件):")
        for f in outputs[:10]:  # 最初の10件を表示
            logger.info(f"  - {f.relative_to(PROJECT_ROOT)}")
        if len(outputs) > 10:
            logger.info(f"  ... 他 {len(outputs) - 10}件")
    
    if others:
        logger.info(f"\nその他 ({len(others)}件):")
        for f in others:
            logger.info(f"  - {f.relative_to(PROJECT_ROOT)}")

def delete_files(files):
    """ファイルを削除"""
    logger.info("\nファイルを削除中...")
    deleted_count = 0
    error_count = 0
    
    for file_path in files:
        try:
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()
            deleted_count += 1
        except Exception as e:
            logger.error(f"削除エラー: {file_path} - {e}")
            error_count += 1
    
    logger.info(f"削除完了: {deleted_count}件")
    if error_count > 0:
        logger.warning(f"エラー: {error_count}件")

def main():
    """メイン処理"""
    import sys
    
    # --forceオプションのチェック
    force_mode = "--force" in sys.argv
    
    logger.info("プロジェクトクリーンアップを開始します")
    
    # 削除対象ファイルを検索
    files_to_delete = find_files_to_delete()
    
    if not files_to_delete:
        logger.info("削除対象ファイルはありません")
        return
    
    # 削除対象を表示
    show_files_to_delete(files_to_delete)
    
    # 確認
    if force_mode:
        logger.info(f"\n--forceモードで{len(files_to_delete)}個のファイルを削除します")
    else:
        try:
            response = input(f"\n{len(files_to_delete)}個のファイルを削除しますか？ (yes/no): ")
            if response.lower() != "yes":
                logger.info("キャンセルしました")
                return
        except EOFError:
            logger.info("\n自動実行環境で確認できません。--forceオプションを使用してください")
            return
    
    # 削除実行
    delete_files(files_to_delete)
    
    logger.info("\nクリーンアップが完了しました")

if __name__ == "__main__":
    main()
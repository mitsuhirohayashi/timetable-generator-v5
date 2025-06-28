#!/usr/bin/env python3
"""テスト期間の問題を詳細分析"""

import logging
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.value_objects.time_slot import TimeSlot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# テスト期間の定義
TEST_PERIODS = {
    ("月", 1), ("月", 2), ("月", 3),
    ("火", 1), ("火", 2), ("火", 3),
    ("水", 1), ("水", 2)
}

def analyze_test_periods():
    """テスト期間の詳細分析"""
    # リポジトリ初期化
    schedule_repo = CSVScheduleRepository()
    school_repo = CSVSchoolRepository()
    
    # 学校データ読み込み
    school = school_repo.load_school_data("data/config/base_timetable.csv")
    
    # 元のスケジュールと生成されたスケジュールを読み込み
    original = schedule_repo.load("data/input/input.csv", school)
    generated = schedule_repo.load("data/output/output.csv", school)
    
    logger.info("=== テスト期間の分析 ===")
    
    # 変更をカウント
    total_changes = 0
    changes_by_period = {}
    
    for (day, period) in sorted(TEST_PERIODS):
        time_slot = TimeSlot(day, period)
        changes_by_period[(day, period)] = []
        
        logger.info(f"\n{day}曜{period}限:")
        
        for class_ref in school.get_all_classes():
            orig_assignment = original.get_assignment(time_slot, class_ref)
            gen_assignment = generated.get_assignment(time_slot, class_ref)
            
            if orig_assignment and gen_assignment:
                orig_subject = orig_assignment.subject.name if orig_assignment.subject else "空き"
                gen_subject = gen_assignment.subject.name if gen_assignment.subject else "空き"
                
                if orig_subject != gen_subject:
                    logger.warning(f"  {class_ref}: {orig_subject} → {gen_subject} ❌")
                    changes_by_period[(day, period)].append({
                        'class': str(class_ref),
                        'original': orig_subject,
                        'generated': gen_subject
                    })
                    total_changes += 1
                else:
                    # 同じ場合は最初の数個だけ表示
                    if len([c for c in school.get_all_classes() if str(c) == str(class_ref)]) <= 3:
                        logger.info(f"  {class_ref}: {orig_subject} ✓")
    
    # サマリー
    logger.info(f"\n=== サマリー ===")
    logger.info(f"総変更数: {total_changes}件")
    
    for (day, period), changes in changes_by_period.items():
        if changes:
            logger.info(f"{day}曜{period}限: {len(changes)}件の変更")
    
    # 特に多い変更パターンを分析
    logger.info(f"\n=== 変更パターン分析 ===")
    pattern_count = {}
    
    for period_changes in changes_by_period.values():
        for change in period_changes:
            pattern = f"{change['original']} → {change['generated']}"
            pattern_count[pattern] = pattern_count.get(pattern, 0) + 1
    
    for pattern, count in sorted(pattern_count.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"{pattern}: {count}件")
    
    return total_changes, changes_by_period

def check_generation_method():
    """どの生成方法が使われているか確認"""
    logger.info("\n=== 生成方法の確認 ===")
    
    # 最近のログファイルを確認
    import glob
    log_files = glob.glob("generate_log*.txt")
    if log_files:
        latest_log = max(log_files)
        logger.info(f"最新のログファイル: {latest_log}")
        
        with open(latest_log, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 使用されているアルゴリズムを検索
        if "Ultrathink" in content or "ultrathink" in content:
            logger.info("Ultrathinkアルゴリズムが使用されています")
        if "HybridScheduleGeneratorV7" in content:
            logger.info("HybridScheduleGeneratorV7が使用されています")
        if "テスト期間保護" in content:
            logger.info("テスト期間保護が言及されています")
            
        # テスト期間関連のログを抽出
        lines = content.split('\n')
        test_period_logs = [line for line in lines if "テスト期間" in line or "test_period" in line.lower()]
        
        if test_period_logs:
            logger.info("\nテスト期間関連のログ:")
            for log in test_period_logs[:10]:
                logger.info(f"  {log}")

def main():
    # テスト期間の分析
    total_changes, changes_by_period = analyze_test_periods()
    
    # 生成方法の確認
    check_generation_method()
    
    # 結論
    logger.info("\n=== 結論 ===")
    if total_changes > 0:
        logger.error(f"❌ テスト期間に{total_changes}件の不正な変更が発生しています")
        logger.info("原因: テスト期間保護機能が正しく動作していない可能性があります")
        logger.info("推奨対策:")
        logger.info("1. HybridScheduleGeneratorのテスト期間保護実装を確認")
        logger.info("2. 初期スケジュールの読み込みタイミングを修正")
        logger.info("3. テスト期間のスロットをスキップする処理を追加")
    else:
        logger.info("✅ テスト期間は正しく保護されています")

if __name__ == "__main__":
    main()
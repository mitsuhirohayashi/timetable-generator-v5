#!/usr/bin/env python3
"""
HybridScheduleGeneratorV5のテストスクリプト

柔軟な標準時数保証システムを統合した新しいハイブリッドジェネレーターのテスト
"""
import logging
import sys
from pathlib import Path

# パスの設定
sys.path.append(str(Path(__file__).parent))

from src.domain.services.ultrathink.hybrid_schedule_generator_v5 import HybridScheduleGeneratorV5
from src.infrastructure.repositories.csv_repository import CSVRepository
from src.infrastructure.parsers.enhanced_followup_parser import EnhancedFollowupParser

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """メイン関数"""
    logger.info("=== HybridScheduleGeneratorV5テスト開始 ===")
    
    # リポジトリの初期化
    repository = CSVRepository()
    
    # 学校データの読み込み
    logger.info("学校データを読み込み中...")
    school = repository.load_school()
    
    # 初期スケジュールの読み込み（あれば）
    try:
        initial_schedule = repository.load_schedule(school)
        logger.info("初期スケジュールを読み込みました")
    except:
        initial_schedule = None
        logger.info("初期スケジュールなしで開始します")
    
    # Follow-upデータの読み込み
    logger.info("Follow-upデータを読み込み中...")
    followup_parser = EnhancedFollowupParser()
    followup_path = Path("data/input/Follow-up.csv")
    
    if followup_path.exists():
        followup_data = followup_parser.parse(str(followup_path))
        logger.info(f"Follow-upデータを読み込みました: {len(followup_data)}日分")
        
        # 特別な日の表示
        for day, info in followup_data.items():
            if "テスト" in str(info) or "振休" in str(info) or "外勤" in str(info):
                logger.info(f"特別な日検出: {day}")
    else:
        followup_data = None
        logger.info("Follow-upデータが見つかりません")
    
    # ジェネレーターの初期化
    generator = HybridScheduleGeneratorV5(enable_logging=True)
    
    # スケジュール生成
    logger.info("\nスケジュール生成を開始します...")
    result = generator.generate(
        school=school,
        initial_schedule=initial_schedule,
        target_violations=0,
        time_limit=300,
        followup_data=followup_data
    )
    
    # 結果の表示
    logger.info("\n=== 生成結果サマリー ===")
    logger.info(f"総割り当て数: {result.statistics['total_assignments']}")
    logger.info(f"制約違反数: {result.violations}")
    logger.info(f"教師重複数: {result.teacher_conflicts}")
    logger.info(f"空きスロット数: {result.statistics['empty_slots']}")
    logger.info(f"柔軟な満足度: {result.statistics['flexible_satisfaction_rate']:.1f}%")
    logger.info(f"完全充足クラス数: {result.statistics['fully_satisfied_classes']}")
    logger.info(f"特別な状況: {result.statistics['special_circumstances']}件")
    logger.info(f"警告: {result.statistics['warnings_count']}件")
    
    # 科目別達成率の表示
    if 'subject_completion' in result.statistics:
        logger.info("\n=== 科目別達成率 ===")
        sorted_subjects = sorted(
            result.statistics['subject_completion'].items(),
            key=lambda x: x[1]['completion_rate'],
            reverse=True
        )
        for subject_name, data in sorted_subjects:
            logger.info(
                f"{subject_name}: {data['completion_rate']:.1f}% "
                f"({data['assigned']}/{data['standard']})"
            )
    
    # 改善点の表示
    if result.improvements:
        logger.info("\n=== 達成した改善 ===")
        for improvement in result.improvements:
            logger.info(f"✓ {improvement}")
    
    # 柔軟な時数結果の詳細表示
    if result.flexible_hours_results:
        logger.info("\n=== 柔軟な時数配分の詳細 ===")
        
        # 特別な状況の影響
        special_circumstances = result.flexible_hours_results.get('special_circumstances', [])
        if special_circumstances:
            logger.info("\n特別な状況の影響:")
            for circ in special_circumstances:
                logger.info(
                    f"  {circ['class']}: {circ['lost_slots']}コマ減少 "
                    f"(影響日数: {circ['affected_days']}日)"
                )
        
        # クラス別の満足度（低い順に表示）
        by_class = result.flexible_hours_results.get('by_class', {})
        if by_class:
            logger.info("\n満足度の低いクラス（上位5件）:")
            sorted_classes = sorted(
                by_class.items(),
                key=lambda x: x[1]['satisfaction_rate']
            )[:5]
            for class_name, class_data in sorted_classes:
                logger.info(
                    f"  {class_name}: 満足度 {class_data['satisfaction_rate']*100:.1f}% "
                    f"({class_data['used_slots']}/{class_data['total_slots']}スロット使用)"
                )
                
                # 不足している科目を表示
                subjects = class_data.get('subjects', {})
                shortage_subjects = [
                    (name, data) for name, data in subjects.items()
                    if data['satisfaction'] in ['不足', '最低限']
                ]
                if shortage_subjects:
                    logger.info(f"    不足科目:")
                    for subj_name, subj_data in shortage_subjects[:3]:
                        logger.info(
                            f"      {subj_name}: {subj_data['assigned']}/{subj_data['ideal']} "
                            f"({subj_data['satisfaction']})"
                        )
    
    # スケジュールの保存
    logger.info("\n生成されたスケジュールを保存中...")
    try:
        repository.save_schedule(result.schedule)
        logger.info("スケジュールを data/output/output.csv に保存しました")
    except Exception as e:
        logger.error(f"スケジュールの保存に失敗しました: {e}")
    
    logger.info("\n=== HybridScheduleGeneratorV5テスト完了 ===")


if __name__ == "__main__":
    main()


"""信頼性の高い教師重複分析スクリプト"""
import logging
from pathlib import Path
import sys

# プロジェクトのルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.infrastructure.config.path_config import path_config
from src.infrastructure.config.logging_config import LoggingConfig
from src.infrastructure.repositories.csv_repository import CSVScheduleRepository, CSVSchoolRepository
from src.domain.constraints.teacher_conflict_constraint import TeacherConflictConstraint

def run_analysis():
    """教師重複の分析を実行し、結果をコンソールに出力する"""
    LoggingConfig.setup_development_logging()
    logger = logging.getLogger(__name__)
    logger.info("信頼性の高い教師重複分析を開始します...")

    try:
        # 1. 学校の基本データを読み込む（教師マッピングを含む）
        school_repo = CSVSchoolRepository(path_config.config_dir)
        school = school_repo.load_school_data("base_timetable.csv")
        logger.info(f"学校データを読み込みました。教師数: {len(school.get_all_teachers())}")

        # 2. 生成された時間割(output.csv)を読み込む
        schedule_repo = CSVScheduleRepository(path_config.data_dir)
        schedule = schedule_repo.load("output/output.csv", school)
        logger.info("時間割データを読み込みました。")

        # 3. 教師重複制約のインスタンスを作成
        conflict_constraint = TeacherConflictConstraint()
        logger.info("教師重複制約チェッカーを初期化しました。")

        # 4. 制約検証を実行
        result = conflict_constraint.validate(schedule, school)
        logger.info("制約の検証が完了しました。")

        # 5. 結果を分かりやすく表示
        print("\n--- 教師重複の分析結果 ---")
        if not result.violations:
            print("✅ 教師の重複違反は見つかりませんでした。")
        else:
            print(f"🔥 {len(result.violations)}件の教師重複違反が検出されました:")
            i = 1
            for v in result.violations:
                print(f"\n{i}. {v.description}")
                i += 1

        print("\n-------------------------")

    except FileNotFoundError as e:
        logger.error(f"エラー: 必要なファイルが見つかりません: {e}")
    except Exception as e:
        logger.error(f"分析中に予期せぬエラーが発生しました: {e}", exc_info=True)

if __name__ == "__main__":
    run_analysis()


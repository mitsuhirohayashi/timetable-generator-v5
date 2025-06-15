"""CLIメインインターフェース"""
import argparse
import logging
import sys
from pathlib import Path
import datetime

from ...application.use_cases.generate_schedule import (
    GenerateScheduleUseCase,
    GenerateScheduleRequest,
    ValidateScheduleUseCase
)
from ...application.services.documentation_service import get_documentation_service
from ...infrastructure.config.path_config import path_config
from ...infrastructure.config.logging_config import LoggingConfig


class TimetableCLI:
    """時間割生成システムのCLIインターフェース"""
    
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
    
    def setup_logging(self):
        """ログ設定"""
        # 新しいロギング設定を使用
        LoggingConfig.setup_production_logging()
    
    def run(self, args=None):
        """CLIメイン実行"""
        parser = self.create_parser()
        parsed_args = parser.parse_args(args)
        
        # ログレベル設定
        if parsed_args.verbose:
            LoggingConfig.setup_development_logging()
        elif parsed_args.quiet:
            LoggingConfig.setup_quiet_logging()
        
        try:
            if parsed_args.command == "generate":
                return self.handle_generate_command(parsed_args)
            elif parsed_args.command == "validate":
                return self.handle_validate_command(parsed_args)
            else:
                parser.print_help()
                return 1
                
        except Exception as e:
            self.logger.error(f"実行エラー: {e}")
            if parsed_args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def create_parser(self):
        """コマンドライン引数パーサーを作成"""
        parser = argparse.ArgumentParser(
            description="中学校時間割自動生成システム v3.0 (高度なCSPアルゴリズム標準搭載)",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用例:
  %(prog)s generate                          # 高度なCSPアルゴリズムで時間割生成（デフォルト）
  %(prog)s generate --max-iterations 300     # より多くの反復で最適化
  %(prog)s generate --enable-all-optimizations  # すべての最適化を有効化
  %(prog)s generate --optimize-gym-usage     # 体育館使用を最適化
  %(prog)s generate --optimize-meeting-times # 会議時間を最適化
  %(prog)s generate --optimize-workload      # 教師負担を最適化
  %(prog)s generate --use-legacy             # レガシーアルゴリズムを使用
  %(prog)s validate output.csv               # 時間割を検証

詳細情報:
  - デフォルトで高度なCSPアルゴリズムが使用されます
  - 空きコマは自動的に埋められます
  - 制約違反チェックは check_violations.py を使用してください
            """
        )
        
        # グローバルオプション
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="詳細なログを出力"
        )
        parser.add_argument(
            "--quiet", "-q", 
            action="store_true",
            help="警告以上のログのみ出力"
        )
        parser.add_argument(
            "--data-dir",
            type=Path,
            default=path_config.data_dir,
            help="データファイルのディレクトリ (デフォルト: timetable_v5/data)"
        )
        
        # サブコマンド
        subparsers = parser.add_subparsers(dest="command", help="利用可能なコマンド")
        
        # generateコマンド
        generate_parser = subparsers.add_parser(
            "generate",
            help="時間割を生成"
        )
        generate_parser.add_argument(
            "--base-timetable",
            default=str(path_config.base_timetable_csv),
            help="標準時数ファイル (デフォルト: data/config/base_timetable.csv)"
        )
        generate_parser.add_argument(
            "--desired-timetable", 
            default=str(path_config.input_csv),
            help="希望時間割ファイル (デフォルト: data/input/input.csv)"
        )
        generate_parser.add_argument(
            "--followup-prompt",
            default=str(path_config.followup_csv),
            help="週次要望ファイル (デフォルト: data/input/Follow-up.csv)"
        )
        generate_parser.add_argument(
            "--output",
            default=str(path_config.default_output_csv), 
            help="出力ファイル名 (デフォルト: data/output/output.csv)"
        )
        generate_parser.add_argument(
            "--max-iterations",
            type=int,
            default=100,
            help="最大反復回数 (デフォルト: 100)"
        )
        generate_parser.add_argument(
            "--soft-constraints",
            action="store_true",
            help="ソフト制約も適用する"
        )
        generate_parser.add_argument(
            "--use-random",
            action="store_true",
            help="ランダム性を導入して異なる解を探索"
        )
        generate_parser.add_argument(
            "--randomness-level",
            type=float,
            default=0.3,
            help="ランダム性のレベル 0.0-1.0 (デフォルト: 0.3)"
        )
        generate_parser.add_argument(
            "--exploration-range",
            type=int,
            default=10,
            help="探索範囲（最高スコアから何点差まで許容するか、デフォルト: 10）"
        )
        generate_parser.add_argument(
            "--start-empty",
            action="store_true",
            help="空の時間割から生成を開始（入力ファイルを無視）"
        )
        generate_parser.add_argument(
            "--use-legacy",
            action="store_true",
            help="レガシーアルゴリズムを使用（デフォルトは高度なCSPアルゴリズム）"
        )
        # 拡張機能オプション
        generate_parser.add_argument(
            "--optimize-meeting-times",
            action="store_true",
            help="会議時間の最適化を有効化"
        )
        generate_parser.add_argument(
            "--optimize-gym-usage",
            action="store_true",
            help="体育館使用の最適化を有効化"
        )
        generate_parser.add_argument(
            "--optimize-workload",
            action="store_true",
            help="教師の負担バランスを最適化"
        )
        generate_parser.add_argument(
            "--use-support-hours",
            action="store_true",
            help="5組の時数表記（5支、16支等）を使用"
        )
        generate_parser.add_argument(
            "--enable-all-optimizations",
            action="store_true",
            help="すべての最適化機能を有効化"
        )
        
        # validateコマンド
        validate_parser = subparsers.add_parser(
            "validate",
            help="時間割を検証"
        )
        validate_parser.add_argument(
            "schedule_file",
            help="検証する時間割ファイル"
        )
        
        return parser
    
    def handle_generate_command(self, args):
        """時間割生成コマンドを処理"""
        # ドキュメント管理サービスを初期化（ドキュメントを読み込んで構造を理解）
        doc_service = get_documentation_service()
        doc_service.initialize()
        doc_service.log_architecture_understanding()
        
        self.print_header()
        
        # ファイル存在確認
        required_files = [args.base_timetable]
        missing_files = []
        
        for file in required_files:
            # ファイルパスは既に完全パスの可能性があるので直接確認
            file_path = Path(file)
            if not file_path.exists():
                # data_dirとの結合も試す
                file_path = args.data_dir / file
                if not file_path.exists():
                    missing_files.append(file)
        
        if missing_files:
            self.logger.error("必要なファイルが見つかりません:")
            for file in missing_files:
                self.logger.error(f"  - {file}")
            return 1
        
        # ファイル状況表示
        self.print_file_status(args)
        
        # すべての最適化を有効化するオプションの処理
        if args.enable_all_optimizations:
            args.optimize_meeting_times = True
            args.optimize_gym_usage = True
            args.optimize_workload = True
        
        # リクエスト作成（統合版）
        request = GenerateScheduleRequest(
            base_timetable_file=args.base_timetable,
            desired_timetable_file=args.desired_timetable,
            followup_prompt_file=args.followup_prompt,
            output_file=args.output,
            data_directory=args.data_dir,
            max_iterations=args.max_iterations,
            enable_soft_constraints=args.soft_constraints,
            use_random=args.use_random,
            randomness_level=args.randomness_level,
            start_empty=args.start_empty,
            use_advanced_csp=not args.use_legacy,
            optimize_meeting_times=args.optimize_meeting_times,
            optimize_gym_usage=args.optimize_gym_usage,
            optimize_workload=args.optimize_workload,
            use_support_hours=args.use_support_hours
        )
        
        # 時間割生成実行前にモジュールチェック
        doc_service.check_before_modification("GenerateScheduleUseCase")
        
        # 有効化された機能をログ出力
        if any([request.optimize_meeting_times, request.optimize_gym_usage, 
                request.optimize_workload, request.use_support_hours]):
            self.logger.info("時間割生成を開始（拡張機能有効）...")
            features = []
            if request.optimize_meeting_times:
                features.append("会議時間最適化")
            if request.optimize_gym_usage:
                features.append("体育館使用最適化")
            if request.optimize_workload:
                features.append("教師負担最適化")
            if request.use_support_hours:
                features.append("5組時数表記")
            self.logger.info("有効な機能: %s", ", ".join(features))
        else:
            self.logger.info("時間割生成を開始...")  
        
        # 時間割生成実行（統合版）
        use_case = GenerateScheduleUseCase()
        result = use_case.execute(request)
        
        # 結果表示
        self.print_generation_result(result)
        
        # 出力ファイル確認
        self.check_output_file(args.data_dir / args.output)
        
        self.print_footer(result.success)
        
        return 0 if result.success else 1
    
    def handle_validate_command(self, args):
        """時間割検証コマンドを処理"""
        self.print_header("時間割検証システム")
        
        schedule_file = args.data_dir / args.schedule_file
        if not schedule_file.exists():
            self.logger.error(f"時間割ファイルが見つかりません: {schedule_file}")
            return 1
        
        self.logger.info(f"時間割を検証中: {schedule_file}")
        
        use_case = ValidateScheduleUseCase()
        result = use_case.execute(args.schedule_file, args.data_dir)
        
        if "error" in result:
            self.logger.error(f"検証エラー: {result['error']}")
            return 1
        
        # 検証結果表示
        self.print_validation_result(result)
        
        return 0 if result['is_valid'] else 1
    
    def print_header(self, title="時間割自動生成システム"):
        """ヘッダーを表示"""
        print("=" * 60)
        print(f"　　　　{title}")
        print("=" * 60)
        print(f"実行日時: {datetime.datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
        print()
    
    def print_file_status(self, args):
        """ファイル状況を表示"""
        print("【ファイル確認】")
        files_info = [
            (args.base_timetable, "標準時数データ"),
            (args.desired_timetable, "希望時間割"),
            (args.followup_prompt, "週次要望"),
        ]
        
        for filename, description in files_info:
            file_path = args.data_dir / filename
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"✓ {filename} ({description}) - {size} bytes")
            else:
                print(f"✗ {filename} ({description}) - ファイルが見つかりません")
        print()
    
    def print_generation_result(self, result):
        """生成結果を表示"""
        print("【生成結果】")
        print(result.message)
        
        # 拡張機能の結果表示
        if hasattr(result, 'meeting_improvements') and result.meeting_improvements > 0:
            print(f"✓ 会議時間調整: {result.meeting_improvements} 件改善")
        if hasattr(result, 'gym_improvements') and result.gym_improvements > 0:
            print(f"✓ 体育館使用最適化: {result.gym_improvements} 件改善")
        if hasattr(result, 'workload_improvements') and result.workload_improvements > 0:
            print(f"✓ 教師負担バランス: {result.workload_improvements} 件改善")
        
        if result.violations_count > 0:
            print(f"⚠️  制約違反が {result.violations_count} 件残っています")
            
            # 違反の詳細を表示（最初の5件）
            violations = result.schedule.get_violations()[:5]
            for violation in violations:
                print(f"   - {violation}")
            
            if len(result.schedule.get_violations()) > 5:
                print(f"   ... 他 {len(result.schedule.get_violations()) - 5} 件")
        else:
            print("✓ 全ての制約を満たしています")
        
        print()
    
    def print_validation_result(self, result):
        """検証結果を表示"""
        print("【検証結果】")
        print(f"総割り当て数: {result['total_assignments']}件")
        print(f"ハード制約違反: {result['hard_violations']}件")
        print(f"ソフト制約違反: {result['soft_violations']}件")
        
        if result['is_valid']:
            print("✓ 時間割は有効です")
        else:
            print("✗ 時間割に問題があります")
            
            if result['hard_violation_details']:
                print("\nハード制約違反の詳細:")
                for violation in result['hard_violation_details']:
                    print(f"  - {violation}")
            
            if result['soft_violation_details']:
                print("\nソフト制約違反の詳細:")
                for violation in result['soft_violation_details']:
                    print(f"  - {violation}")
        
        print()
    
    def check_output_file(self, output_path):
        """出力ファイルの確認"""
        print("【出力ファイル確認】")
        if output_path.exists():
            size = output_path.stat().st_size
            print(f"✓ {output_path.name} が生成されました ({size} bytes)")
        else:
            print(f"✗ {output_path.name} が生成されませんでした")
        print()
    
    def print_footer(self, success=True):
        """フッターを表示"""
        print("=" * 60)
        if success:
            print("時間割生成処理が正常に完了しました。")
        else:
            print("時間割生成処理が完了しましたが、問題があります。")
        print("=" * 60)


def main():
    """メイン関数"""
    cli = TimetableCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
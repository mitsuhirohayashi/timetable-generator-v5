"""CLIメインインターフェース"""
import argparse
import logging
import sys
from pathlib import Path
import datetime

from ...application.use_cases.request_models import (
    GenerateScheduleRequest,
    ValidateScheduleRequest
)
from ...application.use_cases.use_case_factory import UseCaseFactory
from ...application.services.documentation_service import get_documentation_service
from ...infrastructure.config.path_config import path_config
from ...infrastructure.config.logging_config import LoggingConfig
from ...shared.mixins.logging_mixin import LoggingMixin
from .qanda_integration import QandAIntegration


class TimetableCLI(LoggingMixin):
    """時間割生成システムのCLIインターフェース"""
    
    def __init__(self):
        super().__init__()
        self.setup_logging()
    
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
            elif parsed_args.command == "fix":
                return self.handle_fix_command(parsed_args)
            else:
                parser.print_help()
                return 1
                
        except Exception as e:
            self.log_error(f"実行エラー: {e}")
            if parsed_args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def create_parser(self):
        """コマンドライン引数パーサーを作成"""
        parser = argparse.ArgumentParser(
            description="中学校時間割自動生成システム v4.0 (Ultrathink Perfect Generator標準搭載)",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
使用例:
  %(prog)s generate                          # Ultrathink Perfect Generatorで完璧な時間割生成（デフォルト）
  %(prog)s generate --no-ultrathink          # 従来の高度なCSPアルゴリズムを使用
  %(prog)s generate --max-iterations 300     # より多くの反復で最適化
  %(prog)s generate --enable-all-optimizations  # すべての最適化を有効化
  %(prog)s generate --optimize-gym-usage     # 体育館使用を最適化
  %(prog)s generate --optimize-meeting-times # 会議時間を最適化
  %(prog)s generate --optimize-workload      # 教師負担を最適化
  %(prog)s generate --use-legacy             # レガシーアルゴリズムを使用
  %(prog)s validate output.csv               # 時間割を検証
  %(prog)s fix                               # 時間割の問題を自動修正
  %(prog)s fix --fix-tuesday                 # 火曜日の問題のみ修正
  %(prog)s fix --fix-daily-duplicates        # 日内重複のみ修正

詳細情報:
  - デフォルトでUltratrink Perfect Generatorが使用されます（完璧な時間割を最初から生成）
  - --no-ultrathinkで従来の高度なCSPアルゴリズムに切り替えできます
  - 空きコマは自動的に埋められます
  - 制約違反チェックは check_violations.py を使用してください
  - fixコマンドで生成後の問題を自動修正できます
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
            "--strategy",
            choices=["legacy", "advanced_csp", "improved_csp", "ultrathink", "grade5_priority", "unified_hybrid", "simple_v2"],
            required=True,
            help="使用する生成戦略を選択します。"
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
        generate_parser.add_argument(
            "--search-mode",
            choices=["standard", "priority", "smart", "hybrid"],
            default="standard",
            help="探索モード: standard(従来), priority(優先度), smart(制約伝播), hybrid(複合)"
        )
        generate_parser.add_argument(
            "--use-advanced-search",
            action="store_true",
            help="高度な探索アルゴリズム（制約伝播、優先度配置、SA最適化）を使用"
        )
        generate_parser.add_argument(
            "--use-ultra-optimized",
            action="store_true",
            help="超最適化ジェネレーター（コンポーネント分離、並列処理、学習機能）を使用"
        )
        generate_parser.add_argument(
            "--ultra-cache-size",
            type=int,
            default=100,
            help="超最適化ジェネレーターのキャッシュサイズ（MB、デフォルト: 100）"
        )
        generate_parser.add_argument(
            "--ultra-beam-width",
            type=int,
            default=10,
            help="超最適化ジェネレーターのビーム幅（デフォルト: 10）"
        )
        generate_parser.add_argument(
            "--auto-optimization",
            action="store_true",
            default=True,
            help="自動最適化を使用してシステムが最適な設定を決定（デフォルト: 有効）"
        )
        generate_parser.add_argument(
            "--no-auto-optimization",
            dest="auto_optimization",
            action="store_false",
            help="自動最適化を無効化（手動で設定を指定）"
        )
        
        generate_parser.add_argument(
            "--human-like-flexibility",
            action="store_true",
            help="人間的な柔軟性を有効化（教師代替、時数借用など）"
        )

        generate_parser.add_argument(
            "--use-simple-generator",
            action="store_true",
            help="シンプルジェネレーターを使用"
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
        
        # fixコマンド
        fix_parser = subparsers.add_parser(
            "fix",
            help="時間割の問題を自動修正"
        )
        fix_parser.add_argument(
            "--input",
            default=str(path_config.default_output_csv),
            help="修正する時間割ファイル (デフォルト: data/output/output.csv)"
        )
        fix_parser.add_argument(
            "--output",
            default=str(Path(path_config.output_dir) / "output_fixed.csv"),
            help="修正後の出力ファイル (デフォルト: data/output/output_fixed.csv)"
        )
        fix_parser.add_argument(
            "--fix-tuesday",
            action="store_true",
            help="火曜日の問題を重点的に修正"
        )
        fix_parser.add_argument(
            "--fix-daily-duplicates",
            action="store_true",
            help="日内重複を修正"
        )
        fix_parser.add_argument(
            "--fix-exchange-sync",
            action="store_true",
            help="交流学級の同期を修正"
        )
        fix_parser.add_argument(
            "--fix-teacher-conflicts",
            action="store_true",
            help="教師の重複を修正"
        )
        fix_parser.add_argument(
            "--fix-all",
            action="store_true",
            help="すべての問題を自動修正（デフォルト）"
        )
        
        return parser
    
    def handle_generate_command(self, args):
        """時間割生成コマンドを処理"""
        # ドキュメント管理サービスを初期化（ドキュメントを読み込んで構造を理解）
        doc_service = get_documentation_service()
        doc_service.initialize()
        doc_service.log_architecture_understanding()
        
        self.print_header()
        
        # QandAシステムの初期化と事前チェック
        qanda = QandAIntegration()
        qanda.pre_generation_check()
        
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
            self.log_error("必要なファイルが見つかりません:")
            for file in missing_files:
                self.log_error(f"  - {file}")
            return 1
        
        # ファイル状況表示
        self.print_file_status(args)
        
        # すべての最適化を有効化するオプションの処理
        if args.enable_all_optimizations:
            args.optimize_meeting_times = True
            args.optimize_gym_usage = True
            args.optimize_workload = True
        
        # 高度な探索モードの処理
        if args.use_advanced_search:
            args.search_mode = "hybrid"  # デフォルトでハイブリッドモードを使用
        
        # 超最適化オプションの処理
        ultra_config = None
        if hasattr(args, 'use_ultra_optimized') and args.use_ultra_optimized:
            ultra_config = {
                'enable_parallel': True,
                'cache_size_mb': args.ultra_cache_size if hasattr(args, 'ultra_cache_size') else 100,
                'beam_width': args.ultra_beam_width if hasattr(args, 'ultra_beam_width') else 10,
                'optimization_level': 'extreme'  # 超最適化は最高レベル
            }
        
        if args.use_simple_generator:
            from ...application.services.simple_generator import SimpleGenerator
            # 学校データを読み込み
            from ...infrastructure.repositories.csv_repository import CSVSchoolRepository
            school_repo = CSVSchoolRepository(path_config.config_dir)
            school = school_repo.load_school_data("base_timetable.csv")
            # 初期スケジュールを読み込み
            from ...infrastructure.repositories.csv_repository import CSVScheduleRepository
            schedule_repo = CSVScheduleRepository(path_config.data_dir)
            initial_schedule = schedule_repo.load("input/input.csv", school)

            generator = SimpleGenerator(school, initial_schedule)
            result_schedule = generator.generate()
            # 結果を保存
            schedule_repo.save(result_schedule, args.output)
            self.log_info(f"時間割を {args.output} に保存しました。")
            return 0

        # リクエスト作成（統合版）
        print(f"[DEBUG] args.use_ultra_optimized = {getattr(args, 'use_ultra_optimized', 'NOT SET')}")
        print(f"[DEBUG] hasattr(args, 'use_ultra_optimized') = {hasattr(args, 'use_ultra_optimized')}")
        request = GenerateScheduleRequest(
            base_timetable_file=args.base_timetable,
            desired_timetable_file=args.desired_timetable,
            followup_prompt_file=args.followup_prompt,
            output_file=args.output,
            data_directory=args.data_dir,
            strategy=args.strategy,
        )
        
        # 時間割生成実行前にモジュールチェック
        doc_service.check_before_modification("GenerateScheduleUseCase")
        
        # 有効化された機能をログ出力
        if any([request.optimize_meeting_times, request.optimize_gym_usage, 
                request.optimize_workload, request.use_support_hours]):
            self.log_info("時間割生成を開始（拡張機能有効）...")
            features = []
            if request.optimize_meeting_times:
                features.append("会議時間最適化")
            if request.optimize_gym_usage:
                features.append("体育館使用最適化")
            if request.optimize_workload:
                features.append("教師負担最適化")
            if request.use_support_hours:
                features.append("5組時数表記")
            self.log_info("有効な機能: %s", ", ".join(features))
        else:
            if request.use_ultrathink:
                self.log_info("時間割生成を開始（Ultrathink Perfect Generator）...")
            else:
                self.log_info("時間割生成を開始...")  
        
        # 時間割生成実行（統合版）
        use_case = UseCaseFactory.create_generate_schedule_use_case()
        result = use_case.execute(request)
        
        # 結果表示
        self.print_generation_result(result)
        
        # 出力ファイル確認
        self.check_output_file(args.data_dir / args.output)
        
        # QandAシステムによる違反分析（違反がある場合）
        if result.violations_count > 0:
            # 違反情報を取得するために検証を実行
            validate_use_case = UseCaseFactory.create_validate_schedule_use_case()
            validate_request = ValidateScheduleRequest(
                schedule_file=args.output,
                data_directory=args.data_dir,
                enable_soft_constraints=args.soft_constraints
            )
            validation_result = validate_use_case.execute(validate_request)
            
            if validation_result.violations:
                qanda.post_generation_analysis(validation_result.violations)
        else:
            qanda.post_generation_analysis([])
        
        self.print_footer(result.success)
        
        return 0 if result.success else 1
    
    def handle_validate_command(self, args):
        """時間割検証コマンドを処理"""
        self.print_header("時間割検証システム")
        
        schedule_file = args.data_dir / args.schedule_file
        if not schedule_file.exists():
            self.log_error(f"時間割ファイルが見つかりません: {schedule_file}")
            return 1
        
        self.log_info(f"時間割を検証中: {schedule_file}")
        
        use_case = UseCaseFactory.create_validate_schedule_use_case()
        # リクエストオブジェクトを作成
        request = ValidateScheduleRequest(
            schedule_file=args.schedule_file,
            data_directory=args.data_dir
        )
        result = use_case.execute(request)
        
        if not result.is_valid and result.violations_count == 1 and "error" in result.violations[0]:
            self.log_error(f"検証エラー: {result.message}")
            return 1
        
        # 検証結果表示
        self.print_validation_result(result)
        
        return 0 if result.is_valid else 1
    
    def handle_fix_command(self, args):
        """時間割修正コマンドを処理"""
        self.print_header("時間割自動修正システム")
        
        # 入力ファイルの確認
        input_file = Path(args.input)
        if not input_file.exists():
            self.log_error(f"入力ファイルが見つかりません: {input_file}")
            return 1
        
        # DataFrame読み込み
        import pandas as pd
        df = pd.read_csv(input_file, header=None)
        
        # 修正サービスの初期化
        from ...application.services.schedule_fixer_service import ScheduleFixerService
        fixer = ScheduleFixerService(df)
        
        # 現在の状態を分析
        self.log_info("【現在の状態分析】")
        initial_conflicts = fixer.analyze_all_conflicts()
        initial_count = sum(len(conflicts) for conflicts in initial_conflicts.values())
        self.log_info(f"初期競合数: {initial_count}件")
        
        # 修正オプションの処理
        if args.fix_all or (not args.fix_tuesday and not args.fix_daily_duplicates and not args.fix_exchange_sync):
            # デフォルトまたは--fix-allの場合はすべて修正
            self.log_info("\nすべての問題を修正します...")
            df_fixed, fixes = fixer.fix_all_conflicts()
        else:
            # 個別修正
            fix_count = 0
            if args.fix_tuesday:
                self.log_info("\n火曜日の問題を修正します...")
                fix_count += fixer.fix_tuesday_conflicts()
            
            if args.fix_daily_duplicates:
                self.log_info("\n日内重複を修正します...")
                fix_count += fixer.fix_daily_duplicates()
            
            if args.fix_exchange_sync:
                self.log_info("\n交流学級の同期を修正します...")
                fix_count += fixer.fix_exchange_class_sync()

            if args.fix_teacher_conflicts:
                self.log_info("\n教師の重複を修正します...")
                # TeacherConflictResolverServiceをインポートして使用
                from ...application.services.teacher_conflict_resolver_service import TeacherConflictResolverService
                resolver = TeacherConflictResolverService(df)
                df_fixed, teacher_fixes = resolver.resolve_conflicts()
                fixer.df = df_fixed # 修正後のDataFrameをfixerに反映
                fixer.fixes.extend(teacher_fixes) # 修正内容を記録
                fix_count += len(teacher_fixes)
            
            df_fixed = fixer.df
            fixes = fixer.fixes
        
        # 最終状態の分析
        final_conflicts = fixer.analyze_all_conflicts()
        final_count = sum(len(conflicts) for conflicts in final_conflicts.values())
        
        # 結果の表示
        print("\n【修正結果】")
        print(f"修正前の競合数: {initial_count}件")
        print(f"修正後の競合数: {final_count}件")
        
        if initial_count > 0:
            improvement = ((initial_count - final_count) / initial_count * 100)
            print(f"改善率: {improvement:.1f}%")
        
        print(f"\n実行した修正: {len(fixes)}件")
        
        # 修正内容の表示（最初の10件）
        if fixes:
            print("\n【修正内容（最初の10件）】")
            for i, fix in enumerate(fixes[:10]):
                print(f"  {i+1}. {fix}")
            
            if len(fixes) > 10:
                print(f"  ... 他 {len(fixes) - 10} 件")
        
        # ファイル保存
        output_file = Path(args.output)
        fixer.save_to_file(output_file)
        
        print(f"\n修正結果を保存しました: {output_file}")
        
        # 検証の実行
        if final_count > 0:
            print("\n⚠️  まだ競合が残っています。check_violations.py で詳細を確認してください。")
        else:
            print("\n✓ すべての競合が解決されました！")
        
        return 0 if final_count == 0 else 1
    
    def print_header(self, title="時間割自動生成システム (Ultrathink Perfect Generator)"):
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
        print(f"制約違反数: {result.violations_count}件")
        print(f"検証結果: {result.message}")
        
        if result.is_valid:
            print("✓ 時間割は有効です")
        else:
            print("✗ 時間割に問題があります")
            
            if result.violations:
                print("\n制約違反の詳細 (最初の10件):")
                for i, violation in enumerate(result.violations[:10]):
                    if isinstance(violation, dict):
                        print(f"  {i+1}. {violation['class']} {violation['day']}{violation['period']}校時: "
                              f"{violation['subject']} - {violation['message']} [{violation['priority']}]")
                    else:
                        print(f"  {i+1}. {violation}")
                
                if len(result.violations) > 10:
                    print(f"  ... 他 {len(result.violations) - 10} 件")
        
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
            print("時間割生成処理が正常に完了しました（Ultrathink Perfect Generator）。")
        else:
            print("時間割生成処理が完了しましたが、問題があります。")
        print("=" * 60)


def main():
    """メイン関数"""
    cli = TimetableCLI()
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
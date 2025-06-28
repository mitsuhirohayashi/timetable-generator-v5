#!/usr/bin/env python3
"""
Streamlined violation fixer

シンプルな方法で違反を修正します。
"""
import os
import sys
import logging

# プロジェクトルートのパスを追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.presentation.cli.main import TimetableCLI

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger.info("=== Streamlined Violation Fixer ===\n")
    
    # CLIを使用してfixコマンドを実行
    cli = TimetableCLI()
    
    # 引数を構築
    args = type('args', (), {
        'command': 'fix',
        'input': str(os.path.join(os.path.dirname(__file__), 'data', 'output', 'output.csv')),
        'output': str(os.path.join(os.path.dirname(__file__), 'data', 'output', 'output.csv')),
        'fix_tuesday': False,
        'fix_daily_duplicates': False,
        'fix_exchange_sync': False,
        'fix_all': True,
        'quiet': False,
        'verbose': True
    })()
    
    try:
        # 修正を実行
        cli.handle_fix_command(args)
        
        logger.info("\n修正完了！")
        
        # 違反チェックを実行
        logger.info("\n=== 修正後の違反チェック ===")
        os.system("python3 scripts/analysis/check_violations.py")
        
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
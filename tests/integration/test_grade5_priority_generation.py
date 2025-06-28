#!/usr/bin/env python3
"""5組優先配置アルゴリズムのテストスクリプト"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """5組優先配置アルゴリズムでの生成テスト"""
    print("=== 5組優先配置アルゴリズム テスト ===\n")
    
    # Ultrathinkを無効化して、5組優先配置を使用
    cmd = [
        "python3", "main.py", 
        "--verbose",            # 詳細ログ（グローバルオプション）
        "generate",
        "--no-ultrathink",      # Ultrathinkを無効化
        "--use-grade5-priority", # 5組優先配置を使用
        "--output", "data/output/output_grade5_priority.csv"
    ]
    
    print("実行コマンド:")
    print(" ".join(cmd))
    print("\n生成中...\n")
    
    # 生成実行
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 生成成功！")
            print("\n生成ログ（抜粋）:")
            # 重要な部分のみ表示
            for line in result.stdout.split('\n'):
                if any(keyword in line for keyword in [
                    '5組優先配置', 'Phase', '配置しました', 
                    '教師重複', '違反', '生成統計'
                ]):
                    print(f"  {line}")
        else:
            print("❌ 生成失敗")
            print("\nエラー内容:")
            print(result.stderr)
            return 1
            
    except Exception as e:
        print(f"実行エラー: {e}")
        return 1
    
    # 違反チェック
    print("\n=== 制約違反チェック ===")
    check_cmd = ["python3", "scripts/analysis/check_violations.py"]
    
    try:
        check_result = subprocess.run(check_cmd, capture_output=True, text=True)
        
        # 違反数を抽出
        for line in check_result.stdout.split('\n'):
            if '違反件数:' in line or '5組同一教科違反' in line or '教師重複違反' in line:
                print(f"  {line}")
                
    except Exception as e:
        print(f"チェックエラー: {e}")
    
    # 結果比較
    print("\n=== 改善効果の比較 ===")
    print("改善前（通常のCSP）:")
    print("  - 5組同期違反: 100件")
    print("  - 教師重複: 18件")
    print("  - 総違反数: 118件")
    
    print("\n改善後（5組優先配置）:")
    print("  - 上記の違反チェック結果を確認してください")
    print("  - 期待値: 5組同期違反 0件、教師重複 5件以下")
    
    print("\n出力ファイル: data/output/output_grade5_priority.csv")

if __name__ == "__main__":
    sys.exit(main())
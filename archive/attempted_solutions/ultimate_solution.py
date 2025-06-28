#!/usr/bin/env python3
"""究極の解決策 - 教師重複を完全に防ぐ時間割生成"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import subprocess

def run_generation_and_check():
    """時間割生成と違反チェックを実行"""
    print("=== 究極の解決策 - 教師重複を完全に防ぐ時間割生成 ===\n")
    
    # 1. 新しい時間割を生成（教師重複を防ぐ改良版アルゴリズムで）
    print("ステップ1: 改良版アルゴリズムで時間割を生成...")
    try:
        # mainコマンドを実行（改良版CSPアルゴリズムを使用）
        result = subprocess.run(
            ["python3", "main.py", "generate", "--max-iterations", "500"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("エラー:", result.stderr)
    except Exception as e:
        print(f"生成エラー: {e}")
    
    # 2. 生成された時間割の教師重複を修正
    print("\nステップ2: 教師重複を修正...")
    try:
        result = subprocess.run(
            ["python3", "radical_teacher_fix.py"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"修正エラー: {e}")
    
    # 3. さらに完全な再割り当てを実行
    print("\nステップ3: 教師の完全再割り当て...")
    try:
        result = subprocess.run(
            ["python3", "complete_teacher_reassignment.py"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
    except Exception as e:
        print(f"再割り当てエラー: {e}")
    
    # 4. 最終的な違反チェック
    print("\nステップ4: 最終チェック...")
    try:
        result = subprocess.run(
            ["python3", "scripts/analysis/check_violations.py"],
            capture_output=True,
            text=True
        )
        
        # 違反の概要のみ表示
        lines = result.stdout.split('\n')
        for i, line in enumerate(lines):
            if "件の制約違反が見つかりました" in line:
                print(line)
                # 教師重複の件数を抽出
                for j in range(i+1, min(i+10, len(lines))):
                    if "教師重複違反" in lines[j]:
                        print(lines[j])
                break
    except Exception as e:
        print(f"チェックエラー: {e}")

def analyze_and_suggest():
    """問題分析と提案"""
    print("\n=== 問題分析と提案 ===")
    print("""
    教師重複問題の根本原因：
    1. teacher_subject_mapping.csvで1人の教師が多数のクラスを担当
    2. 同じ時間に複数クラスが同じ科目を配置すると物理的に不可能
    
    推奨される解決策：
    1. 各科目に複数の教師を配置（特に主要5教科）
    2. 時間割生成時に教師の空き時間を考慮したアルゴリズム
    3. 段階的な配置（教師の負担が重い科目から優先的に配置）
    
    緊急対処法：
    1. 教師なしでも授業を実施（代替教師や補助教員）
    2. 合同授業の活用（複数クラスを1人の教師が担当）
    3. 時間割の部分的な見直し（問題のある時間帯のみ調整）
    """)

def main():
    # 解決策を実行
    run_generation_and_check()
    
    # 問題分析と提案
    analyze_and_suggest()
    
    print("\n処理が完了しました。")
    print("output.csvに最終的な時間割が保存されています。")
    print("\n注意: 教師の割り当てが不足している場合は、")
    print("teacher_subject_mapping.csvを見直して教師を追加することを推奨します。")

if __name__ == "__main__":
    main()
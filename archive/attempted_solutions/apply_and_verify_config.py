#!/usr/bin/env python3
"""修正した設定ファイルを適用して検証"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import shutil
import subprocess
from datetime import datetime
from src.infrastructure.config.path_config import path_config

class ConfigApplier:
    """設定ファイル適用クラス"""
    
    def __init__(self):
        self.config_dir = path_config.config_dir
        self.original_file = self.config_dir / "teacher_subject_mapping.csv"
        self.modified_file = self.config_dir / "teacher_subject_mapping_modified.csv"
        self.backup_file = None
        
    def create_backup(self):
        """元のファイルのバックアップを作成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_file = self.config_dir / f"teacher_subject_mapping_backup_{timestamp}.csv"
        
        print(f"バックアップを作成: {self.backup_file}")
        shutil.copy2(self.original_file, self.backup_file)
        
    def apply_modified_config(self):
        """修正版の設定を適用"""
        print(f"\n修正版を適用: {self.modified_file} → {self.original_file}")
        shutil.copy2(self.modified_file, self.original_file)
        print("✓ 適用完了")
        
    def generate_test_schedule(self):
        """テスト用の時間割を生成"""
        print("\n=== テスト時間割生成 ===")
        
        try:
            # mainコマンドを実行
            result = subprocess.run(
                ["python3", "main.py", "generate", "--max-iterations", "100"],
                capture_output=True,
                text=True,
                timeout=60  # 60秒でタイムアウト
            )
            
            # 出力から重要な情報を抽出
            lines = result.stdout.split('\n')
            for line in lines:
                if "スケジュール生成完了" in line:
                    print(line)
                if "制約違反" in line:
                    print(line)
                if "割り当て数" in line:
                    print(line)
                    
            if result.returncode != 0:
                print(f"エラー: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("エラー: 時間割生成がタイムアウトしました")
        except Exception as e:
            print(f"エラー: {e}")
            
    def check_violations(self):
        """制約違反をチェック"""
        print("\n=== 制約違反チェック ===")
        
        try:
            result = subprocess.run(
                ["python3", "scripts/analysis/check_violations.py"],
                capture_output=True,
                text=True
            )
            
            lines = result.stdout.split('\n')
            violation_count = 0
            teacher_conflicts = 0
            
            for line in lines:
                if "件の制約違反が見つかりました" in line:
                    print(line)
                    # 数字を抽出
                    import re
                    match = re.search(r'(\d+)\s*件', line)
                    if match:
                        violation_count = int(match.group(1))
                        
                if "教師重複違反:" in line:
                    teacher_conflicts += 1
                    
            print(f"\n教師重複違反: {teacher_conflicts}件")
            print(f"総違反数: {violation_count}件")
            
            return violation_count, teacher_conflicts
            
        except Exception as e:
            print(f"エラー: {e}")
            return -1, -1
            
    def compare_results(self, original_violations, modified_violations):
        """結果を比較"""
        print("\n=== 結果比較 ===")
        print(f"{'項目':<20} {'修正前':>10} {'修正後':>10} {'改善':>10}")
        print("-" * 50)
        
        orig_total, orig_teacher = original_violations
        mod_total, mod_teacher = modified_violations
        
        if orig_total >= 0 and mod_total >= 0:
            total_improvement = orig_total - mod_total
            teacher_improvement = orig_teacher - mod_teacher
            
            print(f"{'総違反数':<20} {orig_total:>10} {mod_total:>10} {total_improvement:>10}")
            print(f"{'教師重複違反':<20} {orig_teacher:>10} {mod_teacher:>10} {teacher_improvement:>10}")
            
            if mod_total < orig_total:
                print("\n✅ 改善が見られます！")
            elif mod_total == 0:
                print("\n🎉 全ての違反が解消されました！")
            else:
                print("\n⚠️ まだ改善の余地があります")
                
    def restore_original(self):
        """元の設定に戻す"""
        if self.backup_file and self.backup_file.exists():
            print(f"\n元の設定に戻します: {self.backup_file} → {self.original_file}")
            shutil.copy2(self.backup_file, self.original_file)
            print("✓ 復元完了")

def main():
    """メイン処理"""
    print("=== 修正設定ファイルの適用と検証 ===\n")
    
    applier = ConfigApplier()
    
    # 1. 現在の状態を記録（オプション）
    print("現在の制約違反を確認中...")
    original_violations = applier.check_violations()
    
    # 2. バックアップを作成
    applier.create_backup()
    
    # 3. 修正版を適用
    applier.apply_modified_config()
    
    # 4. テスト時間割を生成
    applier.generate_test_schedule()
    
    # 5. 制約違反をチェック
    modified_violations = applier.check_violations()
    
    # 6. 結果を比較
    applier.compare_results(original_violations, modified_violations)
    
    # 7. ユーザーに選択肢を提示
    print("\n" + "="*50)
    print("修正版の設定ファイルでのテストが完了しました。")
    print("\n選択してください:")
    print("1. 修正版を採用する（現在の状態を維持）")
    print("2. 元の設定に戻す")
    print("3. 手動で調整する")
    
    choice = input("\n選択 (1/2/3): ").strip()
    
    if choice == "2":
        applier.restore_original()
        print("\n元の設定に戻しました。")
    elif choice == "1":
        print("\n修正版を採用しました。")
        print("今後はこの設定で時間割生成を行ってください。")
    else:
        print("\n手動調整を選択しました。")
        print(f"修正版: {applier.modified_file}")
        print(f"バックアップ: {applier.backup_file}")
        print("必要に応じてファイルを編集してください。")
        
    print("\n処理が完了しました。")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
全てのハイブリッドジェネレーターにテスト期間保護機能を追加するスクリプト
"""
import os
import re
from pathlib import Path


def add_test_period_protection_to_generator(file_path: Path):
    """指定されたジェネレーターファイルにテスト期間保護機能を追加"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 既に追加済みかチェック
    if 'TestPeriodProtector' in content:
        print(f"✓ {file_path.name} は既に修正済みです")
        return False
    
    print(f"📝 {file_path.name} を修正中...")
    
    # インポートの追加
    import_pattern = r'(from \.\.grade5_synchronizer_refactored import RefactoredGrade5Synchronizer)'
    import_replacement = r'\1\nfrom .test_period_protector import TestPeriodProtector'
    content = re.sub(import_pattern, import_replacement, content)
    
    # 初期化処理の追加
    init_pattern = r'(self\.exchange_synchronizer = ExchangeClassSynchronizer\(\))'
    init_replacement = r'''\1
        
        # テスト期間保護サービス
        self.test_period_protector = TestPeriodProtector()'''
    content = re.sub(init_pattern, init_replacement, content)
    
    # generateメソッドのパラメータ追加
    generate_pattern = r'(def generate\([^)]+)(time_limit: int = 300)'
    generate_replacement = r'\1\2,\n        followup_data: Optional[Dict[str, List[str]]] = None'
    content = re.sub(generate_pattern, generate_replacement, content)
    
    # Dictのインポート追加（必要な場合）
    if 'from typing import' in content and 'Dict' not in content:
        typing_pattern = r'(from typing import[^)]+)'
        if 'Optional' in content:
            content = re.sub(typing_pattern, r'\1, Dict', content)
    
    # generateメソッドの開始部分でテスト期間保護の初期化
    generate_start_pattern = r'(self\.logger\.info\("=== .*? ==="\))'
    generate_start_replacement = r'''\1
        
        # テスト期間保護の初期化
        if followup_data:
            self.test_period_protector.load_followup_data(followup_data)
            # test_periodsも更新
            self.test_periods = self.test_period_protector.test_periods.copy()
        
        # 初期スケジュールの準備
        if initial_schedule:
            # テスト期間の割り当てを保存
            self.test_period_protector.load_initial_schedule(initial_schedule)'''
    
    # 最初のlogger.infoを見つけて置換
    content = re.sub(generate_start_pattern, generate_start_replacement, content, count=1)
    
    # _place_remaining_smartメソッド内でテスト期間チェックを追加
    if '_place_remaining_smart' in content:
        place_pattern = r'(# 既に配置済みならスキップ\s+if schedule\.get_assignment\(time_slot, class_ref\):\s+continue)'
        place_replacement = r'''\1
                        
                        # テスト期間中はスキップ
                        if self.test_period_protector.is_test_period(time_slot):
                            continue'''
        content = re.sub(place_pattern, place_replacement, content)
    
    # 最終的なテスト期間保護の適用（最適化フェーズの後）
    if 'best_schedule = self._optimize_schedule' in content:
        optimize_pattern = r'(best_schedule = self\._optimize_schedule[^)]+\))'
        optimize_replacement = r'''\1
        
        # テスト期間保護の適用
        self.logger.info("テスト期間保護の適用")
        if self.test_period_protector.test_periods:
            changes = self.test_period_protector.protect_test_periods(best_schedule, school)
            if changes > 0:
                self.logger.info(f"テスト期間保護により{changes}個の割り当てを修正しました")'''
        content = re.sub(optimize_pattern, optimize_replacement, content)
    
    # ファイルに書き戻す
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ {file_path.name} の修正が完了しました")
    return True


def main():
    """メイン処理"""
    print("=== 全ハイブリッドジェネレーターへのテスト期間保護機能追加 ===\n")
    
    # ultrathinkディレクトリのパス
    ultrathink_dir = Path(__file__).parent.parent.parent / 'src' / 'domain' / 'services' / 'ultrathink'
    
    # 対象のジェネレーターファイル
    target_files = [
        'hybrid_schedule_generator_v2.py',
        'hybrid_schedule_generator_v3.py',
        'hybrid_schedule_generator_v5.py',
        'hybrid_schedule_generator_v6.py',
        'hybrid_schedule_generator_v7.py',
        'hybrid_schedule_generator_v8.py'
    ]
    
    modified_count = 0
    
    for file_name in target_files:
        file_path = ultrathink_dir / file_name
        if file_path.exists():
            if add_test_period_protection_to_generator(file_path):
                modified_count += 1
        else:
            print(f"⚠️  {file_name} が見つかりません")
    
    print(f"\n✅ 修正完了: {modified_count}個のファイルを更新しました")
    
    # CLAUDE.mdの更新
    claude_md_path = Path(__file__).parent.parent.parent / 'CLAUDE.md'
    
    if claude_md_path.exists():
        print("\n📝 CLAUDE.mdを更新中...")
        
        with open(claude_md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # テスト期間保護に関する記述を追加
        new_section = """
## 🔒 テスト期間保護システム（2025-06-20実装）

### テスト期間の自動保護
Follow-up.csvで「テストなので時間割の変更をしないでください」と指定された期間は、input.csvの内容が完全に保護されます。

**実装内容**：
1. **TestPeriodProtector**: テスト期間保護専用サービス
2. **全ハイブリッドジェネレーター対応**: V2-V8すべてにテスト期間保護を統合
3. **自動検出**: Follow-up.csvからテスト期間を自動的に検出
4. **完全保護**: テスト期間中の授業は変更されません

**保護される期間（Follow-up.csvより）**：
- 月曜1-3限：テスト期間
- 火曜1-3限：テスト期間
- 水曜1-2限：テスト期間

この機能により、テスト期間中の授業が勝手に変更される問題が解決されました。
"""
        
        # 既知の問題セクションの前に追加
        if "## ⚠️ 既知の問題と対処法" in content:
            content = content.replace(
                "## ⚠️ 既知の問題と対処法",
                new_section + "\n## ⚠️ 既知の問題と対処法"
            )
        else:
            # 末尾に追加
            content += "\n" + new_section
        
        with open(claude_md_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ CLAUDE.mdの更新が完了しました")


if __name__ == "__main__":
    main()
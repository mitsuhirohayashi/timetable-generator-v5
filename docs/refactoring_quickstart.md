# 🚀 リファクタリング Quick Start Guide

## 今すぐ実行できるコマンド（5分で完了）

### 1. アーカイブディレクトリの作成と古いファイルの移動

```bash
# アーカイブディレクトリ作成
mkdir -p archive/{old_generators,old_tests,old_scripts,duplicate_analysis}

# 古いジェネレーターのアーカイブ（v2-v13）
find . -name "*generator_v[2-9].py" -o -name "*generator_v1[0-3].py" | xargs -I {} mv {} archive/old_generators/

# 古いテストファイルのアーカイブ
find . -name "test_v[2-9]_*.py" -o -name "test_v1[0-3]_*.py" | xargs -I {} mv {} archive/old_tests/

# 重複分析スクリプトのアーカイブ
mv scripts/analysis/analyze_teacher_duplications_v2.py archive/duplicate_analysis/
mv scripts/analysis/check_*_old.py archive/old_scripts/ 2>/dev/null || true
```

### 2. 未使用ファイルのクリーンアップ

```bash
# __pycache__の削除
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# .pyc ファイルの削除
find . -name "*.pyc" -delete

# 空のディレクトリを削除
find . -type d -empty -delete 2>/dev/null || true
```

### 3. 重複スクリプトの統合（スクリプト作成）

```bash
# 統合分析スクリプトの作成
cat > scripts/analysis/unified_analyzer.py << 'EOF'
#!/usr/bin/env python3
"""統合分析ツール - 全ての分析機能を1つのスクリプトに統合"""

import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent.parent))

from scripts.analysis.analyze_violations import analyze_all_violations
from scripts.analysis.analyze_teacher_duplications import analyze_teacher_issues
from scripts.analysis.analyze_gym_violations import analyze_gym_usage

def main():
    parser = argparse.ArgumentParser(description='統合分析ツール')
    parser.add_argument('--type', choices=['all', 'teacher', 'gym', 'daily', 'exchange'],
                        default='all', help='分析タイプ')
    parser.add_argument('--fix', action='store_true', help='自動修正を実行')
    args = parser.parse_args()
    
    if args.type == 'all':
        print("全ての制約違反を分析中...")
        analyze_all_violations(fix=args.fix)
    elif args.type == 'teacher':
        print("教師関連の問題を分析中...")
        analyze_teacher_issues(fix=args.fix)
    elif args.type == 'gym':
        print("体育館使用状況を分析中...")
        analyze_gym_usage(fix=args.fix)
    
    print("分析完了！")

if __name__ == "__main__":
    main()
EOF

chmod +x scripts/analysis/unified_analyzer.py
```

### 4. 基本的なプロジェクト構造の確認

```bash
# 現在の構造を可視化
echo "=== プロジェクト構造 ==="
echo "Pythonファイル数:"
find src -name "*.py" | wc -l | xargs echo "  src/:"
find scripts -name "*.py" | wc -l | xargs echo "  scripts/:"
find tests -name "*.py" | wc -l | xargs echo "  tests/:"
find archive -name "*.py" 2>/dev/null | wc -l | xargs echo "  archive/:"

echo -e "\n大きなファイル（500行以上）:"
find . -name "*.py" -exec wc -l {} + | sort -nr | head -10
```

### 5. Git での変更確認とコミット

```bash
# 変更内容の確認
git status

# アーカイブした内容をコミット（推奨）
git add archive/
git commit -m "refactor: 古いジェネレーターと重複ファイルをアーカイブ

- v2-v13のジェネレーターをarchive/old_generators/に移動
- 重複する分析スクリプトをアーカイブ
- 統合分析ツール(unified_analyzer.py)を作成"
```

## 次のステップ（30分で完了）

### サービスレイヤーの整理

```python
# scripts/refactor/organize_services.py として保存
import os
import shutil
from pathlib import Path

def organize_services():
    """サービスを適切なレイヤーに再配置"""
    domain_services = Path("src/domain/services")
    app_services = Path("src/application/services")
    
    # アプリケーション層に移動すべきサービス
    app_level_services = [
        "*generator*.py",
        "*optimizer*.py",
        "*loader*.py",
        "*filler*.py",
        "*corrector*.py"
    ]
    
    for pattern in app_level_services:
        for file in domain_services.glob(pattern):
            dest = app_services / file.name
            print(f"Moving {file} -> {dest}")
            shutil.move(str(file), str(dest))

if __name__ == "__main__":
    organize_services()
```

## 効果測定

実行前後で以下のコマンドを実行して効果を確認：

```bash
# ファイル数の変化
echo "Pythonファイル総数: $(find . -name '*.py' | wc -l)"
echo "未整理ファイル数: $(git status --porcelain | grep '^??' | grep '\.py$' | wc -l)"

# コード行数の変化
echo "総コード行数: $(find . -name '*.py' -exec cat {} + | wc -l)"
```

---

これらのコマンドを実行することで、**即座に100個以上のファイルを整理**でき、プロジェクトの見通しが大幅に改善されます。
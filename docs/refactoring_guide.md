# リファクタリングガイド - 重複コード削減

## Phase 1 完了状況

### 1.1 スクリプト整理 ✅
- ルートディレクトリから16個のPythonスクリプトを移動
- `scripts/fixes/`, `scripts/analysis/`, `scripts/utilities/`に整理
- ルートには`main.py`と`setup.py`のみ残存

### 1.2 重複コード統合 ✅ 
- `ScriptUtilities`クラスを作成（`src/application/services/script_utilities.py`）
- 共通機能を集約:
  - CSV読み書き
  - スケジュール操作（get_cell, set_cell）
  - 固定科目チェック
  - 交流学級・5組判定
  - 空きスロット検索
  - 日内重複チェック
  - 交流学級同期チェック

### リファクタリング前後の比較

**Before (fix_final_violations.py):**
```python
# 238行の重複コード
def load_csv():
    with open("data/output/output.csv", 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)
    return rows

# 各スクリプトで同じ実装を繰り返し
```

**After:**
```python
# 186行に削減（22%削減）
from src.application.services.script_utilities import script_utils

# 共通機能を再利用
df = script_utils.read_schedule()
script_utils.save_schedule(df)
```

### 削減効果の推定
- 52個のfixスクリプト × 平均50行削減 = 約2,600行の削減
- コードの一貫性向上
- バグ修正が1箇所で完了

## Phase 2: アーキテクチャ簡素化（次のステップ）

### 2.1 制約システムの簡素化
- 統合制約管理システムへの移行
- 重複した制約チェックロジックの削除

### 2.2 サービス層の整理
- 似た機能のサービスを統合
- インターフェースの明確化

### 2.3 ジェネレーターの統一
- AdvancedCSPGeneratorをデフォルトに
- レガシーコードの削除
EOF < /dev/null

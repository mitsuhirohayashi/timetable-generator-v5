# 開発者ガイド

## 目次
1. [アーキテクチャ概要](#アーキテクチャ概要)
2. [開発環境のセットアップ](#開発環境のセットアップ)
3. [コーディング規約](#コーディング規約)
4. [主要コンポーネント](#主要コンポーネント)
5. [拡張方法](#拡張方法)
6. [デバッグとトラブルシューティング](#デバッグとトラブルシューティング)

## アーキテクチャ概要

本システムはClean Architecture原則に基づいて設計されています。

### レイヤー構造

```
src/
├── presentation/   # プレゼンテーション層（CLI）
├── application/    # アプリケーション層（ユースケース）
├── domain/        # ドメイン層（ビジネスロジック）
└── infrastructure/ # インフラ層（外部システム連携）
```

### 依存関係のルール
- 依存は外側から内側に向かう（presentation → application → domain）
- domainは他のレイヤーに依存しない
- インターフェースを使用して依存性を逆転

## 開発環境のセットアップ

### 必要な環境
- Python 3.8以上
- pip（パッケージ管理）

### セットアップ手順

```bash
# リポジトリのクローン
git clone <repository-url>
cd timetable_v5

# 仮想環境の作成（推奨）
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# または
venv\Scripts\activate  # Windows

# 依存パッケージのインストール
pip install -r requirements.txt

# 開発用パッケージのインストール（オプション）
pip install -r requirements-dev.txt
```

## コーディング規約

### 基本原則
1. **PEP 8準拠**: Pythonの標準コーディング規約に従う
2. **型ヒント**: 可能な限り型ヒントを使用
3. **ドキュメント文字列**: すべての公開関数・クラスにdocstringを記載

### 命名規則
- **クラス名**: PascalCase（例：`ScheduleGenerator`）
- **関数・変数名**: snake_case（例：`generate_schedule`）
- **定数**: UPPER_SNAKE_CASE（例：`MAX_ITERATIONS`）

### コード例

```python
from typing import List, Optional

class ScheduleGenerator:
    """スケジュール生成クラス
    
    時間割を生成するための主要なクラス。
    CSPアルゴリズムを使用して制約を満たす時間割を生成します。
    """
    
    def generate(self, 
                 school: School, 
                 constraints: List[Constraint],
                 max_iterations: int = 100) -> Optional[Schedule]:
        """スケジュールを生成
        
        Args:
            school: 学校情報
            constraints: 制約リスト
            max_iterations: 最大反復回数
            
        Returns:
            生成されたスケジュール。失敗時はNone
            
        Raises:
            TimetableGenerationError: 生成に失敗した場合
        """
        pass
```

## 主要コンポーネント

### 1. エンティティ（Domain Layer）

#### Schedule
時間割全体を表現するエンティティ。

```python
from src.domain.entities.schedule import Schedule

# スケジュールの作成
schedule = Schedule()

# 授業の割り当て
schedule.assign(time_slot, class_ref, assignment)

# ロック機能
schedule.lock(time_slot, class_ref)
```

#### School
学校の情報（クラス、教師、科目）を管理。

```python
from src.domain.entities.school import School

school = School()
school.add_class(class_ref)
school.add_teacher(teacher)
school.add_subject(subject)
```

### 2. 制約システム（Domain Layer）

#### 制約の定義

```python
from src.domain.constraints.base import Constraint, ConstraintPriority

class MyConstraint(Constraint):
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.HIGH,
            name="My Constraint",
            description="制約の説明"
        )
    
    def check(self, schedule, school, time_slot, assignment):
        # 制約チェックロジック
        return True  # or False
```

#### 制約の優先度
- `CRITICAL`: 絶対に守るべき制約
- `HIGH`: 重要な制約
- `MEDIUM`: 望ましい制約
- `LOW`: 可能であれば守る制約

### 3. サービス（Domain/Application Layer）

#### CSPオーケストレーター
制約充足問題を解くメインのサービス。

```python
from src.domain.services.csp_orchestrator import CSPOrchestratorImproved

orchestrator = CSPOrchestratorImproved(constraint_validator)
schedule = orchestrator.generate(school, max_iterations)
```

#### SmartEmptySlotFiller
空きスロットを賢く埋めるサービス。

```python
from src.domain.services.smart_empty_slot_filler import SmartEmptySlotFiller

filler = SmartEmptySlotFiller(constraint_system)
filled_count = filler.fill_empty_slots(schedule, school)
```

### 4. リポジトリ（Infrastructure Layer）

#### CSVRepository
CSVファイルの読み書きを担当。

```python
from src.infrastructure.repositories.csv_repository import CSVRepository

repo = CSVRepository()
schedule = repo.load_schedule("input.csv")
repo.save_schedule(schedule, "output.csv")
```

## 拡張方法

### 新しい制約の追加

1. `src/domain/constraints/`に新しい制約クラスを作成

```python
# src/domain/constraints/my_new_constraint.py
from .base import Constraint, ConstraintPriority

class MyNewConstraint(Constraint):
    def __init__(self):
        super().__init__(
            priority=ConstraintPriority.MEDIUM,
            name="新しい制約",
            description="新しい制約の説明"
        )
    
    def check(self, schedule, school, time_slot, assignment):
        # 制約チェックロジックを実装
        return True
```

2. 制約を登録

```python
# src/application/services/constraint_registration_service.py
from ...domain.constraints.my_new_constraint import MyNewConstraint

# _register_standard_constraintsメソッド内に追加
constraints.append((MyNewConstraint(), ConstraintPriority.MEDIUM))
```

### 新しい最適化戦略の追加

1. `src/domain/services/interfaces/fill_strategy.py`のインターフェースを実装

```python
from ..interfaces.fill_strategy import FillStrategy

class MyFillStrategy(FillStrategy):
    def create_candidates(self, schedule, school, time_slot, class_ref, subjects):
        # 候補生成ロジック
        pass
    
    def get_description(self):
        return "私の埋め込み戦略"
```

2. SmartEmptySlotFillerで使用

```python
filler = SmartEmptySlotFiller(constraint_system)
filler.fill_with_strategy(schedule, school, MyFillStrategy())
```

## デバッグとトラブルシューティング

### ロギング設定

開発時は詳細ログを有効化：

```bash
python main.py generate --verbose
```

### パフォーマンス計測

```python
from src.infrastructure.performance import global_profiler

with global_profiler.measure("my_operation"):
    # 計測したい処理
    pass

# レポート出力
global_profiler.print_report()
```

### よくある問題と解決方法

#### 1. インポートエラー
```
ImportError: No module named 'src.domain.constraints.xxx'
```

**解決方法**:
- `sys.path`の確認
- `__init__.py`ファイルの存在確認
- 相対インポートの使用

#### 2. 制約違反が解消されない

**確認事項**:
- 制約の優先度設定
- 制約同士の競合
- ログで違反の詳細を確認

```bash
python check_violations.py
```

#### 3. パフォーマンスの問題

**対処法**:
- `--max-iterations`を調整
- キャッシング機能の活用
- プロファイラーで遅い部分を特定

### テストの実行

```bash
# 基本テストの実行
python -m pytest tests/

# 特定のテストのみ実行
python tests/test_basic_functionality.py
```

## エラーハンドリング

### カスタム例外の使用

```python
from src.domain.exceptions import (
    TimetableGenerationError,
    ConstraintViolationError,
    DataLoadingError
)

try:
    # 処理
    pass
except DataLoadingError as e:
    logger.error(f"データ読み込みエラー: {e.file_path}")
except ConstraintViolationError as e:
    logger.error(f"制約違反: {len(e.violations)}件")
except TimetableGenerationError as e:
    logger.error(f"生成エラー: {e.message}")
```

### エラーコンテキストの追加

```python
from src.infrastructure.config.logging_config import get_schedule_logger

logger = get_schedule_logger(__name__)

# コンテキスト付きログ
logger.set_context(phase="generation", iteration=1)
logger.error("エラーが発生しました", 
            error_details={'code': 'E001', 'reason': '教師不足'})
```

## コントリビューション

### プルリクエストの作成手順

1. フィーチャーブランチを作成
```bash
git checkout -b feature/my-new-feature
```

2. 変更をコミット
```bash
git add .
git commit -m "Add: 新機能の説明"
```

3. テストを実行して確認
```bash
python -m pytest tests/
```

4. プルリクエストを作成

### コミットメッセージの規約

- `Add:` 新機能追加
- `Fix:` バグ修正
- `Update:` 既存機能の更新
- `Remove:` 機能削除
- `Refactor:` リファクタリング
- `Docs:` ドキュメント更新
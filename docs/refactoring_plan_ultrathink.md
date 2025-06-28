# 🚀 UltraThink リファクタリング計画 - 時間割生成システムv5

## 📊 現状分析サマリー

### 問題点
- **502個のPythonファイル**（管理困難）
- **アーキテクチャ違反**: Clean Architectureの原則に違反
- **コード重複**: 25個以上の類似分析スクリプト、15個のジェネレーターバージョン
- **大きすぎるファイル**: 最大1282行（理想は300行以下）
- **ハードコーディング**: 設定値が7個以上のファイルに散在

### 目標
- ファイル数を**70%削減**（502→150）
- アーキテクチャスコアを**3/10から8/10**へ
- テストカバレッジを**80%以上**に
- 保守性と拡張性の大幅向上

## 📅 実装フェーズ

### 🔥 Phase 1: 即座のクリーンアップ（1週間）

#### 1.1 古いジェネレーターのアーカイブ
```bash
# 実行コマンド
mkdir -p archive/old_generators
mv src/domain/services/implementations/*_generator_v{2..13}.py archive/old_generators/
mv scripts/debug/test_v{2..13}_*.py archive/old_tests/
```

**削減効果**: 150ファイル、15,000行以上のコード

#### 1.2 重複スクリプトの統合
```python
# scripts/analysis/unified_analyzer.py として統合
class UnifiedAnalyzer:
    def analyze_violations(self, violation_type: str = "all"):
        """全ての分析機能を統合"""
        analyzers = {
            "teacher": self._analyze_teacher_violations,
            "gym": self._analyze_gym_violations,
            "daily": self._analyze_daily_duplicates,
            "exchange": self._analyze_exchange_sync,
            "all": self._analyze_all
        }
        return analyzers[violation_type]()
```

**削減効果**: 40ファイル→5ファイル

#### 1.3 テストの再編成
```
tests/
├── unit/           # 単体テスト
├── integration/    # 統合テスト
├── e2e/           # エンドツーエンドテスト
└── fixtures/       # テストデータ
```

### 🏗️ Phase 2: アーキテクチャ修正（2-3週間）

#### 2.1 レイヤー間の依存関係修正

**現在の問題**:
```python
# ❌ Application層がInfrastructure層に直接依存
from ...infrastructure.repositories.csv_repository import CSVRepository
```

**修正後**:
```python
# ✅ インターフェース経由で依存
from ...domain.interfaces.repositories import IScheduleRepository
```

#### 2.2 サービスの適切な配置

```
# 移動計画
src/domain/services/ (110ファイル) → src/application/services/ (ビジネスロジック)
                                    → src/domain/services/ (ドメインロジックのみ)
```

**ドメインに残すサービス**:
- ScheduleValidator
- ConstraintChecker
- Grade5Synchronizer
- ExchangeClassRules

**アプリケーションに移動**:
- ScheduleGenerator系
- Optimizer系
- DataLoader系
- FileIO関連

#### 2.3 依存性注入の実装

```python
# src/infrastructure/di_container.py
class DIContainer:
    def __init__(self):
        self._services = {}
        self._singletons = {}
    
    def register(self, interface: Type, implementation: Type, singleton: bool = False):
        """インターフェースと実装を登録"""
        self._services[interface] = (implementation, singleton)
    
    def resolve(self, interface: Type):
        """依存関係を解決"""
        # 実装は省略
```

### 💎 Phase 3: コード品質改善（3-4週間）

#### 3.1 大きなファイルの分割

**例: schedule_generation_service.py (891行) → 4ファイルに分割**
```
schedule_generation/
├── __init__.py
├── generator_interface.py     # インターフェース定義
├── generator_factory.py       # ファクトリーパターン
├── generation_pipeline.py     # パイプライン処理
└── generation_strategies.py   # 各種戦略
```

#### 3.2 共通パターンの抽出

```python
# src/shared/csv_operations.py
class CSVOperations:
    """全てのCSV操作を統一"""
    @staticmethod
    def read_csv(path: Path, encoding: str = 'utf-8') -> List[Dict]:
        pass
    
    @staticmethod
    def write_csv(path: Path, data: List[Dict], encoding: str = 'utf-8'):
        pass
```

#### 3.3 設定の外部化

```python
# src/config/settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    # 環境変数から読み込み
    MAX_ITERATIONS: int = 100
    CONSTRAINT_PRIORITIES: Dict[str, str] = {
        "teacher_conflict": "CRITICAL",
        "daily_duplicate": "HIGH",
        "gym_usage": "MEDIUM"
    }
    
    class Config:
        env_file = ".env"
```

### 🚀 Phase 4: 長期改善（2ヶ月目）

#### 4.1 プラグインアーキテクチャ

```python
# src/plugins/constraint_plugin.py
class ConstraintPlugin(ABC):
    @abstractmethod
    def check(self, schedule: Schedule) -> List[Violation]:
        pass
    
    @abstractmethod
    def get_priority(self) -> ConstraintPriority:
        pass

# 制約の動的ロード
constraint_loader = PluginLoader("constraints")
constraints = constraint_loader.load_all()
```

#### 4.2 イベント駆動アーキテクチャ

```python
# src/events/schedule_events.py
class ScheduleEvent:
    ASSIGNMENT_ADDED = "assignment.added"
    CONSTRAINT_VIOLATED = "constraint.violated"
    OPTIMIZATION_COMPLETE = "optimization.complete"

# イベントハンドラー
@event_handler(ScheduleEvent.CONSTRAINT_VIOLATED)
def handle_violation(event: Event):
    logger.warning(f"Constraint violated: {event.data}")
```

#### 4.3 性能最適化

```python
# src/performance/cache_manager.py
class CacheManager:
    def __init__(self):
        self._constraint_cache = LRUCache(maxsize=1000)
        self._teacher_cache = TTLCache(maxsize=500, ttl=300)
    
    @cache_result
    def get_teacher_availability(self, teacher: str, day: str, period: int):
        # キャッシュされた結果を返す
        pass
```

## 📈 期待される成果

### 定量的成果
- **ファイル数**: 502 → 150 (**70%削減**)
- **最大ファイルサイズ**: 1282行 → 300行 (**77%削減**)
- **重複コード**: 25% → 5% (**80%削減**)
- **テストカバレッジ**: 不明 → 80%以上

### 定性的成果
- **保守性**: 新機能追加が容易に
- **可読性**: コードの意図が明確に
- **拡張性**: プラグインによる機能追加
- **性能**: キャッシュとJITによる高速化
- **品質**: 自動テストによる回帰防止

## 🛠️ 実装優先順位

1. **最優先**: Phase 1.1 - 古いジェネレーターのアーカイブ
2. **高優先**: Phase 2.1 - アーキテクチャ違反の修正
3. **中優先**: Phase 3.2 - 共通パターンの抽出
4. **低優先**: Phase 4.1 - プラグインアーキテクチャ

## 📝 実装チェックリスト

- [ ] archive/ディレクトリの作成
- [ ] 古いジェネレーター（v2-v13）のアーカイブ
- [ ] 重複分析スクリプトの統合
- [ ] インターフェースの定義
- [ ] DIコンテナの実装
- [ ] サービスレイヤーの再配置
- [ ] 大きなファイルの分割
- [ ] 共通ユーティリティの抽出
- [ ] 設定の外部化
- [ ] テストの再編成
- [ ] ドキュメントの更新

## 🎯 成功基準

1. **新しい制約追加が1ファイルの変更で可能**
2. **全てのテストが5分以内に完了**
3. **コードレビューで指摘される問題が50%減少**
4. **新規開発者が1日でコードベースを理解できる**

## 🔄 継続的改善

毎週金曜日に以下を実施：
- コード品質メトリクスの測定
- リファクタリング進捗の確認
- 新たな技術的負債の特定
- 改善計画の更新

---

*このリファクタリング計画は生きたドキュメントです。進捗に応じて更新してください。*
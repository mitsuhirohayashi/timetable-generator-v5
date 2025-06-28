# Ultrathink制約違反学習システム ガイド

## 概要

Ultrathink学習システムは、時間割生成時に発生する制約違反のパターンを機械学習的に分析し、将来の生成時に同じ違反を回避するための高度な学習システムです。

## 主な機能

### 1. 違反パターン分析
- **特徴抽出**: 時間帯、クラス、科目、教師の組み合わせから違反パターンを抽出
- **頻度分析**: 違反の発生頻度と重要度を計算
- **クラスタリング**: DBSCAN アルゴリズムによる類似パターンのグループ化

### 2. 学習データ管理
- **永続化**: 違反履歴をJSONファイルに保存（`data/learning/violation_patterns.json`）
- **世代管理**: 各生成世代ごとの違反推移を記録
- **信頼度スコア**: パターンの信頼性を動的に評価

### 3. 回避戦略生成
- **自動ルール生成**: 学習したパターンから回避ルールを自動生成
- **優先度ランキング**: 効果的な戦略を優先度付きで管理
- **予防的チェック**: 配置前に違反リスクを予測

### 4. 統計分析
- **違反タイプ別統計**: 各種違反の発生頻度を分析
- **時間帯別傾向**: 曜日・時限ごとの違反傾向を把握
- **教師・クラス別分析**: 問題が多い教師やクラスを特定

### 5. 自動適用
- **リアルタイム予測**: 生成時に違反確率を即座に計算
- **代替案提案**: 高リスクな配置に対する代替案を自動提案
- **継続的改善**: 実行のたびにシステムが賢くなる

## システム構成

```
src/domain/services/ultrathink/
├── __init__.py
├── violation_pattern_analyzer.py    # パターン分析エンジン
└── constraint_violation_learning_system.py  # 学習システム本体

src/application/services/
└── ultrathink_learning_adapter.py  # 統合アダプター
```

## 使用方法

### 1. 基本的な使用方法

```python
from src.application.services.ultrathink_learning_adapter import UltrathinkLearningAdapter
from src.infrastructure.repositories import CSVRepository
from src.infrastructure.config import PathConfig

# 初期化
path_config = PathConfig()
repository = CSVRepository(path_config)
school = repository.load_school()
schedule = repository.load_schedule()

# 学習アダプターの作成
adapter = UltrathinkLearningAdapter()

# 生成前分析
pre_analysis = adapter.pre_generation_analysis(schedule, school)
print(f"High-risk slots: {len(pre_analysis['high_risk_slots'])}")

# 制約違反から学習
violations = check_all_constraints(schedule, school)  # 実際の制約チェック
post_result = adapter.post_generation_learning(violations, schedule, school)
print(f"Improvement rate: {post_result['improvement_rate']:.2%}")
```

### 2. スケジュール生成サービスとの統合

```python
class ScheduleGenerationService:
    def __init__(self, ...):
        # 既存の初期化コード
        self.learning_adapter = UltrathinkLearningAdapter()
    
    def generate_schedule(self, school, initial_schedule=None):
        # 生成前の学習結果を適用
        if initial_schedule:
            pre_analysis = self.learning_adapter.pre_generation_analysis(
                initial_schedule, school
            )
            # 高リスクスロットを避けて生成
            
        # 通常の生成処理
        schedule = self._generate_with_csp(school)
        
        # 生成後の学習
        violations = self.constraint_system.check_all_constraints(schedule)
        self.learning_adapter.post_generation_learning(violations, schedule, school)
        
        return schedule
```

### 3. CLI統合例

```python
# main.py に追加
@click.option('--enable-learning', is_flag=True, help='Enable Ultrathink learning system')
def generate(enable_learning, ...):
    if enable_learning:
        # 学習システムを有効化
        learning_adapter = UltrathinkLearningAdapter()
        # 生成前後で学習を実行
```

## 学習データの構造

### violation_patterns.json
```json
{
  "patterns": {
    "TeacherConflict_1_4_2-1_数学_井上": {
      "pattern_id": "abc12345",
      "features": [...],
      "frequency": 5,
      "confidence_score": 0.85,
      "first_seen": "2025-06-20T10:00:00",
      "last_seen": "2025-06-20T15:30:00"
    }
  },
  "statistics": {
    "total_violations": 150,
    "unique_patterns": 23,
    "violation_types": {...}
  }
}
```

### learning_state.json
```json
{
  "generation_count": 42,
  "total_violations": 315,
  "avoided_violations": 127,
  "avoidance_rate": 0.403,
  "strategy_database": {...},
  "generation_history": [...]
}
```

## 回避戦略の例

### 1. 時間帯回避戦略
```json
{
  "strategy_id": "avoid_time_abc123",
  "description": "Avoid 数学 at day 1, period 4 for 2-1",
  "conditions": {
    "day": 1,
    "period": 4,
    "class_id": "2-1",
    "subject": "数学"
  },
  "actions": [
    {"type": "avoid_assignment", "params": {"alternative_periods": [[1, 2], [1, 3]]}}
  ]
}
```

### 2. 教師競合回避戦略
```json
{
  "strategy_id": "avoid_teacher_conflict_def456",
  "description": "Avoid teacher 井上 conflicts",
  "conditions": {
    "teacher": "井上",
    "violation_type": "TeacherConflict"
  },
  "actions": [
    {"type": "check_teacher_availability"},
    {"type": "use_alternative_teacher"}
  ]
}
```

### 3. 交流学級ルール戦略
```json
{
  "strategy_id": "ensure_jiritsu_rule_ghi789",
  "description": "Ensure parent class has Math/English when exchange class has Jiritsu",
  "conditions": {
    "violation_type": "JiritsuRule",
    "exchange_class": "3-6"
  },
  "actions": [
    {"type": "check_parent_class_subject"},
    {"type": "swap_to_allowed_subject"}
  ]
}
```

## デモンストレーション

システムの動作を確認するには、以下のコマンドを実行：

```bash
python demo_ultrathink_learning.py
```

このデモでは以下を実演します：
1. 学習システムの初期化
2. 生成前の違反リスク分析
3. サンプル違反からの学習
4. 統計情報の表示
5. 違反ヒートマップの可視化
6. 効果的な戦略の表示
7. 新しい制約の提案

## パフォーマンスとスケーラビリティ

- **メモリ効率**: 最新100世代の履歴のみ保持
- **処理速度**: 違反分析は通常1秒以内に完了
- **スケーラビリティ**: 数千のパターンを効率的に管理可能

## トラブルシューティング

### scikit-learn がインストールされていない
```bash
pip install numpy scikit-learn
```

### 学習データが読み込めない
- `data/learning` ディレクトリが存在するか確認
- ファイルの権限を確認
- JSONファイルの形式が正しいか確認

### 違反が減らない
- 十分な学習データが蓄積されているか確認（最低10世代推奨）
- 高頻度パターンのレポートを確認
- 戦略の成功率を確認し、効果の低い戦略を見直す

## 今後の拡張予定

1. **深層学習モデルの導入**: より複雑なパターンの学習
2. **強化学習**: 戦略の自動最適化
3. **可視化ダッシュボード**: Webベースの分析UI
4. **分散学習**: 複数の学校間での学習データ共有
5. **説明可能AI**: 違反予測の理由を明確に提示

## まとめ

Ultrathink学習システムは、時間割生成の品質を継続的に改善する強力なツールです。システムを使用すればするほど、より良い時間割が生成されるようになります。制約違反のパターンを自動的に学習し、予防的な対策を提案することで、手動での調整作業を大幅に削減できます。
# 時間割生成プログラムの根本的改良

## 概要

時間割生成プログラムの制約違反を最小化するため、以下の4つのコンポーネントを根本的に改良しました。

## 1. 改良版制約検証サービス（ConstraintValidatorImproved）

### 主な改良点
- **キャッシング機能**: 頻繁にチェックされる制約結果をメモリにキャッシュ
- **学習ルール統合**: QandAシステムから学習したルール（井上先生の火曜5限など）を自動適用
- **効率的なチェック**: 重複した制約チェックを削減

### キャッシュの仕組み
```python
# 3種類のキャッシュを実装
_cache_teacher_availability  # 教師の利用可能性
_cache_daily_counts         # 日内の科目カウント
_cache_validation_results   # 総合的な検証結果
```

## 2. 改良版優先度ベース配置サービス（PriorityBasedPlacementServiceImproved）

### 配置戦略の改善
1. **配置難易度の計算**
   - 残り必要時間数
   - 配置可能スロット数
   - 教師の制約
   - 科目の重要度

2. **バックトラッキング**
   - 配置失敗時に他の授業を移動して再試行
   - 最大限の制約充足を目指す

3. **段階的制約緩和**
   - strict（厳密）→ normal（通常）→ relaxed（緩和）の順で試行
   - どうしても配置できない場合のみ制約を緩める

## 3. 改良版CSPオーケストレーター（CSPOrchestratorImproved）

### 6フェーズ管理
1. **Phase 1**: 初期設定と保護
2. **Phase 2**: 自立活動の配置
3. **Phase 3**: 5組の同期配置
4. **Phase 4**: 交流学級の早期同期
5. **Phase 5**: 通常教科の配置（優先度ベース）
6. **Phase 6**: 最適化

### 統計情報の詳細化
- 各フェーズの成果を詳細に記録
- 制約違反の種類別集計
- 最適化の効果測定

## 4. 統合サービス（ScheduleGenerationServiceImproved）

### 改良版コンポーネントの統合
- 全ての改良版コンポーネントを統合
- エラーハンドリングの強化
- 詳細なログ出力

## 導入方法

### 1. 既存のインポートを変更

```python
# main.pyまたは使用箇所で
from src.application.services.schedule_generation_service_improved import ScheduleGenerationServiceImproved

# サービスの初期化
generation_service = ScheduleGenerationServiceImproved()

# スケジュール生成
schedule = generation_service.generate_schedule(
    school=school,
    initial_schedule=initial_schedule,
    parameters={
        'max_iterations': 200,
        'enable_optimization': True
    }
)
```

### 2. DIコンテナの更新（オプション）

既存のサービスを完全に置き換える場合：

```python
# di_container.pyで
def get_schedule_generation_service():
    return ScheduleGenerationServiceImproved()
```

## 期待される効果

1. **制約違反の大幅削減**
   - 配置前チェックの強化により、そもそも違反が発生しにくい
   - キャッシングにより高速化

2. **井上先生問題の解決**
   - 学習ルールの自動適用により、火曜5限は最大1クラスに制限

3. **日内重複の防止**
   - 優先度ベース配置により、重複を事前に回避

4. **体育館使用の最適化**
   - 5組の合同体育を正しく認識
   - 競合を事前に検出

## パフォーマンスへの影響

- **初回実行**: やや遅くなる可能性（制約チェックの強化のため）
- **2回目以降**: キャッシングにより高速化
- **メモリ使用**: キャッシュのため若干増加

## トラブルシューティング

### キャッシュのクリア
制約条件が変更された場合：
```python
constraint_validator.clear_cache()
```

### デバッグモード
詳細なログを出力：
```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## 今後の拡張

1. **機械学習の導入**
   - 過去の成功パターンを学習
   - より効率的な配置順序の予測

2. **並列処理**
   - 複数のクラスを並行して処理
   - マルチコアCPUの活用

3. **インクリメンタル生成**
   - 部分的な変更のみを再生成
   - 大規模な学校への対応
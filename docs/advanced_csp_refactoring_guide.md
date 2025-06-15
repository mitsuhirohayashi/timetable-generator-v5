# AdvancedCSPScheduleGenerator リファクタリングガイド

## 概要

AdvancedCSPScheduleGenerator（717行）は、学校時間割生成システムの中核となるCSPアルゴリズムを実装していますが、責務が過大で保守性に問題があります。本ガイドでは、Clean Architectureの原則に基づいた段階的なリファクタリング方法を提示します。

## 現状の問題点

### 1. 単一責任原則（SRP）違反
- 自立活動配置、5組同期、通常配置、最適化など複数の責務を持つ
- 717行という巨大なクラスサイズ
- メソッド数が多く、凝集度が低い

### 2. 開放閉鎖原則（OCP）違反
- 新しい制約や配置戦略の追加が困難
- ハードコードされた設定値（一部は外部化済み）
- 拡張ポイントが不明確

### 3. 依存性逆転原則（DIP）違反
- 具体的な実装に直接依存
- テスタビリティが低い
- モックを使用した単体テストが困難

### 4. テストカバレッジ不足
- 統合テストのみで単体テストが不足
- 各責務の独立したテストが困難

## リファクタリング方針

### フェーズ1: 責務の分離（現在完了）

```
AdvancedCSPScheduleGenerator
├── JiritsuPlacementService（自立活動配置）
├── Grade5SynchronizationService（5組同期）
├── RegularSubjectPlacementService（通常教科配置）
├── LocalSearchOptimizer（局所探索最適化）
├── ScheduleEvaluator（スケジュール評価）
└── CSPOrchestrator（調整役）
```

### フェーズ2: インターフェースの導入

各サービスに対応するインターフェースを定義し、実装を差し替え可能にします。

### フェーズ3: ファクトリーパターンの導入

サービスの生成をファクトリーに委譲し、設定に基づいて適切な実装を選択できるようにします。

## 詳細設計

### 1. JiritsuPlacementService

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

class JiritsuPlacementService(ABC):
    """自立活動配置サービスのインターフェース"""
    
    @abstractmethod
    def analyze_requirements(self, school: School, schedule: Schedule) -> List[JiritsuRequirement]:
        """自立活動要件を分析"""
        pass
    
    @abstractmethod
    def place_activities(self, schedule: Schedule, school: School, 
                        requirements: List[JiritsuRequirement]) -> int:
        """自立活動を配置し、配置数を返す"""
        pass
```

**責務**:
- 自立活動要件の分析
- 自立活動と親学級の数学/英語の同時配置
- バックトラッキングによる最適配置

**設定項目**:
- jiritsu_subjects: 自立活動系教科リスト
- parent_subjects: 親学級に配置する教科（数、英）
- max_jiritsu_per_day: 1日あたりの最大自立活動数

### 2. Grade5SynchronizationService

```python
class Grade5SynchronizationService(ABC):
    """5組同期サービスのインターフェース"""
    
    @abstractmethod
    def get_common_subjects(self, school: School, grade5_classes: List[ClassReference]) 
                          -> Dict[Subject, int]:
        """共通教科と必要時間数を取得"""
        pass
    
    @abstractmethod
    def synchronize_placement(self, schedule: Schedule, school: School) -> int:
        """5組の同期配置を実行し、配置数を返す"""
        pass
```

**責務**:
- 5組（1-5, 2-5, 3-5）の共通教科識別
- 同一時限への同期配置
- 体育以外の教科の同期

**設定項目**:
- grade5_classes: 5組クラスリスト
- excluded_sync_subjects: 同期から除外する教科

### 3. RegularSubjectPlacementService

```python
class RegularSubjectPlacementService(ABC):
    """通常教科配置サービスのインターフェース"""
    
    @abstractmethod
    def place_subjects(self, schedule: Schedule, school: School) -> int:
        """通常教科を配置し、配置数を返す"""
        pass
    
    @abstractmethod
    def find_best_slot(self, schedule: Schedule, school: School,
                      class_ref: ClassReference, subject: Subject,
                      teacher: Teacher) -> Optional[TimeSlot]:
        """最適なスロットを探索"""
        pass
```

**責務**:
- 通常クラス（5組、6組、7組以外）の教科配置
- 標準時数に基づく配置
- 制約を考慮した最適スロット選択

### 4. LocalSearchOptimizer

```python
class LocalSearchOptimizer(ABC):
    """局所探索最適化のインターフェース"""
    
    @abstractmethod
    def optimize(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement],
                max_iterations: int) -> OptimizationResult:
        """局所探索による最適化を実行"""
        pass
```

**責務**:
- ランダムな授業交換による改善
- 制約違反の解消
- 教員負荷の平準化

**設定項目**:
- max_iterations: 最大反復回数
- no_improvement_threshold: 改善なし終了閾値
- swap_probability: 交換確率

### 5. ScheduleEvaluator

```python
class ScheduleEvaluator(ABC):
    """スケジュール評価のインターフェース"""
    
    @abstractmethod
    def evaluate(self, schedule: Schedule, school: School,
                jiritsu_requirements: List[JiritsuRequirement]) -> float:
        """スケジュールの品質を評価（低いほど良い）"""
        pass
```

**責務**:
- 自立活動制約違反の評価
- その他制約違反の評価
- 教員負荷バランスの評価

**評価重み設定**:
- jiritsu_violation_weight: 1000
- constraint_violation_weight: 100
- teacher_load_variance_weight: 0.01

### 6. CSPOrchestrator

```python
class CSPOrchestrator:
    """CSPアルゴリズムの調整役"""
    
    def __init__(self, 
                 jiritsu_service: JiritsuPlacementService,
                 grade5_service: Grade5SynchronizationService,
                 regular_service: RegularSubjectPlacementService,
                 optimizer: LocalSearchOptimizer,
                 evaluator: ScheduleEvaluator,
                 config: AdvancedCSPConfig):
        self.jiritsu_service = jiritsu_service
        self.grade5_service = grade5_service
        self.regular_service = regular_service
        self.optimizer = optimizer
        self.evaluator = evaluator
        self.config = config
    
    def generate(self, school: School, initial_schedule: Optional[Schedule] = None) -> Schedule:
        """CSPアプローチでスケジュールを生成"""
        # 各サービスを順番に実行
        pass
```

## リファクタリング手順

### ステップ1: インターフェースの定義
```bash
src/domain/services/interfaces/
├── jiritsu_placement_service.py
├── grade5_synchronization_service.py
├── regular_subject_placement_service.py
├── local_search_optimizer.py
└── schedule_evaluator.py
```

### ステップ2: 具体的な実装の分離
```bash
src/domain/services/implementations/
├── backtrack_jiritsu_placement_service.py
├── synchronized_grade5_service.py
├── greedy_subject_placement_service.py
├── random_swap_optimizer.py
└── weighted_schedule_evaluator.py
```

### ステップ3: ファクトリーの実装
```python
class CSPServiceFactory:
    """CSPサービスのファクトリー"""
    
    @staticmethod
    def create_services(config: AdvancedCSPConfig) -> Dict[str, Any]:
        """設定に基づいてサービスを生成"""
        return {
            'jiritsu_service': BacktrackJiritsuPlacementService(config),
            'grade5_service': SynchronizedGrade5Service(config),
            'regular_service': GreedySubjectPlacementService(config),
            'optimizer': RandomSwapOptimizer(config),
            'evaluator': WeightedScheduleEvaluator(config)
        }
```

### ステップ4: 既存コードの移行
1. 各メソッドを対応するサービスクラスに移動
2. 共通ユーティリティメソッドを基底クラスに抽出
3. 設定値をconfigオブジェクトから取得するよう変更

### ステップ5: テストの追加
```python
# 各サービスの単体テスト
class TestJiritsuPlacementService(TestCase):
    def test_analyze_requirements(self):
        # 要件分析のテスト
        pass
    
    def test_place_activities(self):
        # 配置ロジックのテスト
        pass

# 統合テスト
class TestCSPOrchestrator(TestCase):
    def test_full_generation(self):
        # 全体フローのテスト
        pass
```

## 期待される効果

### 1. 保守性の向上
- 各サービスが単一の責務を持つ
- 変更の影響範囲が限定的
- コードの理解が容易

### 2. テスタビリティの向上
- 各サービスを独立してテスト可能
- モックを使用した単体テストが容易
- エッジケースのテストが簡単

### 3. 拡張性の向上
- 新しい配置戦略の追加が容易
- 既存コードへの影響を最小限に
- プラグイン的な機能追加が可能

### 4. パフォーマンスの最適化
- 各サービスを独立して最適化可能
- 並列処理の導入が容易
- ボトルネックの特定が簡単

## 移行計画

### Phase 1（1週間）
- インターフェースの定義と基本実装
- 既存のテストが通ることを確認

### Phase 2（1週間）
- 各サービスの詳細実装
- 単体テストの追加

### Phase 3（3日）
- 統合とパフォーマンステスト
- ドキュメントの更新

### Phase 4（2日）
- 本番環境での検証
- 完全移行

## 注意事項

1. **後方互換性の維持**: 既存のAPIは維持し、内部実装のみを変更
2. **段階的移行**: 一度にすべてを変更せず、サービスごとに移行
3. **十分なテスト**: 各段階で既存のテストがすべてパスすることを確認
4. **パフォーマンス監視**: リファクタリング前後でパフォーマンスが劣化していないことを確認

## まとめ

このリファクタリングにより、AdvancedCSPScheduleGeneratorは保守性、テスタビリティ、拡張性が大幅に向上します。各サービスが独立して動作するため、将来的な機能追加や最適化も容易になります。
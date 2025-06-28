# UltraOptimized時間割生成システム - クイックスタートガイド

## 概要
このガイドでは、最適化された時間割生成システムの使用方法を説明します。

## 基本的な使用方法

### 1. 最もシンプルな使用方法（推奨）
```bash
# 自動最適化で時間割を生成
python3 main.py generate --use-ultrathink
```

このコマンドで：
- システムが環境を自動分析
- 最適な設定を自動選択
- 高品質な時間割を生成

### 2. 手動設定を使用する場合
```python
from src.domain.services.ultrathink.ultra_optimized_schedule_generator import (
    UltraOptimizedScheduleGenerator,
    UltraOptimizationConfig,
    OptimizationLevel
)

# 設定を手動で作成
config = UltraOptimizationConfig(
    optimization_level=OptimizationLevel.QUALITY,
    enable_parallel_processing=True,
    enable_teacher_satisfaction=True,
    enable_violation_learning=True,
    max_workers=8,
    beam_width=15
)

# 生成器を作成
generator = UltraOptimizedScheduleGenerator(config)

# 時間割を生成
result = generator.generate(school, initial_schedule, followup_data)
```

### 3. 自動最適化をプログラムで使用
```python
# 自動最適化を使用して生成器を作成
generator = UltraOptimizedScheduleGenerator.create_with_auto_optimization(
    school=school,
    initial_schedule=initial_schedule
)

# 時間割を生成
result = generator.generate(school, initial_schedule, followup_data)
```

## 最適化レベル

### FAST（高速モード）
- 実行時間: 3秒以内
- 用途: プロトタイピング、テスト
- 品質: 良好

### BALANCED（バランスモード）
- 実行時間: 5秒以内
- 用途: 通常の使用
- 品質: 高品質

### QUALITY（品質重視モード）
- 実行時間: 10秒以内
- 用途: 本番環境
- 品質: 最高品質

### EXTREME（極限最適化）
- 実行時間: 制限なし
- 用途: 研究、ベンチマーク
- 品質: 理論的最適解

## 主要機能

### 教師満足度最適化
```python
config.enable_teacher_satisfaction = True
```
- 教師の時間帯選好を考慮
- 連続授業の最適化
- クラスとの相性を考慮

### 制約違反パターン学習
```python
config.enable_violation_learning = True
```
- 頻出する違反パターンを学習
- 予防的ルールを自動生成
- 実行のたびに賢くなる

### 並列処理
```python
config.enable_parallel_processing = True
config.max_workers = 16  # CPU数に応じて調整
```
- マルチコアCPUを完全活用
- 大規模問題でも高速処理

### テスト期間保護
```python
config.enable_test_period_protection = True
```
- テスト期間中の授業を保護
- Follow-up.csvから自動検出

## パフォーマンスのヒント

### 1. 初回実行時
- システムプロファイルが作成される（約1秒）
- 2回目以降はキャッシュされ高速化

### 2. 大規模学校の場合
- 自動最適化が並列度を最大化
- メモリが十分あることを確認

### 3. 低スペックマシンの場合
- 自動最適化が適切に調整
- FASTモードが自動選択される

## トラブルシューティング

### Q: メモリ不足エラーが出る
A: 自動最適化がメモリを考慮して設定を調整します。手動設定の場合は：
```python
config.cache_size_mb = 100  # キャッシュサイズを削減
config.enable_parallel_processing = False  # 並列処理を無効化
```

### Q: 実行が遅い
A: 最新版では10-25倍高速化されています。それでも遅い場合：
```python
config.optimization_level = OptimizationLevel.FAST
```

### Q: 制約違反が残る
A: QUALITYモードまたはEXTREMEモードを使用：
```python
config.optimization_level = OptimizationLevel.QUALITY
config.target_violations = 0
```

## デモの実行

自動最適化の動作を確認：
```bash
python3 demo_auto_optimization.py
```

## 詳細情報

- [リファクタリング完了報告](refactoring_final_report_complete.md)
- [自動最適化の詳細](phase5_auto_optimization_complete.md)
- [アーキテクチャ設計](phase1_architecture_optimization_complete.md)
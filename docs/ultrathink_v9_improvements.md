# Ultrathink Perfect Generator V9 - 教師割り当て完全版

## 問題の分析

V7-V8では教師の重複が多数発生していました。原因は：

1. **教師割り当ての誤解**
   - システムは「科目→教師」の単純なマッピングを想定
   - 実際は「クラス＋科目→教師」の複雑なマッピング

2. **具体例**
   - 国語：1年は寺田先生、2-3年は小野塚先生
   - 数学：学年ごとに異なる教師（1年梶永、2年井上、3年森山）
   - 道徳・学活・総合・YT：各クラスの担任が担当

3. **既存配置の問題**
   - input.csvには科目名のみで教師情報なし
   - 教師の利用状況を把握できない

## V9での解決策

### 1. 教師情報の復元
```python
def _restore_teacher_assignments(self, schedule: Schedule, school: School) -> None:
    """既存配置から教師情報を復元"""
    for time_slot, assignment in list(schedule.get_all_assignments()):
        if assignment.teacher is None:
            # schoolの情報から正しい教師を取得
            teacher = school.get_assigned_teacher(assignment.subject, assignment.class_ref)
```

### 2. クラス別教師の取得
```python
def _get_teacher_for_class_subject(self, school: School, class_ref: ClassRef, subject: str) -> Optional[Teacher]:
    """クラスと科目の組み合わせから正しい教師を取得"""
    subject_obj = Subject(subject)
    teacher = school.get_assigned_teacher(subject_obj, class_ref)
```

### 3. 配置時の厳密なチェック
- 科目の配置前に、そのクラス・科目の正しい教師を取得
- 教師の利用可能性を事前にチェック
- 利用不可な場合は配置をスキップ

## 期待される効果

1. **教師重複の解消**
   - 同じ時間に同じ教師が複数クラスを担当する問題を防止
   - 各クラスに正しい教師が割り当てられる

2. **正確な時間割生成**
   - teacher_subject_mapping.csvの情報を完全に活用
   - 学年別、クラス別の教師割り当てを正確に反映

3. **デバッグ情報の充実**
   - 教師の割り当て状況をログに出力
   - 問題の特定と修正が容易に

## 実装のポイント

### Schoolオブジェクトの活用
```python
# クラスと科目から教師を取得
teacher = school.get_assigned_teacher(subject, class_ref)
```

この機能により、teacher_subject_mapping.csvで定義された複雑な教師割り当てルールを正確に反映できます。

### 統計情報の追加
- `teacher_assignments_restored`: 復元された教師情報の数
- `teacher_conflicts_avoided`: 回避された教師重複の数

これにより、V9の効果を定量的に確認できます。
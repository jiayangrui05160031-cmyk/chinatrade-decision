# Pull Request Template

## 变更说明

<!-- 简述本次 PR 解决什么 / 加什么 -->

## 关联 Issue

<!-- 关联的 issue 编号,例: Fixes #123 -->

## 改动类型

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactor (no functional change)
- [ ] CI / Build / Tooling
- [ ] Data update (HS 表 / 政策快照)

## 测试

- [ ] 现有测试通过 (`pytest`)
- [ ] 新增/修改的代码有对应测试
- [ ] 覆盖率维持 ≥ 80%
- [ ] `ruff check` 0 警告
- [ ] `mypy src` 0 错误

## 数据源核查 (数据类 PR 必填)

- [ ] 数据来源官方/半官方
- [ ] 每条数据带 `source_url`
- [ ] 每条数据带 `crawled_at` 时间戳
- [ ] 没有凭印象/经验捏造数据

## 风险评估

<!-- 改动对决策卡正确性的影响 -->

## 截图 / 输出示例 (UI/数据类 PR)

<!-- 如有,贴上;如无,删掉这一节 -->

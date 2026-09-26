<!-- 机器生成，请勿手改：python scripts/build_acceptance_report.py -->

# 验收报告（最近一次实跑）

- 生成时间：2026-09-26 22:49:20（Python 3.12.0）
- 后端应用版本：`0.5.0`（来源 `backend/app/main.py`，本报告是文档引用版本号的唯一来源）
- 结果：**18/18 个脚本通过**，跳过 6 个（原因见下表）

> 文档里**不许**手抄下表的数字；只能写「见 `validation/acceptance_latest.md`」。
> `scripts/verify_docs.py` 会核对这条纪律。

| 脚本 | 结果 | 合计 | 证据来源 | 备注 |
|---|---|---|---|---|
| `scripts/verify_sprint0.py` | ✅ exit 0 | **14/14** | 合计 | — |
| `scripts/test_business_graph.py` | ✅ exit 0 | **161/161** | 逐行相加 | 该脚本不打印总计，报告里的合计由各项目 `N/M 项通过` 逐行相加 |
| `scripts/test_design_rubric.py` | ✅ exit 0 | **90/90** | 结果 | — |
| `scripts/test_design_seed.py` | ✅ exit 0 | **33/33** | 小结 | — |
| `scripts/test_teaching_coverage.py` | ✅ exit 0 | **22/22** | 合计 | — |
| `scripts/test_teaching_card_coverage.py` | ✅ exit 0 | **40/40** | 合计 | — |
| `scripts/test_training_questions.py` | ✅ exit 0 | **53/53** | 结果 | — |
| `scripts/test_logic_platform.py` | ✅ exit 0 | **28/28** | 标记计数（[PASS]/[FAIL] 行） | 不加 --live：现场重跑分析很慢，且它不是验收口径 |
| `scripts/check_determinism.py` | ✅ exit 0 | — | — | — |
| `scripts/check_determinism.py --cross-process` | ✅ exit 0 | — | — | 同进程双跑查不出 `set` 迭代顺序那一类问题（§19.2 ⑳） |
| `scripts/audit_hardcoding.py --include-frontend` | ✅ exit 0 | — | — | `engine_scanned_files=62`、`engine_hits=0`、`frontend_scanned_files=52`、`frontend_hits=0` |
| `scripts/validate_contract.py --project sample_projects/lab_safety_assistant` | ✅ exit 0 | **15/15** | 标记计数（[PASS]/[FAIL] 行） | — |
| `scripts/validate_contract.py --project validation/python_dotenv` | ✅ exit 0 | **15/15** | 标记计数（[PASS]/[FAIL] 行） | — |
| `scripts/test_logic_platform_api.py` | ✅ exit 0 | **37/37** | 标记计数（[PASS]/[FAIL] 行） | 需要 8000 端口上的 uvicorn；且改过后端代码必须先重启（§19.5） |
| `node scripts/browser_clickthrough.mjs --project lab_safety_assistant` | ✅ exit 0 | **109/109** | 合计 | 需要后端 + 走查 bundle（`.smoke-dist`，改了 .vue 必须重建，§19.5） |
| `node scripts/browser_clickthrough.mjs --project python_dotenv` | ✅ exit 0 | **109/109** | 合计 | 换一个真实第三方项目跑同一套断言：证明走查不是只对着自造样本能过 |
| `node scripts/browser_clickthrough.mjs --project lab_safety_assistant --offline` | ✅ exit 0 | **55/55** | 合计 | `--offline` 把 /api 指向死端口，验证离线降级与「如实报不可用」，不是在线路径的重复 |
| `node scripts/browser_clickthrough.mjs --project python_dotenv --offline` | ✅ exit 0 | **55/55** | 合计 | 离线快照按项目分目录，只跑一个项目会漏掉快照缺失 |

## 本次未跑（不是通过，也不是失败）

| 脚本 | 组 | 为什么没跑 |
|---|---|---|
| `scripts/validate_business_graph.py --output validation/business_graph_validation.md --json-output validation/business_graph_metrics.json --emit-review` | `manual` | ⚠️ --emit-review 会**覆盖**人工判定列（§20.3 ①：要重跑就先跑再填） |
| `scripts/graph_review_report.py` | `manual` | 判定列未填时**退出码 1 是验收语义**，不是失败运行（§0.3 注） |
| `scripts/export_domain_review_worksheet.py` | `manual` | 覆盖写 `validation/graph_review_worksheet.md` |
| `scripts/test_project_analyzer.py` | `order-trap` | 会重写 `frontend/public/demo/project_analysis.json`，跑完必须重跑产物脚本（§19.5） |
| `scripts/test_deep_analyzer.py` | `order-trap` | 与上一条同一类顺序陷阱 |
| `scripts/test_full_engine.py` | `order-trap` | 与上一条同一类顺序陷阱 |

## 怎么复现

```bash
python scripts/build_acceptance_report.py
python scripts/verify_docs.py     # 核对文档里的数字与本报告是否一致
```

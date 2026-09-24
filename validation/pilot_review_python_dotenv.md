# 试点核对纸 · `validation/python_dotenv`（一级域 6 行）

> 由 `python scripts/export_domain_review_worksheet.py --pilot validation/python_dotenv` 生成，**可重复执行、逐字节可复现**。

## 这份纸是干什么的（先读这三条）

1. **它不是正式统计。** 正式数字只认 `validation/business_graph_validation.md` 第 6 节填满后由 `scripts/graph_review_report.py` 算出来的那一份；本纸只有 `python_dotenv` 一个项目、且只做一级域。
2. **它的目的有三个**：① 校准「每行要花多久」，好推算 184 行的真实工期；
   ② 验证四个判定词在实际代码上好不好用（不好用就现在改口径，别等填完 184 行）；
   ③ **把发现的引擎问题记下来** —— 引擎还会改，但「哪里改得不对」这份清单不会作废。
3. **判定绑定 `source_hash`**，所以引擎一改、正式核对就得重做 —— 这正是把正式核对放到「引擎冻结之后」的理由（README §6.1 / §18 优先级 2）。

本纸对应的图谱：`validation/python_dotenv` ｜ `source_hash` = `sha256:1e0d7a1f50bb75f0c30e910eceb7bd35`
（**重跑本纸时看一眼这行**：哈希变了说明引擎/代码变过，之前的判断要重新审视。）

## 一、填判定（只有这 6 列要你写）

判定词只有四个：`正确` / `命名不当` / `划分错误` / `无法判定`（`无法判定` 是合法答案，不要为了填满而猜）。
**备注列写一句话理由** —— 它会在两处派上用场：答辩被追问时是答案，
汇总成「引擎问题清单」时是证据。

| domain_id | 系统命名 | 角色 | 置信度 | 人工判定 | 备注（一句话理由） |
|---|---|---|---|---|---|
| `d_atom` | Atom | `core` | `inferred` |  |  |
| `d_binding` | Binding | `core` | `inferred` |  |  |
| `d_cli` | 系统装配（cli） | `orchestrator` | `inferred-low` |  |  |
| `d_dot_env` | 系统装配（main） | `orchestrator` | `inferred` |  |  |
| `d_i_python_dot_env` | I Python Dot Env | `core` | `inferred` |  |  |
| `d_init` | 系统装配（__init__） | `orchestrator` | `inferred-low` |  |  |

> 每一行的判断材料在下面第二节（按 `domain_id` 一一对应）。

## 二、判断材料（每个域一张卡片）



### 1. `d_atom` · **Atom**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 4 个 ｜ 子能力点 1 个
- 聚类依据：`identifier_root=atom`（来自 Atom）、`identifier_root=literal`（来自 Literal）、`identifier_root=variable`（来自 Variable）、`identifier_root=variables`（来自 variables）、`merge=call_adjacent(2)`（域合并依据）、`merge=call_adjacent(7)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=same_file(7)`（域合并依据）
- 涉及文件：`variables.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_atom_query_general` | 查询/读取操作 | `query/` | `inferred` | `resolve` — `variables.py:26` ；`resolve` — `variables.py:44-45` ；`resolve` — `variables.py:64-67` ；`parse_variables` — `variables.py:70-86` |

### 2. `d_binding` · **Binding**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 6 个 ｜ 子能力点 7 个
- 聚类依据：`identifier_root=binding`（来自 Binding）、`identifier_root=error`（来自 Error）、`identifier_root=original`（来自 Original）、`identifier_root=parser`（来自 parser）、`identifier_root=position`（来自 Position）、`identifier_root=reader`（来自 Reader）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:parser(5)`（域合并依据）
- 涉及文件：`parser.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_binding_create_general` | 提交/创建操作 | `create/` | `inferred` | `make_regex` — `parser.py:14-15` |
| `c_d_binding_misc_unclassified` | 其他能力（待归类：advance、has_next、peek） | `misc/unclassified` | `inferred-low` | `advance` — `parser.py:62-64` ；`has_next` — `parser.py:77-78` ；`peek` — `parser.py:89-90` |
| `c_d_binding_query_general` | 查询/读取操作 | `query/` | `inferred` | `get_marked` — `parser.py:83-87` ；`read` — `parser.py:92-97` ；`read_regex` — `parser.py:99-104` ；`parse_binding` — `parser.py:144-178` ；`parse_stream` — `parser.py:181-184` |
| `c_d_binding_query_value` | 查询数据项 | `query/value` | `inferred` | `parse_key` — `parser.py:114-122` ；`parse_unquoted_value` — `parser.py:125-127` ；`parse_value` — `parser.py:130-141` |
| `c_d_binding_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `decode_escapes` — `parser.py:107-111` |
| `c_d_binding_transition_general` | 状态流转操作 | `transition/` | `inferred` | `start` — `parser.py:55-56` |
| `c_d_binding_update_general` | 更新/修改操作 | `update/` | `inferred` | `set` — `parser.py:58-60` ；`set_mark` — `parser.py:80-81` |

### 3. `d_cli` · **系统装配（cli）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 5 个
- 聚类依据：`identifier_root=cli`（来自 cli）、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`cli.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_cli_misc_config` | 配置相关操作 | `misc/config` | `inferred` | `enumerate_env` — `cli.py:24-35` |
| `c_d_cli_misc_file` | 文件相关操作 | `misc/file` | `inferred` | `stream_file` — `cli.py:68-80` |
| `c_d_cli_misc_unclassified` | 其他能力（待归类：cli、unset、run、run_command） | `misc/unclassified` | `inferred-low` | `cli` — `cli.py:62-64` ；`unset` — `cli.py:154-167` ；`run` — `cli.py:184-201` ；`run_command` — `cli.py:204-247` |
| `c_d_cli_query_general` | 查询/读取操作 | `query/` | `inferred` | `list_values` — `cli.py:93-109` ；`get` — `cli.py:137-148` |
| `c_d_cli_update_value` | 修改数据项 | `update/value` | `inferred` | `set_value` — `cli.py:116-131` |

### 4. `d_dot_env` · **系统装配（main）**

- 角色 `orchestrator` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_structural_role` ｜ 单元 2 个 ｜ 子能力点 8 个
- 聚类依据：`identifier_root=dot_env`（来自 DotEnv）、`identifier_root=main`（来自 main）、`merge=call_adjacent(2)`（域合并依据）、`merge=call_adjacent(6)`（域合并依据）、`merge=same_file(6)`（域合并依据）、`merge=shared_token:dot,env(1)`（域合并依据）
- 涉及文件：`main.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_dot_env_misc_file` | 文件相关操作 | `misc/file` | `inferred-low` | `_is_file_or_fifo` — `main.py:475-487` |
| `c_d_dot_env_misc_unclassified` | 其他能力（待归类：dict、rewrite、dotenv_values） | `misc/unclassified` | `inferred-low` | `dict` — `main.py:75-89` ；`rewrite` — `main.py:139-190` ；`dotenv_values` — `main.py:438-472` |
| `c_d_dot_env_misc_value` | 数据项相关操作 | `misc/value` | `inferred` | `unset_key` — `main.py:253-291` |
| `c_d_dot_env_notify_general` | 通知/告警操作 | `notify/` | `inferred` | `with_warn_for_invalid_lines` — `main.py:32-39` |
| `c_d_dot_env_query_general` | 查询/读取操作 | `query/` | `inferred` | `_load_dotenv_disabled` — `main.py:22-29` ；`_get_stream` — `main.py:61-73` ；`parse` — `main.py:91-95` ；`get` — `main.py:112-122` ；`resolve_variables` — `main.py:294-316` ；`_walk_to_root` — `main.py:319-334` ；`find_dotenv` — `main.py:337-385` ；`load_dotenv` — `main.py:388-435` ；`_is_file_or_fifo` — `main.py:475-487` |
| `c_d_dot_env_query_value` | 查询数据项 | `query/value` | `inferred` | `get_key` — `main.py:125-135` |
| `c_d_dot_env_update_general` | 更新/修改操作 | `update/` | `inferred` | `set_as_environment_variables` — `main.py:97-110` |
| `c_d_dot_env_update_value` | 修改数据项 | `update/value` | `inferred` | `set_key` — `main.py:193-250` |

### 5. `d_i_python_dot_env` · **I Python Dot Env**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 2 个
- 聚类依据：`identifier_root=i_python_dot_env`（来自 IPythonDotEnv）、`identifier_root=ipython`（来自 ipython）、`merge=call_adjacent(2)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:dot,env(1)`（域合并依据）、`merge=shared_token:ipython(5)`（域合并依据）
- 涉及文件：`ipython.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_i_python_dot_env_misc_unclassified` | 其他能力（待归类：dotenv） | `misc/unclassified` | `inferred-low` | `dotenv` — `ipython.py:34-45` |
| `c_d_i_python_dot_env_query_general` | 查询/读取操作 | `query/` | `inferred` | `load_ipython_extension` — `ipython.py:48-50` |

### 6. `d_init` · **系统装配（__init__）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 1 个
- 聚类依据：`identifier_root=init`（来自 __init__）、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`__init__.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_init_query_general` | 查询/读取操作 | `query/` | `inferred` | `load_ipython_extension` — `__init__.py:6-9` ；`get_cli_string` — `__init__.py:12-39` |


## 三、引擎问题清单（试点最值钱的产出）

判的过程中凡是让你犹豫、或者明显不对的地方，按这个格式记一行：

```text
| 现象（一句话） | 证据（domain_id / 能力点 / 文件:行） | 我期望它怎样 | 严重度 |
|---|---|---|---|
| 例：两个明显不同的业务被并成一个域 | d_xxx；成员 foo.py:12、bar.py:40 | 应该拆成两个域 | 高 |
```

**严重度只填三个值**：`高`（影响划分对不对）/ `中`（影响命名或粒度）/ `低`（观感问题）。

> 这份清单的意义：**引擎还会继续改，但「哪里改得不对」不会作废。**
> 正式核对（184 行）应该排在这些改动做完、引擎冻结之后。

# 业务图谱 · 域核对工作纸

> 由 `python scripts/export_domain_review_worksheet.py` 生成，**可重复执行、逐字节可复现**。

## 这张纸怎么用

1. 打开 `validation/business_graph_validation.md` 的第 6 节（那才是**填判定**的地方）；
2. 每判一个域之前，先在本纸里找到同一个 `domain_id`，看三样东西：
   **成员函数到底有哪些**（在哪个文件、第几行）、**聚类依据是什么**、**涉及哪些文件**；
3. 需要看真实代码时，用 `文件:行` 去 `validation/<project>/...` 里翻，
   或在前端「业务图谱」页签里点开证据（有行号跳转）；
4. 判定词只有四个：`正确` / `命名不当` / `划分错误` / `无法判定`
   （口径见 `business_graph_validation.md` 第 6 节；`无法判定` 是合法答案，不要为了填满而猜）。

> ⚠️ **本纸不填任何判定，也不改任何结论。** 它只是把判断材料摊开。
> ⚠️ 自造样本 `sample_projects/lab_safety_assistant` **刻意不在本纸里** ——
> 启发式规则就是照着它调的，它不能用来报告准确率（README §13.2）。

**信号名对照**（聚类依据里那些 `信号=取值`）：

- `call_community` — 调用图社区（调用密集的单元归到一起）
- `directory` — 所在目录 / 包名（只有目录足够小才配当域）
- `docstring` — 文件级中文 docstring（最强信号，等于作者原话）
- `identifier_root` — 类名 / 文件名的词根（真实第三方项目主要靠它）
- `merge` — 并查集合并动作（把若干单元并进同一个域）
- `shared_state` — 两个单元写同一个状态对象

## `validation/python_dotenv`

- 规模：域 **6** 个 / 功能点 **24** 个 / 级别 **L2** / 图谱状态 `needs_review`
- `source_hash`：`sha256:1e0d7a1f50bb75f0c30e910eceb7bd35`

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

---

## `validation/flask`

- 规模：域 **12** 个 / 功能点 **54** 个 / 级别 **L3** / 图谱状态 `needs_review`
- `source_hash`：`sha256:248d2db8b88150acb7db97027a9fdd36`

### 1. `d_app` · **App**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 21 个 ｜ 子能力点 15 个
- 聚类依据：`identifier_root=app`（来自 app（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=app`（来自 App（目录 src/flask/sansio 有 6 个文件，太大不宜整体当域））、`identifier_root=app`（来自 app（目录 src/flask/sansio 有 6 个文件，太大不宜整体当域））、`identifier_root=app_context`（来自 AppContext（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=app_ctx_globals`（来自 _AppCtxGlobals（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=blueprint`（来自 Blueprint（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=blueprint`（来自 Blueprint（目录 src/flask/sansio 有 6 个文件，太大不宜整体当域））、`identifier_root=blueprint_setup_state`（来自 BlueprintSetupState（目录 src/flask/sansio 有 6 个文件，太大不宜整体当域））、…共 28 条
- 涉及文件：`src/flask/app.py`、`src/flask/blueprints.py`、`src/flask/config.py`、`src/flask/ctx.py`、`src/flask/sansio/app.py`、`src/flask/sansio/blueprints.py`、`src/flask/sansio/scaffold.py`、`src/flask/templating.py`、`src/flask/testing.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_app_configure_general` | 配置/装配操作 | `configure/` | `inferred` | `_check_setup_finished` — `src/flask/sansio/app.py:410-420` ；`_check_setup_finished` — `src/flask/sansio/blueprints.py:213-221` ；`setupmethod` — `src/flask/sansio/scaffold.py:42-49` ；`_check_setup_finished` — `src/flask/sansio/scaffold.py:220-221` |
| `c_d_app_create_config` | 提交配置 | `create/config` | `inferred` | `make_config` — `src/flask/sansio/app.py:479-493` ；`add_template_filter` — `src/flask/sansio/app.py:699-711` ；`add_template_test` — `src/flask/sansio/app.py:756-770` ；`add_template_global` — `src/flask/sansio/app.py:810-824` |
| `c_d_app_create_general` | 提交/创建/删除/移除操作 | `create/` | `inferred` | `_make_timedelta` — `src/flask/app.py:74-78` ；`remove_ctx` — `src/flask/app.py:86-93` ；`add_ctx` — `src/flask/app.py:98-107` ；`open_resource` — `src/flask/app.py:415-446` ；`open_instance_resource` — `src/flask/app.py:448-468` ；`create_jinja_environment` — `src/flask/app.py:470-508` ；`create_url_adapter` — `src/flask/app.py:510-561` ；`update_template_context` — `src/flask/app.py:591-619` ；`make_shell_context` — `src/flask/app.py:621-631` ；`make_default_options_response` — `src/flask/app.py:1056-1066` ；`make_response` — `src/flask/app.py:1227-1367` ；`process_response` — `src/flask/app.py:1397-1421` ；`open_resource` — `src/flask/blueprints.py:104-128` ；`setdefault` — `src/flask/ctx.py:93-103` ；`_get_session` — `src/flask/ctx.py:381-393` ；`_make_timedelta` — `src/flask/sansio/app.py:52-56` ；`create_jinja_environment` — `src/flask/sansio/app.py:476-477` ；`make_aborter` — `src/flask/sansio/app.py:495-505` ；`create_global_jinja_loader` — `src/flask/sansio/app.py:520-531` ；`register_blueprint` — `src/flask/sansio/app.py:570-595` ；`add_url_rule` — `src/flask/sansio/app.py:605-661` ；`handle_url_build_error` — `src/flask/sansio/app.py:981-1013` ；`add_url_rule` — `src/flask/sansio/blueprints.py:87-116` ；`make_setup_state` — `src/flask/sansio/blueprints.py:246-253` ；`register_blueprint` — `src/flask/sansio/blueprints.py:256-271` ；`register` — `src/flask/sansio/blueprints.py:273-377` ；`_merge_blueprint_funcs` — `src/flask/sansio/blueprints.py:379-410` ；`add_url_rule` — `src/flask/sansio/blueprints.py:413-441` ；`add_app_template_filter` — `src/flask/sansio/blueprints.py:476-495` ；`add_app_template_test` — `src/flask/sansio/blueprints.py:532-553` ；`add_app_template_global` — `src/flask/sansio/blueprints.py:590-611` ；`_method_route` — `src/flask/sansio/scaffold.py:284-293` ；`delete` — `src/flask/sansio/scaffold.py:328-333` ；`patch` — `src/flask/sansio/scaffold.py:336-341` ；`add_url_rule` — `src/flask/sansio/scaffold.py:376-441` ；`register_error_handler` — `src/flask/sansio/scaffold.py:650-662` ；`_get_exc_class_and_code` — `src/flask/sansio/scaffold.py:665-706` ；`_endpoint_from_view_func` — `src/flask/sansio/scaffold.py:709-714` ；`_copy_environ` — `src/flask/testing.py:185-191` ；`_request_from_builder_args` — `src/flask/testing.py:193-202` ；`open` — `src/flask/testing.py:204-247` |
| `c_d_app_misc_config` | 配置相关操作 | `misc/config` | `inferred` | `from_prefixed_env` — `src/flask/config.py:126-185` ；`jinja_env` — `src/flask/sansio/app.py:467-474` ；`debug` — `src/flask/sansio/app.py:550-560` ；`debug` — `src/flask/sansio/app.py:563-567` |
| `c_d_app_misc_file` | 文件相关操作 | `misc/file` | `inferred` | `from_file` — `src/flask/config.py:256-302` ；`static_folder` — `src/flask/sansio/scaffold.py:224-231` ；`static_folder` — `src/flask/sansio/scaffold.py:234-238` ；`has_static_folder` — `src/flask/sansio/scaffold.py:241-246` ；`static_url_path` — `src/flask/sansio/scaffold.py:249-262` ；`static_url_path` — `src/flask/sansio/scaffold.py:265-269` |
| `c_d_app_misc_record` | 记录相关操作 | `misc/record` | `inferred` | `log_exception` — `src/flask/app.py:953-967` ；`record` — `src/flask/sansio/blueprints.py:224-230` ；`record_once` — `src/flask/sansio/blueprints.py:233-244` |
| `c_d_app_misc_unclassified` | 其他能力（待归类：raise_routing_exception、run、test_client、test_cli_runner 等 89 个） | `misc/unclassified` | `inferred-low` | `raise_routing_exception` — `src/flask/app.py:563-589` ；`run` — `src/flask/app.py:633-756` ；`test_client` — `src/flask/app.py:758-814` ；`test_cli_runner` — `src/flask/app.py:816-831` ；`handle_http_exception` — `src/flask/app.py:833-866` ；`handle_exception` — `src/flask/app.py:900-951` ；`dispatch_request` — `src/flask/app.py:969-993` ；`full_dispatch_request` — `src/flask/app.py:995-1022` ；`finalize_request` — `src/flask/app.py:1024-1054` ；`async_to_sync` — `src/flask/app.py:1082-1103` ；`url_for` — `src/flask/app.py:1105-1225` ；`preprocess_request` — `src/flask/app.py:1369-1395` ；`do_teardown_request` — `src/flask/app.py:1423-1454` ；`do_teardown_appcontext` — `src/flask/app.py:1456-1482` ；`app_context` — `src/flask/app.py:1484-1502` ；`request_context` — `src/flask/app.py:1504-1518` ；`test_request_context` — `src/flask/app.py:1520-1567` ；`wsgi_app` — `src/flask/app.py:1569-1619` ；`from_envvar` — `src/flask/config.py:102-124` ；`from_pyfile` — `src/flask/config.py:187-216` ；`from_object` — `src/flask/config.py:218-254` ；`from_mapping` — `src/flask/config.py:304-321` ；`pop` — `src/flask/ctx.py:79-91` ；`after_this_request` — `src/flask/ctx.py:118-148` ；`copy_current_request_context` — `src/flask/ctx.py:154-206` ；`has_request_context` — `src/flask/ctx.py:209-232` ；`has_app_context` — `src/flask/ctx.py:235-257` ；`from_environ` — `src/flask/ctx.py:340-348` ；`has_request` — `src/flask/ctx.py:351-353` ；`copy` — `src/flask/ctx.py:355-368` ；`request` — `src/flask/ctx.py:371-379` ；`session` — `src/flask/ctx.py:396-403` ；`match_request` — `src/flask/ctx.py:405-414` ；`push` — `src/flask/ctx.py:416-444` ；`pop` — `src/flask/ctx.py:446-504` ；`name` — `src/flask/sansio/app.py:423-437` ；`logger` — `src/flask/sansio/app.py:440-464` ；`select_jinja_autoescape` — `src/flask/sansio/app.py:533-547` ；`iter_blueprints` — `src/flask/sansio/app.py:597-602` ；`template_filter` — `src/flask/sansio/app.py:664` ；`template_filter` — `src/flask/sansio/app.py:666-668` ；`template_filter` — `src/flask/sansio/app.py:670-696` ；`template_test` — `src/flask/sansio/app.py:714` ；`template_test` — `src/flask/sansio/app.py:716-718` ；`template_test` — `src/flask/sansio/app.py:720-753` ；`template_global` — `src/flask/sansio/app.py:773` ；`template_global` — `src/flask/sansio/app.py:775-777` ；`template_global` — `src/flask/sansio/app.py:779-807` ；`teardown_appcontext` — `src/flask/sansio/app.py:827-855` ；`shell_context_processor` — `src/flask/sansio/app.py:858-866` ；`trap_http_exception` — `src/flask/sansio/app.py:893-926` ；`redirect` — `src/flask/sansio/app.py:939-958` ；`inject_url_defaults` — `src/flask/sansio/app.py:960-979` ；`app_template_filter` — `src/flask/sansio/blueprints.py:444` ；`app_template_filter` — `src/flask/sansio/blueprints.py:446-448` ；`app_template_filter` — `src/flask/sansio/blueprints.py:450-473` ；`app_template_test` — `src/flask/sansio/blueprints.py:498` ；`app_template_test` — `src/flask/sansio/blueprints.py:500-502` ；`app_template_test` — `src/flask/sansio/blueprints.py:504-529` ；`app_template_global` — `src/flask/sansio/blueprints.py:556` ；`app_template_global` — `src/flask/sansio/blueprints.py:558-560` ；`app_template_global` — `src/flask/sansio/blueprints.py:562-587` ；`before_app_request` — `src/flask/sansio/blueprints.py:614-621` ；`after_app_request` — `src/flask/sansio/blueprints.py:624-631` ；`teardown_app_request` — `src/flask/sansio/blueprints.py:634-641` ；`app_context_processor` — `src/flask/sansio/blueprints.py:644-653` ；`app_errorhandler` — `src/flask/sansio/blueprints.py:656-670` ；`app_url_defaults` — `src/flask/sansio/blueprints.py:685-692` ；`jinja_loader` — `src/flask/sansio/scaffold.py:272-282` ；`post` — `src/flask/sansio/scaffold.py:312-317` ；`put` — `src/flask/sansio/scaffold.py:320-325` ；`route` — `src/flask/sansio/scaffold.py:344-373` ；`endpoint` — `src/flask/sansio/scaffold.py:444-465` ；`before_request` — `src/flask/sansio/scaffold.py:468-492` ；`after_request` — `src/flask/sansio/scaffold.py:495-513` ；`teardown_request` — `src/flask/sansio/scaffold.py:516-547` ；`context_processor` — `src/flask/sansio/scaffold.py:550-564` ；`url_defaults` — `src/flask/sansio/scaffold.py:592-603` ；`errorhandler` — `src/flask/sansio/scaffold.py:606-647` ；`_default_template_ctx_processor` — `src/flask/templating.py:21-33` ；`_iter_loaders` — `src/flask/templating.py:98-106` ；`_render` — `src/flask/templating.py:123-133` ；`render_template` — `src/flask/templating.py:136-148` ；`render_template_string` — `src/flask/templating.py:151-160` ；`_stream` — `src/flask/templating.py:163-178` ；`stream_template` — `src/flask/templating.py:181-197` ；`stream_template_string` — `src/flask/templating.py:200-212` ；`session_transaction` — `src/flask/testing.py:136-183` ；`invoke` — `src/flask/testing.py:275-298` |
| `c_d_app_misc_user` | 用户相关操作 | `misc/user` | `inferred` | `handle_user_exception` — `src/flask/app.py:868-898` ；`_find_error_handler` — `src/flask/sansio/app.py:868-891` |
| `c_d_app_misc_value` | 数据项相关操作 | `misc/value` | `inferred` | `app_url_value_preprocessor` — `src/flask/sansio/blueprints.py:673-682` ；`url_value_preprocessor` — `src/flask/sansio/scaffold.py:567-589` |
| `c_d_app_notify_file` | 通知文件 | `notify/file` | `inferred` | `send_static_file` — `src/flask/app.py:393-413` ；`send_static_file` — `src/flask/blueprints.py:82-102` |
| `c_d_app_query_file` | 查询文件 | `query/file` | `inferred` | `get_send_file_max_age` — `src/flask/app.py:366-391` ；`get_send_file_max_age` — `src/flask/blueprints.py:55-80` ；`auto_find_instance_path` — `src/flask/sansio/app.py:507-518` ；`_find_package_path` — `src/flask/sansio/scaffold.py:717-759` |
| `c_d_app_query_general` | 查询/读取操作 | `query/` | `inferred` | `get_namespace` — `src/flask/config.py:323-364` ；`get` — `src/flask/ctx.py:68-77` ；`_get_session` — `src/flask/ctx.py:381-393` ；`_find_error_handler` — `src/flask/sansio/app.py:868-891` ；`get` — `src/flask/sansio/scaffold.py:296-301` ；`query` — `src/flask/sansio/scaffold.py:304-309` ；`_get_exc_class_and_code` — `src/flask/sansio/scaffold.py:665-706` ；`_find_package_path` — `src/flask/sansio/scaffold.py:717-759` ；`find_package` — `src/flask/sansio/scaffold.py:762-800` ；`get_source` — `src/flask/templating.py:57-62` ；`_get_source_explained` — `src/flask/templating.py:64-86` ；`_get_source_fast` — `src/flask/templating.py:88-96` ；`list_templates` — `src/flask/templating.py:108-120` ；`_get_werkzeug_version` — `src/flask/testing.py:100-106` |
| `c_d_app_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `json_dumps` — `src/flask/testing.py:88-94` |
| `c_d_app_validate_check` | 校验检查 | `validate/check` | `inferred-low` | `_check_setup_finished` — `src/flask/sansio/app.py:410-420` ；`_check_setup_finished` — `src/flask/sansio/blueprints.py:213-221` ；`_check_setup_finished` — `src/flask/sansio/scaffold.py:220-221` |
| `c_d_app_validate_general` | 校验/检测操作 | `validate/` | `inferred` | `ensure_sync` — `src/flask/app.py:1068-1080` |

### 2. `d_app_context_proxy` · **App Context Proxy**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 7 个 ｜ 子能力点 1 个
- 聚类依据：`identifier_root=app_context_proxy`（来自 AppContextProxy（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=app_ctx_globals_proxy`（来自 _AppCtxGlobalsProxy（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=flask_proxy`（来自 FlaskProxy（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=globals`（来自 globals（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=proxy_mixin`（来自 ProxyMixin（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=request_proxy`（来自 RequestProxy（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=session_mixin_proxy`（来自 SessionMixinProxy（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=same_file(5)`（域合并依据）、…共 11 条
- 涉及文件：`src/flask/globals.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_app_context_proxy_query_general` | 查询/读取操作 | `query/` | `inferred-low` | `_get_current_object` — `src/flask/globals.py:18` |

### 3. `d_app_group` · **App Group**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 7 个 ｜ 子能力点 8 个
- 聚类依据：`identifier_root=app_group`（来自 AppGroup（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=cert_param_type`（来自 CertParamType（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=cli`（来自 cli（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=flask_group`（来自 FlaskGroup（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=no_app_exception`（来自 NoAppException（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=script_info`（来自 ScriptInfo（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=separated_path_type`（来自 SeparatedPathType（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、…共 13 条
- 涉及文件：`src/flask/cli.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_app_group_create_general` | 提交/创建操作 | `create/` | `inferred` | `make_context` — `src/flask/cli.py:657-676` |
| `c_d_app_group_misc_config` | 配置相关操作 | `misc/config` | `inferred-low` | `_env_file_callback` — `src/flask/cli.py:493-512` |
| `c_d_app_group_misc_file` | 文件相关操作 | `misc/file` | `inferred-low` | `_path_is_ancestor` — `src/flask/cli.py:691-695` |
| `c_d_app_group_misc_role` | 角色权限相关操作 | `misc/role` | `inferred` | `group` — `src/flask/cli.py:429-437` |
| `c_d_app_group_misc_unclassified` | 其他能力（待归类：prepare_import、locate_app、locate_app、locate_app 等 13 个） | `misc/unclassified` | `inferred-low` | `prepare_import` — `src/flask/cli.py:200-226` ；`locate_app` — `src/flask/cli.py:230-232` ；`locate_app` — `src/flask/cli.py:236-238` ；`locate_app` — `src/flask/cli.py:241-264` ；`with_appcontext` — `src/flask/cli.py:380-402` ；`command` — `src/flask/cli.py:413-427` ；`show_server_banner` — `src/flask/cli.py:766-777` ；`convert` — `src/flask/cli.py:791-825` ；`convert` — `src/flask/cli.py:873-879` ；`run_command` — `src/flask/cli.py:935-993` ；`shell_command` — `src/flask/cli.py:1001-1045` ；`routes_command` — `src/flask/cli.py:1061-1107` ；`main` — `src/flask/cli.py:1122-1123` |
| `c_d_app_group_query_general` | 查询/读取操作 | `query/` | `inferred` | `find_best_app` — `src/flask/cli.py:41-91` ；`_called_with_wrong_args` — `src/flask/cli.py:94-117` ；`find_app_by_string` — `src/flask/cli.py:120-197` ；`get_version` — `src/flask/cli.py:267-280` ；`load_app` — `src/flask/cli.py:333-372` ；`_load_plugin_commands` — `src/flask/cli.py:600-607` ；`get_command` — `src/flask/cli.py:609-634` ；`list_commands` — `src/flask/cli.py:636-655` ；`parse_args` — `src/flask/cli.py:678-688` ；`load_dotenv` — `src/flask/cli.py:698-763` |
| `c_d_app_group_update_general` | 更新/修改操作 | `update/` | `inferred-low` | `_set_app` — `src/flask/cli.py:440-446` ；`_set_debug` — `src/flask/cli.py:468-482` |
| `c_d_app_group_validate_value` | 校验数据项 | `validate/value` | `inferred-low` | `_validate_key` — `src/flask/cli.py:828-864` |

### 4. `d_collect_errors` · **Collect Errors**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 7 个
- 聚类依据：`identifier_root=collect_errors`（来自 _CollectErrors（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=helpers`（来自 helpers（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:helpers(5)`（域合并依据）
- 涉及文件：`src/flask/helpers.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_collect_errors_cancel_general` | 取消/撤回操作 | `cancel/` | `inferred` | `abort` — `src/flask/helpers.py:281-301` |
| `c_d_collect_errors_create_general` | 提交/创建操作 | `create/` | `inferred` | `make_response` — `src/flask/helpers.py:151-197` |
| `c_d_collect_errors_misc_file` | 文件相关操作 | `misc/file` | `inferred-low` | `_split_blueprint_path` — `src/flask/helpers.py:645-651` |
| `c_d_collect_errors_misc_unclassified` | 其他能力（待归类：stream_with_context、stream_with_context、stream_with_context、url_for 等 7 个） | `misc/unclassified` | `inferred-low` | `stream_with_context` — `src/flask/helpers.py:52-54` ；`stream_with_context` — `src/flask/helpers.py:58-60` ；`stream_with_context` — `src/flask/helpers.py:63-148` ；`url_for` — `src/flask/helpers.py:200-251` ；`redirect` — `src/flask/helpers.py:254-278` ；`flash` — `src/flask/helpers.py:326-357` ；`raise_any` — `src/flask/helpers.py:676-682` |
| `c_d_collect_errors_notify_file` | 通知文件 | `notify/file` | `inferred` | `_prepare_send_file_kwargs` — `src/flask/helpers.py:402-414` ；`send_file` — `src/flask/helpers.py:417-540` ；`send_from_directory` — `src/flask/helpers.py:543-584` |
| `c_d_collect_errors_query_file` | 查询文件 | `query/file` | `inferred` | `get_root_path` — `src/flask/helpers.py:587-641` |
| `c_d_collect_errors_query_general` | 查询/读取操作 | `query/` | `inferred` | `get_debug_flag` — `src/flask/helpers.py:28-33` ；`get_load_dotenv` — `src/flask/helpers.py:36-48` ；`get_template_attribute` — `src/flask/helpers.py:304-323` ；`get_flashed_messages` — `src/flask/helpers.py:360-399` |

### 5. `d_debug_files_key_error` · **Debug Files Key Error**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 4 个 ｜ 子能力点 2 个
- 聚类依据：`identifier_root=debug_files_key_error`（来自 DebugFilesKeyError（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=debughelpers`（来自 debughelpers（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=form_data_routing_redirect`（来自 FormDataRoutingRedirect（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=unexpected_unicode_error`（来自 UnexpectedUnicodeError（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=call_adjacent(7)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=same_file(7)`（域合并依据）
- 涉及文件：`src/flask/debughelpers.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_debug_files_key_error_misc_unclassified` | 其他能力（待归类：attach_enctype_error_multidict、explain_template_loading_attempts） | `misc/unclassified` | `inferred-low` | `attach_enctype_error_multidict` — `src/flask/debughelpers.py:81-104` ；`explain_template_loading_attempts` — `src/flask/debughelpers.py:124-179` |
| `c_d_debug_files_key_error_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred-low` | `_dump_loader_info` — `src/flask/debughelpers.py:107-121` |

### 6. `d_default_j_s_o_n` · **系统装配（provider）**

- 角色 `orchestrator` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_structural_role` ｜ 单元 3 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=default_j_s_o_n`（来自 DefaultJSONProvider（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=j_s_o_n`（来自 JSONProvider（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=provider`（来自 provider（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=call_adjacent(3)`（域合并依据）、`merge=call_adjacent(7)`（域合并依据）、`merge=same_file(5)`（域合并依据）
- 涉及文件：`src/flask/json/provider.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_default_j_s_o_n_misc_unclassified` | 其他能力（待归类：_prepare_response_obj、response、_default、response） | `misc/unclassified` | `inferred-low` | `_prepare_response_obj` — `src/flask/json/provider.py:75-87` ；`response` — `src/flask/json/provider.py:89-105` ；`_default` — `src/flask/json/provider.py:108-121` ；`response` — `src/flask/json/provider.py:189-215` |
| `c_d_default_j_s_o_n_query_general` | 查询/读取操作 | `query/` | `inferred` | `load` — `src/flask/json/provider.py:67-73` |
| `c_d_default_j_s_o_n_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `dumps` — `src/flask/json/provider.py:41-47` ；`dump` — `src/flask/json/provider.py:49-57` ；`loads` — `src/flask/json/provider.py:59-65` ；`dumps` — `src/flask/json/provider.py:166-179` ；`loads` — `src/flask/json/provider.py:181-187` |

### 7. `d_init` · **系统装配（__init__）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=init`（来自 __init__（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`src/flask/json/__init__.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_init_misc_unclassified` | 其他能力（待归类：jsonify） | `misc/unclassified` | `inferred-low` | `jsonify` — `src/flask/json/__init__.py:138-170` |
| `c_d_init_query_general` | 查询/读取操作 | `query/` | `inferred` | `load` — `src/flask/json/__init__.py:108-135` |
| `c_d_init_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `dumps` — `src/flask/json/__init__.py:13-44` ；`dump` — `src/flask/json/__init__.py:47-74` ；`loads` — `src/flask/json/__init__.py:77-105` |

### 8. `d_j_s_o_n_tag` · **JSON Tag**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 10 个 ｜ 子能力点 5 个
- 聚类依据：`identifier_root=j_s_o_n_tag`（来自 JSONTag（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=pass_dict`（来自 PassDict（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=pass_list`（来自 PassList（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=tag_bytes`（来自 TagBytes（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=tag_date_time`（来自 TagDateTime（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=tag_dict`（来自 TagDict（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=tag_markup`（来自 TagMarkup（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、`identifier_root=tag_tuple`（来自 TagTuple（目录 src/flask/json 有 14 个文件，太大不宜整体当域））、…共 14 条
- 涉及文件：`src/flask/json/tag.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_j_s_o_n_tag_create_general` | 提交/创建操作 | `create/` | `inferred` | `register` — `src/flask/json/tag.py:256-287` |
| `c_d_j_s_o_n_tag_misc_unclassified` | 其他能力（待归类：to_json、to_python、tag、to_json 等 19 个） | `misc/unclassified` | `inferred-low` | `to_json` — `src/flask/json/tag.py:77-80` ；`to_python` — `src/flask/json/tag.py:82-85` ；`tag` — `src/flask/json/tag.py:87-90` ；`to_json` — `src/flask/json/tag.py:110-112` ；`to_python` — `src/flask/json/tag.py:114-116` ；`to_json` — `src/flask/json/tag.py:125-128` ；`to_json` — `src/flask/json/tag.py:140-141` ；`to_python` — `src/flask/json/tag.py:143-144` ；`to_json` — `src/flask/json/tag.py:153-154` ；`to_json` — `src/flask/json/tag.py:166-167` ；`to_python` — `src/flask/json/tag.py:169-170` ；`to_json` — `src/flask/json/tag.py:184-185` ；`to_python` — `src/flask/json/tag.py:187-188` ；`to_json` — `src/flask/json/tag.py:198-199` ；`to_python` — `src/flask/json/tag.py:201-202` ；`to_json` — `src/flask/json/tag.py:212-213` ；`to_python` — `src/flask/json/tag.py:215-216` ；`tag` — `src/flask/json/tag.py:289-295` ；`untag` — `src/flask/json/tag.py:297-307` |
| `c_d_j_s_o_n_tag_query_general` | 查询/读取操作 | `query/` | `inferred-low` | `_untag_scan` — `src/flask/json/tag.py:309-319` |
| `c_d_j_s_o_n_tag_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `_untag_scan` — `src/flask/json/tag.py:309-319` ；`dumps` — `src/flask/json/tag.py:321-323` ；`loads` — `src/flask/json/tag.py:325-327` |
| `c_d_j_s_o_n_tag_validate_check` | 校验检查 | `validate/check` | `inferred` | `check` — `src/flask/json/tag.py:73-75` ；`check` — `src/flask/json/tag.py:103-108` ；`check` — `src/flask/json/tag.py:122-123` ；`check` — `src/flask/json/tag.py:137-138` ；`check` — `src/flask/json/tag.py:150-151` ；`check` — `src/flask/json/tag.py:163-164` ；`check` — `src/flask/json/tag.py:181-182` ；`check` — `src/flask/json/tag.py:195-196` ；`check` — `src/flask/json/tag.py:209-210` |

### 9. `d_logging` · **系统装配（logging）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 2 个
- 聚类依据：`identifier_root=logging`（来自 logging（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`src/flask/logging.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_logging_create_general` | 提交/创建操作 | `create/` | `inferred` | `create_logger` — `src/flask/logging.py:58-79` |
| `c_d_logging_misc_unclassified` | 其他能力（待归类：wsgi_errors_stream、has_level_handler） | `misc/unclassified` | `inferred-low` | `wsgi_errors_stream` — `src/flask/logging.py:16-28` ；`has_level_handler` — `src/flask/logging.py:31-47` |

### 10. `d_method_view` · **系统装配（views）**

- 角色 `orchestrator` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_structural_role` ｜ 单元 2 个 ｜ 子能力点 1 个
- 聚类依据：`identifier_root=method_view`（来自 MethodView（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=view`（来自 View（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:view,views(5)`（域合并依据）
- 涉及文件：`src/flask/views.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_method_view_misc_unclassified` | 其他能力（待归类：dispatch_request、as_view、dispatch_request） | `misc/unclassified` | `inferred-low` | `dispatch_request` — `src/flask/views.py:78-83` ；`as_view` — `src/flask/views.py:86-135` ；`dispatch_request` — `src/flask/views.py:182-191` |

### 11. `d_null_session` · **Null Session**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 6 个 ｜ 子能力点 5 个
- 聚类依据：`identifier_root=null_session`（来自 NullSession（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=secure_cookie_session`（来自 SecureCookieSession（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=secure_cookie_session_interface`（来自 SecureCookieSessionInterface（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=session_interface`（来自 SessionInterface（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=session_mixin`（来自 SessionMixin（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=sessions`（来自 sessions（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=same_file(5)`（域合并依据）、`merge=shared_token:session(1)`（域合并依据）、…共 10 条
- 涉及文件：`src/flask/sessions.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_null_session_create_general` | 提交/创建操作 | `create/` | `inferred` | `make_null_session` — `src/flask/sessions.py:150-160` ；`open_session` — `src/flask/sessions.py:249-261` ；`open_session` — `src/flask/sessions.py:323-335` |
| `c_d_null_session_misc_unclassified` | 其他能力（待归类：permanent、permanent、_fail、is_null_session 等 7 个） | `misc/unclassified` | `inferred-low` | `permanent` — `src/flask/sessions.py:28-30` ；`permanent` — `src/flask/sessions.py:33-34` ；`_fail` — `src/flask/sessions.py:89-94` ；`is_null_session` — `src/flask/sessions.py:162-169` ；`save_session` — `src/flask/sessions.py:263-270` ；`_lazy_sha1` — `src/flask/sessions.py:276-281` ；`save_session` — `src/flask/sessions.py:337-385` |
| `c_d_null_session_query_file` | 查询文件 | `query/file` | `inferred` | `get_cookie_path` — `src/flask/sessions.py:187-193` |
| `c_d_null_session_query_general` | 查询/读取操作 | `query/` | `inferred` | `get_cookie_name` — `src/flask/sessions.py:171-173` ；`get_cookie_domain` — `src/flask/sessions.py:175-185` ；`get_cookie_httponly` — `src/flask/sessions.py:195-200` ；`get_cookie_secure` — `src/flask/sessions.py:202-206` ；`get_cookie_samesite` — `src/flask/sessions.py:208-213` ；`get_cookie_partitioned` — `src/flask/sessions.py:215-221` ；`get_expiration_time` — `src/flask/sessions.py:223-231` ；`get_signing_serializer` — `src/flask/sessions.py:303-321` |
| `c_d_null_session_update_general` | 更新/修改操作 | `update/` | `inferred` | `should_set_cookie` — `src/flask/sessions.py:233-247` |

### 12. `d_request` · **Request**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 2 个
- 聚类依据：`identifier_root=request`（来自 Request（目录 src/flask 有 46 个文件，太大不宜整体当域））、`identifier_root=response`（来自 Response（目录 src/flask 有 46 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:request(1)`（域合并依据）、`merge=shared_token:wrappers(5)`（域合并依据）
- 涉及文件：`src/flask/wrappers.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_request_misc_unclassified` | 其他能力（待归类：max_content_length、max_content_length、max_form_memory_size、max_form_memory_size 等 11 个） | `misc/unclassified` | `inferred-low` | `max_content_length` — `src/flask/wrappers.py:60-86` ；`max_content_length` — `src/flask/wrappers.py:89-90` ；`max_form_memory_size` — `src/flask/wrappers.py:93-113` ；`max_form_memory_size` — `src/flask/wrappers.py:116-117` ；`max_form_parts` — `src/flask/wrappers.py:120-140` ；`max_form_parts` — `src/flask/wrappers.py:143-144` ；`endpoint` — `src/flask/wrappers.py:147-159` ；`blueprint` — `src/flask/wrappers.py:162-178` ；`blueprints` — `src/flask/wrappers.py:181-195` ；`on_json_loading_failed` — `src/flask/wrappers.py:212-219` ；`max_cookie_size` — `src/flask/wrappers.py:247-257` |
| `c_d_request_query_general` | 查询/读取操作 | `query/` | `inferred-low` | `_load_form_data` — `src/flask/wrappers.py:197-210` |

---

## `validation/urllib3`

- 规模：域 **19** 个 / 功能点 **69** 个 / 级别 **L3** / 图谱状态 `needs_review`
- `source_hash`：`sha256:396ebf2a9e5ae8a5c6aa731dc34453de`

### 1. `d_app` · **系统装配（app）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=app`（来自 app（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`dummyserver/app.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_app_create_general` | 提交/创建操作 | `create/` | `inferred` | `apply_caching` — `dummyserver/app.py:321-324` |
| `c_d_app_misc_unclassified` | 其他能力（待归类：index、alpn_protocol、certificate、specific_method 等 30 个） | `misc/unclassified` | `inferred-low` | `index` — `dummyserver/app.py:40-41` ；`alpn_protocol` — `dummyserver/app.py:45-48` ；`certificate` — `dummyserver/app.py:52-56` ；`specific_method` — `dummyserver/app.py:61-71` ；`upload` — `dummyserver/app.py:75-103` ；`chunked` — `dummyserver/app.py:107-112` ；`chunked_gzip` — `dummyserver/app.py:116-124` ；`keepalive` — `dummyserver/app.py:128-134` ；`echo` — `dummyserver/app.py:138-144` ；`echo_json` — `dummyserver/app.py:149-154` ；`echo_uri` — `dummyserver/app.py:159-162` ；`echo_params` — `dummyserver/app.py:166-170` ；`headers` — `dummyserver/app.py:174-176` ；`headers_and_params` — `dummyserver/app.py:180-186` ；`multi_headers` — `dummyserver/app.py:190-192` ；`multi_redirect` — `dummyserver/app.py:196-207` ；`encodingrequest` — `dummyserver/app.py:211-231` ；`redirect` — `dummyserver/app.py:236-253` ；`redirect_after` — `dummyserver/app.py:257-269` ；`retry_after` — `dummyserver/app.py:273-283` ；`status` — `dummyserver/app.py:288-292` ；`source_address` — `dummyserver/app.py:296-298` ；`successful_retry` — `dummyserver/app.py:302-317` ；`slow` — `dummyserver/app.py:328-330` ；`dripfeed` — `dummyserver/app.py:334-346` ；`bigfile` — `dummyserver/app.py:350-354` ；`mediumfile` — `dummyserver/app.py:358-361` ；`pyodide_upload` — `dummyserver/app.py:365-384` ；`pyodide` — `dummyserver/app.py:452-477` ；`wheel` — `dummyserver/app.py:481-492` |
| `c_d_app_query_general` | 查询/读取操作 | `query/` | `inferred-low` | `_find_built_wheel` — `dummyserver/app.py:387-394` ；`_get_pyodide_template` — `dummyserver/app.py:397-448` |

### 2. `d_asgi_proxy` · **Asgi Proxy**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 100 个 ｜ 子能力点 9 个
- 聚类依据：`identifier_root=asgi_proxy`（来自 asgi_proxy（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=base_h_t_t_p_response`（来自 BaseHTTPResponse（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=base_s_s_l_error`（来自 BaseSSLError（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=body_not_httplib_compatible`（来自 BodyNotHttplibCompatible（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=brotli_decoder`（来自 BrotliDecoder（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=bytes_queue_buffer`（来自 BytesQueueBuffer（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=closed_pool_error`（来自 ClosedPoolError（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=collections`（来自 _collections（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、…共 107 条
- 涉及文件：`dummyserver/asgi_proxy.py`、`dummyserver/socketserver.py`、`src/urllib3/_collections.py`、`src/urllib3/connection.py`、`src/urllib3/connectionpool.py`、`src/urllib3/contrib/emscripten/connection.py`、`src/urllib3/contrib/emscripten/fetch.py`、`src/urllib3/contrib/emscripten/response.py`、`src/urllib3/contrib/socks.py`、`src/urllib3/exceptions.py`、`src/urllib3/http2/connection.py`、`src/urllib3/poolmanager.py`、`src/urllib3/response.py`、`src/urllib3/util/connection.py`、`src/urllib3/util/proxy.py`、`src/urllib3/util/response.py`、`src/urllib3/util/retry.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_asgi_proxy_create_general` | 提交/创建/删除/移除操作 | `create/` | `inferred` | `_start_server` — `dummyserver/socketserver.py:121-140` ；`clear` — `src/urllib3/_collections.py:141-149` ；`setdefault` — `src/urllib3/_collections.py:275-276` ；`add` — `src/urllib3/_collections.py:306-339` ；`_prepare_for_method_change` — `src/urllib3/_collections.py:399-419` ；`_new_conn` — `src/urllib3/connection.py:233-260` ；`set_tunnel` — `src/urllib3/connection.py:262-274` ；`close` — `src/urllib3/connection.py:442-455` ；`close` — `src/urllib3/connectionpool.py:111-114` ；`_new_pool_queue` — `src/urllib3/connectionpool.py:116-119` ；`_new_conn` — `src/urllib3/connectionpool.py:242-260` ；`_make_request` — `src/urllib3/connectionpool.py:383-562` ；`close` — `src/urllib3/connectionpool.py:564-574` ；`_new_conn` — `src/urllib3/connectionpool.py:1076-1115` ；`_close_pool_connections` — `src/urllib3/connectionpool.py:1203-1211` ；`set_tunnel` — `src/urllib3/contrib/emscripten/connection.py:73-80` ；`close` — `src/urllib3/contrib/emscripten/connection.py:139-141` ；`set_cert` — `src/urllib3/contrib/emscripten/connection.py:242-254` ；`_obj_from_dict` — `src/urllib3/contrib/emscripten/fetch.py:93-94` ；`closed` — `src/urllib3/contrib/emscripten/fetch.py:127-128` ；`close` — `src/urllib3/contrib/emscripten/fetch.py:130-142` ；`closed` — `src/urllib3/contrib/emscripten/fetch.py:351-352` ；`close` — `src/urllib3/contrib/emscripten/fetch.py:354-365` ；`_init_length` — `src/urllib3/contrib/emscripten/response.py:103-138` ；`close` — `src/urllib3/contrib/emscripten/response.py:230-237` ；`_new_conn` — `src/urllib3/contrib/socks.py:98-154` ；`_new_h2_conn` — `src/urllib3/http2/connection.py:101-103` ；`set_tunnel` — `src/urllib3/http2/connection.py:216-225` ；`close` — `src/urllib3/http2/connection.py:308-322` ；`close` — `src/urllib3/http2/connection.py:356-357` ；`_new_pool` — `src/urllib3/poolmanager.py:245-281` ；`clear` — `src/urllib3/poolmanager.py:283-290` ；`_set_proxy_headers` — `src/urllib3/poolmanager.py:644-659` ；`close` — `src/urllib3/response.py:615-616` ；`_init_decoder` — `src/urllib3/response.py:618-640` ；`_init_length` — `src/urllib3/response.py:860-914` ；`close` — `src/urllib3/response.py:1309-1319` ；`closed` — `src/urllib3/response.py:1322-1332` ；`_update_chunk_length` — `src/urllib3/response.py:1362-1383` ；`create_connection` — `src/urllib3/util/connection.py:27-90` ；`_set_socket_options` — `src/urllib3/util/connection.py:93-100` ；`new` — `src/urllib3/util/retry.py:278-300` |
| `c_d_asgi_proxy_misc_unclassified` | 其他能力（待归类：absolute_uri、connect、_resolves_to_ipv6、_has_ipv6 等 151 个） | `misc/unclassified` | `inferred-low` | `absolute_uri` — `dummyserver/asgi_proxy.py:49-90` ；`connect` — `dummyserver/asgi_proxy.py:92-115` ；`_resolves_to_ipv6` — `dummyserver/socketserver.py:44-55` ；`_has_ipv6` — `dummyserver/socketserver.py:58-78` ；`run` — `dummyserver/socketserver.py:142-143` ；`ssl_options_to_context` — `dummyserver/socketserver.py:146-173` ；`keys` — `src/urllib3/_collections.py:16` ；`keys` — `src/urllib3/_collections.py:151-153` ；`discard` — `src/urllib3/_collections.py:300-304` ；`extend` — `src/urllib3/_collections.py:341-371` ；`_copy_from` — `src/urllib3/_collections.py:432-435` ；`copy` — `src/urllib3/_collections.py:437-440` ；`iteritems` — `src/urllib3/_collections.py:442-447` ；`itermerged` — `src/urllib3/_collections.py:449-453` ；`items` — `src/urllib3/_collections.py:455-456` ；`host` — `src/urllib3/connection.py:205-221` ；`host` — `src/urllib3/connection.py:224-231` ；`_wrap_ipv6` — `src/urllib3/connection.py:280-283` ；`_tunnel` — `src/urllib3/connection.py:297-346` ；`_tunnel` — `src/urllib3/connection.py:352-395` ；`connect` — `src/urllib3/connection.py:397-412` ；`is_closed` — `src/urllib3/connection.py:415-416` ；`is_connected` — `src/urllib3/connection.py:419-422` ；`has_connected_to_proxy` — `src/urllib3/connection.py:425-426` ；`proxy_is_forwarding` — `src/urllib3/connection.py:429-433` ；`proxy_is_tunneling` — `src/urllib3/connection.py:436-440` ；`putrequest` — `src/urllib3/connection.py:457-475` ；`putheader` — `src/urllib3/connection.py:477-487` ；`request` — `src/urllib3/connection.py:491-586` ；`request_chunked` — `src/urllib3/connection.py:588-605` ；`connect` — `src/urllib3/connection.py:792-941` ；`_connect_tls_proxy` — `src/urllib3/connection.py:943-993` ；`_ssl_wrap_socket_and_match_hostname` — `src/urllib3/connection.py:1006-1128` ；`_match_hostname` — `src/urllib3/connection.py:1131-1154` ；`_wrap_proxy_error` — `src/urllib3/connection.py:1157-1179` ；`_put_conn` — `src/urllib3/connectionpool.py:300-341` ；`_prepare_proxy` — `src/urllib3/connectionpool.py:348-350` ；`_raise_timeout` — `src/urllib3/connectionpool.py:364-381` ；`is_same_host` — `src/urllib3/connectionpool.py:576-596` ；`urlopen` — `src/urllib3/connectionpool.py:598-992` ；`_prepare_proxy` — `src/urllib3/connectionpool.py:1061-1074` ；`connection_from_url` — `src/urllib3/connectionpool.py:1140-1167` ；`_normalize_host` — `src/urllib3/connectionpool.py:1171` ；`_normalize_host` — `src/urllib3/connectionpool.py:1175` ；`_normalize_host` — `src/urllib3/connectionpool.py:1178-1193` ；`_url_from_pool` — `src/urllib3/connectionpool.py:1196-1200` ；`connect` — `src/urllib3/contrib/emscripten/connection.py:82-83` ；`request` — `src/urllib3/contrib/emscripten/connection.py:85-127` ；`is_closed` — `src/urllib3/contrib/emscripten/connection.py:144-149` ；`is_connected` — `src/urllib3/contrib/emscripten/connection.py:152-154` ；`has_connected_to_proxy` — `src/urllib3/contrib/emscripten/connection.py:157-162` ；`is_closed` — `src/urllib3/contrib/emscripten/fetch.py:122-123` ；`writable` — `src/urllib3/contrib/emscripten/fetch.py:147-148` ；`seekable` — `src/urllib3/contrib/emscripten/fetch.py:150-151` ；`is_closed` — `src/urllib3/contrib/emscripten/fetch.py:346-347` ；`writable` — `src/urllib3/contrib/emscripten/fetch.py:370-371` ；`seekable` — `src/urllib3/contrib/emscripten/fetch.py:373-374` ；`is_in_browser_main_thread` — `src/urllib3/contrib/emscripten/fetch.py:410-411` ；`is_cross_origin_isolated` — `src/urllib3/contrib/emscripten/fetch.py:414-415` ；`is_in_node` — `src/urllib3/contrib/emscripten/fetch.py:418-424` ；`is_worker_available` — `src/urllib3/contrib/emscripten/fetch.py:427-428` ；`has_jspi` — `src/urllib3/contrib/emscripten/fetch.py:680-696` ；`streaming_ready` — `src/urllib3/contrib/emscripten/fetch.py:714-718` ；`wait_for_streaming_ready` — `src/urllib3/contrib/emscripten/fetch.py:721-726` ；`url` — `src/urllib3/contrib/emscripten/response.py:57-58` ；`url` — `src/urllib3/contrib/emscripten/response.py:61-62` ；`connection` — `src/urllib3/contrib/emscripten/response.py:65-66` ；`retries` — `src/urllib3/contrib/emscripten/response.py:69-70` ；`retries` — `src/urllib3/contrib/emscripten/response.py:73-75` ；`stream` — `src/urllib3/contrib/emscripten/response.py:77-101` ；`release_conn` — `src/urllib3/contrib/emscripten/response.py:192-197` ；`drain_conn` — `src/urllib3/contrib/emscripten/response.py:199-200` ；`data` — `src/urllib3/contrib/emscripten/response.py:203-207` ；`json` — `src/urllib3/contrib/emscripten/response.py:209-228` ；`pool` — `src/urllib3/exceptions.py:155-163` ；`_is_legal_header_name` — `src/urllib3/http2/connection.py:29-41` ；`connect` — `src/urllib3/http2/connection.py:105-110` ；`putrequest` — `src/urllib3/http2/connection.py:112-142` ；`putheader` — `src/urllib3/http2/connection.py:144-155` ；`endheaders` — `src/urllib3/http2/connection.py:157-169` ；`request` — `src/urllib3/http2/connection.py:269-306` ；`data` — `src/urllib3/http2/connection.py:350-351` ；`connection_from_host` — `src/urllib3/poolmanager.py:292-319` ；`connection_from_context` — `src/urllib3/poolmanager.py:321-344` ；`connection_from_url` — `src/urllib3/poolmanager.py:372-388` ；`_merge_pool_kwargs` — `src/urllib3/poolmanager.py:390-410` ；`_proxy_requires_url_absolute_form` — `src/urllib3/poolmanager.py:412-423` ；`urlopen` — `src/urllib3/poolmanager.py:425-510` ；`connection_from_host` — `src/urllib3/poolmanager.py:628-642` ；`urlopen` — `src/urllib3/poolmanager.py:661-673` ；`proxy_from_url` — `src/urllib3/poolmanager.py:676-677` ；`decompress` — `src/urllib3/response.py:65-66` ；`has_unconsumed_tail` — `src/urllib3/response.py:69-70` ；`flush` — `src/urllib3/response.py:72-73` ；`decompress` — `src/urllib3/response.py:83-127` ；`has_unconsumed_tail` — `src/urllib3/response.py:130-135` ；`flush` — `src/urllib3/response.py:137-138` ；`decompress` — `src/urllib3/response.py:153-201` ；`has_unconsumed_tail` — `src/urllib3/response.py:204-205` ；`flush` — `src/urllib3/response.py:207-208` ；`_decompress` — `src/urllib3/response.py:225-226` ；`decompress` — `src/urllib3/response.py:228-241` ；`has_unconsumed_tail` — `src/urllib3/response.py:244-248` ；`flush` — `src/urllib3/response.py:250-253` ；`decompress` — `src/urllib3/response.py:270-302` ；`has_unconsumed_tail` — `src/urllib3/response.py:305-308` ；`flush` — `src/urllib3/response.py:310-313` ；`flush` — `src/urllib3/response.py:338-339` ；`decompress` — `src/urllib3/response.py:341-365` ；`has_unconsumed_tail` — `src/urllib3/response.py:368-369` ；`put` — `src/urllib3/response.py:411-413` ；`data` — `src/urllib3/response.py:532-533` ；`json` — `src/urllib3/response.py:535-554` ；`url` — `src/urllib3/response.py:557-558` ；`url` — `src/urllib3/response.py:561-562` ；`connection` — `src/urllib3/response.py:565-566` ；`retries` — `src/urllib3/response.py:569-570` ；`retries` — `src/urllib3/response.py:573-577` ；`stream` — `src/urllib3/response.py:579-582` ；`release_conn` — `src/urllib3/response.py:606-607` ；`drain_conn` — `src/urllib3/response.py:609-610` ；`shutdown` — `src/urllib3/response.py:612-613` ；`info` — `src/urllib3/response.py:705-706` ；`release_conn` — `src/urllib3/response.py:810-815` ；`drain_conn` — `src/urllib3/response.py:817-832` ；`data` — `src/urllib3/response.py:835-843` ；`connection` — `src/urllib3/response.py:846-847` ；`isclosed` — `src/urllib3/response.py:849-850` ；`tell` — `src/urllib3/response.py:852-858` ；`stream` — `src/urllib3/response.py:1262-1294` ；`shutdown` — `src/urllib3/response.py:1300-1307` ；`fileno` — `src/urllib3/response.py:1334-1343` ；`flush` — `src/urllib3/response.py:1345-1351` ；`supports_chunked_reads` — `src/urllib3/response.py:1353-1360` ；`url` — `src/urllib3/response.py:1499-1505` ；`url` — `src/urllib3/response.py:1508-1509` ；`is_connection_dropped` — `src/urllib3/util/connection.py:15-20` ；`allowed_gai_family` — `src/urllib3/util/connection.py:103-111` ；`_has_ipv6` — `src/urllib3/util/connection.py:114-134` ；`connection_requires_http_tunnel` — `src/urllib3/util/proxy.py:11-43` ；`is_fp_closed` — `src/urllib3/util/response.py:9-37` ；`is_response_to_head` — `src/urllib3/util/response.py:91-101` ；`from_int` — `src/urllib3/util/retry.py:303-319` ；`sleep_for_retry` — `src/urllib3/util/retry.py:371-377` ；`_sleep_backoff` — `src/urllib3/util/retry.py:379-383` ；`sleep` — `src/urllib3/util/retry.py:385-399` ；`_is_connection_error` — `src/urllib3/util/retry.py:401-407` ；`_is_method_retryable` — `src/urllib3/util/retry.py:415-421` ；`is_retry` — `src/urllib3/util/retry.py:423-443` ；`is_exhausted` — `src/urllib3/util/retry.py:445-462` ；`increment` — `src/urllib3/util/retry.py:464-559` |
| `c_d_asgi_proxy_misc_value` | 数据项相关操作 | `misc/value` | `inferred` | `encrypt_key_pem` — `dummyserver/socketserver.py:181-190` ；`_has_value_for_header` — `src/urllib3/_collections.py:458-461` ；`_normalize_header_value` — `src/urllib3/connection.py:85-88` ；`_is_illegal_header_value` — `src/urllib3/http2/connection.py:44-51` ；`_default_key_normalizer` — `src/urllib3/poolmanager.py:97-149` ；`_new_pool` — `src/urllib3/poolmanager.py:245-281` ；`connection_from_pool_key` — `src/urllib3/poolmanager.py:346-370` |
| `c_d_asgi_proxy_notify_general` | 通知/告警操作 | `notify/` | `inferred` | `send` — `src/urllib3/contrib/emscripten/fetch.py:229-299` ；`send_streaming_request` — `src/urllib3/contrib/emscripten/fetch.py:449-463` ；`_show_timeout_warning` — `src/urllib3/contrib/emscripten/fetch.py:469-474` ；`_show_streaming_warning` — `src/urllib3/contrib/emscripten/fetch.py:480-496` ；`send_request` — `src/urllib3/contrib/emscripten/fetch.py:499-545` ；`send_jspi_request` — `src/urllib3/contrib/emscripten/fetch.py:548-623` ；`_run_sync_with_timeout` — `src/urllib3/contrib/emscripten/fetch.py:626-677` ；`_is_node_js` — `src/urllib3/contrib/emscripten/fetch.py:699-711` ；`send` — `src/urllib3/http2/connection.py:171-214` |
| `c_d_asgi_proxy_query_general` | 查询/读取操作 | `query/` | `inferred` | `_read_body` — `dummyserver/asgi_proxy.py:18-28` ；`get_unreachable_address` — `dummyserver/socketserver.py:176-178` ；`getlist` — `src/urllib3/_collections.py:374` ；`getlist` — `src/urllib3/_collections.py:377` ；`getlist` — `src/urllib3/_collections.py:379-397` ；`_normalize_header_values` — `src/urllib3/connection.py:91-110` ；`getresponse` — `src/urllib3/connection.py:607-668` ；`_url_from_connection` — `src/urllib3/connection.py:1197-1204` ；`_get_conn` — `src/urllib3/connectionpool.py:262-298` ；`_get_timeout` — `src/urllib3/connectionpool.py:352-362` ；`getresponse` — `src/urllib3/contrib/emscripten/connection.py:129-137` ；`readable` — `src/urllib3/contrib/emscripten/fetch.py:144-145` ；`readinto` — `src/urllib3/contrib/emscripten/fetch.py:153-197` ；`readable` — `src/urllib3/contrib/emscripten/fetch.py:367-368` ；`_get_next_buffer` — `src/urllib3/contrib/emscripten/fetch.py:376-390` ；`readinto` — `src/urllib3/contrib/emscripten/fetch.py:392-406` ；`read` — `src/urllib3/contrib/emscripten/response.py:140-178` ；`read_chunked` — `src/urllib3/contrib/emscripten/response.py:180-190` ；`_error_catcher` — `src/urllib3/contrib/emscripten/response.py:240-281` ；`getresponse` — `src/urllib3/http2/connection.py:227-267` ；`get_redirect_location` — `src/urllib3/http2/connection.py:353-354` ；`_get_decoder` — `src/urllib3/response.py:372-387` ；`get` — `src/urllib3/response.py:415-448` ；`get_all` — `src/urllib3/response.py:450-464` ；`get_redirect_location` — `src/urllib3/response.py:519-529` ；`read` — `src/urllib3/response.py:584-590` ；`read1` — `src/urllib3/response.py:592-597` ；`read_chunked` — `src/urllib3/response.py:599-604` ；`_init_decoder` — `src/urllib3/response.py:618-640` ；`_decode` — `src/urllib3/response.py:642-677` ；`_flush_decoder` — `src/urllib3/response.py:679-686` ；`readinto` — `src/urllib3/response.py:689-695` ；`getheaders` — `src/urllib3/response.py:698-699` ；`getheader` — `src/urllib3/response.py:701-702` ；`geturl` — `src/urllib3/response.py:708-709` ；`_error_catcher` — `src/urllib3/response.py:917-976` ；`_fp_read` — `src/urllib3/response.py:978-1029` ；`_raw_read` — `src/urllib3/response.py:1031-1081` ；`read` — `src/urllib3/response.py:1083-1189` ；`read1` — `src/urllib3/response.py:1191-1260` ；`readable` — `src/urllib3/response.py:1297-1298` ；`_update_chunk_length` — `src/urllib3/response.py:1362-1383` ；`_handle_chunk` — `src/urllib3/response.py:1385-1405` ；`read_chunked` — `src/urllib3/response.py:1407-1496` ；`get_backoff_time` — `src/urllib3/util/retry.py:321-338` ；`parse_retry_after` — `src/urllib3/util/retry.py:340-359` ；`get_retry_after` — `src/urllib3/util/retry.py:361-369` ；`_is_read_error` — `src/urllib3/util/retry.py:409-413` |
| `c_d_asgi_proxy_query_user` | 查询用户 | `query/user` | `inferred-low` | `_get_default_user_agent` — `src/urllib3/connection.py:1182-1183` |
| `c_d_asgi_proxy_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred-low` | `_decode` — `src/urllib3/response.py:642-677` |
| `c_d_asgi_proxy_update_file` | 修改文件 | `update/file` | `inferred` | `set_cert` — `src/urllib3/connection.py:751-790` |
| `c_d_asgi_proxy_validate_general` | 校验/检测操作 | `validate/` | `inferred` | `ensure_can_construct_http_header_dict` — `src/urllib3/_collections.py:43-60` ；`_validate_conn` — `src/urllib3/connectionpool.py:343-346` ；`_validate_conn` — `src/urllib3/connectionpool.py:1117-1137` ；`assert_header_parsing` — `src/urllib3/util/response.py:40-88` |

### 3. `d_base_h_t_t_p_connection` · **Base HTTP Connection**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 4 个 ｜ 子能力点 4 个
- 聚类依据：`identifier_root=base_h_t_t_p_connection`（来自 BaseHTTPConnection（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=base_h_t_t_p_s_connection`（来自 BaseHTTPSConnection（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=proxy_config`（来自 ProxyConfig（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=response_options`（来自 _ResponseOptions（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=call_adjacent(3)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:connection(1)`（域合并依据）
- 涉及文件：`src/urllib3/_base_connection.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_base_h_t_t_p_connection_misc_unclassified` | 其他能力（待归类：connect、request、is_closed、is_connected 等 5 个） | `misc/unclassified` | `inferred-low` | `connect` — `src/urllib3/_base_connection.py:77` ；`request` — `src/urllib3/_base_connection.py:79-93` ；`is_closed` — `src/urllib3/_base_connection.py:100-104` ；`is_connected` — `src/urllib3/_base_connection.py:107-108` ；`has_connected_to_proxy` — `src/urllib3/_base_connection.py:111-115` |
| `c_d_base_h_t_t_p_connection_query_general` | 查询/读取操作 | `query/` | `inferred` | `getresponse` — `src/urllib3/_base_connection.py:95` |
| `c_d_base_h_t_t_p_connection_transition_general` | 状态流转操作 | `transition/` | `inferred` | `close` — `src/urllib3/_base_connection.py:97` |
| `c_d_base_h_t_t_p_connection_update_general` | 更新/修改操作 | `update/` | `inferred` | `set_tunnel` — `src/urllib3/_base_connection.py:69-75` |

### 4. `d_certificate_error` · **Certificate Error**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 1 个
- 聚类依据：`identifier_root=certificate_error`（来自 CertificateError（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`identifier_root=ssl_match_hostname`（来自 ssl_match_hostname（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`merge=same_file(5)`（域合并依据）、`merge=shared_token:error(1)`（域合并依据）、`merge=shared_token:hostname,match(5)`（域合并依据）、`merge=shared_token:ssl(1)`（域合并依据）
- 涉及文件：`src/urllib3/util/ssl_match_hostname.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_certificate_error_misc_unclassified` | 其他能力（待归类：_dnsname_match、_ipaddress_match、match_hostname） | `misc/unclassified` | `inferred-low` | `_dnsname_match` — `src/urllib3/util/ssl_match_hostname.py:24-77` ；`_ipaddress_match` — `src/urllib3/util/ssl_match_hostname.py:80-92` ；`match_hostname` — `src/urllib3/util/ssl_match_hostname.py:95-153` |

### 5. `d_chunks_and_content_length` · **Chunks And Content Length**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 3 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=chunks_and_content_length`（来自 ChunksAndContentLength（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`identifier_root=request`（来自 request（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`identifier_root=t_y_p_e_f_a_i_l_e_d_t_e_l_l`（来自 _TYPE_FAILEDTELL（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`merge=same_file(5)`（域合并依据）、`merge=shared_token:and(1)`（域合并依据）、`merge=shared_token:content(1)`（域合并依据）、`merge=shared_token:length(1)`（域合并依据）
- 涉及文件：`src/urllib3/util/request.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_chunks_and_content_length_create_general` | 提交/创建操作 | `create/` | `inferred` | `make_headers` — `src/urllib3/util/request.py:60-173` |
| `c_d_chunks_and_content_length_misc_unclassified` | 其他能力（待归类：rewind_body、body_to_chunks） | `misc/unclassified` | `inferred-low` | `rewind_body` — `src/urllib3/util/request.py:196-225` ；`body_to_chunks` — `src/urllib3/util/request.py:233-299` |
| `c_d_chunks_and_content_length_update_file` | 修改文件 | `update/file` | `inferred` | `set_file_position` — `src/urllib3/util/request.py:176-193` |

### 6. `d_config` · **系统装配（hypercornserver）**

- 角色 `orchestrator` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_structural_role` ｜ 单元 2 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=config`（来自 Config（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=hypercornserver`（来自 hypercornserver（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:config(1)`（域合并依据）、`merge=shared_token:hypercornserver(5)`（域合并依据）
- 涉及文件：`dummyserver/hypercornserver.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_config_create_general` | 提交/创建操作 | `create/` | `inferred` | `create_sockets` — `dummyserver/hypercornserver.py:23-32` ；`_retry_create_urllib3_sockets` — `dummyserver/hypercornserver.py:34-53` ；`_create_urllib3_sockets` — `dummyserver/hypercornserver.py:55-86` |
| `c_d_config_misc_unclassified` | 其他能力（待归类：run_hypercorn_in_thread、main） | `misc/unclassified` | `inferred-low` | `run_hypercorn_in_thread` — `dummyserver/hypercornserver.py:111-138` ；`main` — `dummyserver/hypercornserver.py:141-149` |
| `c_d_config_transition_general` | 状态流转操作 | `transition/` | `inferred-low` | `_start_server` — `dummyserver/hypercornserver.py:89-107` |

### 7. `d_connection_marker` · **Connection Marker**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 9 个 ｜ 子能力点 6 个
- 聚类依据：`identifier_root=connection_marker`（来自 ConnectionMarker（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=h_t_t_p_s_hypercorn_dummy_server_test_case`（来自 HTTPSHypercornDummyServerTestCase（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=hypercorn_dummy_proxy_test_case`（来自 HypercornDummyProxyTestCase（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=hypercorn_dummy_server_test_case`（来自 HypercornDummyServerTestCase（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=i_p_v4_socket_dummy_server_test_case`（来自 IPV4SocketDummyServerTestCase（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=i_pv6_hypercorn_dummy_proxy_test_case`（来自 IPv6HypercornDummyProxyTestCase（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=i_pv6_hypercorn_dummy_server_test_case`（来自 IPv6HypercornDummyServerTestCase（目录 dummyserver 有 17 个文件，太大不宜整体当域））、`identifier_root=socket_dummy_server_test_case`（来自 SocketDummyServerTestCase（目录 dummyserver 有 17 个文件，太大不宜整体当域））、…共 13 条
- 涉及文件：`dummyserver/testcase.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_connection_marker_configure_general` | 配置/装配操作 | `configure/` | `inferred` | `setup_class` — `dummyserver/testcase.py:206-211` ；`setup_class` — `dummyserver/testcase.py:255-272` |
| `c_d_connection_marker_misc_unclassified` | 其他能力（待归类：consume_socket、quit_server_thread、teardown_class、teardown_method 等 7 个） | `misc/unclassified` | `inferred-low` | `consume_socket` — `dummyserver/testcase.py:20-38` ；`quit_server_thread` — `dummyserver/testcase.py:134-142` ；`teardown_class` — `dummyserver/testcase.py:145-147` ；`teardown_method` — `dummyserver/testcase.py:149-151` ；`teardown_class` — `dummyserver/testcase.py:214-215` ；`teardown_class` — `dummyserver/testcase.py:275-276` ；`consume_request` — `dummyserver/testcase.py:332-345` |
| `c_d_connection_marker_query_general` | 查询/读取操作 | `query/` | `inferred-low` | `_get_socket_mark` — `dummyserver/testcase.py:348-353` |
| `c_d_connection_marker_transition_general` | 状态流转操作 | `transition/` | `inferred` | `_start_server` — `dummyserver/testcase.py:66-82` ；`start_response_handler` — `dummyserver/testcase.py:85-121` ；`start_basic_handler` — `dummyserver/testcase.py:124-131` ；`_start_server` — `dummyserver/testcase.py:175-192` |
| `c_d_connection_marker_update_general` | 更新/修改操作 | `update/` | `inferred` | `mark` — `dummyserver/testcase.py:309-329` ；`_get_socket_mark` — `dummyserver/testcase.py:348-353` |
| `c_d_connection_marker_validate_general` | 校验/检测操作 | `validate/` | `inferred` | `assert_header_received` — `dummyserver/testcase.py:153-170` |

### 8. `d_emscripten_request` · **Emscripten Request**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=emscripten_request`（来自 EmscriptenRequest（目录 src/urllib3/contrib/emscripten 有 13 个文件，太大不宜整体当域））、`identifier_root=request_methods`（来自 RequestMethods（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`merge=call_adjacent(3)`（域合并依据）、`merge=shared_state:headers(4)`（域合并依据）、`merge=shared_token:emscripten(1)`（域合并依据）、`merge=shared_token:emscripten(3)`（域合并依据）、`shared_state=headers`（2 个单元共享该状态）
- 涉及文件：`src/urllib3/_request_methods.py`、`src/urllib3/contrib/emscripten/request.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_emscripten_request_misc_unclassified` | 其他能力（待归类：urlopen、request） | `misc/unclassified` | `inferred-low` | `urlopen` — `src/urllib3/_request_methods.py:54-67` ；`request` — `src/urllib3/_request_methods.py:69-145` |
| `c_d_emscripten_request_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `request_encode_url` — `src/urllib3/_request_methods.py:147-182` ；`request_encode_body` — `src/urllib3/_request_methods.py:184-278` |
| `c_d_emscripten_request_update_general` | 更新/修改操作 | `update/` | `inferred` | `set_header` — `src/urllib3/contrib/emscripten/request.py:18-19` ；`set_body` — `src/urllib3/contrib/emscripten/request.py:21-22` |

### 9. `d_fields` · **Fields**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=fields`（来自 fields（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=request_field`（来自 RequestField（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`merge=call_adjacent(7)`（域合并依据）、`merge=same_file(7)`（域合并依据）、`merge=shared_token:fields(7)`（域合并依据）
- 涉及文件：`src/urllib3/fields.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_fields_create_general` | 提交/创建操作 | `create/` | `inferred` | `_render_parts` — `src/urllib3/fields.py:260-289` ；`make_multipart` — `src/urllib3/fields.py:310-341` |
| `c_d_fields_misc_unclassified` | 其他能力（待归类：guess_content_type、from_tuples、_render_part、render_headers） | `misc/unclassified` | `inferred-low` | `guess_content_type` — `src/urllib3/fields.py:15-28` ；`from_tuples` — `src/urllib3/fields.py:200-242` ；`_render_part` — `src/urllib3/fields.py:244-258` ；`render_headers` — `src/urllib3/fields.py:291-308` |
| `c_d_fields_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `format_header_param_rfc2231` — `src/urllib3/fields.py:31-76` ；`format_multipart_header_param` — `src/urllib3/fields.py:79-114` ；`format_header_param_html5` — `src/urllib3/fields.py:117-132` ；`format_header_param` — `src/urllib3/fields.py:135-150` |

### 10. `d_filepost` · **系统装配（filepost）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 2 个
- 聚类依据：`identifier_root=filepost`（来自 filepost（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`src/urllib3/filepost.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_filepost_misc_unclassified` | 其他能力（待归类：choose_boundary、iter_field_objects） | `misc/unclassified` | `inferred-low` | `choose_boundary` — `src/urllib3/filepost.py:22-26` ；`iter_field_objects` — `src/urllib3/filepost.py:29-48` |
| `c_d_filepost_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `encode_multipart_formdata` — `src/urllib3/filepost.py:51-89` |

### 11. `d_h_t_t_p2_probe_cache` · **HTTP2 Probe Cache**

- 角色 `core` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_identifier` ｜ 单元 1 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=h_t_t_p2_probe_cache`（来自 _HTTP2ProbeCache（目录 src/urllib3/http2 有 6 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=call_adjacent(3)`（域合并依据）、`merge=shared_token:h,p2(3)`（域合并依据）、`merge=shared_token:h,t(1)`（域合并依据）
- 涉及文件：`src/urllib3/http2/probe.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_h_t_t_p2_probe_cache_misc_unclassified` | 其他能力（待归类：_values、_reset） | `misc/unclassified` | `inferred-low` | `_values` — `src/urllib3/http2/probe.py:65-68` ；`_reset` — `src/urllib3/http2/probe.py:70-74` |
| `c_d_h_t_t_p2_probe_cache_query_general` | 查询/读取操作 | `query/` | `inferred` | `acquire_and_get` — `src/urllib3/http2/probe.py:18-49` |
| `c_d_h_t_t_p2_probe_cache_update_general` | 更新/修改操作 | `update/` | `inferred` | `set_and_release` — `src/urllib3/http2/probe.py:51-63` |

### 12. `d_init` · **Init**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 3 个 ｜ 子能力点 3 个
- 聚类依据：`identifier_root=init`（来自 __init__（目录 src/urllib3 有 78 个文件，太大不宜整体当域））、`identifier_root=init`（来自 __init__（目录 src/urllib3/contrib/emscripten 有 13 个文件，太大不宜整体当域））、`identifier_root=init`（来自 __init__（目录 src/urllib3/http2 有 6 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`src/urllib3/__init__.py`、`src/urllib3/contrib/emscripten/__init__.py`、`src/urllib3/http2/__init__.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_init_create_general` | 提交/创建操作 | `create/` | `inferred` | `add_stderr_logger` — `src/urllib3/__init__.py:74-91` |
| `c_d_init_misc_unclassified` | 其他能力（待归类：request、inject_into_urllib3、inject_into_urllib3、extract_from_urllib3） | `misc/unclassified` | `inferred-low` | `request` — `src/urllib3/__init__.py:117-205` ；`inject_into_urllib3` — `src/urllib3/contrib/emscripten/__init__.py:9-17` ；`inject_into_urllib3` — `src/urllib3/http2/__init__.py:15-40` ；`extract_from_urllib3` — `src/urllib3/http2/__init__.py:43-53` |
| `c_d_init_transition_general` | 状态流转操作 | `transition/` | `inferred` | `disable_warnings` — `src/urllib3/__init__.py:107-111` |

### 13. `d_noxfile` · **系统装配（noxfile）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 2 个
- 聚类依据：`identifier_root=noxfile`（来自 noxfile）、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`noxfile.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_noxfile_misc_unclassified` | 其他能力（待归类：tests_impl、test、test_integration、test_min_pyopenssl 等 13 个） | `misc/unclassified` | `inferred-low` | `tests_impl` — `noxfile.py:15-104` ；`test` — `noxfile.py:119-121` ；`test_integration` — `noxfile.py:125-128` ；`test_min_pyopenssl` — `noxfile.py:133-144` ；`test_brotlipy` — `noxfile.py:148-158` ；`git_clone` — `noxfile.py:161-176` ；`downstream_botocore` — `noxfile.py:180-195` ；`downstream_requests` — `noxfile.py:199-215` ；`lint` — `noxfile.py:225-229` ；`pyodideconsole` — `noxfile.py:233-254` ；`emscripten` — `noxfile.py:261-319` ；`mypy` — `noxfile.py:323-339` ；`docs` — `noxfile.py:343-362` |
| `c_d_noxfile_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred` | `format` — `noxfile.py:219-221` |

### 14. `d_py_open_s_s_l_context` · **Py Open SSL Context**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 5 个 ｜ 子能力点 7 个
- 聚类依据：`identifier_root=py_open_s_s_l_context`（来自 PyOpenSSLContext（目录 src/urllib3/contrib 有 10 个文件，太大不宜整体当域））、`identifier_root=pyopenssl`（来自 pyopenssl（目录 src/urllib3/contrib 有 10 个文件，太大不宜整体当域））、`identifier_root=s_s_l_transport`（来自 SSLTransport（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`identifier_root=unsupported_extension`（来自 UnsupportedExtension（目录 src/urllib3/contrib 有 10 个文件，太大不宜整体当域））、`identifier_root=wrapped_socket`（来自 WrappedSocket（目录 src/urllib3/contrib 有 10 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=call_adjacent(3)`（域合并依据）、`merge=same_file(5)`（域合并依据）、…共 11 条
- 涉及文件：`src/urllib3/contrib/pyopenssl.py`、`src/urllib3/util/ssltransport.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_py_open_s_s_l_context_create_general` | 提交/创建操作 | `create/` | `inferred` | `makefile` — `src/urllib3/util/ssltransport.py:116-166` |
| `c_d_py_open_s_s_l_context_misc_unclassified` | 其他能力（待归类：inject_into_urllib3、extract_from_urllib3、_dnsname_to_stdlib、fileno 等 27 个） | `misc/unclassified` | `inferred-low` | `inject_into_urllib3` — `src/urllib3/contrib/pyopenssl.py:141-149` ；`extract_from_urllib3` — `src/urllib3/contrib/pyopenssl.py:152-158` ；`_dnsname_to_stdlib` — `src/urllib3/contrib/pyopenssl.py:187-225` ；`fileno` — `src/urllib3/contrib/pyopenssl.py:300-301` ；`_decref_socketios` — `src/urllib3/contrib/pyopenssl.py:304-308` ；`recv` — `src/urllib3/contrib/pyopenssl.py:310-333` ；`recv_into` — `src/urllib3/contrib/pyopenssl.py:335-356` ；`shutdown` — `src/urllib3/contrib/pyopenssl.py:380-384` ；`version` — `src/urllib3/contrib/pyopenssl.py:421-422` ；`selected_alpn_protocol` — `src/urllib3/contrib/pyopenssl.py:424-426` ；`options` — `src/urllib3/contrib/pyopenssl.py:449-450` ；`options` — `src/urllib3/contrib/pyopenssl.py:453-455` ；`wrap_socket` — `src/urllib3/contrib/pyopenssl.py:539-568` ；`minimum_version` — `src/urllib3/contrib/pyopenssl.py:578-579` ；`minimum_version` — `src/urllib3/contrib/pyopenssl.py:582-584` ；`maximum_version` — `src/urllib3/contrib/pyopenssl.py:587-588` ；`maximum_version` — `src/urllib3/contrib/pyopenssl.py:591-593` ；`fileno` — `src/urllib3/util/ssltransport.py:78-79` ；`recv` — `src/urllib3/util/ssltransport.py:84-87` ；`recv_into` — `src/urllib3/util/ssltransport.py:89-99` ；`unwrap` — `src/urllib3/util/ssltransport.py:168-169` ；`version` — `src/urllib3/util/ssltransport.py:185-186` ；`cipher` — `src/urllib3/util/ssltransport.py:188-189` ；`selected_alpn_protocol` — `src/urllib3/util/ssltransport.py:191-192` ；`shared_ciphers` — `src/urllib3/util/ssltransport.py:194-195` ；`compression` — `src/urllib3/util/ssltransport.py:197-198` ；`_decref_socketios` — `src/urllib3/util/ssltransport.py:206-207` |
| `c_d_py_open_s_s_l_context_notify_general` | 通知/告警操作 | `notify/` | `inferred` | `_send_until_done` — `src/urllib3/contrib/pyopenssl.py:361-370` ；`sendall` — `src/urllib3/contrib/pyopenssl.py:372-378` ；`sendall` — `src/urllib3/util/ssltransport.py:101-109` ；`send` — `src/urllib3/util/ssltransport.py:111-114` ；`_ssl_io_loop` — `src/urllib3/util/ssltransport.py:220` ；`_ssl_io_loop` — `src/urllib3/util/ssltransport.py:224` ；`_ssl_io_loop` — `src/urllib3/util/ssltransport.py:228-233` ；`_ssl_io_loop` — `src/urllib3/util/ssltransport.py:235-271` |
| `c_d_py_open_s_s_l_context_query_general` | 查询/读取操作 | `query/` | `inferred` | `get_subj_alt_name` — `src/urllib3/contrib/pyopenssl.py:228-273` ；`_get_common_name` — `src/urllib3/contrib/pyopenssl.py:276-282` ；`getpeercert` — `src/urllib3/contrib/pyopenssl.py:398-400` ；`getpeercert` — `src/urllib3/contrib/pyopenssl.py:403` ；`getpeercert` — `src/urllib3/contrib/pyopenssl.py:405-419` ；`load_verify_locations` — `src/urllib3/contrib/pyopenssl.py:482-497` ；`load_cert_chain` — `src/urllib3/contrib/pyopenssl.py:499-533` ；`read` — `src/urllib3/util/ssltransport.py:81-82` ；`getpeercert` — `src/urllib3/util/ssltransport.py:175-177` ；`getpeercert` — `src/urllib3/util/ssltransport.py:180` ；`getpeercert` — `src/urllib3/util/ssltransport.py:182-183` ；`gettimeout` — `src/urllib3/util/ssltransport.py:203-204` ；`_wrap_ssl_read` — `src/urllib3/util/ssltransport.py:209-216` |
| `c_d_py_open_s_s_l_context_transition_general` | 状态流转操作 | `transition/` | `inferred` | `close` — `src/urllib3/contrib/pyopenssl.py:386-389` ；`_real_close` — `src/urllib3/contrib/pyopenssl.py:391-395` ；`close` — `src/urllib3/util/ssltransport.py:171-172` |
| `c_d_py_open_s_s_l_context_update_general` | 更新/修改操作 | `update/` | `inferred` | `settimeout` — `src/urllib3/contrib/pyopenssl.py:358-359` ；`set_default_verify_paths` — `src/urllib3/contrib/pyopenssl.py:474-475` ；`set_ciphers` — `src/urllib3/contrib/pyopenssl.py:477-480` ；`set_alpn_protocols` — `src/urllib3/contrib/pyopenssl.py:535-537` ；`_set_ctx_options` — `src/urllib3/contrib/pyopenssl.py:570-575` ；`settimeout` — `src/urllib3/util/ssltransport.py:200-201` |
| `c_d_py_open_s_s_l_context_validate_general` | 校验/检测操作 | `validate/` | `inferred` | `_validate_dependencies_met` — `src/urllib3/contrib/pyopenssl.py:161-184` ；`verify_flags` — `src/urllib3/contrib/pyopenssl.py:458-459` ；`verify_flags` — `src/urllib3/contrib/pyopenssl.py:462-464` ；`verify_mode` — `src/urllib3/contrib/pyopenssl.py:467-468` ；`verify_mode` — `src/urllib3/contrib/pyopenssl.py:471-472` ；`_verify_callback` — `src/urllib3/contrib/pyopenssl.py:596-603` ；`_validate_ssl_context_for_tls_in_tls` — `src/urllib3/util/ssltransport.py:34-47` |

### 15. `d_ssl` · **Ssl**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 6 个
- 聚类依据：`identifier_root=ssl`（来自 ssl_（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`identifier_root=t_y_p_e_p_e_e_r_c_e_r_t_r_e_t_d_i_c_t`（来自 _TYPE_PEER_CERT_RET_DICT（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）、`merge=same_file(5)`（域合并依据）、`merge=shared_token:ssl(1)`（域合并依据）、`merge=shared_token:ssl(5)`（域合并依据）
- 涉及文件：`src/urllib3/util/ssl_.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_ssl_create_general` | 提交/创建操作 | `create/` | `inferred` | `create_urllib3_context` — `src/urllib3/util/ssl_.py:184-328` |
| `c_d_ssl_misc_file` | 文件相关操作 | `misc/file` | `inferred-low` | `_is_key_file_encrypted` — `src/urllib3/util/ssl_.py:454-462` |
| `c_d_ssl_misc_unclassified` | 其他能力（待归类：ssl_wrap_socket、ssl_wrap_socket、ssl_wrap_socket、is_ipaddress 等 5 个） | `misc/unclassified` | `inferred-low` | `ssl_wrap_socket` — `src/urllib3/util/ssl_.py:332-346` ；`ssl_wrap_socket` — `src/urllib3/util/ssl_.py:350-364` ；`ssl_wrap_socket` — `src/urllib3/util/ssl_.py:367-438` ；`is_ipaddress` — `src/urllib3/util/ssl_.py:441-451` ；`_ssl_wrap_socket_impl` — `src/urllib3/util/ssl_.py:465-481` |
| `c_d_ssl_query_general` | 查询/读取操作 | `query/` | `inferred` | `resolve_cert_reqs` — `src/urllib3/util/ssl_.py:145-165` ；`resolve_ssl_version` — `src/urllib3/util/ssl_.py:168-181` |
| `c_d_ssl_validate_check` | 校验检查 | `validate/check` | `inferred-low` | `_is_has_never_check_common_name_reliable` — `src/urllib3/util/ssl_.py:31-38` |
| `c_d_ssl_validate_general` | 校验/检测操作 | `validate/` | `inferred` | `assert_fingerprint` — `src/urllib3/util/ssl_.py:108-142` |

### 16. `d_t_y_p_e_d_e_f_a_u_l_t` · **TYPEDEFAULT**

- 角色 `core` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_identifier` ｜ 单元 2 个 ｜ 子能力点 4 个
- 聚类依据：`identifier_root=t_y_p_e_d_e_f_a_u_l_t`（来自 _TYPE_DEFAULT（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`identifier_root=timeout`（来自 Timeout（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`merge=same_file(5)`（域合并依据）、`merge=shared_token:a,d(1)`（域合并依据）、`merge=shared_token:d,e(1)`（域合并依据）、`merge=shared_token:e,p(1)`（域合并依据）
- 涉及文件：`src/urllib3/util/timeout.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_t_y_p_e_d_e_f_a_u_l_t_misc_unclassified` | 其他能力（待归类：from_float、clone、connect_timeout） | `misc/unclassified` | `inferred-low` | `from_float` — `src/urllib3/util/timeout.py:173-186` ；`clone` — `src/urllib3/util/timeout.py:188-200` ；`connect_timeout` — `src/urllib3/util/timeout.py:228-243` |
| `c_d_t_y_p_e_d_e_f_a_u_l_t_query_general` | 查询/读取操作 | `query/` | `inferred` | `resolve_default_timeout` — `src/urllib3/util/timeout.py:127-128` ；`get_connect_duration` — `src/urllib3/util/timeout.py:213-225` ；`read_timeout` — `src/urllib3/util/timeout.py:246-275` |
| `c_d_t_y_p_e_d_e_f_a_u_l_t_transition_general` | 状态流转操作 | `transition/` | `inferred` | `start_connect` — `src/urllib3/util/timeout.py:202-211` |
| `c_d_t_y_p_e_d_e_f_a_u_l_t_validate_general` | 校验/检测操作 | `validate/` | `inferred-low` | `_validate_timeout` — `src/urllib3/util/timeout.py:131-170` |

### 17. `d_url` · **系统装配（url）**

- 角色 `orchestrator` ｜ 置信度 `inferred` ｜ 命名词根来源 `from_structural_role` ｜ 单元 2 个 ｜ 子能力点 4 个
- 聚类依据：`identifier_root=url`（来自 Url（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`identifier_root=url`（来自 url（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`src/urllib3/util/url.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_url_delete_file` | 删除文件 | `delete/file` | `inferred-low` | `_remove_path_dot_segments` — `src/urllib3/util/url.py:323-350` |
| `c_d_url_misc_unclassified` | 其他能力（待归类：auth_decoded、auth_decoded_joined、hostname、request_uri 等 9 个） | `misc/unclassified` | `inferred-low` | `auth_decoded` — `src/urllib3/util/url.py:127-141` ；`auth_decoded_joined` — `src/urllib3/util/url.py:144-164` ；`hostname` — `src/urllib3/util/url.py:167-169` ；`request_uri` — `src/urllib3/util/url.py:172-179` ；`authority` — `src/urllib3/util/url.py:182-195` ；`netloc` — `src/urllib3/util/url.py:198-209` ；`url` — `src/urllib3/util/url.py:212-257` ；`_normalize_host_percent_encoding` — `src/urllib3/util/url.py:415-422` ；`_normalize_zone_id_percent_encoding` — `src/urllib3/util/url.py:425-429` |
| `c_d_url_query_general` | 查询/读取操作 | `query/` | `inferred` | `_encode_invalid_chars` — `src/urllib3/util/url.py:264-267` ；`_encode_invalid_chars` — `src/urllib3/util/url.py:271-274` ；`_encode_invalid_chars` — `src/urllib3/util/url.py:277-320` ；`_remove_path_dot_segments` — `src/urllib3/util/url.py:323-350` ；`_normalize_host` — `src/urllib3/util/url.py:354` ；`_normalize_host` — `src/urllib3/util/url.py:358` ；`_normalize_host` — `src/urllib3/util/url.py:361-399` ；`parse_url` — `src/urllib3/util/url.py:471-577` |
| `c_d_url_serialize_general` | 序列化/格式化操作 | `serialize/` | `inferred-low` | `_encode_invalid_chars` — `src/urllib3/util/url.py:264-267` ；`_encode_invalid_chars` — `src/urllib3/util/url.py:271-274` ；`_encode_invalid_chars` — `src/urllib3/util/url.py:277-320` ；`_decode_percent_encoding` — `src/urllib3/util/url.py:402-412` ；`_idna_encode` — `src/urllib3/util/url.py:432-450` ；`_encode_target` — `src/urllib3/util/url.py:453-468` |

### 18. `d_util` · **系统装配（util）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 1 个
- 聚类依据：`identifier_root=util`（来自 util（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`src/urllib3/util/util.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_util_misc_unclassified` | 其他能力（待归类：to_bytes、to_str、reraise） | `misc/unclassified` | `inferred-low` | `to_bytes` — `src/urllib3/util/util.py:7-16` ；`to_str` — `src/urllib3/util/util.py:19-28` ；`reraise` — `src/urllib3/util/util.py:31-42` |

### 19. `d_wait` · **系统装配（wait）**

- 角色 `orchestrator` ｜ 置信度 `inferred-low` ｜ 命名词根来源 `from_structural_role` ｜ 单元 1 个 ｜ 子能力点 2 个
- 聚类依据：`identifier_root=wait`（来自 wait（目录 src/urllib3/util 有 19 个文件，太大不宜整体当域））、`merge=call_adjacent(2)`（域合并依据）
- 涉及文件：`src/urllib3/util/wait.py`

| 能力点 | 系统命名 | 动词/对象 | 置信度 | 成员函数（文件:行） |
|---|---|---|---|---|
| `c_d_wait_misc_unclassified` | 其他能力（待归类：select_wait_for_socket、poll_wait_for_socket、_have_working_poll、wait_for_socket 等 5 个） | `misc/unclassified` | `inferred-low` | `select_wait_for_socket` — `src/urllib3/util/wait.py:33-54` ；`poll_wait_for_socket` — `src/urllib3/util/wait.py:57-79` ；`_have_working_poll` — `src/urllib3/util/wait.py:82-92` ；`wait_for_socket` — `src/urllib3/util/wait.py:95-110` ；`wait_for_write` — `src/urllib3/util/wait.py:120-124` |
| `c_d_wait_query_general` | 查询/读取操作 | `query/` | `inferred` | `wait_for_read` — `src/urllib3/util/wait.py:113-117` |

---

# 业务图谱 · 多项目验证报告

> 由 `python scripts/validate_business_graph.py` 生成。**可重复执行**。

> 
> **这份报告里没有「准确率」** —— 准确率必须人工核对后才有。
> 脚本只负责把**可机器判定**的指标算出来，并把人工核对所需的材料列全。
> README4 §9.2：不美化数据；自造样本不得用来报告准确率。


## 1. 规模与产出

| 项目 | 类型 | 文件 | 行数 | 域 | 功能点 | 卡片 | 事实 | 关系 | 流程 | 级别 | 耗时 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `sample_projects/lab_safety_assistant` | **自造样本** | 6 | 784 | 5 | 29 | 34 | 133 | 8 | 6 | L2 | 0.12s |
| `validation/python_dotenv` | 真实第三方 | 8 | 1112 | 6 | 24 | 30 | 74 | 3 | 8 | L2 | 0.1s |
| `validation/flask` | 真实第三方 | 24 | 9513 | 12 | 54 | 66 | 459 | 23 | 9 | L3 | 0.79s |
| `validation/urllib3` | 真实第三方 | 42 | 13940 | 19 | 69 | 88 | 1044 | 22 | 8 | L3 | 1.4s |

> ⚠️ **`sample_projects/lab_safety_assistant` 是自造样本，其上的任何指标都不具备说服力**
> （启发式规则就是照着它调的，等于在训练集上报告成绩）。
> 它留在这里只作为**对照基线**：如果真实第三方项目的指标比它差很多，说明规则过拟合了。


## 2. 命名来源分布（可机器判定）

`from_docstring` = 作者自己写的中文 docstring（最可靠）；
`from_lexicon` = 词典翻译；`from_identifier` = 只能退回标识符词根（**质量最差**）；
`from_structural_role` = 结构性角色名（如「系统装配」）。

| 项目 | 域：docstring / lexicon / identifier / structural | 功能点：docstring / lexicon / identifier |
|---|---|---|
| `sample_projects/lab_safety_assistant` | 4 / 0 / 0 / 1 | 22 / 7 / 0 |
| `validation/python_dotenv` | 0 / 0 / 3 / 3 | 0 / 20 / 0 |
| `validation/flask` | 0 / 0 / 8 / 4 | 0 / 43 / 0 |
| `validation/urllib3` | 0 / 0 / 12 / 7 | 0 / 50 / 0 |

## 3. 置信度与退化指标（可机器判定）

| 项目 | 域置信度 | 功能点置信度 | 成员带行号 | 二级卡片带证据 | 事实带行号 | flat 层级域 | 待归类功能点 | 目标待教师填 |
|---|---|---|---|---|---|---|---|---|
| `sample_projects/lab_safety_assistant` | {'inferred': 5} | {'inferred': 26, 'inferred-low': 3} | 37/37 (100.0%) | 29/29 (100.0%) | 133/133 (100.0%) | 1/5 | 0/29 (0.0%) | 3/29 (10.3%) |
| `validation/python_dotenv` | {'inferred': 4, 'inferred-low': 2} | {'inferred': 19, 'inferred-low': 5} | 51/51 (100.0%) | 24/24 (100.0%) | 74/74 (100.0%) | 3/6 | 4/24 (16.7%) | 11/24 (45.8%) |
| `validation/flask` | {'inferred': 10, 'inferred-low': 2} | {'inferred': 33, 'inferred-low': 21} | 318/318 (100.0%) | 54/54 (100.0%) | 459/459 (100.0%) | 5/12 | 11/54 (20.4%) | 13/54 (24.1%) |
| `validation/urllib3` | {'inferred-low': 6, 'inferred': 13} | {'inferred': 40, 'inferred-low': 29} | 495/495 (100.0%) | 69/69 (100.0%) | 1044/1044 (100.0%) | 5/19 | 19/69 (27.5%) | 28/69 (40.6%) |

**怎么读这张表**：
- `成员带行号` / `二级卡片带证据` / `事实带行号` 越接近 100% 越好 —— 它们决定「结论能不能回指代码」；
- `待归类功能点` 比例高，说明词典覆盖不住这个项目的命名风格（**这是引擎的真实短板，要如实写进材料**）；
- `目标待教师填` 是**设计上就应该高**的：README4 §2.1 要求业务含义必须由教师确认，规则引擎给不出就不编。


## 4. 确定性

| 项目 | 同进程双跑逐字节一致 |
|---|---|
| `sample_projects/lab_safety_assistant` | ✅ 是 |
| `validation/python_dotenv` | ✅ 是 |
| `validation/flask` | ✅ 是 |
| `validation/urllib3` | ✅ 是 |

## 5. 场景类型分布

| 项目 | normal | exception | edge_case |
|---|---:|---:|---:|
| `sample_projects/lab_safety_assistant` | 5 | 0 | 1 |
| `validation/python_dotenv` | 8 | 0 | 0 |
| `validation/flask` | 9 | 0 | 0 |
| `validation/urllib3` | 8 | 0 | 0 |

## 6. 人工核对模板

**下面每一行的「人工判定」列都必须由人填写**，脚本不填。
建议的判定口径（三分类，不要用「对/错」二分）：

| 判定 | 含义 |
|---|---|
| `正确` | 划分与命名都符合业务实际 |
| `命名不当` | 划分对了，但中文名不准（可由教师改名修掉） |
| `划分错误` | 该合没合 / 该拆没拆 / 根本不该存在 |
| `无法判定` | 需要业务知识，标成待教师确认 |

> 统计口径：`划分错误 / 总域数` 才是「业务图谱划分错误率」，
> 它和 README2 §19 的「事实错误率」**不是一回事，不能混着报**。


### 6.x `validation/python_dotenv`（1112 行）

#### 一级业务域

| domain_id | 系统命名 | 角色 | 置信度 | 子节点 | 聚类依据 | 人工判定 | 备注 |
|---|---|---|---|---:|---|---|---|
| `d_atom` | Atom | core | inferred | 1 | identifier_root=atom; identifier_root=literal; identifier_root=variable; identifier_root=variables |  |  |
| `d_binding` | Binding | core | inferred | 7 | identifier_root=binding; identifier_root=error; identifier_root=original; identifier_root=parser |  |  |
| `d_cli` | 系统装配（cli） | orchestrator | inferred-low | 5 | identifier_root=cli; merge=call_adjacent(2) |  |  |
| `d_dot_env` | 系统装配（main） | orchestrator | inferred | 8 | identifier_root=dot_env; identifier_root=main; merge=call_adjacent(2); merge=call_adjacent(6) |  |  |
| `d_i_python_dot_env` | I Python Dot Env | core | inferred | 2 | identifier_root=i_python_dot_env; identifier_root=ipython; merge=call_adjacent(2); merge=same_file(5) |  |  |
| `d_init` | 系统装配（__init__） | orchestrator | inferred-low | 1 | identifier_root=init; merge=call_adjacent(2) |  |  |

#### 二级功能点

| capability_id | 系统命名 | 所属域 | 动词/对象 | 置信度 | 成员函数 | 人工判定 | 备注 |
|---|---|---|---|---|---|---|---|
| `c_d_atom_query_general` | 查询/读取操作 | `d_atom` | query/ | inferred | resolve, resolve, resolve, parse_variables |  |  |
| `c_d_binding_create_general` | 提交/创建操作 | `d_binding` | create/ | inferred | make_regex |  |  |
| `c_d_binding_misc_unclassified` | 其他能力（待归类：advance、has_next、peek） | `d_binding` | misc/unclassified | inferred-low | advance, has_next, peek |  |  |
| `c_d_binding_query_general` | 查询/读取操作 | `d_binding` | query/ | inferred | get_marked, read, read_regex, parse_binding, parse_stream |  |  |
| `c_d_binding_query_value` | 查询数据项 | `d_binding` | query/value | inferred | parse_key, parse_unquoted_value, parse_value |  |  |
| `c_d_binding_serialize_general` | 序列化/格式化操作 | `d_binding` | serialize/ | inferred | decode_escapes |  |  |
| `c_d_binding_transition_general` | 状态流转操作 | `d_binding` | transition/ | inferred | start |  |  |
| `c_d_binding_update_general` | 更新/修改操作 | `d_binding` | update/ | inferred | set, set_mark |  |  |
| `c_d_cli_misc_config` | 配置相关操作 | `d_cli` | misc/config | inferred | enumerate_env |  |  |
| `c_d_cli_misc_file` | 文件相关操作 | `d_cli` | misc/file | inferred | stream_file |  |  |
| `c_d_cli_misc_unclassified` | 其他能力（待归类：cli、unset、run、run_command） | `d_cli` | misc/unclassified | inferred-low | cli, unset, run, run_command |  |  |
| `c_d_cli_query_general` | 查询/读取操作 | `d_cli` | query/ | inferred | list_values, get |  |  |
| `c_d_cli_update_value` | 修改数据项 | `d_cli` | update/value | inferred | set_value |  |  |
| `c_d_dot_env_misc_file` | 文件相关操作 | `d_dot_env` | misc/file | inferred-low | _is_file_or_fifo |  |  |
| `c_d_dot_env_misc_unclassified` | 其他能力（待归类：dict、rewrite、dotenv_values） | `d_dot_env` | misc/unclassified | inferred-low | dict, rewrite, dotenv_values |  |  |
| `c_d_dot_env_misc_value` | 数据项相关操作 | `d_dot_env` | misc/value | inferred | unset_key |  |  |
| `c_d_dot_env_notify_general` | 通知/告警操作 | `d_dot_env` | notify/ | inferred | with_warn_for_invalid_lines |  |  |
| `c_d_dot_env_query_general` | 查询/读取操作 | `d_dot_env` | query/ | inferred | _load_dotenv_disabled, _get_stream, parse, get, resolve_variables, _walk_to_root, find_dotenv, load_dotenv, _is_file_or_fifo |  |  |
| `c_d_dot_env_query_value` | 查询数据项 | `d_dot_env` | query/value | inferred | get_key |  |  |
| `c_d_dot_env_update_general` | 更新/修改操作 | `d_dot_env` | update/ | inferred | set_as_environment_variables |  |  |
| `c_d_dot_env_update_value` | 修改数据项 | `d_dot_env` | update/value | inferred | set_key |  |  |
| `c_d_i_python_dot_env_misc_unclassified` | 其他能力（待归类：dotenv） | `d_i_python_dot_env` | misc/unclassified | inferred-low | dotenv |  |  |
| `c_d_i_python_dot_env_query_general` | 查询/读取操作 | `d_i_python_dot_env` | query/ | inferred | load_ipython_extension |  |  |
| `c_d_init_query_general` | 查询/读取操作 | `d_init` | query/ | inferred | load_ipython_extension, get_cli_string |  |  |

### 6.x `validation/flask`（9513 行）

#### 一级业务域

| domain_id | 系统命名 | 角色 | 置信度 | 子节点 | 聚类依据 | 人工判定 | 备注 |
|---|---|---|---|---:|---|---|---|
| `d_app` | App | core | inferred | 15 | identifier_root=app; identifier_root=app; identifier_root=app; identifier_root=app_context |  |  |
| `d_app_context_proxy` | App Context Proxy | core | inferred | 1 | identifier_root=app_context_proxy; identifier_root=app_ctx_globals_proxy; identifier_root=flask_proxy; identifier_root=globals |  |  |
| `d_app_group` | App Group | core | inferred | 8 | identifier_root=app_group; identifier_root=cert_param_type; identifier_root=cli; identifier_root=flask_group |  |  |
| `d_collect_errors` | Collect Errors | core | inferred | 7 | identifier_root=collect_errors; identifier_root=helpers; merge=call_adjacent(2); merge=same_file(5) |  |  |
| `d_debug_files_key_error` | Debug Files Key Error | core | inferred | 2 | identifier_root=debug_files_key_error; identifier_root=debughelpers; identifier_root=form_data_routing_redirect; identifier_root=unexpected_unicode_error |  |  |
| `d_default_j_s_o_n` | 系统装配（provider） | orchestrator | inferred | 3 | identifier_root=default_j_s_o_n; identifier_root=j_s_o_n; identifier_root=provider; merge=call_adjacent(2) |  |  |
| `d_init` | 系统装配（__init__） | orchestrator | inferred-low | 3 | identifier_root=init; merge=call_adjacent(2) |  |  |
| `d_j_s_o_n_tag` | JSON Tag | core | inferred | 5 | identifier_root=j_s_o_n_tag; identifier_root=pass_dict; identifier_root=pass_list; identifier_root=tag_bytes |  |  |
| `d_logging` | 系统装配（logging） | orchestrator | inferred-low | 2 | identifier_root=logging; merge=call_adjacent(2) |  |  |
| `d_method_view` | 系统装配（views） | orchestrator | inferred | 1 | identifier_root=method_view; identifier_root=view; merge=call_adjacent(2); merge=same_file(5) |  |  |
| `d_null_session` | Null Session | core | inferred | 5 | identifier_root=null_session; identifier_root=secure_cookie_session; identifier_root=secure_cookie_session_interface; identifier_root=session_interface |  |  |
| `d_request` | Request | core | inferred | 2 | identifier_root=request; identifier_root=response; merge=call_adjacent(2); merge=same_file(5) |  |  |

#### 二级功能点

| capability_id | 系统命名 | 所属域 | 动词/对象 | 置信度 | 成员函数 | 人工判定 | 备注 |
|---|---|---|---|---|---|---|---|
| `c_d_app_configure_general` | 配置/装配操作 | `d_app` | configure/ | inferred | _check_setup_finished, _check_setup_finished, setupmethod, _check_setup_finished |  |  |
| `c_d_app_create_config` | 提交配置 | `d_app` | create/config | inferred | make_config, add_template_filter, add_template_test, add_template_global |  |  |
| `c_d_app_create_general` | 提交/创建/删除/移除操作 | `d_app` | create/ | inferred | _make_timedelta, remove_ctx, add_ctx, open_resource, open_instance_resource, create_jinja_environment, create_url_adapter, update_template_context, make_shell_context, make_default_options_response, make_response, process_response, open_resource, setdefault, _get_session, _make_timedelta, create_jinja_environment, make_aborter, create_global_jinja_loader, register_blueprint, add_url_rule, handle_url_build_error, add_url_rule, make_setup_state, register_blueprint, register, _merge_blueprint_funcs, add_url_rule, add_app_template_filter, add_app_template_test, add_app_template_global, _method_route, delete, patch, add_url_rule, register_error_handler, _get_exc_class_and_code, _endpoint_from_view_func, _copy_environ, _request_from_builder_args, open |  |  |
| `c_d_app_misc_config` | 配置相关操作 | `d_app` | misc/config | inferred | from_prefixed_env, jinja_env, debug, debug |  |  |
| `c_d_app_misc_file` | 文件相关操作 | `d_app` | misc/file | inferred | from_file, static_folder, static_folder, has_static_folder, static_url_path, static_url_path |  |  |
| `c_d_app_misc_record` | 记录相关操作 | `d_app` | misc/record | inferred | log_exception, record, record_once |  |  |
| `c_d_app_misc_unclassified` | 其他能力（待归类：raise_routing_exception、run、test_client、test_cli_runner 等 89 个） | `d_app` | misc/unclassified | inferred-low | raise_routing_exception, run, test_client, test_cli_runner, handle_http_exception, handle_exception, dispatch_request, full_dispatch_request, finalize_request, async_to_sync, url_for, preprocess_request, do_teardown_request, do_teardown_appcontext, app_context, request_context, test_request_context, wsgi_app, from_envvar, from_pyfile, from_object, from_mapping, pop, after_this_request, copy_current_request_context, has_request_context, has_app_context, from_environ, has_request, copy, request, session, match_request, push, pop, name, logger, select_jinja_autoescape, iter_blueprints, template_filter, template_filter, template_filter, template_test, template_test, template_test, template_global, template_global, template_global, teardown_appcontext, shell_context_processor, trap_http_exception, redirect, inject_url_defaults, app_template_filter, app_template_filter, app_template_filter, app_template_test, app_template_test, app_template_test, app_template_global, app_template_global, app_template_global, before_app_request, after_app_request, teardown_app_request, app_context_processor, app_errorhandler, app_url_defaults, jinja_loader, post, put, route, endpoint, before_request, after_request, teardown_request, context_processor, url_defaults, errorhandler, _default_template_ctx_processor, _iter_loaders, _render, render_template, render_template_string, _stream, stream_template, stream_template_string, session_transaction, invoke |  |  |
| `c_d_app_misc_user` | 用户相关操作 | `d_app` | misc/user | inferred | handle_user_exception, _find_error_handler |  |  |
| `c_d_app_misc_value` | 数据项相关操作 | `d_app` | misc/value | inferred | app_url_value_preprocessor, url_value_preprocessor |  |  |
| `c_d_app_notify_file` | 通知文件 | `d_app` | notify/file | inferred | send_static_file, send_static_file |  |  |
| `c_d_app_query_file` | 查询文件 | `d_app` | query/file | inferred | get_send_file_max_age, get_send_file_max_age, auto_find_instance_path, _find_package_path |  |  |
| `c_d_app_query_general` | 查询/读取操作 | `d_app` | query/ | inferred | get_namespace, get, _get_session, _find_error_handler, get, query, _get_exc_class_and_code, _find_package_path, find_package, get_source, _get_source_explained, _get_source_fast, list_templates, _get_werkzeug_version |  |  |
| `c_d_app_serialize_general` | 序列化/格式化操作 | `d_app` | serialize/ | inferred | json_dumps |  |  |
| `c_d_app_validate_check` | 校验检查 | `d_app` | validate/check | inferred-low | _check_setup_finished, _check_setup_finished, _check_setup_finished |  |  |
| `c_d_app_validate_general` | 校验/检测操作 | `d_app` | validate/ | inferred | ensure_sync |  |  |
| `c_d_app_context_proxy_query_general` | 查询/读取操作 | `d_app_context_proxy` | query/ | inferred-low | _get_current_object |  |  |
| `c_d_app_group_create_general` | 提交/创建操作 | `d_app_group` | create/ | inferred | make_context |  |  |
| `c_d_app_group_misc_config` | 配置相关操作 | `d_app_group` | misc/config | inferred-low | _env_file_callback |  |  |
| `c_d_app_group_misc_file` | 文件相关操作 | `d_app_group` | misc/file | inferred-low | _path_is_ancestor |  |  |
| `c_d_app_group_misc_role` | 角色权限相关操作 | `d_app_group` | misc/role | inferred | group |  |  |
| `c_d_app_group_misc_unclassified` | 其他能力（待归类：prepare_import、locate_app、locate_app、locate_app 等 13 个） | `d_app_group` | misc/unclassified | inferred-low | prepare_import, locate_app, locate_app, locate_app, with_appcontext, command, show_server_banner, convert, convert, run_command, shell_command, routes_command, main |  |  |
| `c_d_app_group_query_general` | 查询/读取操作 | `d_app_group` | query/ | inferred | find_best_app, _called_with_wrong_args, find_app_by_string, get_version, load_app, _load_plugin_commands, get_command, list_commands, parse_args, load_dotenv |  |  |
| `c_d_app_group_update_general` | 更新/修改操作 | `d_app_group` | update/ | inferred-low | _set_app, _set_debug |  |  |
| `c_d_app_group_validate_value` | 校验数据项 | `d_app_group` | validate/value | inferred-low | _validate_key |  |  |
| `c_d_collect_errors_cancel_general` | 取消/撤回操作 | `d_collect_errors` | cancel/ | inferred | abort |  |  |
| `c_d_collect_errors_create_general` | 提交/创建操作 | `d_collect_errors` | create/ | inferred | make_response |  |  |
| `c_d_collect_errors_misc_file` | 文件相关操作 | `d_collect_errors` | misc/file | inferred-low | _split_blueprint_path |  |  |
| `c_d_collect_errors_misc_unclassified` | 其他能力（待归类：stream_with_context、stream_with_context、stream_with_context、url_for 等 7 个） | `d_collect_errors` | misc/unclassified | inferred-low | stream_with_context, stream_with_context, stream_with_context, url_for, redirect, flash, raise_any |  |  |
| `c_d_collect_errors_notify_file` | 通知文件 | `d_collect_errors` | notify/file | inferred | _prepare_send_file_kwargs, send_file, send_from_directory |  |  |
| `c_d_collect_errors_query_file` | 查询文件 | `d_collect_errors` | query/file | inferred | get_root_path |  |  |
| `c_d_collect_errors_query_general` | 查询/读取操作 | `d_collect_errors` | query/ | inferred | get_debug_flag, get_load_dotenv, get_template_attribute, get_flashed_messages |  |  |
| `c_d_debug_files_key_error_misc_unclassified` | 其他能力（待归类：attach_enctype_error_multidict、explain_template_loading_attempts） | `d_debug_files_key_error` | misc/unclassified | inferred-low | attach_enctype_error_multidict, explain_template_loading_attempts |  |  |
| `c_d_debug_files_key_error_serialize_general` | 序列化/格式化操作 | `d_debug_files_key_error` | serialize/ | inferred-low | _dump_loader_info |  |  |
| `c_d_default_j_s_o_n_misc_unclassified` | 其他能力（待归类：_prepare_response_obj、response、_default、response） | `d_default_j_s_o_n` | misc/unclassified | inferred-low | _prepare_response_obj, response, _default, response |  |  |
| `c_d_default_j_s_o_n_query_general` | 查询/读取操作 | `d_default_j_s_o_n` | query/ | inferred | load |  |  |
| `c_d_default_j_s_o_n_serialize_general` | 序列化/格式化操作 | `d_default_j_s_o_n` | serialize/ | inferred | dumps, dump, loads, dumps, loads |  |  |
| `c_d_init_misc_unclassified` | 其他能力（待归类：jsonify） | `d_init` | misc/unclassified | inferred-low | jsonify |  |  |
| `c_d_init_query_general` | 查询/读取操作 | `d_init` | query/ | inferred | load |  |  |
| `c_d_init_serialize_general` | 序列化/格式化操作 | `d_init` | serialize/ | inferred | dumps, dump, loads |  |  |
| `c_d_j_s_o_n_tag_create_general` | 提交/创建操作 | `d_j_s_o_n_tag` | create/ | inferred | register |  |  |
| `c_d_j_s_o_n_tag_misc_unclassified` | 其他能力（待归类：to_json、to_python、tag、to_json 等 19 个） | `d_j_s_o_n_tag` | misc/unclassified | inferred-low | to_json, to_python, tag, to_json, to_python, to_json, to_json, to_python, to_json, to_json, to_python, to_json, to_python, to_json, to_python, to_json, to_python, tag, untag |  |  |
| `c_d_j_s_o_n_tag_query_general` | 查询/读取操作 | `d_j_s_o_n_tag` | query/ | inferred-low | _untag_scan |  |  |
| `c_d_j_s_o_n_tag_serialize_general` | 序列化/格式化操作 | `d_j_s_o_n_tag` | serialize/ | inferred | _untag_scan, dumps, loads |  |  |
| `c_d_j_s_o_n_tag_validate_check` | 校验检查 | `d_j_s_o_n_tag` | validate/check | inferred | check, check, check, check, check, check, check, check, check |  |  |
| `c_d_logging_create_general` | 提交/创建操作 | `d_logging` | create/ | inferred | create_logger |  |  |
| `c_d_logging_misc_unclassified` | 其他能力（待归类：wsgi_errors_stream、has_level_handler） | `d_logging` | misc/unclassified | inferred-low | wsgi_errors_stream, has_level_handler |  |  |
| `c_d_method_view_misc_unclassified` | 其他能力（待归类：dispatch_request、as_view、dispatch_request） | `d_method_view` | misc/unclassified | inferred-low | dispatch_request, as_view, dispatch_request |  |  |
| `c_d_null_session_create_general` | 提交/创建操作 | `d_null_session` | create/ | inferred | make_null_session, open_session, open_session |  |  |
| `c_d_null_session_misc_unclassified` | 其他能力（待归类：permanent、permanent、_fail、is_null_session 等 7 个） | `d_null_session` | misc/unclassified | inferred-low | permanent, permanent, _fail, is_null_session, save_session, _lazy_sha1, save_session |  |  |
| `c_d_null_session_query_file` | 查询文件 | `d_null_session` | query/file | inferred | get_cookie_path |  |  |
| `c_d_null_session_query_general` | 查询/读取操作 | `d_null_session` | query/ | inferred | get_cookie_name, get_cookie_domain, get_cookie_httponly, get_cookie_secure, get_cookie_samesite, get_cookie_partitioned, get_expiration_time, get_signing_serializer |  |  |
| `c_d_null_session_update_general` | 更新/修改操作 | `d_null_session` | update/ | inferred | should_set_cookie |  |  |
| `c_d_request_misc_unclassified` | 其他能力（待归类：max_content_length、max_content_length、max_form_memory_size、max_form_memory_size 等 11 个） | `d_request` | misc/unclassified | inferred-low | max_content_length, max_content_length, max_form_memory_size, max_form_memory_size, max_form_parts, max_form_parts, endpoint, blueprint, blueprints, on_json_loading_failed, max_cookie_size |  |  |
| `c_d_request_query_general` | 查询/读取操作 | `d_request` | query/ | inferred-low | _load_form_data |  |  |

### 6.x `validation/urllib3`（13940 行）

#### 一级业务域

| domain_id | 系统命名 | 角色 | 置信度 | 子节点 | 聚类依据 | 人工判定 | 备注 |
|---|---|---|---|---:|---|---|---|
| `d_app` | 系统装配（app） | orchestrator | inferred-low | 3 | identifier_root=app; merge=call_adjacent(2) |  |  |
| `d_asgi_proxy` | Asgi Proxy | core | inferred | 9 | identifier_root=asgi_proxy; identifier_root=base_h_t_t_p_response; identifier_root=base_s_s_l_error; identifier_root=body_not_httplib_compatible |  |  |
| `d_base_h_t_t_p_connection` | Base HTTP Connection | core | inferred | 4 | identifier_root=base_h_t_t_p_connection; identifier_root=base_h_t_t_p_s_connection; identifier_root=proxy_config; identifier_root=response_options |  |  |
| `d_certificate_error` | Certificate Error | core | inferred | 1 | identifier_root=certificate_error; identifier_root=ssl_match_hostname; merge=same_file(5); merge=shared_token:error(1) |  |  |
| `d_chunks_and_content_length` | Chunks And Content Length | core | inferred | 3 | identifier_root=chunks_and_content_length; identifier_root=request; identifier_root=t_y_p_e_f_a_i_l_e_d_t_e_l_l; merge=same_file(5) |  |  |
| `d_config` | 系统装配（hypercornserver） | orchestrator | inferred | 3 | identifier_root=config; identifier_root=hypercornserver; merge=call_adjacent(2); merge=same_file(5) |  |  |
| `d_connection_marker` | Connection Marker | core | inferred | 6 | identifier_root=connection_marker; identifier_root=h_t_t_p_s_hypercorn_dummy_server_test_case; identifier_root=hypercorn_dummy_proxy_test_case; identifier_root=hypercorn_dummy_server_test_case |  |  |
| `d_emscripten_request` | Emscripten Request | core | inferred | 3 | identifier_root=emscripten_request; identifier_root=request_methods; merge=call_adjacent(3); merge=shared_state:headers(4) |  |  |
| `d_fields` | Fields | core | inferred | 3 | identifier_root=fields; identifier_root=request_field; merge=call_adjacent(7); merge=same_file(7) |  |  |
| `d_filepost` | 系统装配（filepost） | orchestrator | inferred-low | 2 | identifier_root=filepost; merge=call_adjacent(2) |  |  |
| `d_h_t_t_p2_probe_cache` | HTTP2 Probe Cache | core | inferred-low | 3 | identifier_root=h_t_t_p2_probe_cache; merge=call_adjacent(2); merge=call_adjacent(3); merge=shared_token:h,p2(3) |  |  |
| `d_init` | Init | core | inferred | 3 | identifier_root=init; identifier_root=init; identifier_root=init; merge=call_adjacent(2) |  |  |
| `d_noxfile` | 系统装配（noxfile） | orchestrator | inferred-low | 2 | identifier_root=noxfile; merge=call_adjacent(2) |  |  |
| `d_py_open_s_s_l_context` | Py Open SSL Context | core | inferred | 7 | identifier_root=py_open_s_s_l_context; identifier_root=pyopenssl; identifier_root=s_s_l_transport; identifier_root=unsupported_extension |  |  |
| `d_ssl` | Ssl | core | inferred | 6 | identifier_root=ssl; identifier_root=t_y_p_e_p_e_e_r_c_e_r_t_r_e_t_d_i_c_t; merge=call_adjacent(2); merge=same_file(5) |  |  |
| `d_t_y_p_e_d_e_f_a_u_l_t` | TYPEDEFAULT | core | inferred | 4 | identifier_root=t_y_p_e_d_e_f_a_u_l_t; identifier_root=timeout; merge=same_file(5); merge=shared_token:a,d(1) |  |  |
| `d_url` | 系统装配（url） | orchestrator | inferred | 4 | identifier_root=url; identifier_root=url; merge=call_adjacent(2) |  |  |
| `d_util` | 系统装配（util） | orchestrator | inferred-low | 1 | identifier_root=util; merge=call_adjacent(2) |  |  |
| `d_wait` | 系统装配（wait） | orchestrator | inferred-low | 2 | identifier_root=wait; merge=call_adjacent(2) |  |  |

#### 二级功能点

| capability_id | 系统命名 | 所属域 | 动词/对象 | 置信度 | 成员函数 | 人工判定 | 备注 |
|---|---|---|---|---|---|---|---|
| `c_d_app_create_general` | 提交/创建操作 | `d_app` | create/ | inferred | apply_caching |  |  |
| `c_d_app_misc_unclassified` | 其他能力（待归类：index、alpn_protocol、certificate、specific_method 等 30 个） | `d_app` | misc/unclassified | inferred-low | index, alpn_protocol, certificate, specific_method, upload, chunked, chunked_gzip, keepalive, echo, echo_json, echo_uri, echo_params, headers, headers_and_params, multi_headers, multi_redirect, encodingrequest, redirect, redirect_after, retry_after, status, source_address, successful_retry, slow, dripfeed, bigfile, mediumfile, pyodide_upload, pyodide, wheel |  |  |
| `c_d_app_query_general` | 查询/读取操作 | `d_app` | query/ | inferred-low | _find_built_wheel, _get_pyodide_template |  |  |
| `c_d_asgi_proxy_create_general` | 提交/创建/删除/移除操作 | `d_asgi_proxy` | create/ | inferred | _start_server, clear, setdefault, add, _prepare_for_method_change, _new_conn, set_tunnel, close, close, _new_pool_queue, _new_conn, _make_request, close, _new_conn, _close_pool_connections, set_tunnel, close, set_cert, _obj_from_dict, closed, close, closed, close, _init_length, close, _new_conn, _new_h2_conn, set_tunnel, close, close, _new_pool, clear, _set_proxy_headers, close, _init_decoder, _init_length, close, closed, _update_chunk_length, create_connection, _set_socket_options, new |  |  |
| `c_d_asgi_proxy_misc_unclassified` | 其他能力（待归类：absolute_uri、connect、_resolves_to_ipv6、_has_ipv6 等 151 个） | `d_asgi_proxy` | misc/unclassified | inferred-low | absolute_uri, connect, _resolves_to_ipv6, _has_ipv6, run, ssl_options_to_context, keys, keys, discard, extend, _copy_from, copy, iteritems, itermerged, items, host, host, _wrap_ipv6, _tunnel, _tunnel, connect, is_closed, is_connected, has_connected_to_proxy, proxy_is_forwarding, proxy_is_tunneling, putrequest, putheader, request, request_chunked, connect, _connect_tls_proxy, _ssl_wrap_socket_and_match_hostname, _match_hostname, _wrap_proxy_error, _put_conn, _prepare_proxy, _raise_timeout, is_same_host, urlopen, _prepare_proxy, connection_from_url, _normalize_host, _normalize_host, _normalize_host, _url_from_pool, connect, request, is_closed, is_connected, has_connected_to_proxy, is_closed, writable, seekable, is_closed, writable, seekable, is_in_browser_main_thread, is_cross_origin_isolated, is_in_node, is_worker_available, has_jspi, streaming_ready, wait_for_streaming_ready, url, url, connection, retries, retries, stream, release_conn, drain_conn, data, json, pool, _is_legal_header_name, connect, putrequest, putheader, endheaders, request, data, connection_from_host, connection_from_context, connection_from_url, _merge_pool_kwargs, _proxy_requires_url_absolute_form, urlopen, connection_from_host, urlopen, proxy_from_url, decompress, has_unconsumed_tail, flush, decompress, has_unconsumed_tail, flush, decompress, has_unconsumed_tail, flush, _decompress, decompress, has_unconsumed_tail, flush, decompress, has_unconsumed_tail, flush, flush, decompress, has_unconsumed_tail, put, data, json, url, url, connection, retries, retries, stream, release_conn, drain_conn, shutdown, info, release_conn, drain_conn, data, connection, isclosed, tell, stream, shutdown, fileno, flush, supports_chunked_reads, url, url, is_connection_dropped, allowed_gai_family, _has_ipv6, connection_requires_http_tunnel, is_fp_closed, is_response_to_head, from_int, sleep_for_retry, _sleep_backoff, sleep, _is_connection_error, _is_method_retryable, is_retry, is_exhausted, increment |  |  |
| `c_d_asgi_proxy_misc_value` | 数据项相关操作 | `d_asgi_proxy` | misc/value | inferred | encrypt_key_pem, _has_value_for_header, _normalize_header_value, _is_illegal_header_value, _default_key_normalizer, _new_pool, connection_from_pool_key |  |  |
| `c_d_asgi_proxy_notify_general` | 通知/告警操作 | `d_asgi_proxy` | notify/ | inferred | send, send_streaming_request, _show_timeout_warning, _show_streaming_warning, send_request, send_jspi_request, _run_sync_with_timeout, _is_node_js, send |  |  |
| `c_d_asgi_proxy_query_general` | 查询/读取操作 | `d_asgi_proxy` | query/ | inferred | _read_body, get_unreachable_address, getlist, getlist, getlist, _normalize_header_values, getresponse, _url_from_connection, _get_conn, _get_timeout, getresponse, readable, readinto, readable, _get_next_buffer, readinto, read, read_chunked, _error_catcher, getresponse, get_redirect_location, _get_decoder, get, get_all, get_redirect_location, read, read1, read_chunked, _init_decoder, _decode, _flush_decoder, readinto, getheaders, getheader, geturl, _error_catcher, _fp_read, _raw_read, read, read1, readable, _update_chunk_length, _handle_chunk, read_chunked, get_backoff_time, parse_retry_after, get_retry_after, _is_read_error |  |  |
| `c_d_asgi_proxy_query_user` | 查询用户 | `d_asgi_proxy` | query/user | inferred-low | _get_default_user_agent |  |  |
| `c_d_asgi_proxy_serialize_general` | 序列化/格式化操作 | `d_asgi_proxy` | serialize/ | inferred-low | _decode |  |  |
| `c_d_asgi_proxy_update_file` | 修改文件 | `d_asgi_proxy` | update/file | inferred | set_cert |  |  |
| `c_d_asgi_proxy_validate_general` | 校验/检测操作 | `d_asgi_proxy` | validate/ | inferred | ensure_can_construct_http_header_dict, _validate_conn, _validate_conn, assert_header_parsing |  |  |
| `c_d_base_h_t_t_p_connection_misc_unclassified` | 其他能力（待归类：connect、request、is_closed、is_connected 等 5 个） | `d_base_h_t_t_p_connection` | misc/unclassified | inferred-low | connect, request, is_closed, is_connected, has_connected_to_proxy |  |  |
| `c_d_base_h_t_t_p_connection_query_general` | 查询/读取操作 | `d_base_h_t_t_p_connection` | query/ | inferred | getresponse |  |  |
| `c_d_base_h_t_t_p_connection_transition_general` | 状态流转操作 | `d_base_h_t_t_p_connection` | transition/ | inferred | close |  |  |
| `c_d_base_h_t_t_p_connection_update_general` | 更新/修改操作 | `d_base_h_t_t_p_connection` | update/ | inferred | set_tunnel |  |  |
| `c_d_certificate_error_misc_unclassified` | 其他能力（待归类：_dnsname_match、_ipaddress_match、match_hostname） | `d_certificate_error` | misc/unclassified | inferred-low | _dnsname_match, _ipaddress_match, match_hostname |  |  |
| `c_d_chunks_and_content_length_create_general` | 提交/创建操作 | `d_chunks_and_content_length` | create/ | inferred | make_headers |  |  |
| `c_d_chunks_and_content_length_misc_unclassified` | 其他能力（待归类：rewind_body、body_to_chunks） | `d_chunks_and_content_length` | misc/unclassified | inferred-low | rewind_body, body_to_chunks |  |  |
| `c_d_chunks_and_content_length_update_file` | 修改文件 | `d_chunks_and_content_length` | update/file | inferred | set_file_position |  |  |
| `c_d_config_create_general` | 提交/创建操作 | `d_config` | create/ | inferred | create_sockets, _retry_create_urllib3_sockets, _create_urllib3_sockets |  |  |
| `c_d_config_misc_unclassified` | 其他能力（待归类：run_hypercorn_in_thread、main） | `d_config` | misc/unclassified | inferred-low | run_hypercorn_in_thread, main |  |  |
| `c_d_config_transition_general` | 状态流转操作 | `d_config` | transition/ | inferred-low | _start_server |  |  |
| `c_d_connection_marker_configure_general` | 配置/装配操作 | `d_connection_marker` | configure/ | inferred | setup_class, setup_class |  |  |
| `c_d_connection_marker_misc_unclassified` | 其他能力（待归类：consume_socket、quit_server_thread、teardown_class、teardown_method 等 7 个） | `d_connection_marker` | misc/unclassified | inferred-low | consume_socket, quit_server_thread, teardown_class, teardown_method, teardown_class, teardown_class, consume_request |  |  |
| `c_d_connection_marker_query_general` | 查询/读取操作 | `d_connection_marker` | query/ | inferred-low | _get_socket_mark |  |  |
| `c_d_connection_marker_transition_general` | 状态流转操作 | `d_connection_marker` | transition/ | inferred | _start_server, start_response_handler, start_basic_handler, _start_server |  |  |
| `c_d_connection_marker_update_general` | 更新/修改操作 | `d_connection_marker` | update/ | inferred | mark, _get_socket_mark |  |  |
| `c_d_connection_marker_validate_general` | 校验/检测操作 | `d_connection_marker` | validate/ | inferred | assert_header_received |  |  |
| `c_d_emscripten_request_misc_unclassified` | 其他能力（待归类：urlopen、request） | `d_emscripten_request` | misc/unclassified | inferred-low | urlopen, request |  |  |
| `c_d_emscripten_request_serialize_general` | 序列化/格式化操作 | `d_emscripten_request` | serialize/ | inferred | request_encode_url, request_encode_body |  |  |
| `c_d_emscripten_request_update_general` | 更新/修改操作 | `d_emscripten_request` | update/ | inferred | set_header, set_body |  |  |
| `c_d_fields_create_general` | 提交/创建操作 | `d_fields` | create/ | inferred | _render_parts, make_multipart |  |  |
| `c_d_fields_misc_unclassified` | 其他能力（待归类：guess_content_type、from_tuples、_render_part、render_headers） | `d_fields` | misc/unclassified | inferred-low | guess_content_type, from_tuples, _render_part, render_headers |  |  |
| `c_d_fields_serialize_general` | 序列化/格式化操作 | `d_fields` | serialize/ | inferred | format_header_param_rfc2231, format_multipart_header_param, format_header_param_html5, format_header_param |  |  |
| `c_d_filepost_misc_unclassified` | 其他能力（待归类：choose_boundary、iter_field_objects） | `d_filepost` | misc/unclassified | inferred-low | choose_boundary, iter_field_objects |  |  |
| `c_d_filepost_serialize_general` | 序列化/格式化操作 | `d_filepost` | serialize/ | inferred | encode_multipart_formdata |  |  |
| `c_d_h_t_t_p2_probe_cache_misc_unclassified` | 其他能力（待归类：_values、_reset） | `d_h_t_t_p2_probe_cache` | misc/unclassified | inferred-low | _values, _reset |  |  |
| `c_d_h_t_t_p2_probe_cache_query_general` | 查询/读取操作 | `d_h_t_t_p2_probe_cache` | query/ | inferred | acquire_and_get |  |  |
| `c_d_h_t_t_p2_probe_cache_update_general` | 更新/修改操作 | `d_h_t_t_p2_probe_cache` | update/ | inferred | set_and_release |  |  |
| `c_d_init_create_general` | 提交/创建操作 | `d_init` | create/ | inferred | add_stderr_logger |  |  |
| `c_d_init_misc_unclassified` | 其他能力（待归类：request、inject_into_urllib3、inject_into_urllib3、extract_from_urllib3） | `d_init` | misc/unclassified | inferred-low | request, inject_into_urllib3, inject_into_urllib3, extract_from_urllib3 |  |  |
| `c_d_init_transition_general` | 状态流转操作 | `d_init` | transition/ | inferred | disable_warnings |  |  |
| `c_d_noxfile_misc_unclassified` | 其他能力（待归类：tests_impl、test、test_integration、test_min_pyopenssl 等 13 个） | `d_noxfile` | misc/unclassified | inferred-low | tests_impl, test, test_integration, test_min_pyopenssl, test_brotlipy, git_clone, downstream_botocore, downstream_requests, lint, pyodideconsole, emscripten, mypy, docs |  |  |
| `c_d_noxfile_serialize_general` | 序列化/格式化操作 | `d_noxfile` | serialize/ | inferred | format |  |  |
| `c_d_py_open_s_s_l_context_create_general` | 提交/创建操作 | `d_py_open_s_s_l_context` | create/ | inferred | makefile |  |  |
| `c_d_py_open_s_s_l_context_misc_unclassified` | 其他能力（待归类：inject_into_urllib3、extract_from_urllib3、_dnsname_to_stdlib、fileno 等 27 个） | `d_py_open_s_s_l_context` | misc/unclassified | inferred-low | inject_into_urllib3, extract_from_urllib3, _dnsname_to_stdlib, fileno, _decref_socketios, recv, recv_into, shutdown, version, selected_alpn_protocol, options, options, wrap_socket, minimum_version, minimum_version, maximum_version, maximum_version, fileno, recv, recv_into, unwrap, version, cipher, selected_alpn_protocol, shared_ciphers, compression, _decref_socketios |  |  |
| `c_d_py_open_s_s_l_context_notify_general` | 通知/告警操作 | `d_py_open_s_s_l_context` | notify/ | inferred | _send_until_done, sendall, sendall, send, _ssl_io_loop, _ssl_io_loop, _ssl_io_loop, _ssl_io_loop |  |  |
| `c_d_py_open_s_s_l_context_query_general` | 查询/读取操作 | `d_py_open_s_s_l_context` | query/ | inferred | get_subj_alt_name, _get_common_name, getpeercert, getpeercert, getpeercert, load_verify_locations, load_cert_chain, read, getpeercert, getpeercert, getpeercert, gettimeout, _wrap_ssl_read |  |  |
| `c_d_py_open_s_s_l_context_transition_general` | 状态流转操作 | `d_py_open_s_s_l_context` | transition/ | inferred | close, _real_close, close |  |  |
| `c_d_py_open_s_s_l_context_update_general` | 更新/修改操作 | `d_py_open_s_s_l_context` | update/ | inferred | settimeout, set_default_verify_paths, set_ciphers, set_alpn_protocols, _set_ctx_options, settimeout |  |  |
| `c_d_py_open_s_s_l_context_validate_general` | 校验/检测操作 | `d_py_open_s_s_l_context` | validate/ | inferred | _validate_dependencies_met, verify_flags, verify_flags, verify_mode, verify_mode, _verify_callback, _validate_ssl_context_for_tls_in_tls |  |  |
| `c_d_ssl_create_general` | 提交/创建操作 | `d_ssl` | create/ | inferred | create_urllib3_context |  |  |
| `c_d_ssl_misc_file` | 文件相关操作 | `d_ssl` | misc/file | inferred-low | _is_key_file_encrypted |  |  |
| `c_d_ssl_misc_unclassified` | 其他能力（待归类：ssl_wrap_socket、ssl_wrap_socket、ssl_wrap_socket、is_ipaddress 等 5 个） | `d_ssl` | misc/unclassified | inferred-low | ssl_wrap_socket, ssl_wrap_socket, ssl_wrap_socket, is_ipaddress, _ssl_wrap_socket_impl |  |  |
| `c_d_ssl_query_general` | 查询/读取操作 | `d_ssl` | query/ | inferred | resolve_cert_reqs, resolve_ssl_version |  |  |
| `c_d_ssl_validate_check` | 校验检查 | `d_ssl` | validate/check | inferred-low | _is_has_never_check_common_name_reliable |  |  |
| `c_d_ssl_validate_general` | 校验/检测操作 | `d_ssl` | validate/ | inferred | assert_fingerprint |  |  |
| `c_d_t_y_p_e_d_e_f_a_u_l_t_misc_unclassified` | 其他能力（待归类：from_float、clone、connect_timeout） | `d_t_y_p_e_d_e_f_a_u_l_t` | misc/unclassified | inferred-low | from_float, clone, connect_timeout |  |  |
| `c_d_t_y_p_e_d_e_f_a_u_l_t_query_general` | 查询/读取操作 | `d_t_y_p_e_d_e_f_a_u_l_t` | query/ | inferred | resolve_default_timeout, get_connect_duration, read_timeout |  |  |
| `c_d_t_y_p_e_d_e_f_a_u_l_t_transition_general` | 状态流转操作 | `d_t_y_p_e_d_e_f_a_u_l_t` | transition/ | inferred | start_connect |  |  |
| `c_d_t_y_p_e_d_e_f_a_u_l_t_validate_general` | 校验/检测操作 | `d_t_y_p_e_d_e_f_a_u_l_t` | validate/ | inferred-low | _validate_timeout |  |  |
| `c_d_url_delete_file` | 删除文件 | `d_url` | delete/file | inferred-low | _remove_path_dot_segments |  |  |
| `c_d_url_misc_unclassified` | 其他能力（待归类：auth_decoded、auth_decoded_joined、hostname、request_uri 等 9 个） | `d_url` | misc/unclassified | inferred-low | auth_decoded, auth_decoded_joined, hostname, request_uri, authority, netloc, url, _normalize_host_percent_encoding, _normalize_zone_id_percent_encoding |  |  |
| `c_d_url_query_general` | 查询/读取操作 | `d_url` | query/ | inferred | _encode_invalid_chars, _encode_invalid_chars, _encode_invalid_chars, _remove_path_dot_segments, _normalize_host, _normalize_host, _normalize_host, parse_url |  |  |
| `c_d_url_serialize_general` | 序列化/格式化操作 | `d_url` | serialize/ | inferred-low | _encode_invalid_chars, _encode_invalid_chars, _encode_invalid_chars, _decode_percent_encoding, _idna_encode, _encode_target |  |  |
| `c_d_util_misc_unclassified` | 其他能力（待归类：to_bytes、to_str、reraise） | `d_util` | misc/unclassified | inferred-low | to_bytes, to_str, reraise |  |  |
| `c_d_wait_misc_unclassified` | 其他能力（待归类：select_wait_for_socket、poll_wait_for_socket、_have_working_poll、wait_for_socket 等 5 个） | `d_wait` | misc/unclassified | inferred-low | select_wait_for_socket, poll_wait_for_socket, _have_working_poll, wait_for_socket, wait_for_write |  |  |
| `c_d_wait_query_general` | 查询/读取操作 | `d_wait` | query/ | inferred | wait_for_read |  |  |

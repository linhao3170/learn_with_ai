"""业务逻辑分析平台 · 可选的 LLM 讲解服务

**默认关闭。** 不配环境变量时，这个模块什么都不做，
接口会返回 503 并说明"平台默认关闭 LLM 讲解层"。

为什么放在 backend 而不是 engine
--------------------------------
``engine/`` 有一条被测试强制的纪律：无随机、无网络、无 LLM。
``scripts/test_teaching_coverage.py`` 等三个脚本里写死了::

    FORBIDDEN_IMPORTS = ("requests","httpx","urllib","http","socket",
                         "openai","anthropic","random","time","datetime")

所以模型调用**只能**放在引擎之外。引擎那边只留契约与把关逻辑
（``engine/logic_platform/narration.py``），这里是真正的出口。
这样"离线跑引擎测试"与"线上可选开启讲解"两件事互不干扰。

开启方式（三步）
----------------
::

    set LWAI_NARRATION_PROVIDER=openai-compatible
    set LWAI_NARRATION_BASE_URL=https://your-endpoint/v1
    set LWAI_NARRATION_API_KEY=sk-...
    set LWAI_NARRATION_MODEL=gpt-4o-mini        # 可选

然后重启后端（``uvicorn`` 没开 ``--reload``，见 README §19.5），
并在请求里显式带上 ``provider``。

安全与纪律（在代码里落实，不只是写在文档里）
--------------------------------------------
1. **默认关闭**：没配置就是 503，绝不静默降级成本地模板后假装"AI 生成过";
2. **提示词里写死"给不出证据就别写"**（``narration.NARRATION_SYSTEM_PROMPT``）；
3. **模型返回的代码文本一律丢弃** —— 引擎合并时会自己从磁盘读真实摘录；
4. **讲解产物进不了"已确认"**：``generated_by=llm_draft``，状态强制 ``needs_review``；
5. **超时必设**（默认 30s）：不能让一次模型调用把学生页面挂住；
6. **不发源码全文**，只发段的行范围与结构事实（见 ``build_narration_request``）。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

ErrorDetail = Tuple[int, str]

#: 默认超时（秒）。模型慢是常态，但不能无限等。
DEFAULT_TIMEOUT = 30.0

#: 允许的 provider 取值。目前只实现 OpenAI 兼容的 ``/chat/completions``。
SUPPORTED_PROVIDERS = ("openai-compatible",)


def _env(name: str) -> str:
    return str(os.environ.get(name) or "").strip()


def config() -> Dict[str, Any]:
    """读当前配置（不打印密钥）。"""
    return {
        "provider": _env("LWAI_NARRATION_PROVIDER"),
        "base_url": _env("LWAI_NARRATION_BASE_URL"),
        "model": _env("LWAI_NARRATION_MODEL") or "gpt-4o-mini",
        "has_api_key": bool(_env("LWAI_NARRATION_API_KEY")),
        "timeout_seconds": float(_env("LWAI_NARRATION_TIMEOUT") or DEFAULT_TIMEOUT),
    }


def status() -> Dict[str, Any]:
    """讲解层状态 —— 给界面显示"这个平台有没有用 AI"用。

    ``llm_in_critical_path=False`` 是刻意暴露给评审看的一个事实：
    **讲解层不在关键路径上**，关掉它整套分析、板块、讲稿结构、证据校验照常工作。
    """
    cfg = config()
    provider = cfg["provider"]
    if not provider:
        return {
            "enabled": False,
            "reason": "未配置 LWAI_NARRATION_PROVIDER —— 平台以纯确定性模式运行（默认）",
            "config": cfg,
            "supported_providers": list(SUPPORTED_PROVIDERS),
            "llm_in_critical_path": False,
            "detached_from_engine": True,
        }
    missing = [
        name
        for name, value in (
            ("LWAI_NARRATION_BASE_URL", cfg["base_url"]),
            ("LWAI_NARRATION_API_KEY", "set" if cfg["has_api_key"] else ""),
        )
        if not value
    ]
    if missing:
        return {
            "enabled": False,
            "reason": f"provider 已设为 {provider}，但缺少：{'、'.join(missing)}",
            "config": cfg,
            "supported_providers": list(SUPPORTED_PROVIDERS),
            "llm_in_critical_path": False,
            "detached_from_engine": True,
        }
    if provider not in SUPPORTED_PROVIDERS:
        return {
            "enabled": False,
            "reason": f"不支持的 provider：{provider}（当前支持：{'、'.join(SUPPORTED_PROVIDERS)}）",
            "config": cfg,
            "supported_providers": list(SUPPORTED_PROVIDERS),
            "llm_in_critical_path": False,
            "detached_from_engine": True,
        }
    return {
        "enabled": True,
        "reason": f"已启用 {provider}（模型 {cfg['model']}）—— 产物状态强制为待教师确认",
        "config": cfg,
        "supported_providers": list(SUPPORTED_PROVIDERS),
        "llm_in_critical_path": False,
        "detached_from_engine": True,
        "caveats": [
            "讲解层不在关键路径上：关掉它，大小分析、业务板块、讲稿结构、证据校验全部照常工作。",
            "模型返回的代码文本会被丢弃；讲稿里的代码一律由引擎从磁盘重读。",
            "LLM 产物永远拿不到 can_publish=true，必须过教师确认。",
        ],
    }


def request_narration(
    lesson: dict,
    provider: Optional[str] = None,
) -> Tuple[Optional[dict], Optional[ErrorDetail]]:
    """向配置好的模型请求一份讲解。

    返回 ``(narration, error)``：

    - 未启用 → ``(None, None)``（调用方据此返回 503）；
    - 配置错误 / 网络失败 / 返回不是合法 JSON → ``(None, (状态码, 中文说明))``；
    - 成功 → ``(narration 字典, None)``。

    **任何情况下都不会返回一个"编造的"讲解** —— 拿不到就说拿不到。
    """
    from engine.logic_platform import narration as engine_narration

    cfg = config()
    requested = str(provider or cfg["provider"] or "").strip()
    if not requested or not status().get("enabled"):
        return None, None
    if requested not in SUPPORTED_PROVIDERS:
        return None, (400, f"不支持的 provider：{requested}（当前支持：{'、'.join(SUPPORTED_PROVIDERS)}）")

    request_body = engine_narration.build_narration_request(lesson)
    payload = {
        "model": cfg["model"],
        "temperature": 0,
        "messages": [
            {"role": "system", "content": engine_narration.NARRATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "以下是这一课的结构化事实。请按 system 里的规矩写出讲解，"
                    "严格输出 JSON，结构见 response_schema 字段。\n\n"
                    + json.dumps(request_body, ensure_ascii=False)
                ),
            },
        ],
    }

    endpoint = cfg["base_url"].rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_env('LWAI_NARRATION_API_KEY')}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=cfg["timeout_seconds"]) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
        except Exception:  # pragma: no cover
            pass
        return None, (502, f"讲解模型返回 HTTP {exc.code}：{detail}")
    except urllib.error.URLError as exc:
        return None, (504, f"连接讲解模型失败：{exc.reason}")
    except TimeoutError:
        return None, (504, f"讲解模型超时（{cfg['timeout_seconds']}s）")
    except Exception as exc:  # pragma: no cover - 兜底，不吞成"成功"
        return None, (502, f"讲解模型调用失败：{exc}")

    try:
        envelope = json.loads(raw)
    except ValueError:
        return None, (502, "讲解模型返回的不是合法 JSON")

    choices = envelope.get("choices") or []
    if not choices:
        return None, (502, "讲解模型返回里没有 choices")
    content = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
    if not content:
        return None, (502, "讲解模型返回内容为空")

    # 模型有时候会用 ```json 包起来 —— 剥掉围栏，但仍然要求内容是 JSON
    if content.startswith("```"):
        content = content.split("```")[1] if "```" in content[3:] else content[3:]
        if content.lstrip().lower().startswith("json"):
            content = content.lstrip()[4:]
    try:
        narration = json.loads(content)
    except ValueError:
        return None, (502, "讲解模型返回的内容不是合法 JSON（已剥离代码围栏后仍无法解析）")

    if not isinstance(narration, dict):
        return None, (502, "讲解模型返回的 JSON 顶层不是对象")
    narration.setdefault("narrator", requested)
    narration.setdefault("model", cfg["model"])
    narration.setdefault("lesson_id", str(lesson.get("lesson_id") or ""))
    return narration, None

"""每次发现当前 LivingHello；支持历史运行时名字，不保存跨重载实例。"""

NAMES = ("astrbot_plugin_at_guard", "astrbot_plugin_LivingHello",
         "astrbot_plugin_livinghello", "livinghello")


def discover(lookup):
    """所有协作入口使用同一名字表；lookup 负责排除已停用实例。"""
    for name in NAMES:
        try:
            peer = lookup(name)
        except Exception:
            continue
        if peer is not None:
            return peer
    return None


def policy(context):
    getter = getattr(context, "get_registered_star", None)
    if not callable(getter):
        return None
    # 线上历史名称含大写，注册表查询区分大小写。
    for name in NAMES:
        method = None
        try:
            meta = getter(name)
            method = getattr(getattr(meta, "star_cls", None), "get_function_coupling", None)
            if meta and meta.activated and callable(method):
                value = method()
                if isinstance(value, dict) and value.get("contract") == "livinghello.function-coupling.v1":
                    return value
        except Exception:
            if callable(method):
                return {"contract":"livinghello.function-coupling.v1", "managed":True, "integrations":{}}
            continue
    return None


def allowed(context, kind):
    # Coupling controls LivingHello's calls, not LivingEmotion's autonomous hooks.
    if kind == "livingemotion":
        return True
    value = policy(context)
    return value is None or value.get("integrations", {}).get(kind, {}).get("effective") is True


def shared_prompts(context, request, variant):
    """Read LH's public runtime contract; standalone/older LH retains LE defaults."""
    from .prompt_bundle import request_shared_settings
    frozen = request_shared_settings(request)
    if frozen is not None:
        return frozen
    getter = getattr(context, "get_registered_star", None)
    if not callable(getter):
        return None
    for name in NAMES:
        try:
            meta = getter(name)
            peer = getattr(meta, "star_cls", None)
            method = getattr(peer, "get_shared_prompt_snapshot", None)
            if meta and meta.activated and callable(method):
                return request_shared_settings(request, method(variant=variant))
        except Exception:
            continue
    return None

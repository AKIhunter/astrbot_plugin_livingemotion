"""每次发现当前 LivingHello；支持历史运行时名字，不保存跨重载实例。"""


def policy(context):
    getter = getattr(context, "get_registered_star", None)
    if not callable(getter):
        return None
    # 线上历史名称含大写，注册表查询区分大小写。
    for name in ("astrbot_plugin_at_guard", "astrbot_plugin_LivingHello", "astrbot_plugin_livinghello", "livinghello"):
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
    value = policy(context)
    return value is None or value.get("integrations", {}).get(kind, {}).get("effective") is True

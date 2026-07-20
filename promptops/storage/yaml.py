"""自研 YAML emitter，覆盖对象、数组、标量、多行字符串。"""
from __future__ import annotations

from typing import Any


def _indent(level: int) -> str:
    return "  " * level


def _scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if "\n" in s:
        # block scalar
        lines = s.split("\n")
        return "|\n" + "\n".join(_indent(1) + line for line in lines)
    # 需要引号的情况
    if not s or s.startswith("{") or s.startswith("[") or s.startswith("'") or s.startswith('"'):
        return repr(s)
    if ":" in s or "#" in s:
        return f'"{s}"'
    return s


def to_yaml(obj: Any, level: int = 0) -> str:
    """将 Python 对象序列化为 YAML 字符串。"""
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines: list[str] = []
        for k, v in obj.items():
            prefix = _indent(level) + f"{k}: "
            if isinstance(v, dict):
                if not v:
                    lines.append(prefix + "{}")
                else:
                    lines.append(prefix.rstrip())
                    lines.append(to_yaml(v, level + 1))
            elif isinstance(v, list):
                if not v:
                    lines.append(prefix + "[]")
                else:
                    lines.append(prefix.rstrip())
                    lines.append(to_yaml(v, level + 1))
            else:
                val = _scalar(v)
                if val.startswith("|"):
                    lines.append(prefix.rstrip())
                    lines.append(_indent(level + 1) + val)
                else:
                    lines.append(prefix + val)
        return "\n".join(lines)
    elif isinstance(obj, list):
        if not obj:
            return _indent(level) + "[]"
        lines = []
        for item in obj:
            prefix = _indent(level) + "- "
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    if first:
                        lines.append(prefix + f"{k}: " + (to_yaml(v, level + 2).strip() if not isinstance(v, (dict, list)) else ""))
                        if isinstance(v, (dict, list)) and v:
                            lines.append(to_yaml(v, level + 2))
                        first = False
                    else:
                        lines.append(_indent(level + 1) + f"{k}: " + (to_yaml(v, level + 2).strip() if not isinstance(v, (dict, list)) else ""))
                        if isinstance(v, (dict, list)) and v:
                            lines.append(to_yaml(v, level + 2))
            elif isinstance(item, list):
                lines.append(prefix)
                lines.append(to_yaml(item, level + 1))
            else:
                lines.append(prefix + _scalar(item))
        return "\n".join(lines)
    else:
        return _indent(level) + _scalar(obj)

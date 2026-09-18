"""SML 子集解析器（rec-blog 专用）。

支持：# / -- / // 行注释、/* */ 与 _* *_ 块注释、引号串（\\n \\t \\u{} 等转义）、
裸词、int/float/bool/null、对象块、数组、裸块（`name arg { }`）、同名键合并为数组。

约定（与本项目内容格式绑定）：
  - 裸词遇空白或 `} ] , {` 结束；含空格的文本必须加引号。
  - 裸块 `topic 标题 { ... }` 解析为 {__type: "topic", __name: "标题", ...}。
  - 同名键重复出现时合并为数组并保持书写顺序。
"""

import copy
import re

_WS = " \t\r\n"
_STOP = "}]{,"


class SmlError(Exception):
    pass


def _scalar(tok):
    if tok == "true":
        return True
    if tok == "false":
        return False
    if tok in ("null", "none"):
        return None
    if re.fullmatch(r"[+-]?\d+", tok):
        return int(tok)
    if re.fullmatch(r"[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?", tok) and (
        "." in tok or "e" in tok.lower()
    ):
        return float(tok)
    return tok


class _Parser:
    def __init__(self, text, path="<sml>"):
        self.s = text
        self.i = 0
        self.n = len(text)
        self.path = path
        self.contracts = {}

    def err(self, msg):
        line = self.s.count("\n", 0, self.i) + 1
        raise SmlError("%s:%d: %s" % (self.path, line, msg))

    def skip(self):
        while self.i < self.n:
            c = self.s[self.i]
            if c in _WS:
                self.i += 1
                continue
            if c == "#" or self.s.startswith("//", self.i) or self.s.startswith("--", self.i):
                nl = self.s.find("\n", self.i)
                self.i = self.n if nl < 0 else nl + 1
                continue
            if self.s.startswith("/*", self.i):
                e = self.s.find("*/", self.i + 2)
                if e < 0:
                    self.err("未闭合块注释 /*")
                self.i = e + 2
                continue
            if self.s.startswith("_*", self.i):
                e = self.s.find("*_", self.i + 2)
                if e < 0:
                    self.err("未闭合块注释 _*")
                self.i = e + 2
                continue
            break

    def bare(self):
        start = self.i
        while self.i < self.n:
            c = self.s[self.i]
            if c in _WS or c in _STOP or c in "#:":
                break
            if self.s.startswith("//", self.i) or self.s.startswith("--", self.i):
                break
            self.i += 1
        if self.i == start:
            self.err("期望一个值")
        return self.s[start:self.i]

    def string(self):
        self.i += 1
        buf = []
        while True:
            if self.i >= self.n:
                self.err("未闭合字符串")
            c = self.s[self.i]
            if c == '"':
                self.i += 1
                break
            if c == "\\":
                self.i += 1
                if self.i >= self.n:
                    self.err("转义符后缺字符")
                e = self.s[self.i]
                self.i += 1
                if e in ("n", "t", "r", "0", '"', "\\"):
                    buf.append({"n": "\n", "t": "\t", "r": "\r", "0": "\0", '"': '"', "\\": "\\"}[e])
                elif e == "u":
                    if self.i < self.n and self.s[self.i] == "{":
                        j = self.s.find("}", self.i)
                        if j < 0:
                            self.err("未闭合 \\u{}")
                        buf.append(chr(int(self.s[self.i + 1:j], 16)))
                        self.i = j + 1
                    else:
                        buf.append(chr(int(self.s[self.i:self.i + 4], 16)))
                        self.i += 4
                else:
                    buf.append(e)
            else:
                buf.append(c)
                self.i += 1
        return "".join(buf)

    def raw_block(self):
        """原样抓取 `{ ... }` 的内部文本（契约定义用，不受数据语法影响）。"""
        if self.s[self.i] != "{":
            self.err("期望 `{`")
        self.i += 1
        start = self.i
        depth = 1
        while self.i < self.n:
            c = self.s[self.i]
            if c == '"':
                self.string()
                continue
            if self.s.startswith("/*", self.i) or self.s.startswith("_*", self.i):
                end = "*/" if self.s.startswith("/*", self.i) else "*_"
                j = self.s.find(end, self.i + 2)
                self.i = self.n if j < 0 else j + 2
                continue
            if c == "#" or self.s.startswith("//", self.i) or self.s.startswith("--", self.i):
                nl = self.s.find("\n", self.i)
                self.i = self.n if nl < 0 else nl + 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    body = self.s[start:self.i]
                    self.i += 1
                    return body
            self.i += 1
        self.err("未闭合的契约定义块")

    def put_entry(self, obj, key, val):
        """统一处理 `@is` 与 `@` 指令：`@is` 记为 __is；片段定义保留给展开阶段；其余指令丢弃。"""
        if key == "@is":
            obj["__is"] = val.strip() if isinstance(val, str) else str(val)
            return
        if isinstance(key, str) and key.startswith("@"):
            if key != "@contract" and isinstance(val, dict):
                _put(obj, key, val)   # @名字 { } 片段定义，等 _expand 处理
            return
        _put(obj, key, val)

    def scan_tokens(self):
        """从当前位置收集裸词/字符串，直到遇到 `{`（视为裸块参数）或 `}`/`]`/`,`。
        返回 (tokens, 是否遇到 `{`)。不消费定界符本身。"""
        toks = []
        while True:
            self.skip()
            if self.i >= self.n:
                break
            c = self.s[self.i]
            if c == "{":
                return toks, True
            if c in "}],":
                break
            toks.append(self.string() if c == '"' else self.bare())
        return toks, False

    def value(self):
        self.skip()
        if self.i >= self.n:
            self.err("期望一个值")
        c = self.s[self.i]
        if c == "{":
            return self.object()
        if c == "[":
            return self.array()
        if c == '"':
            return self.string()
        return _scalar(self.bare())

    def object(self):
        self.i += 1
        obj = {}
        while True:
            self.skip()
            if self.i >= self.n:
                self.err("未闭合块")
            if self.s[self.i] == "}":
                self.i += 1
                break
            key, val = self.entry()
            self.put_entry(obj, key, val)
        return obj

    def array(self):
        self.i += 1
        arr = []
        while True:
            self.skip()
            if self.i >= self.n:
                self.err("未闭合数组")
            c = self.s[self.i]
            if c == "]":
                self.i += 1
                break
            if c == ",":
                self.i += 1
                continue
            if c == "{":
                arr.append(self.object())
                continue
            if c == "[":
                arr.append(self.array())
                continue
            first = self.string() if c == '"' else self.bare()
            after_first = self.i
            args, is_block = self.scan_tokens()
            if is_block:
                sub = self.object()
                sub["__type"] = first
                if args:
                    sub["__name"] = args[0]
                if len(args) > 1:
                    sub["__args"] = args[1:]
                arr.append(sub)
            else:
                self.i = after_first
                arr.append(_scalar(first))
        return arr

    def entry(self):
        self.skip()
        head = self.string() if self.s[self.i] == '"' else self.bare()
        if head == "@contract":
            args, _ = self.scan_tokens()
            name = args[0] if args else ""
            self.skip()
            if self.i < self.n and self.s[self.i] == "{":
                self.contracts[name] = _parse_contract_body(self.raw_block(), name)
            return head, {"__contract": name}
        self.skip()
        if self.i < self.n and self.s[self.i] == ":":
            self.i += 1
            return head, self.value()
        args, is_block = self.scan_tokens()
        if is_block:
            sub = self.object()
            sub["__type"] = head
            if args:
                sub["__name"] = args[0]
                if len(args) > 1:
                    sub["__args"] = args[1:]
            return head, sub
        if args:
            return head, (_scalar(args[0]) if len(args) == 1 else [_scalar(a) for a in args])
        return head, True


def _put(obj, key, val):
    if key not in obj:
        obj[key] = val
        return
    cur = obj[key]
    if isinstance(cur, list):
        cur.append(val)
    else:
        obj[key] = [cur, val]


def _expand(node, frags):
    """展开片段引用：`@名字 { ... }` 定义、`&名字` 以值形式引用；@ 开头的指令/定义不进结果。"""
    if isinstance(node, list):
        return [_expand(x, frags) for x in node]
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if isinstance(k, str) and k.startswith("@"):
                continue
            if isinstance(v, str) and v.startswith("&") and len(v) > 1 and v[1:] in frags:
                sub = _expand(copy.deepcopy(frags[v[1:]]), frags)
                if isinstance(sub, dict):
                    sub = {k2: v2 for k2, v2 in sub.items() if not k2.startswith("__")}
                out[k] = sub
                continue
            out[k] = _expand(v, frags)
        return out
    return node


def parse_doc(text, path="<sml>"):
    """返回 (值, 契约表)。契约表来自文件内的 `@contract 名 { ... }` 定义。"""
    p = _Parser(text, path)
    p.skip()
    if p.i < p.n and p.s[p.i] == "{":
        obj = p.object()
    else:
        obj = {}
        while True:
            p.skip()
            if p.i >= p.n:
                break
            if p.s[p.i] == "}":
                p.err("多余的 }")
            key, val = p.entry()
            p.put_entry(obj, key, val)
    frags = {k[1:]: v for k, v in obj.items()
             if isinstance(k, str) and k.startswith("@") and isinstance(v, dict)}
    val = _expand(obj, frags) if frags else obj
    return val, p.contracts


def parse(text, path="<sml>"):
    return parse_doc(text, path)[0]


_CONTRACT_FIELD = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.+)$")


def _num(tok):
    try:
        return int(tok)
    except ValueError:
        try:
            return float(tok)
        except ValueError:
            return None


def _parse_contract_body(text, name=""):
    """契约定义体 → {"name","loose","fields":{字段:{type,required,enum,min,max,default,doc}}}

    `#` 后的文字作为该字段的说明，会出现在自动生成的契约文档页里（代码即文档）。
    """
    spec = {"name": name, "loose": False, "fields": {}}
    for raw in text.split("\n"):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("--"):
            continue
        doc = ""
        if "#" in line:
            line, doc = line.split("#", 1)
            doc = doc.strip()
        line = line.strip()
        if not line:
            continue
        if line in ("loose", "loose true"):
            spec["loose"] = True
            continue
        m = _CONTRACT_FIELD.match(line)
        if not m:
            continue
        fname, rest = m.group(1), m.group(2).strip()
        toks = rest.split()
        if toks and toks[0] == "enum":
            mm = re.search(r"\[(.*?)\]", rest)
            vals = [x for x in re.split(r"[,\s]+", mm.group(1).strip()) if x] if mm else []
            tail = rest.split("]", 1)[1] if "]" in rest else ""
            spec["fields"][fname] = {
                "type": "str", "required": "optional" not in tail.split(),
                "enum": vals, "min": None, "max": None,
                "default": None, "doc": doc,
            }
            continue
        f = {"type": toks[0] if toks else "any", "required": True,
             "enum": None, "min": None, "max": None, "default": None, "doc": doc}
        i = 1
        while i < len(toks):
            t = toks[i]
            if t == "optional":
                f["required"] = False
            elif t == "required":
                f["required"] = True
            elif t == "enum":
                mm = re.search(r"\[(.*?)\]", " ".join(toks[i + 1:]))
                if mm:
                    f["enum"] = [x for x in re.split(r"[,\s]+", mm.group(1).strip()) if x]
                i = len(toks)
                continue
            elif t == "min" and i + 1 < len(toks):
                i += 1
                f["min"] = _num(toks[i])
            elif t == "max" and i + 1 < len(toks):
                i += 1
                f["max"] = _num(toks[i])
            elif t == "default" and i + 1 < len(toks):
                i += 1
                f["default"] = toks[i].strip('"')
            i += 1
        spec["fields"][fname] = f
    return spec


def load_doc(path):
    """返回 (值, 契约表)。"""
    with open(path, "r", encoding="utf-8") as fh:
        return parse_doc(fh.read(), str(path))


def load(path):
    return load_doc(path)[0]


def get(d, key, default=None):
    if isinstance(d, dict):
        v = d.get(key)
        return default if v is None else v
    return default


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def as_str(v, default=""):
    if v is None:
        return default
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)

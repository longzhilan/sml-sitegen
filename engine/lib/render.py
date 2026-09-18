"""SML 值 → HTML 片段（rec-blog 专用）。

正文一律先转义再套标签；投稿内容不会以 innerHTML 形式被信任。
块类型：topic/section/para/p/quote/code/ul/ol/li/table/img/a/hr/math/theorem/proof/video/note
内联角色：{ref:}/{term:}/{math:}/{em:}/{strong:}/{link:}
"""

import html
import re

QUOTE_ENT = "&quot;"


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def _unquote(arg):
    a = arg.strip()
    if a.startswith(QUOTE_ENT) and a.endswith(QUOTE_ENT) and len(a) >= 12:
        a = a[6:-6]
    a = a.strip('"')
    return a


def _role(inner):
    if ":" not in inner:
        return None
    name, arg = inner.split(":", 1)
    name = name.strip().lower()
    arg = _unquote(arg)
    if name == "ref":
        if "|" in arg:
            target, text = arg.split("|", 1)
        else:
            target = text = arg
        return '<a class="ref" href="#%s">%s</a>' % (esc(target.strip()), esc(text.strip()))
    if name == "term":
        return "<dfn>%s</dfn>" % esc(arg)
    if name == "math":
        return '<span class="math">\\(%s\\)</span>' % esc(arg)
    if name == "em":
        return "<em>%s</em>" % esc(arg)
    if name == "strong":
        return "<strong>%s</strong>" % esc(arg)
    if name == "link":
        if "|" in arg:
            url, text = arg.split("|", 1)
        else:
            url = text = arg
        return '<a href="%s" target="_blank" rel="nofollow noopener">%s</a>' % (
            esc(url.strip()), esc(text.strip()))
    return None


def apply_roles(s):
    """对**已转义**的文本做内联角色替换（{ref:}/{term:}/{math:}/{em:}/{strong:}/{link:}）。"""
    out = []
    i = 0
    while i < len(s):
        if s[i] == "{":
            depth = 1
            j = i + 1
            while j < len(s) and depth:
                if s[j] == "{":
                    depth += 1
                elif s[j] == "}":
                    depth -= 1
                j += 1
            if depth:
                out.append(s[i])
                i += 1
                continue
            rep = _role(s[i + 1:j - 1])
            out.append(rep if rep is not None else s[i:j])
            i = j
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def inline(s):
    return apply_roles(esc(s))


def slugify(text, used):
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(text)).strip("-").lower()
    if not base:
        base = "sec"
    slug = base
    k = 2
    while slug in used:
        slug = "%s-%d" % (base, k)
        k += 1
    used.add(slug)
    return slug


class Ctx:
    def __init__(self):
        self.used = set()
        self.toc = []


def _text_of(v):
    for k in ("title", "__name", "text"):
        s = v.get(k)
        if isinstance(s, str) and s:
            return s
    return ""


def _children(v):
    for k in ("children", "body", "items"):
        c = v.get(k)
        if c is not None:
            return c
    return None


def render(v, ctx=None, level=0):
    ctx = ctx or Ctx()
    if isinstance(v, str):
        return "<p>%s</p>\n" % inline(v)
    if isinstance(v, list):
        return "".join(render(x, ctx, level) for x in v)
    if not isinstance(v, dict):
        return "<p>%s</p>\n" % inline(str(v))
    t = v.get("__type")
    if not isinstance(t, str):
        kids = _children(v)
        return render(kids, ctx, level) if kids is not None else ""
    t = t.lower()

    if t in ("topic", "section", "h1", "h2", "h3", "h4", "h5", "h6"):
        lvl = min(level + 1, 6)
        title = _text_of(v)
        label = v.get("label")
        ident = label if isinstance(label, str) and label else slugify(title, ctx.used)
        ctx.toc.append({"id": ident, "text": title, "level": lvl})
        head = '<h%d id="%s">%s</h%d>\n' % (lvl, esc(ident), inline(title), lvl)
        kids = _children(v)
        return head + (render(kids, ctx, lvl) if kids is not None else "")

    if t in ("para", "p", "text"):
        return "<p>%s</p>\n" % inline(_text_of(v))

    if t in ("quote", "blockquote"):
        kids = _children(v)
        inner = render(kids, ctx, level) if kids is not None else "<p>%s</p>\n" % inline(_text_of(v))
        cite = v.get("cite")
        foot = '<footer>%s</footer>' % inline(cite) if isinstance(cite, str) else ""
        return "<blockquote>%s%s</blockquote>\n" % (inner, foot)

    if t == "code":
        lang = v.get("lang") or v.get("language") or ""
        code = v.get("text") or v.get("code") or ""
        return '<pre><code class="language-%s">%s</code></pre>\n' % (esc(lang), esc(code))

    if t in ("ul", "ol"):
        items = _children(v) or []
        lis = "".join("<li>%s</li>\n" % _li(x, ctx, level) for x in items)
        return "<%s>\n%s</%s>\n" % (t, lis, t)

    if t == "li":
        return "<li>%s</li>\n" % _li(v, ctx, level)

    if t == "table":
        head = as_listish(v.get("head"))
        rows = as_listish(v.get("rows"))
        out = ["<table>\n"]
        if head:
            out.append("<thead><tr>" + "".join("<th>%s</th>" % inline(c) for c in head) + "</tr></thead>\n")
        if rows:
            out.append("<tbody>\n")
            for r in rows:
                cells = as_listish(r)
                out.append("<tr>" + "".join("<td>%s</td>" % inline(c) for c in cells) + "</tr>\n")
            out.append("</tbody>\n")
        out.append("</table>\n")
        return "".join(out)

    if t == "img":
        src = v.get("src") or v.get("url") or ""
        alt = v.get("alt") or ""
        cap = v.get("caption")
        img = '<img src="%s" alt="%s" loading="lazy">' % (esc(src), esc(alt))
        if isinstance(cap, str) and cap:
            return '<figure>%s<figcaption>%s</figcaption></figure>\n' % (img, inline(cap))
        return "<p>%s</p>\n" % img

    if t == "a":
        href = v.get("href") or v.get("url") or ""
        return '<p><a href="%s" target="_blank" rel="nofollow noopener">%s</a></p>\n' % (
            esc(href), inline(_text_of(v) or href))

    if t == "hr":
        return "<hr>\n"

    if t == "math":
        return '<div class="math">\\[%s\\]</div>\n' % esc(_text_of(v))

    if t == "theorem":
        title = _text_of(v)
        label = v.get("label")
        ident = label if isinstance(label, str) and label else slugify(title or "theorem", ctx.used)
        head = '<h3 class="theorem-title">%s</h3>\n' % inline(title) if title else ""
        kids = render(_children(v), ctx, level)
        return '<article class="theorem" id="%s">%s%s</article>\n' % (esc(ident), head, kids)

    if t == "proof":
        kids = render(_children(v), ctx, level)
        return '<div class="proof">%s</div>\n' % kids

    if t == "video":
        return video_embed(v.get("bvid") or v.get("url") or "")

    if t in ("note", "tip", "warn", "warning"):
        kind = {"note": "note", "tip": "tip", "warn": "warn", "warning": "warn"}[t]
        kids = _children(v)
        inner = render(kids, ctx, level) if kids is not None else "<p>%s</p>\n" % inline(_text_of(v))
        return '<aside class="admonition %s">%s</aside>\n' % (kind, inner)

    kids = _children(v)
    if kids is not None:
        return render(kids, ctx, level)
    if _text_of(v):
        return "<p>%s</p>\n" % inline(_text_of(v))
    return ""


def _li(x, ctx, level):
    if isinstance(x, dict):
        kids = _children(x)
        if kids is not None:
            return render(kids, ctx, level)
        return inline(_text_of(x))
    return inline(str(x))


def as_listish(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def video_embed(ref):
    """B 站嵌入：只接受 BV 号或 player.bilibili.com 链接，白名单外返回空串。"""
    ref = str(ref).strip()
    bvid = ""
    if ref.startswith("BV") and len(ref) >= 12:
        bvid = ref
    else:
        m = re.search(r"(BV[0-9A-Za-z]{10})", ref)
        if m and ("bilibili.com" in ref or ref.startswith("BV")):
            bvid = m.group(1)
    if not bvid:
        return ""
    src = "https://player.bilibili.com/player.html?bvid=%s&high_quality=1" % bvid
    return (
        '<div class="video"><iframe src="%s" scrolling="no" frameborder="0" '
        'allowfullscreen loading="lazy"></iframe></div>\n' % esc(src)
    )


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

#!/usr/bin/env python3
"""rec-blog 命令行（engine 侧）。

    python engine/cli.py new "probe-rs 上手" --tags rust,embedded --author sal
    python engine/cli.py list --tag rust
    python engine/cli.py contracts      # 终端里看契约字段表（代码即文档）
    python engine/cli.py build | check | test | preview

加 --site <目录> 可操作别的站点（engine 与内容分离，便于复用）。
"""

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
sys.path.insert(0, str(ENGINE / "lib"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import config  # noqa: E402
import markdown as mdmod  # noqa: E402
import sml  # noqa: E402
import contract as contract_mod  # noqa: E402

MD_TMPL = """---
title: "{title}"
author: {author}
date: {date}
tags: [{tags}]
summary: "一句话摘要（列表页与分享卡片用）"
{extra}---

## 第一个小节

正文。支持 **粗体**、`行内代码`、表格、引用、代码块、图片（`assets/` 下）。

```rust
fn main() {{ }}
```
"""

SML_TMPL = """title: "{title}"
author: {author}
date: {date}
tags: [{tags}]
summary: "一句话摘要（列表页与分享卡片用）"
{extra}
body: [
  topic 第一个小节 {
    children: [
      para { text: "正文。多行文本可以直接换行写，不需要转义。" }
    ]
  }
]
"""

TOPIC_TMPL = """---
title: "{title}"
summary: "一句话定义（词条页与知识页用）"
tags: [{tags}]
{extra}---

## 定义

写清楚这个主题到底是什么、边界在哪里。

## 要点

- 要点一
- 要点二
"""


def slugify(title, fallback=""):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    return s or fallback


def _site_arg(args):
    return ["--site", args.site] if getattr(args, "site", "") else []


def cmd_new(args):
    slug = args.slug or slugify(args.title)
    if not slug:
        print("标题里没有可用作目录名的英文字符，请加 --slug，例如 --slug probe-rs-intro")
        return 2
    tags = " ".join(args.tags.split(",")) if args.tags else "rust"
    if args.topic:
        path = config.CONTENT / "topics" / (slug + ".md")
        extra = "related: []\n"
        tmpl = TOPIC_TMPL
    else:
        year = str(dt.date.today().year)
        path = config.CONTENT / "posts" / year / slug / "index." + ("sml" if args.sml else "md")
        extra = ""
        if args.series:
            extra = "series:\n  id: %s\n  title: %s\n  order: 1\n" % (args.series, args.series)
        tmpl = SML_TMPL if args.sml else MD_TMPL
    if path.exists():
        print("已存在：%s" % path)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tmpl.format(title=args.title, author=args.author, date=dt.date.today().isoformat(),
                                tags=tags, extra=extra), encoding="utf-8")
    print("已创建 %s" % path.relative_to(config.SITE))
    print("写完跑：python engine/cli.py build && python engine/cli.py preview --no-build")
    return 0


def cmd_list(args):
    rows = []
    for f in sorted((config.CONTENT / "posts").glob("*/*/index.*")):
        if f.suffix.lower() not in (".md", ".markdown", ".sml"):
            continue
        d, _ = (sml.load_doc(f) if f.suffix.lower() == ".sml"
                else mdmod.split_front_matter(f.read_text(encoding="utf-8")))
        tags = d.get("tags") or []
        if args.tag and args.tag not in tags:
            continue
        if args.year and f.parent.parent.name != args.year:
            continue
        rows.append((str(d.get("date", "")), f.parent.name, str(d.get("title", "")),
                     " ".join(tags), str(d.get("author", ""))))
    rows.sort(reverse=True)
    if not rows:
        print("没有匹配的文章。")
        return 0
    for date, slug, title, tags, author in rows:
        print("%-12s %-22s %-40s %-20s %s" % (date, slug, title[:38], tags[:18], author))
    print("\n共 %d 篇" % len(rows))
    return 0


def cmd_contracts(args):
    reg = {}
    for f in sorted((config.CONTENT / "contracts").glob("*.sml")):
        _, cs = sml.load_doc(f)
        reg.update(cs)
    if not reg:
        print("没有契约（%s 是空的）。" % (config.CONTENT / "contracts").relative_to(config.REPO))
        return 1
    for c in contract_mod.describe(reg):
        print("\n%s%s" % (c["name"], "（loose）" if c["loose"] else ""))
        for f in c["fields"]:
            print("  %-16s %-12s %-4s %-22s %s"
                  % (f["name"], f["type"], "必填" if f["required"] else "可选",
                     f["constraint"], f["doc"]))
    return 0


def run(*cmd):
    return subprocess.call([sys.executable] + list(cmd), cwd=str(config.REPO))


def cmd_build(args):
    extra = ["--offline"] if args.offline else []
    if args.contract_loose:
        extra.append("--contract-loose")
    return run(str(ENGINE / "build.py"), *_site_arg(args), *extra)


def main():
    ap = argparse.ArgumentParser(prog="rec-blog", description="群博客命令行（engine）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="新建文章/词条骨架")
    p.add_argument("title")
    p.add_argument("--slug", default="")
    p.add_argument("--tags", default="rust")
    p.add_argument("--author", default="sal")
    p.add_argument("--series", default="")
    p.add_argument("--sml", action="store_true", help="生成 SML 版本而不是 Markdown")
    p.add_argument("--topic", action="store_true", help="创建主题词条（content/topics/）")
    config.add_site_arg(p)
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("list", help="列出文章")
    p.add_argument("--tag", default="")
    p.add_argument("--year", default="")
    config.add_site_arg(p)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("contracts", help="打印内容契约字段表")
    config.add_site_arg(p)
    p.set_defaults(func=cmd_contracts)

    p = sub.add_parser("build", help="构建")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--contract-loose", action="store_true")
    config.add_site_arg(p)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="产物自检")
    config.add_site_arg(p)
    p.set_defaults(func=lambda a: run(str(ENGINE / "check.py"), *_site_arg(a)))

    p = sub.add_parser("test", help="契约引擎自测")
    config.add_site_arg(p)
    p.set_defaults(func=lambda a: run(str(ENGINE / "test_contracts.py"), *_site_arg(a)))

    p = sub.add_parser("preview", help="构建并本地预览")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--detach", action="store_true")
    p.add_argument("--no-build", action="store_true")
    config.add_site_arg(p)
    p.set_defaults(func=lambda a: run(str(ENGINE / "preview.py"),
                                      "--port", str(a.port),
                                      *(["--detach"] if a.detach else []),
                                      *(["--no-build"] if a.no_build else []),
                                      *_site_arg(a)))

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

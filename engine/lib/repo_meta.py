"""仓库元数据抓取（构建期执行，结果写进 manifest 并缓存）。

支持 GitHub / Gitee / Codeberg / 自托管 Gitea（含 Gitea 系）。
失败时回退到上次缓存（标记 stale），再失败则返回 None，构建不会因此中断。
"""

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

UA = "rec-blog-builder/0.1 (+static site build)"
TIMEOUT = 10


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect(url):
    """返回 (host_kind, api_host, owner, repo)。host_kind: github/gitee/gitea。"""
    u = urlparse(url if "://" in url else "https://" + url)
    host = u.netloc.lower()
    parts = [p for p in u.path.split("/") if p]
    if len(parts) < 2:
        return None, host, "", ""
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if "github.com" in host:
        return "github", "api.github.com", owner, repo
    if "gitee.com" in host:
        return "gitee", "gitee.com", owner, repo
    return "gitea", host, owner, repo


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _norm(d, host_kind, url):
    lic = d.get("license")
    if isinstance(lic, dict):
        lic = lic.get("spdx_id") or lic.get("key") or lic.get("name")
    if lic in ("NOASSERTION", ""):
        lic = None
    if host_kind == "github":
        stars, forks, pushed = d.get("stargazers_count"), d.get("forks_count"), d.get("pushed_at")
    elif host_kind == "gitee":
        stars, forks, pushed = d.get("stargazers_count"), d.get("forks_count"), d.get("pushed_at")
    else:
        stars, forks = d.get("stars_count"), d.get("forks_count")
        pushed = d.get("pushed_at") or d.get("updated_at")
        if isinstance(pushed, (int, float)):
            pushed = datetime.fromtimestamp(pushed, timezone.utc).isoformat()
    return {
        "host": host_kind,
        "url": url,
        "stars": stars,
        "forks": forks,
        "language": d.get("language"),
        "license": lic,
        "updated_at": pushed or d.get("updated_at"),
        "description": d.get("description"),
        "archived": bool(d.get("archived")),
        "fetched_at": now_iso(),
        "stale": False,
    }


def fetch(url):
    kind, host, owner, repo = detect(url)
    if not owner or not repo:
        return None
    try:
        if kind == "github":
            d = _get("https://api.github.com/repos/%s/%s" % (owner, repo))
        elif kind == "gitee":
            d = _get("https://gitee.com/api/v5/repos/%s/%s" % (owner, repo))
        else:
            d = _get("https://%s/api/v1/repos/%s/%s" % (host, owner, repo))
        return _norm(d, kind, url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as e:
        print("  ! 元数据抓取失败 %s (%s)" % (url, e))
        return None


class Cache:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.data = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, url, offline=False):
        if offline:
            hit = self.data.get(url)
            if hit:
                hit = dict(hit, stale=True)
            return hit
        d = fetch(url)
        if d:
            self.data[url] = d
            return d
        hit = self.data.get(url)
        if hit:
            hit = dict(hit, stale=True)
            print("  ~ 使用缓存（stale）%s" % url)
            return hit
        return None

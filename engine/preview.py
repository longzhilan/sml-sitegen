#!/usr/bin/env python3
"""本地预览：先构建，再在本地起静态服务器（默认 http://127.0.0.1:8080）。

    python engine/preview.py                 # 构建 + 前台运行
    python engine/preview.py --detach        # 构建 + 后台运行（日志 .preview.log）
    python engine/preview.py --no-build      # 只起服务
    python engine/preview.py --port 9000
"""

import argparse
import http.server
import os
import socket
import socketserver
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402

ENGINE = Path(__file__).resolve().parent
DIST = config.OUT
LOG = config.REPO / ".preview.log"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DIST), **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write("%s %s\n" % (self.log_date_time_string(), fmt % args))
        except OSError:
            pass


def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--detach", action="store_true")
    config.add_site_arg(ap)
    args = ap.parse_args()

    if not args.no_build:
        cmd = [sys.executable, str(ENGINE / "build.py"), "--offline"]
        if args.site:
            cmd += ["--site", args.site]
        rc = subprocess.call(cmd)
        if rc != 0:
            print("构建失败，停止预览。")
            return rc

    if args.detach:
        log = open(LOG, "ab")
        flags = 0
        if os.name == "nt":
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        cmd = [sys.executable, str(ENGINE / "preview.py"),
               "--port", str(args.port), "--no-build"]
        if args.site:
            cmd += ["--site", args.site]
        p = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                             creationflags=flags, close_fds=True)
        print("预览已后台启动 (pid=%d)：http://127.0.0.1:%d/" % (p.pid, args.port))
        print("站点根：%s" % config.SITE)
        print("日志：%s" % LOG)
        return 0

    if not port_free(args.port):
        print("端口 %d 已被占用。" % args.port)
        return 1
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), Handler) as httpd:
        print("预览：http://127.0.0.1:%d/  (Ctrl+C 停止)" % args.port)
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

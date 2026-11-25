# -*- coding: utf-8 -*-
"""检测 m3u 直播源是否存活。

用法：
    python tools/check_m3u.py tv/m3u/index.m3u
    python tools/check_m3u.py tv/m3u/index.m3u -o tv/m3u/alive.m3u
    python tools/check_m3u.py tv/m3u/index.m3u --timeout 6 --workers 20

输出：
    - 控制台：每个频道的检测结果
    - alive.m3u：只保留可用源（可选）
    - dead.txt：失效源清单（可选）

判定标准：
    HTTP 200 且响应内容像 m3u8 / m3u 播放列表，或返回 TS 分片。
"""

import argparse
import concurrent.futures
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)
TIMEOUT = 8
MAX_BYTES = 64 * 1024


def read_text_any(path):
    """自动识别编码：先 UTF-8，失败再按 GB18030。"""
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def parse_m3u(path):
    """返回 [(标题行, 地址行, 显示名), ...]"""
    text = read_text_any(path)
    lines = [line.strip() for line in text.splitlines()]
    items = []
    pending = None
    for line in lines:
        if not line:
            continue
        if line.startswith("#EXTINF"):
            pending = line
            continue
        if line.startswith("#"):
            continue
        name = ""
        if pending:
            match = re.search(r",(.*)$", pending)
            name = match.group(1).strip() if match else pending
        items.append((pending or "", line, name))
        pending = None
    return items


def fetch(url, timeout):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": url.split("/")[0] + "//" + url.split("/")[2] + "/",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        body = response.read(MAX_BYTES)
    return status, content_type, body


def looks_alive(content_type, body):
    head = body[:4096].decode("utf-8", errors="ignore").lstrip()
    if head.startswith("#EXTM3U"):
        return True, "m3u8"
    lowered = content_type.lower()
    if "mpegurl" in lowered or "video" in lowered or "octet-stream" in lowered:
        return True, content_type or "binary"
    if body[:1] == b"\x47":  # TS 包同步字节 0x47
        return True, "ts"
    return False, content_type or "unknown"


def check(item, timeout):
    header, url, name = item
    started = time.time()
    try:
        status, content_type, body = fetch(url, timeout)
        ok, kind = looks_alive(content_type, body)
        cost = int((time.time() - started) * 1000)
        if status == 200 and ok:
            return True, name, url, f"{status} {kind} {cost}ms", header
        return False, name, url, f"{status} {kind} {cost}ms", header
    except urllib.error.HTTPError as exc:
        return False, name, url, f"HTTP {exc.code}", header
    except Exception as exc:  # noqa: BLE001
        return False, name, url, f"{type(exc).__name__}", header


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="输入的 m3u 文件")
    parser.add_argument("-o", "--output", help="输出存活 m3u 文件")
    parser.add_argument("--dead", help="输出失效清单")
    parser.add_argument("--timeout", type=float, default=TIMEOUT)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    items = parse_m3u(args.source)
    if not items:
        print("没有解析到频道，检查文件格式")
        return 1

    print(f"共 {len(items)} 个频道，开始检测（超时 {args.timeout}s，并发 {args.workers}）\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(check, item, args.timeout) for item in items]
        for index, future in enumerate(concurrent.futures.as_completed(futures), 1):
            result = future.result()
            results.append(result)
            mark = "OK  " if result[0] else "FAIL"
            print(f"[{index}/{len(items)}] {mark} {result[1] or '(未命名)'} -> {result[3]}")

    alive = [r for r in results if r[0]]
    dead = [r for r in results if not r[0]]

    print(f"\n存活 {len(alive)} / 失效 {len(dead)} / 总计 {len(results)}")

    if args.output:
        alive_urls = {r[2] for r in alive}
        lines = ["#EXTM3U"]
        for header, url, _ in items:
            if url in alive_urls:
                if header:
                    lines.append(header)
                lines.append(url)
        Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已写入 {args.output}")

    if args.dead:
        Path(args.dead).write_text(
            "\n".join(f"{r[1]}\t{r[2]}\t{r[3]}" for r in dead) + "\n",
            encoding="utf-8",
        )
        print(f"已写入 {args.dead}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""把检测后的 m3u 整理成规整的频道列表。

做的事：
    1. 清洗频道名：去掉 (1080p)/(720p)/[Geo-blocked]/[Not 24/7] 等标记
    2. 分组：央视 / 卫视 / 港澳台 / 地方
    3. 台标：优先匹配 tv/ 目录下的同名 png
    4. 排序：央视按频道号，卫视按常见顺序，其余按名称
    5. 去重：同名频道只留第一个

用法：
    python tools/build_channels.py tv/m3u/alive2.m3u -o tv/m3u/index.m3u
"""

import argparse
import re
from pathlib import Path

CCTV_ORDER = [
    "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+", "CCTV6", "CCTV7",
    "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14",
    "CCTV15", "CCTV16", "CCTV17", "CCTV4K", "CCTV8K", "CCTV3D",
    "CCTV4欧洲", "CCTV4美洲",
]

SATELLITE_ORDER = [
    "北京卫视", "东方卫视", "湖南卫视", "江苏卫视", "浙江卫视", "广东卫视",
    "深圳卫视", "山东卫视", "安徽卫视", "天津卫视", "河北卫视", "山西卫视",
    "内蒙古卫视", "辽宁卫视", "吉林卫视", "黑龙江卫视", "河南卫视", "湖北卫视",
    "江西卫视", "福建东南卫视", "东南卫视", "广西卫视", "海南卫视", "重庆卫视",
    "四川卫视", "贵州卫视", "云南卫视", "陕西卫视", "甘肃卫视", "青海卫视",
    "宁夏卫视", "新疆卫视", "西藏卫视", "厦门卫视", "三沙卫视", "兵团卫视",
    "延边卫视", "大湾区卫视", "南方卫视", "香港卫视", "澳亚卫视", "莲花卫视",
    "星空卫视", "海峡卫视", "东风卫视", "人间卫视",
]

HMT_WORDS = ("香港", "澳门", "台湾", "凤凰", "翡翠", "明珠", "无线", "TVB", "HOY", "ViuTV")

CLEAN_PATTERNS = [
    r"\((?:1080|720|576|540|480|404|360)[pi]\)",
    r"\[Geo-blocked\]",
    r"\[Not 24/7\]",
    r"\(Geo-blocked\)",
    r"\(\d+[pi]\)",
    r"\bHD\b",
    r"\bSD\b",
]


def read_text_any(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def parse_m3u(text):
    items = []
    header = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            header = line
            continue
        if line.startswith("#"):
            continue
        if header:
            match = re.search(r",(.*)$", header)
            name = match.group(1).strip() if match else ""
            items.append((name, line, header))
        header = None
    return items


def clean_name(name):
    for pattern in CLEAN_PATTERNS:
        name = re.sub(pattern, "", name)
    name = re.sub(r"\s{2,}", " ", name).strip(" -_")
    return name


def cctv_key(name):
    match = re.match(r"CCTV-?(\d+)(\+)?", name, re.IGNORECASE)
    if not match:
        return None
    key = "CCTV" + match.group(1) + (match.group(2) or "")
    return key


def to_cctv_display(key):
    mapping = {
        "CCTV1": "CCTV-1 综合", "CCTV2": "CCTV-2 财经", "CCTV3": "CCTV-3 综艺",
        "CCTV4": "CCTV-4 中文国际", "CCTV5": "CCTV-5 体育", "CCTV5+": "CCTV-5+ 体育赛事",
        "CCTV6": "CCTV-6 电影", "CCTV7": "CCTV-7 国防军事", "CCTV8": "CCTV-8 电视剧",
        "CCTV9": "CCTV-9 纪录", "CCTV10": "CCTV-10 科教", "CCTV11": "CCTV-11 戏曲",
        "CCTV12": "CCTV-12 社会与法", "CCTV13": "CCTV-13 新闻", "CCTV14": "CCTV-14 少儿",
        "CCTV15": "CCTV-15 音乐", "CCTV16": "CCTV-16 奥林匹克", "CCTV17": "CCTV-17 农业农村",
    }
    return mapping.get(key, key)


def classify(name):
    if cctv_key(name):
        return "央视高清"
    if "卫视" in name:
        return "卫视高清"
    if "CGTN" in name.upper():
        return "国际频道"
    if any(word in name for word in HMT_WORDS):
        return "港澳台"
    return "地方频道"


def logo_for(name, tv_dir):
    key = cctv_key(name)
    candidates = []
    if key:
        candidates.append(key + ".png")
    candidates.append(name + ".png")
    base = re.sub(r"\s*CCTV-", "CCTV", name)
    candidates.append(base + ".png")
    for candidate in candidates:
        if (tv_dir / candidate).exists():
            return candidate
    return ""


GROUP_ORDER = {"央视高清": 0, "卫视高清": 1, "国际频道": 2, "港澳台": 3, "地方频道": 4}


def sort_key(entry):
    group, name, key = entry[0], entry[1], entry[5]
    if group == "央视高清":
        order = CCTV_ORDER.index(key) if key in CCTV_ORDER else 99
        return (0, order, name)
    if group == "卫视高清":
        order = SATELLITE_ORDER.index(name) if name in SATELLITE_ORDER else 99
        return (1, order, name)
    return (GROUP_ORDER.get(group, 9), 0, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="+", help="一个或多个 m3u 文件（按顺序合并）")
    parser.add_argument("-o", "--output", default="tv/m3u/index.m3u")
    args = parser.parse_args()

    tv_dir = Path(args.output).resolve().parent.parent
    items = []
    for source in args.source:
        items.extend(parse_m3u(read_text_any(source)))

    seen = set()
    entries = []
    for name, url, _ in items:
        clean = clean_name(name)
        if not clean:
            continue
        key = cctv_key(clean)
        display = to_cctv_display(key) if key else clean
        group = classify(display)
        if display in seen:
            continue
        seen.add(display)
        entries.append((group, display, url, logo_for(display, tv_dir), group, key))

    entries.sort(key=sort_key)

    lines = ["#EXTM3U"]
    for group, display, url, logo, _, _ in entries:
        logo_attr = f' tvg-logo="{logo}"' if logo else ""
        lines.append(
            f'#EXTINF:-1 tvg-name="{display}"{logo_attr} group-title="{group}",{display}'
        )
        lines.append(url)

    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = {}
    for entry in entries:
        counts[entry[0]] = counts.get(entry[0], 0) + 1
    print(f"共 {len(entries)} 个频道")
    for group, count in counts.items():
        print(f"  {group}: {count}")
    print(f"已写入 {args.output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""全量扫描 wangwenge.top 书籍 id: 只探测 do=show 是否有效, 不抓正文/不下载封面。
输出 ids.json(有效 id 列表) + 分段统计。
用法: python scan_full.py [start] [end]
"""
import urllib.request
import re
import json
import time
import os
import sys
import concurrent.futures

BASE = "http://www.wangwenge.top/app/index.php"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def check(bid):
    url = f"{BASE}?i=2&c=entry&m=iweite_xiaoshuo&do=show&id={bid}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        m = re.search(r'<h3 class="detail-title">(.*?)</h3>', html, re.S)
        title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
        return bid, bool(title)
    except Exception:
        return bid, False

if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    end = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
    t = time.time()
    valid = []
    done = 0
    total = end - start + 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as ex:
        for bid, ok in ex.map(check, range(start, end + 1)):
            done += 1
            if ok:
                valid.append(bid)
            if done % 10000 == 0:
                print(f"  进度 {done}/{total}  已发现有效 {len(valid)}", flush=True)
    valid.sort()
    # 累积合并: 分段扫描时保留已有结果
    if os.path.exists("ids.json"):
        try:
            old = json.load(open("ids.json", encoding="utf-8"))
            valid = sorted(set(old) | set(valid))
        except Exception:
            pass
    with open("ids.json", "w", encoding="utf-8") as f:
        json.dump(valid, f)
    print(f"\n区间[{start},{end}] 耗时 {time.time()-t:.1f}s  有效书总数={len(valid)}")
    # 连续段统计
    segs = []
    cur = [valid[0]] if valid else []
    for x in valid[1:]:
        if x - cur[-1] <= 2:
            cur.append(x)
        else:
            segs.append((cur[0], cur[-1], len(cur)))
            cur = [x]
    if cur:
        segs.append((cur[0], cur[-1], len(cur)))
    print(f"连续段数={len(segs)}")
    for a, b, n in segs:
        print(f"  {a}~{b}: {n}本")

#!/usr/bin/env python3
"""
wangwenge.top 整站小说镜像爬虫
- 穷举书籍 id（微擎 iweite_xiaoshuo 模块，自增主键，连续分布）
- 抓取：目录(mulu) -> 逐章正文(read) -> #fuzhi 提取 <p>文本</p>
- 下载封面图
- 增量：已抓取且"已完结"的书跳过；其余只补未完成的章节
- 纯标准库，无需 pip 安装依赖
用法:
  python crawl.py                 # 使用默认区间/环境变量
  START=56000 END=96000 python crawl.py
  python crawl.py 56000 96000    # 命令行参数优先
输出目录(默认 novels):
  novels/<book_id>/meta.json     # 标题/作者/封面/状态/章节数/字数
  novels/<book_id>/full.txt      # 全书纯文本(含章节标题)
  novels/<book_id>/cover.jpg     # 封面
"""
import urllib.request
import urllib.parse
import re
import os
import json
import time
import sys
import random
import concurrent.futures

BASE = "http://www.wangwenge.top/app/index.php"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def http_get(url, timeout=25, raw=False):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Referer": BASE})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return data if raw else data.decode("utf-8", errors="ignore")


def get_book_meta(bid):
    url = f"{BASE}?i=2&c=entry&m=iweite_xiaoshuo&do=show&id={bid}"
    try:
        html = http_get(url)
    except Exception:
        return None
    m = re.search(r'<h3 class="detail-title">(.*?)</h3>', html, re.S)
    if not m:
        return None
    title = re.sub(r"\s+", " ", m.group(1)).strip()
    if not title:
        return None
    # 封面: 详情页里 attachment/images/ 下的图片(避开 banner/addons 图)
    cm = re.search(r'https?://[^\s"\']*attachment/images/[^\s"\']+\.(?:jpg|jpeg|png|gif|webp)', html, re.I)
    cover = cm.group(0) if cm else ""
    am = re.search(r'作者:\s*</div>\s*<div>(.*?)</div>', html, re.S)
    author = re.sub(r"<.*?>", "", am.group(1)).strip() if am else ""
    sm = re.search(r'状态:\s*([^<]+)', html)
    status = sm.group(1).strip() if sm else ""
    return {"id": bid, "title": title, "author": author or "佚名",
            "cover": cover, "status": status}


def get_chapter_list(bid):
    sids = []
    page = 1
    while page <= 60:
        url = (f"{BASE}?i=2&c=entry&tid={bid}&page={page}"
               f"&do=mulu&m=iweite_xiaoshuo")
        try:
            html = http_get(url)
        except Exception:
            break
        items = re.findall(r'sid="(\d+)"\s+ret="([^"]+)"', html)
        if not items:
            break
        for sid, ret in items:
            sids.append((int(sid), ret))
        if f'page={page + 1}' in html:
            page += 1
            time.sleep(0.05)
        else:
            break
    return sids


def get_chapter_text(bid, sid):
    url = (f"{BASE}?i=2&c=entry&tid={bid}&sid={sid}"
           f"&do=read&m=iweite_xiaoshuo")
    try:
        html = http_get(url)
    except Exception:
        return None
    m = re.search(r'id="fuzhi"[^>]*>(.*?)</div>', html, re.S)
    if not m:
        return None
    paras = re.findall(r'<p>([^<]+)', m.group(1))
    text = "\n".join(p.strip() for p in paras if p.strip())
    return text if text else None


def download_cover(cover_url, path):
    if not cover_url:
        return False
    try:
        if cover_url.startswith("//"):
            cover_url = "http:" + cover_url
        data = http_get(cover_url, raw=True)
        with open(path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def crawl_book(bid, out_root):
    meta = get_book_meta(bid)
    if not meta:
        return False
    book_dir = os.path.join(out_root, str(bid))
    os.makedirs(book_dir, exist_ok=True)
    meta_path = os.path.join(book_dir, "meta.json")

    skip = False
    if os.path.exists(meta_path):
        try:
            old = json.load(open(meta_path, encoding="utf-8"))
            if old.get("done") and old.get("status") == "已完结":
                skip = True
        except Exception:
            pass
    if skip:
        return True

    if meta.get("cover") and not os.path.exists(os.path.join(book_dir, "cover.jpg")):
        download_cover(meta["cover"], os.path.join(book_dir, "cover.jpg"))

    chapters = get_chapter_list(bid)
    texts = {}

    def worker(item):
        sid, ret = item
        return sid, get_chapter_text(bid, sid)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for sid, t in ex.map(worker, chapters):
            if t:
                texts[sid] = t
            time.sleep(random.uniform(0.01, 0.05))

    full = []
    for sid, ret in sorted(chapters, key=lambda x: x[0]):
        if sid in texts:
            full.append(f"\n\n{ret}\n\n" + texts[sid])
    with open(os.path.join(book_dir, "full.txt"), "w", encoding="utf-8") as f:
        f.write(meta["title"] + "\n作者：" + meta["author"] + "\n\n")
        f.write("".join(full))

    meta["chapters"] = len(texts)
    meta["chars"] = sum(len(v) for v in texts.values())
    meta["done"] = True
    meta["updated"] = time.strftime("%Y-%m-%d")
    json.dump(meta, open(meta_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[OK] {bid} 《{meta['title'][:24]}》 章={len(texts)} 字={meta['chars']}")
    return True


def scan_ids(start, end, step=100, workers=16):
    """粗扫 + 细扫: 先以 step 步长定位有效区段, 再对命中区段 ±step 细扫。"""
    hits = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for bid, ok in ex.map(lambda b: (b, get_book_meta(b) is not None),
                              range(start, end + 1, step)):
            if ok:
                hits.append(bid)
    if not hits:
        return []
    lo = min(hits) - step
    hi = max(hits) + step
    lo, hi = max(start, lo), min(end, hi)
    valid = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for bid, ok in ex.map(lambda b: (b, get_book_meta(b) is not None),
                              range(lo, hi + 1)):
            if ok:
                valid.append(bid)
    return sorted(valid)


if __name__ == "__main__":
    START = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("START", "56000"))
    END = int(sys.argv[2]) if len(sys.argv) > 2 else int(os.environ.get("END", "96000"))
    OUT = os.environ.get("OUT_DIR", "novels")
    os.makedirs(OUT, exist_ok=True)

    print(f"== 扫描有效 id 区间 [{START}, {END}] ==")
    valid = scan_ids(START, END)
    with open(os.path.join(OUT, "ids.json"), "w", encoding="utf-8") as f:
        json.dump(valid, f)
    print(f"== 发现有效书籍 {len(valid)} 本 ==")

    ok = 0
    for bid in valid:
        try:
            if crawl_book(bid, OUT):
                ok += 1
        except Exception as e:
            print(f"[ERR] {bid}: {e}")
    print(f"== 完成 {ok}/{len(valid)} ==")

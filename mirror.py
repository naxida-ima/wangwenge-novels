#!/usr/bin/env python3
"""按 ID 增量镜像 wangwenge.top: 每本抓到 books/{id}.txt + books/{id}.json;
启动时先把 books/ 里残留文件(孤儿元数据等)打包清空, 续跑跳过已保存 ID;
按体积封包 novels_NNNN.zip(单包<=95MB), progress.json 记已跑过的 ID。
无 wip.zip 累积; 每本单文件 <5MB 永远不超限; books/ 始终保持空, 不堆积小文件。

依赖: crawl.crawl_book(bid, out_root) -> bool (写 out_root/{bid}.txt + {bid}.json)
"""

import json, os, zipfile, time, glob, re, crawl

IDS_FILE = "ids.json"
PROG = "progress.json"
BOOKS = "books"
ZIPS = "novels"
TIME_LIMIT = 250 * 60
MAX_ZIP = 95 * 1024 * 1024  # 单包体积安全线(< GitHub 100MB)


def load_ids():
    return json.load(open(IDS_FILE, encoding="utf-8"))


def existing_ids():
    """从 books/ 单本 txt 和 novels/ 整包 zip 重建已保存的书 ID 集合"""
    done = set()
    if os.path.isdir(BOOKS):
        for f in os.listdir(BOOKS):
            if f.endswith(".txt"):
                try:
                    done.add(int(f[:-4]))
                except ValueError:
                    pass
    if os.path.isdir(ZIPS):
        for zf in glob.glob(os.path.join(ZIPS, "*.zip")):
            with zipfile.ZipFile(zf) as z:
                for n in z.namelist():
                    if n.endswith(".txt"):
                        try:
                            done.add(int(n[:-4]))
                        except ValueError:
                            pass
    return done


def next_zip_index():
    """novels/ 下现有最大编号 + 1, 避免覆盖已有包"""
    idx = 0
    if os.path.isdir(ZIPS):
        for zf in glob.glob(os.path.join(ZIPS, "novels_*.zip")):
            m = re.search(r"novels_(\d+)\.zip$", zf)
            if m:
                idx = max(idx, int(m.group(1)))
    return idx + 1


def pack_books(start_idx):
    """把 books/ 下所有文件按体积分批打 novels_NNNN.zip 并删除原文件。
    返回下一个可用编号。books/ 无文件时直接返回 start_idx。"""
    if not os.path.isdir(BOOKS):
        return start_idx
    files = [os.path.join(BOOKS, f) for f in os.listdir(BOOKS)
             if os.path.isfile(os.path.join(BOOKS, f))]
    if not files:
        return start_idx
    files.sort()
    idx = start_idx
    buf = []

    def flush():
        nonlocal idx, buf
        if not buf:
            return
        zipname = os.path.join(ZIPS, f"novels_{idx:04d}.zip")
        with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as z:
            for p in buf:
                z.write(p, os.path.basename(p))
        for p in buf:
            os.remove(p)
        idx += 1
        buf = []

    for p in files:
        buf.append(p)
        sz = sum(os.path.getsize(x) for x in buf)
        if sz >= MAX_ZIP:
            flush()
    flush()
    return idx


def main():
    ids = load_ids()
    done = existing_ids()  # 实际已保存的书(不依赖可能过期的 progress.json)
    os.makedirs(BOOKS, exist_ok=True)
    os.makedirs(ZIPS, exist_ok=True)

    # 阶段0: 先把 books/ 里上轮残留(孤儿 .json 等)打包清空, 保持不堆积
    idx = next_zip_index()
    idx = pack_books(idx)

    # 阶段1: 续跑抓新书
    start = time.time()
    newly = []
    for bid in ids:
        if bid in done:
            continue
        try:
            if crawl.crawl_book(bid, BOOKS):
                done.add(bid)
                newly.append(bid)
        except Exception as e:
            print(f"[ERR] {bid}: {e}")
        if time.time() - start > TIME_LIMIT:
            print("time limit reached, stop")
            break

    # 阶段2: 把本轮新抓的(正文+元数据)打包, 清空 books/
    idx = pack_books(idx)

    # 写 progress.json (记录已保存的 ID, 轻量几 KB, 永远能 push)
    prog = {"done": sorted(done)}
    json.dump(prog, open(PROG, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"DONE total={len(done)} newly={len(newly)} next_zip={idx}")


if __name__ == "__main__":
    main()

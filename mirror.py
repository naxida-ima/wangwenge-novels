#!/usr/bin/env python3
"""wangwenge.top 增量镜像 -> GitHub 仓库(每1000本一个zip包, 无封面)。
流程:
  1. 恢复 wip.zip (上次未凑满1000本的暂存)
  2. 增量抓取未完成的书(基于 progress.json 的 done 集合, 限时)
  3. 每满1000本(或最后不满1000的尾批)打整包 novels_NNNN.zip; 其余打 wip.zip
  4. 退出, 由 workflow 把 zip + progress.json 提交到仓库
依赖: crawl.py 的 crawl_book
"""
import json
import os
import zipfile
import time
import crawl

IDS_FILE = "ids.json"
PROG = "progress.json"
OUT = "novels"
WIP = "wip.zip"
TIME_LIMIT = 250 * 60  # 秒, 留时间给打包与推送


def load_ids():
    return json.load(open(IDS_FILE, encoding="utf-8"))


def load_prog():
    if os.path.exists(PROG):
        return json.load(open(PROG, encoding="utf-8"))
    return {"done": [], "packed": []}


def restore_wip():
    if os.path.exists(WIP):
        with zipfile.ZipFile(WIP) as z:
            z.extractall(OUT)
        print("restored", WIP)


def crawl_incremental(ids, done_set):
    start = time.time()
    newly = []
    for bid in ids:
        if bid in done_set:
            continue
        try:
            if crawl.crawl_book(bid, OUT):
                newly.append(bid)
                done_set.add(bid)
        except Exception as e:
            print(f"[ERR] {bid}: {e}")
        if time.time() - start > TIME_LIMIT:
            print("time limit reached, stop")
            break
    return newly


def package(ids, done_set, packed):
    idx = {b: i for i, b in enumerate(ids)}
    max_bi = (len(ids) - 1) // 1000
    all_batches = {}
    for b in ids:
        all_batches.setdefault(idx[b] // 1000, []).append(b)
    done_batches = {}
    for b in done_set:
        if b in idx:
            done_batches.setdefault(idx[b] // 1000, []).append(b)

    for bi in sorted(done_batches):
        lst = done_batches[bi]
        full = (len(lst) == 1000) or (
            bi == max_bi and set(lst) == set(all_batches.get(bi, []))
        )
        if full and bi not in packed:
            zipname = f"novels_{bi + 1:04d}.zip"
            with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as z:
                for b in sorted(lst):
                    d = os.path.join(OUT, str(b))
                    for f in ("full.txt", "meta.json"):
                        p = os.path.join(d, f)
                        if os.path.exists(p):
                            z.write(p, os.path.join(str(b), f))
            packed.append(bi)
            print(f"packed {zipname} ({len(lst)} books)")

    packed_ids = set()
    for bi in packed:
        packed_ids |= set(done_batches.get(bi, []))
    wip = [b for b in done_set if b in idx and b not in packed_ids]
    if wip:
        with zipfile.ZipFile(WIP, "w", zipfile.ZIP_DEFLATED) as z:
            for b in sorted(wip):
                d = os.path.join(OUT, str(b))
                for f in ("full.txt", "meta.json"):
                    p = os.path.join(d, f)
                    if os.path.exists(p):
                        z.write(p, os.path.join(str(b), f))
        print(f"wip.zip updated ({len(wip)} books)")
    elif os.path.exists(WIP):
        os.remove(WIP)
        print("wip.zip removed (all packed)")


def main():
    ids = load_ids()
    prog = load_prog()
    done = set(prog.get("done", []))
    packed = prog.get("packed", [])
    restore_wip()
    newly = crawl_incremental(ids, done)
    prog["done"] = sorted(done)
    prog["packed"] = packed
    json.dump(prog, open(PROG, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    package(ids, done, packed)
    print(f"DONE total={len(done)} newly={len(newly)} "
          f"batches_packed={len(packed)}")


if __name__ == "__main__":
    main()

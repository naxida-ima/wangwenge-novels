#!/usr/bin/env python3
"""按 ID 增量镜像 wangwenge.top: 每本存 books/{id}.txt; 满1000本打整包 novels_NNNN.zip; progress.json 记已跑过的 ID。
- 续跑: 启动时从 books/ 单本 txt 和 novels/ 整包 zip 重建已保存的 ID 集合, 跳过这些 ID
- 无 wip.zip 累积(避免单文件超 GitHub 100MB 限制)
- 每本单独文件, 单本 <5MB 永远不超限
依赖: crawl.crawl_book(bid, out_root) -> bool (写 out_root/{bid}.txt + {bid}.json)
"""
import json, os, zipfile, time, glob, crawl

IDS_FILE = "ids.json"
PROG = "progress.json"
BOOKS = "books"
ZIPS = "novels"
TIME_LIMIT = 250 * 60
BATCH = 1000


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


def main():
    ids = load_ids()
    done = existing_ids()
    os.makedirs(BOOKS, exist_ok=True)
    os.makedirs(ZIPS, exist_ok=True)

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

    # 写 progress.json (记录已保存的 ID, 轻量几 KB, 永远能 push)
    prog = {"done": sorted(done)}
    json.dump(prog, open(PROG, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # 打包: 每满 BATCH 本打一个整包, 并删除对应单本 txt (节省空间)
    done_sorted = sorted(done)
    packed = 0
    for i in range(0, len(done_sorted), BATCH):
        batch = done_sorted[i:i + BATCH]
        if len(batch) < BATCH:
            continue  # 尾批不足 BATCH, 留在 books/ 单本
        zipname = os.path.join(ZIPS, f"novels_{i // BATCH + 1:04d}.zip")
        if os.path.exists(zipname):
            continue
        with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as z:
            for b in batch:
                p = os.path.join(BOOKS, f"{b}.txt")
                if os.path.exists(p):
                    z.write(p, f"{b}.txt")
        for b in batch:
            p = os.path.join(BOOKS, f"{b}.txt")
            if os.path.exists(p):
                os.remove(p)
        packed += 1
        print(f"packed {zipname} ({len(batch)} books)")

    print(f"DONE total={len(done)} newly={len(newly)} batches_packed={packed}")


if __name__ == "__main__":
    main()

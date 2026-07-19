#!/usr/bin/env python3
"""按 ID 增量镜像 wangwenge.top: 每本存 books/{id}.txt; 按体积封包 novels_NNNN.zip(每包<=95MB); progress.json 记已跑过的 ID。
- 续跑: 启动时从 books/ 单本 txt 和 novels/ 整包 zip 重建已保存的 ID 集合, 跳过这些 ID
- 无 wip.zip 累积; 每本单文件 <5MB 永远不超限; 整包按体积封(<=95MB)避免超 GitHub 100MB 限制
依赖: crawl.crawl_book(bid, out_root) -> bool (写 out_root/{bid}.txt + {bid}.json)
"""
import json, os, zipfile, time, glob, crawl

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


def main():
    ids = load_ids()
    done = existing_ids()  # 实际已保存的书(不依赖可能过期的 progress.json)
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

    # 按体积封包: 累积到 >=MAX_ZIP 封一包; 尾批也封(不留单本累积)
    done_sorted = sorted(done)
    buf = []
    pack_idx = 1

    def flush():
        nonlocal pack_idx, buf
        if not buf:
            return
        zipname = os.path.join(ZIPS, f"novels_{pack_idx:04d}.zip")
        with zipfile.ZipFile(zipname, "w", zipfile.ZIP_DEFLATED) as z:
            for _, p in buf:
                z.write(p, os.path.basename(p))
        for _, p in buf:
            if os.path.exists(p):
                os.remove(p)
        pack_idx += 1
        buf = []

    for b in done_sorted:
        p = os.path.join(BOOKS, f"{b}.txt")
        if os.path.exists(p):
            buf.append((b, p))
        sz = sum(os.path.getsize(pp) for _, pp in buf)
        if sz >= MAX_ZIP:
            flush()
    flush()  # 尾批
    packed = pack_idx - 1
    print(f"DONE total={len(done)} newly={len(newly)} batches_packed={packed}")


if __name__ == "__main__":
    main()

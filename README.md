# wangwenge-novels

自动镜像 [wangwenge.top](http://www.wangwenge.top) 全站小说（纯文本 + 封面图）的仓库。

## 原理
该站使用微擎 `iweite_xiaoshuo` 小说模块，书籍 id 为自增主键、连续分布。
脚本穷举 id 区间，命中有效书后抓取：
- 书籍详情 `do=show&id=N` → 标题 / 作者 / 状态 / 封面
- 目录 `do=mulu&page=N` → 章节 `sid` 列表
- 正文 `do=read&sid=N` → `#fuzhi` 内 `<p>文本</p>` 提取

> 注：该站"VIP 章节"后端未做鉴权，移动端接口直接返回全文，故可完整抓取。

## 结构
```
crawl.py                  抓取脚本（纯标准库）
.github/workflows/scrape.yml   GitHub Actions：每日定时抓取并自推送
novels/<book_id>/meta.json    书籍元信息
novels/<book_id>/full.txt     全书纯文本
novels/<book_id>/cover.jpg    封面
```

## 本地运行
```bash
pip 无需安装（仅用标准库）
START=56000 END=96000 python crawl.py
```

## 自动化
GitHub Actions 每日 03:17 (UTC) 运行一次，增量补全未抓完的书（已完结的书跳过）。
也可在 Actions 页面手动 `Run workflow`，自定义扫描区间。

## 免责声明
本仓库仅作个人备份 / 技术研究用途，版权归原作者与网站所有。
如涉及侵权请联系删除。

"""摘录哈希 —— **本包内唯一的实现**

为什么单独抽一个模块
--------------------
``walkthrough``（生成时算哈希）、``verify``（校验时重算）、``narration``
（合并外部讲解时算）三处都需要同一个哈希口径。

一开始三处各写了一遍 ``sha256(text)``。这正是 README §2.2 铁律 4 与
§13.6 第 9 条警告过的情况：**同一个不变量只允许有一个实现**
（现实教训是路径规范化写了两份，导致图谱里 1054 处路径失真）。

哈希口径不一致的后果比路径更隐蔽：生成时用 A 口径、校验时用 B 口径，
校验器会把**正确的**摘录报成"不一致"，然后整个平台的证据链就没人信了。
所以这里只留一份。

口径
----
``"sha256:" + sha256(utf-8 编码的文本).hexdigest()``

前缀 ``sha256:`` 是刻意的：契约里出现一个裸十六进制串，
读者分不清它是哈希还是别的 id；带前缀才自解释。
"""

from __future__ import annotations

import hashlib

#: 哈希前缀（契约里可见，不要随手改 —— 改了会让历史讲稿的哈希全部失效）
HASH_PREFIX = "sha256:"


def sha256_text(text: str) -> str:
    """返回 ``sha256:<hex>``。空文本也照常计算（不返回空串）。"""
    return HASH_PREFIX + hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def short_digest(text: str, length: int = 12) -> str:
    """不带前缀的短摘要（用于**派生稳定 id**，例如证据 id ``ev_<12 hex>``）。

    为什么不用序号做 id：序号会随段数 / 要点条数变化而漂移，
    教师挂在某条证据上的审核意见就会指到别处去。内容派生的 id 才稳定。
    """
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[: max(1, int(length))]

# -*- coding: utf-8 -*-
"""《XiaoShuo 书库》机械门禁核心库（novel_lint_core v1.0）

用途：为 lint_episode.py（单集门禁）与 audit_library.py（全库巡检）提供共用能力。
设计原则：只用标准库；一切判定都以"机械可检"为准，不做文学判断。

标点体例（D2 裁决 · 2026-09-23）：全库统一使用中文弯引号 “ ”（U+201C / U+201D）。
  - 禁 ASCII 直引号 "（U+0022）
  - 禁直角引号「」（U+300C / U+300D）
  - 禁连排 "" 与单边引号
依据：《小说写作通用规则.md》§一 A1/A8；本裁决写入《机械门禁与校验规范.md》。

权威关系：本库只产出"机器判定"，不能替代《04-每集验收清单》的内容项与独立审核。
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

VERSION = "1.0"
SPEC_FILE = "机械门禁与校验规范.md"

# ---------------------------------------------------------------- 常量

Q_OPEN = "\u201c"   # “
Q_CLOSE = "\u201d"  # ”
Q_ASCII = "\u0022"  # "
C_OPEN = "\u300c"   # 「
C_CLOSE = "\u300d"  # 」

DASH = "\u2014\u2014"      # ——
ELLIPSIS_OK = "\u2026\u2026"  # ……
HAN = re.compile(r"[\u4e00-\u9fa5]")
SHINGLE_N = 8

# 门禁阈值（详见《机械门禁与校验规范.md》§4）
# 校准依据：2026-09-23 全库 17 本 650 集实测分布——
#   集内重复覆盖率：中位 0%，p90 1.11%，p95 5.57%；健康书 max ≤0.5%，退化书 18%~99%
#   跨集重复率：中位 1.08%，p90 6.83%，p95 9.43%；健康书 max ≤4.6%，退化书 12%~43%
# 取"健康分布之外、且能稳定抓住退化集"的档位，宁松不误杀。
TH = {
    "intra_rep_fail": 6.0,      # 集内重复覆盖率 %
    "intra_rep_warn": 2.5,
    "cross_rep_fail": 12.0,     # 与最近 N 集的最大 8-gram 重合率 %
    "cross_rep_warn": 8.0,
    "cross_window": 30,         # 跨集比对的回看窗口
    "sent_dup_fail": 3,         # 同一句（去标点后 ≥8 字）出现次数
    "shingle_min_count": 4,     # 计入"重复片段"的 8-gram 最少出现次数
    "dash_fail": 5,
    "dash_warn": 3,
}

# 元信息黑名单：创作层标记不得出现在正文（FAIL 级）
# 注意：`ep\d+` 的 lookbehind 只能排除英文字母——中文正文里集号通常紧贴汉字
# （例："你顺着ep26暗线摸"），若把汉字也排除会造成系统性漏检。
# 规则编号 `R/C+\d` 只在【】面板之外算违规（【R51：…】是合法体例），故先做面板屏蔽。
META_FAIL = [
    (r"(?<![A-Za-z])ep\s*\d{1,3}(?![0-9A-Za-z])", "创作集号 epNN"),
    (r"(?<![A-Za-z])V\s*\d{1,2}(?![0-9])", "伏笔编号 VN"),
    (r"第[一二三四五六七八九十]+幕", "幕级用语"),
    (r"检查点", "检查点"),
    (r"幕末", "幕末审计用语"),
    (r"待写|下一集|下一步：", "创作进度用语"),
    (r"本篇完|本集完|全剧终", "剧本用语"),
]
# 规则编号 R/C：本库尚未裁决"面板是否显示编号"，属**待 D2 裁决项**，暂列 WARN。
# 依据：《荒野规则》术语表 §四把 R1、R2… 定义为"跨文件引用统一用这套"（作者层索引），
#      但正文面板自 ep20 起又直接显示【R51：…】，且角色会说"R1 说了"。二者冲突，
#      需用户拍板"面板与角色是否使用编号"后再决定是否 FAIL。见《回滚与决策登记表》。
META_WARN = [
    (r"(?<![A-Za-z])[RC]\s*\d{1,2}(?![0-9A-Za-z])", "规则编号 R/C（待 D2 裁决）"),
    (r"伏笔", "伏笔"),
    (r"收束", "收束"),
    (r"埋线|埋伏笔", "埋线"),
]
PANEL = re.compile(r"【[^】]*】")
# 元信息黑名单：疑似但可能是正常词（WARN 级）。注意"回收"是常见叙事动词，不列入。
META_WARN = [
    (r"伏笔", "伏笔"),
    (r"收束", "收束"),
    (r"埋线|埋伏笔", "埋线"),
]

STOPWORDS = {
    "核心卡", "成长轨迹线", "关系网", "写作红线", "人物档案", "人物卡", "状态", "备注",
    "说明", "更新记录", "修订记录", "关系", "轨迹", "红线", "口头禅", "首次登场",
}


def _re_han_only(s: str) -> bool:
    return bool(s) and bool(HAN.fullmatch(s))


# ---------------------------------------------------------------- 读取与切分

def read_text(path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


HEADER_KEYS = ("涉及人物", "涉及规则", "本集规则", "新埋伏笔", "回收伏笔", "视角",
               "时间线", "时间锚点", "字数预估", "本集：", "本集:", "涉及时间")


def _leading_block_header(text: str):
    """识别"标题行 + 连续引用行"的头部块（无 --- 分隔符的书）。

    仅当块内出现元信息关键词时才认——避免把正文开头的世界观引文误当头部。
    """
    lines = text.split("\n")
    n = len(lines)
    i = 0
    while i < n and not lines[i].strip():
        i += 1
    if i >= n or not lines[i].lstrip().startswith("#"):
        return None
    i += 1
    end = i
    while i < n:
        s = lines[i].strip()
        if s.startswith(">"):
            end = i + 1
            i += 1
            continue
        if not s:
            i += 1
            continue
        break
    # 引用块之后若紧跟一行 --- 分隔符，一并并入头部（否则重建文件时会与上一行粘连）
    j = i
    while j < n and not lines[j].strip():
        j += 1
    if j < n and re.fullmatch(r"-{3,}", lines[j].strip()):
        end = j + 1
    block = "\n".join(lines[:end])
    if not any(k in block for k in HEADER_KEYS):
        return None
    return block, "\n".join(lines[end:])


def split_front_matter(text: str):
    """返回 (头部元信息, 正文)。

    实战中出现了四种头部写法，必须全部识别，否则文件头会被误判为"元信息入正文"：
      ① HTML 注释式：`<!-- 本集：… 涉及人物：… -->`（僵尸等）
      ② YAML 式：文件以 `---` 开头，到下一个 `---` 结束（打脸虐渣 ep33+）
      ③ 标题 + 引用块式：`# 标题` 后跟连续 `> ` 引用行（末世异能、灵魂互换等，无分隔符）
      ④ 分隔符式：标题 + 引用行，以首个独占一行的 `---` 收尾（多数书）
    """
    m = re.match(r"\s*<!--.*?-->", text, re.S)
    if m:
        return text[: m.end()], text[m.end():]
    m = re.match(r"^---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", text, re.S)
    if m:
        return m.group(0), text[m.end():]
    lead = _leading_block_header(text)
    if lead:
        return lead
    m = re.search(r"(?m)^---\s*$", text)
    if m:
        return text[: m.start()], text[m.end():]
    return "", text


def strip_ws(s: str) -> str:
    return re.sub(r"\s", "", s)


def content_only(s: str) -> str:
    """只保留内容字符（汉字/字母/数字），去掉标点与空白。

    重复率必须在这种"去标点"文本上计算：否则对白标签（如 。」温知夏说，「）会被
    误判为注水——那是体例，不是水字。真正的水字是内容字符的重复。
    """
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", s)


def han_count(s: str) -> int:
    return len(HAN.findall(s))


def body_of(path):
    header, body = split_front_matter(read_text(path))
    return header, body


def body_digest(body: str) -> str:
    return hashlib.md5(strip_ws(body).encode("utf-8")).hexdigest()


def episode_files(root):
    """按集号排序返回 epNN-*.md。"""
    root = Path(root)
    files = []
    for p in root.glob("ep*-*.md"):
        m = re.match(r"^ep(\d{1,3})-", p.name)
        if m:
            files.append((int(m.group(1)), p))
    return [p for _, p in sorted(files, key=lambda t: t[0])]


def episode_no(path) -> int:
    m = re.match(r"^ep(\d{1,3})-", Path(path).name)
    return int(m.group(1)) if m else -1


# ---------------------------------------------------------------- 文本度量

def shingle_counter(body: str, n: int = SHINGLE_N) -> Counter:
    s = content_only(body)
    return Counter(s[i:i + n] for i in range(max(0, len(s) - n + 1)))


def shingle_set(body: str, n: int = SHINGLE_N) -> set:
    s = content_only(body)
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def intra_repetition(body: str, n: int = SHINGLE_N):
    """返回 (重复覆盖率%, [(片段, 次数)] top5)。

    覆盖率 = 落在"重复片段"（出现 ≥shingle_min_count 次）内的内容字符位置数 / 总位置数。
    ∈[0,100]，含义直观：本集有多少比例的内容字符处在复读片段里。
    基于去标点内容字符计算，避免把对白标签误判为注水。
    """
    s = content_only(body)
    total = max(0, len(s) - n + 1)
    if not total:
        return 0.0, []
    cnt = Counter(s[i:i + n] for i in range(total))
    top = cnt.most_common(5)
    rep = {sh for sh, c in cnt.items() if c >= TH["shingle_min_count"]}
    covered = sum(1 for i in range(total) if s[i:i + n] in rep)
    return round(covered / total * 100, 2), top


def containment(a: set, b: set) -> float:
    """a 被 b 覆盖的比例 %（用于"本集有多少内容与旧集重合"）。"""
    if not a:
        return 0.0
    return round(len(a & b) / len(a) * 100, 2)


def cross_repetition(root, path):
    """与之前 cross_window 集比对，返回 (最大重合率%, 对应集名)。"""
    eps = episode_files(root)
    idx = eps.index(Path(path))
    cur = shingle_set(body_of(path)[1])
    window = eps[max(0, idx - TH["cross_window"]): idx]
    best, best_ep = 0.0, ""
    for old in window:
        r = containment(cur, shingle_set(body_of(old)[1]))
        if r > best:
            best, best_ep = r, old.name
    return best, best_ep


def sentence_dupes(body: str, min_len: int = 8):
    """单句复读：同一句话（去标点后 ≥8 字）出现 ≥N 次。"""
    sents = [c for c in (content_only(s) for s in re.split(r"[。！？\n]", body)) if len(c) >= min_len]
    dup = [(s, c) for s, c in Counter(sents).items() if c >= TH["sent_dup_fail"]]
    return sorted(dup, key=lambda t: -t[1])[:5]


def dash_count(text: str) -> int:
    return text.count(DASH)


def quote_balance_scan(text: str):
    """跨行引号配平扫描，返回不平衡的行号列表。

    支持跨行对白/规则条文（如「一、闭目。\\n二、…\\n三、走到出声的地方。」）——
    逐行计数会把这类合法写法误判为"单边引号"。ASCII 引号另行按奇偶判定。
    """
    bad, depth = [], 0
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        for ch in line:
            if ch in (Q_OPEN, C_OPEN):
                depth += 1
            elif ch in (Q_CLOSE, C_CLOSE):
                depth -= 1
                if depth < 0:
                    bad.append(i)
                    depth = 0
        if line.count(Q_ASCII) % 2 == 1:
            bad.append(i)
    if depth > 0:
        bad.append(len(lines))
    return sorted(set(bad))


def quote_census(text: str) -> dict:
    lines = text.splitlines()
    unpaired = quote_balance_scan(text)
    return {
        "cn_open": text.count(Q_OPEN),
        "cn_close": text.count(Q_CLOSE),
        "ascii": text.count(Q_ASCII),
        "corner": text.count(C_OPEN) + text.count(C_CLOSE),
        "doubled_ascii": len(re.findall(re.escape(Q_ASCII) + re.escape(Q_ASCII), text)),
        "doubled_cn": len(re.findall(re.escape(Q_CLOSE) + re.escape(Q_CLOSE), text)),
        "unpaired_lines": unpaired,
        "style": quote_style(text),
    }


def quote_style(text: str) -> str:
    cn = text.count(Q_OPEN) + text.count(Q_CLOSE)
    ascii_ = text.count(Q_ASCII)
    corner = text.count(C_OPEN) + text.count(C_CLOSE)
    if ascii_ == 0 and corner == 0:
        return "中文弯引号" if cn else "无对话引号"
    if ascii_ >= cn and ascii_ >= corner:
        return "ASCII直引号"
    if corner >= cn:
        return "直角引号"
    return "混用"


def meta_hits(body: str):
    fail, warn = [], []
    for i, line in enumerate(body.splitlines(), 1):
        masked = PANEL.sub("〘〙", line)      # 【R51：…】属合法体例，屏蔽后再查编号
        for pat, label in META_FAIL:
            if re.search(pat, masked):
                fail.append((i, label, line.strip()[:70]))
        for pat, label in META_WARN:
            if re.search(pat, masked):
                warn.append((i, label, line.strip()[:70]))
    return fail, warn


def rule_id_in_dialogue(body: str):
    """规则编号出现在对话里（角色说出 R/V 编号）= FAIL。"""
    out = []
    for i, line in enumerate(body.splitlines(), 1):
        for m in re.finditer(r"[%s%s]\s*([RVD]\d{1,2})" % (Q_OPEN, C_OPEN), line):
            out.append((i, m.group(1), line.strip()[:70]))
    return out


# ---------------------------------------------------------------- 台账解析

def load_ledger(root):
    """解析 00-进度清单.md 的**集数进度表**，返回 {集号: {claimed, raw}}。

    实战中表体有两种写法，必须都认：
      | ep33 | 脱身 | 已验收 | 1505 | …     （多数书）
      | 01   | 醒来，就是第一条规则 | 已验收 | 2025 | …（荒野规则）
    只认"表头含 集/标题/状态"的那张表，避免把里程碑等其它数字表误当集数表。
    """
    p = Path(root) / "00-进度清单.md"
    rows = {}
    if not p.exists():
        return rows
    lines = read_text(p).splitlines()
    in_table = False
    col_chars = None
    for line in lines:
        s = line.strip()
        if not s.startswith("|"):
            in_table = False
            col_chars = None
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):      # 分隔行
            continue
        if not in_table:
            if ("标题" in s or "状态" in s) and ("集" in s):
                in_table = True
                col_chars = None
                for i, c in enumerate(cells):
                    if "字数" in c:
                        col_chars = i
                continue
            continue
        first = re.sub(r"^ep\s*", "", cells[0], flags=re.I)
        if not re.fullmatch(r"\d{1,3}", first):
            continue
        no = int(first)
        claimed = None
        if col_chars is not None and col_chars < len(cells):
            m = re.fullmatch(r"(\d{3,5})", cells[col_chars])
            if m:
                claimed = int(m.group(1))
        if claimed is None:
            for c in cells[1:]:
                if re.fullmatch(r"\d{3,5}", c):
                    claimed = int(c)
                    break
        rows[no] = {"claimed": claimed, "raw": s[:120]}
    return rows


def load_foreshadow_ids(root):
    """解析 伏笔活表-*.md 里已登记的编号。

    编号单元格可能带后缀注释（例：`V9（新）`、`V10（新）`），必须容忍。
    """
    ids, path = set(), None
    for p in Path(root).glob("伏笔活表-*.md"):
        path = p
        for line in read_text(p).splitlines():
            m = re.match(r"^\|\s*([VCDF]\d{1,2})[^|]*\|", line)
            if m:
                ids.add(m.group(1))
    return ids, path


def load_outline_files(root):
    """返回 (存在的大纲文件, 疑似为副本的大纲文件)。"""
    real, sus = [], []
    for p in Path(root).glob("*幕*大纲*.md"):
        head = read_text(p).splitlines()[:1]
        title = head[0] if head else ""
        if p.name.startswith("幕级大纲-待规划") and "第一幕" in title:
            sus.append(p.name)
        else:
            real.append(p.name)
    return real, sus


def detect_word_range(root):
    """从宪法读取单集字数下限/上限；失败则用默认 2000-3000。

    注意破折号写法在实战中有多种：`–`（U+2013，多数书）、`-`、`—`、`~`、`至`、`～`。
    """
    dash = r"[\-\u2013\u2014\u2212~\uff5e\u81f3]"
    pats = [r"单集[^\n]{0,24}?(\d{3,4})\s*" + dash + r"\s*(\d{3,4})",
            r"单集篇幅[^\n]{0,24}?(\d{3,4})\s*" + dash + r"\s*(\d{3,4})",
            r"(\d{3,4})\s*" + dash + r"\s*(\d{3,4})\s*字"]
    for p in Path(root).glob("宪法-*.md"):
        t = read_text(p)
        for pat in pats:
            m = re.search(pat, t)
            if m:
                return int(m.group(1)), int(m.group(2)), p.name
    return 2000, 3000, "默认值(宪法未识别)"


def load_characters(root):
    """从 02-人物档案 提取候选人物名（表头/标题），供幽灵条目比对。"""
    names = set()
    for p in Path(root).glob("02-人物档案-*.md"):
        for line in read_text(p).splitlines():
            m = re.match(r"^#{2,4}\s*([\u4e00-\u9fa5]{2,4})", line)
            if m and m.group(1) not in STOPWORDS:
                names.add(m.group(1))
            m = re.match(r"^\|\s*([\u4e00-\u9fa5]{2,4})\s*\|", line)
            if m and m.group(1) not in STOPWORDS:
                names.add(m.group(1))
    return sorted(names)


def count_in_episodes(root, needle):
    n = 0
    for p in episode_files(root):
        n += read_text(p).count(needle)
        if n:
            return n
    return n


def book_quote_style(root):
    """全书主导引号体例（按 episode 数投票）。"""
    tally = {}
    for p in episode_files(root):
        s = quote_style(p.read_text(encoding="utf-8", errors="replace"))
        tally[s] = tally.get(s, 0) + 1
    if not tally:
        return "无"
    return max(tally.items(), key=lambda t: t[1])[0]


def acceptance_files(root):
    d = Path(root) / "验收存档"
    return sorted(d.glob("ep*-验收.md")) if d.is_dir() else []


def agents_progress_empty(root):
    p = Path(root) / "AGENTS.md"
    if not p.exists():
        return None
    t = read_text(p)
    m = re.search(r"##\s*四、当前进度(.*)$", t, re.S)
    if not m:
        return None
    seg = m.group(1)
    has_done = bool(re.search(r"已完成[：:]\s*\S", seg))
    has_next = bool(re.search(r"下一步[：:]\s*\S", seg))
    return not (has_done or has_next)

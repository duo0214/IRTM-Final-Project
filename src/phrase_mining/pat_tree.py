"""B's PAT-tree (Patricia trie over every semi-infinite string of the corpus).

結構說明
--------
* 語料中每個位置 (doc, i) 都代表一個 semi-infinite string：text[doc][i:]。
  PAT-tree 就是把所有這些後綴插進一棵「壓縮過的 trie」(Patricia trie)。
* 邊不存字串本身，只存指回原文的指標 (doc, start, length)，所以額外記憶體只跟
  節點數有關，不會複製文本。
* 只有一個子節點、且沒有後綴在此結束的節點會被壓縮掉；因此每個內部節點都是
  「至少兩個後綴在這裡分岔」的地方，節點數 ≤ 2N。
* 後綴在文件結尾就結束，不接到下一份文件，因此查詢結果不可能跨文件。
  每個後綴的起點記在它結束的節點 `ends` 裡（葉節點，或剛好在內部節點結束的短後綴）。

查詢
----
從根往下比對 phrase：若途中失配就是查無結果；若 phrase 用完（停在節點上或
邊的中間），那個節點底下所有後綴的起點就是全部命中位置——包含重疊命中。
查詢只走 len(phrase) 個字，再加上收集 tf 個命中位置，與語料大小無關。
"""


class _Node:
    __slots__ = ('doc', 'start', 'length', 'children', 'ends')

    def __init__(self, doc, start, length):
        # 進入這個節點的邊標籤 = texts[doc][start:start+length]
        self.doc = doc
        self.start = start
        self.length = length
        self.children = {}   # 下一個字元 -> _Node
        self.ends = []        # 在此節點結束的後綴：(doc_index, offset)


class PATTreeIndex:
    backend = 'pat_tree'

    def __init__(self, documents):
        self.doc_ids = [d['doc_id'] for d in documents]
        self.texts = [d['text'] for d in documents]
        self.root = _Node(0, 0, 0)
        self.node_count = 1
        for doc_index, text in enumerate(self.texts):
            for offset in range(len(text)):
                self._insert(doc_index, offset)

    # ------------------------------------------------------------------ build
    def _insert(self, d, i):
        """把後綴 texts[d][i:] 插入樹中。"""
        text = self.texts[d]
        n = len(text)
        node = self.root
        pos = i                                   # 後綴中下一個要比對的字元位置
        while True:
            if pos == n:                          # 後綴剛好在這個節點結束
                node.ends.append((d, i))
                return
            child = node.children.get(text[pos])
            if child is None:                     # 新分支：直接掛一個葉節點
                leaf = _Node(d, pos, n - pos)
                leaf.ends.append((d, i))
                node.children[text[pos]] = leaf
                self.node_count += 1
                return
            label = self.texts[child.doc]
            ls, ll = child.start, child.length
            # 先用切片整段比對（C 層級，快）；不同再逐字找失配點
            remaining = n - pos
            if remaining >= ll and text[pos:pos + ll] == label[ls:ls + ll]:
                pos += ll
                node = child
                continue
            k = 1                                 # 第 0 個字已由 children 的 key 確認相同
            limit = min(ll, remaining)
            while k < limit and text[pos + k] == label[ls + k]:
                k += 1
            # 在邊的第 k 個字切開：node -> mid -> child
            mid = _Node(child.doc, ls, k)
            node.children[text[pos]] = mid
            child.start += k
            child.length -= k
            mid.children[label[child.start]] = child
            self.node_count += 1
            pos += k
            node = mid                            # 下一輪：後綴在 mid 結束或在 mid 開新葉

    # ----------------------------------------------------------------- lookup
    def _locate(self, phrase):
        """回傳 phrase 走完後所在子樹的根；查無則回傳 None。"""
        node = self.root
        pos, m = 0, len(phrase)
        while pos < m:
            child = node.children.get(phrase[pos])
            if child is None:
                return None
            label = self.texts[child.doc]
            take = min(child.length, m - pos)
            if phrase[pos:pos + take] != label[child.start:child.start + take]:
                return None
            pos += take
            node = child
        return node

    def _collect(self, node):
        """收集子樹內所有後綴起點。用迴圈避免深樹遞迴過深。"""
        out = []
        stack = [node]
        while stack:
            current = stack.pop()
            out.extend(current.ends)
            stack.extend(current.children.values())
        return out

    def lookup(self, phrase):
        """與 ReferencePhraseIndex.lookup 相同格式；位置為原文 Unicode code point。"""
        if not phrase:
            raise ValueError('phrase cannot be blank')
        node = self._locate(phrase)
        hits = self._collect(node) if node is not None else []
        by_doc = {}
        for d, offset in hits:
            by_doc.setdefault(d, []).append(offset)
        length = len(phrase)
        matches = []
        for d in sorted(by_doc):                  # 與掃描版相同：依語料順序
            offsets = sorted(by_doc[d])
            matches.append({'doc_id': self.doc_ids[d], 'tf': len(offsets),
                            'positions': [{'start': s, 'end': s + length} for s in offsets]})
        return {'phrase': phrase, 'frequency': sum(m['tf'] for m in matches),
                'df': len(matches), 'documents': matches, 'backend': self.backend}

    # ------------------------------------------------------- phrase mining API
    def _subtree_counts(self):
        """每個節點底下有幾個後綴（= 該節點字串在語料出現次數），只算一次後快取。"""
        if getattr(self, '_counts', None) is None:
            counts, order, stack = {}, [], [self.root]
            while stack:
                node = stack.pop()
                order.append(node)
                stack.extend(node.children.values())
            for node in reversed(order):          # 子節點一定比父節點先算到
                counts[id(node)] = len(node.ends) + sum(counts[id(c)] for c in node.children.values())
            self._counts = counts
        return self._counts

    def count(self, phrase):
        """phrase 在語料出現的總次數（含重疊），不必展開所有位置。"""
        node = self._locate(phrase) if phrase else None
        return self._subtree_counts()[id(node)] if node is not None else 0

    def repeated_strings(self, min_freq=2, min_len=2, max_len=10):
        """列出 PAT-tree 內部節點代表的重複字串（right-maximal repeats）。

        節點字串 = 根到節點路徑上的字。內部節點代表「後面接的字不只一種」，
        停在邊中間的字串後面只會接同一個字，所以只看節點即可。
        產出 (phrase, frequency, right_contexts, occurrences)：
        right_contexts 是 {下一個字: 次數}，文件結尾記為 None。
        """
        counts = self._subtree_counts()
        stack = [(child, '') for child in self.root.children.values()]
        while stack:
            node, prefix = stack.pop()
            freq = counts[id(node)]
            if freq < min_freq:                   # 子樹只會更少，整枝剪掉
                continue
            phrase = prefix + self.texts[node.doc][node.start:node.start + node.length]
            if len(phrase) > max_len:
                continue
            if len(phrase) >= min_len:
                right = {ch: counts[id(c)] for ch, c in node.children.items()}
                if node.ends:
                    right[None] = len(node.ends)
                yield phrase, freq, right, self._collect(node)
            stack.extend((c, phrase) for c in node.children.values())

    def stats(self):
        return {'documents': len(self.texts), 'suffixes': sum(len(t) for t in self.texts),
                'nodes': self.node_count}

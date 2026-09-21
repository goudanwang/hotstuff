# HotStuff 共识实验室

最小可运行的 HotStuff 教学型区块链：Python + FastAPI + 原生 HTML/JavaScript，**单进程模拟 4 个逻辑节点**。无数据库、Docker、外部前端资源或构建工具。

## 运行

需要 Python 3.10+。在本项目根目录执行：

```bash
pip install -r requirements.txt
python backend/main.py
```

打开 **http://localhost:8000**。初始暂停，可直接点击 `Next Step`，或点击 `Start` 每 0.8 秒自动执行一个事件。退出使用 Ctrl+C。所有状态仅在内存中，重启或 Reset 清空。

可选隔离环境：`python -m venv .venv`，激活后运行上述命令。不使用多个 Uvicorn worker；一个进程对应一个共享实验，多个浏览器操作的是同一实验。

## 四个验收演示

### Demo 1：协议流程

1. 点击 `Reset`，初始 View 1、Leader N1，B0 为已提交创世块。
2. 每点一次 `Next Step` 推进一个事件：N1 proposal B1，N1/N2/N3/N4 依次投票，形成 QC(B1)，进入 View 2。
3. 继续到 QC(B2)：HighQC=B2，LockedQC=B1，B1 尚未提交。
4. 继续到 QC(B3)：形成三个连续 View 的已认证区块 B1 ← B2 ← B3，提交 B1。

无故障时每 View 为 7 步（1 proposal + 4 vote + 1 QC + 1 view change）。第 20 步形成 QC(B3) 并提交 B1。QC 形成和对应节点的 lock/commit 更新是同一个原子事件，事件日志分别展示 QC 和 Commit。

### Demo 2：转账完整流程

1. `Reset`，保留表单默认值 Alice → Bob，Amount=10，点击 `Submit`。
2. 看到 Tx1 进入 Mempool，点击 `Start`，或手动单步到第 20 步。
3. Tx1 被打包到 B1。QC(B1) 本身不会改变余额，只有 B1 Commit 才执行交易。
4. 四个节点都显示 Alice=90、Bob=110、Charlie=100，Mempool 清空，交易执行结果显示 Committed。

空块持续产生以推进三链提交。每块最多打包 5 笔交易。金额为正整数，提交时验证输入；余额在提交区块执行交易时检查，余额不足会产生一致的失败回执、不会扣款。交易失败不代表区块共识失败。

### Demo 3：Leader Crash

1. `Reset` 后点击 `Crash Leader`：N1 离线、状态冻结。
2. 点击 `Start` 或连续 `Next Step`。N1 不发 proposal，经过 3 个 timeout tick 后进入 View 2。
3. N2 成为 Leader；N2/N3/N4 三票形成 QC，继续共识。以后轮到 N1 时会再次超时跳过。
4. 点击 `Recover Nodes`：恢复节点从在线节点同步区块、QC、已提交链和账户状态，同时清除不投票故障。

也可在 proposal 后让 Leader 崩溃：即使收到了票，离线 Leader 也不会广播 QC。未认证分支不会提交，其中的交易仍留在 Mempool，可由新 Leader 重新打包。

### Demo 4：Byzantine Replica

1. `Reset`，下拉框选择 `Node 4 不投票`，点击 `Start`。
2. N4 跳过投票，N1/N2/N3 仍形成 3 票 QC。N4 仍接收已认证区块并执行 Commit，四个节点状态一致。
3. 轮到 N4 当 Leader 时仍正常提案，但不投自己的票，其余三个节点仍可形成 QC。

此故障只模拟“扣留投票”，不模拟伪造、双签或 equivocation。同时开启一个崩溃和另一个不投票节点时，可能只剩两票：系统应持续 timeout，不能形成 QC；恢复后继续。

## 页面

- 节点卡片：本地 View、Leader/Replica、HighQC、LockedQC、最新块、最新提交块、账户余额及故障状态。崩溃节点显示冻结前的本地 View。
- 协议控制：Start、Pause、Next Step、Reset、Crash Leader、Recover Nodes。不自动开始执行，提交交易也不会自动启动。
- 区块：按创建顺序列出所有提案，明确标注各自 parent，因此故障产生的分支也可观察。下方单独显示真正的已提交链。
- 区块详情：ID、Parent、View、Leader、Transactions、父块 QC voters、本块 QC voters、Committed/Uncommitted。
- Mempool：尚未在提交链中执行的交易，包括已提案但尚未提交的交易。
- 日志：最近 100 条可见，服务端保留最近 400 条，新事件在上方。

## 核心状态转换

`leader(view) = ((view - 1) % 4) + 1`，`n=4`、`f=1`、`quorum=2f+1=3`。

```text
propose
  → 每个节点分别 vote（包含 Leader 自己）
  → 收到至少 3 个不同节点的投票
  → Leader 广播 QC
  → 在线节点更新 HighQC / LockedQC / Commit
  → View + 1 → 下一 Leader

Leader 离线 / 不足 3 票 / Leader 未能广播 QC
  → timeout tick × 3 → View + 1
```

1. 新 Leader 通过模拟 NEW-VIEW 交换取得在线节点最高 HighQC，在其认证区块上扩展。
2. `Block.qc` 是**父块的证书**，不是本块证书。本块被投票认证后，其 QC 记录在证书表中；UI 分别展示二者。
3. 节点每 View 最多投一票。验证父 QC 和 proposer，并要求提案扩展本地锁定区块，或其 justification QC 的 View 严格高于 LockedQC。
4. 收到 QC(C) 后，HighQC 更新为 C；C 的父块 B 已由 C.qc 认证，LockedQC 可前进到 QC(B)。
5. A ← B ← C 三块均已认证且 View 连续时，提交 A 及其尚未提交祖先，并按链顺序执行交易。跳过 View 会推迟提交，直到再次出现连续三链。
6. 每个节点独立维护余额和回执，按交易 ID 防止重复执行；提案不修改余额。新 Leader 打包时排除父链中已有的交易，孤块交易保留在池中。

## 教学型简化与边界

- 这不是论文的完整实现，也不宣称具备生产级 BFT 安全性。投票与 QC 只有节点 ID，无签名、哈希、身份验证或防篡改；B0 的 QC 为预置信任根。
- 内部队列顺序、可靠地传递消息。API 用简单 HTTP，页面每 400ms 轮询状态；不是实际 P2P 网络，无随机延迟、重排序或网络分区。
- 一个中心化逻辑 pacemaker 协調 View，NEW-VIEW 直接读取正常节点的 HighQC；不实现 timeout certificate、独立节点时钟或完整的跨 View 消息协议。
- Timeout 是**逻辑时间**：一次 Next Step 等于一个 tick，自动运行时一次 tick 约为 0.8 秒。暂停会冻结协议及超时。仅在本轮无法得到 QC 后排入倒计时，不模拟墙钟竞态。
- QC 达到 3 票即可成立。队列中本轮四个 vote 事件先处理完，再广播 QC；正常场景可能显示 4 个 voters，单故障场景为 3 个。
- Commit 在收到第三个块的 QC 时处理；这里采用连续 View 的保守三链规则，未实现流水线优化或其他 HotStuff 变体。
- 恢复节点通过可信同伴快照追赶，不验证状态同步证明。崩溃期间未丢失内存，重启整个进程则重置所有状态。
- 共享交易池和只读交易/区块对象用于简化传输；每个节点的区块索引、QC 指针、投票状态、提交链、余额和执行回执独立保存。
- 不限制长期生成的区块总量；课堂实验结束可 Reset。服务默认仅监听 127.0.0.1，无用户登录，不适合公开部署。

## 文件结构

```text
backend/
  main.py          FastAPI、HTTP 接口、自动执行循环
  models.py        Block / QC / Transaction
  node.py          节点状态、安全投票、锁与三链提交
  hotstuff.py      内部事件队列、View、提案、投票、QC、故障
  blockchain.py   转账状态机与幂等执行回执
frontend/
  index.html
  app.js
  style.css
tests/
  test_hotstuff.py 协议、转账、故障与恢复测试
requirements.txt
README.md
```

## 验证与接口

无需额外测试依赖：

```bash
python -m unittest discover -s tests -v
```

覆盖三链提交、提交前不改余额、交易去重与批量打包、故障后的重新打包、Leader timeout、恢复追赶、单节点不投票、双故障无法形成 QC、锁及单 View 单次投票、View 间隔、余额不足和 Reset。

服务启动后可访问 http://localhost:8000/docs 查看接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/state` | 所有节点、区块、余额、交易和事件 |
| POST | `/api/control/{action}` | `start` / `pause` / `step` / `reset` / `crash-leader` / `recover` |
| POST | `/api/transactions` | `{"sender":"Alice","receiver":"Bob","amount":10}` |
| POST | `/api/byzantine` | `{"node_id":4}`；`null` 清除不投票故障 |

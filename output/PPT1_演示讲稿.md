# PPT1：HotStuff 共识协议讲解与演示

配套 `PPT1_HotStuff_Protocol_Final.pptx`，建议 25–30 分钟。每页讲解也已写入 PPT 演讲者备注。

## 01 HotStuff

开场：这一部分研究多个副本怎样对提案的顺序取得一致。B0、B1、B2 是带父指针的协议提案节点，载荷留空。全程只观察 View、Proposal、Vote、QC、Lock 与 Commit。建议用时 25–30 分钟，其中现场演示约 8 分钟。PPT 中保留英文按钮名，方便在英文 Dashboard 中定位。

## 02 协议目标与运行假设

先区分两个目标。Safety 是正确副本不会提交冲突的历史。Liveness 是满足网络稳定和正确 Leader 条件后能继续做出决定。HotStuff 的理论模型使用固定成员集合、身份认证和部分同步网络，允许最多 f 个拜占庭节点。部分同步指未知时间 GST 之后消息延迟存在上界，并不承诺网络永远延迟很小。本 Demo 只模拟确定性消息队列，不能用它证明任意网络环境下的安全性。

## 03 为什么需要 3 票

在 n=3f+1 的设定中取 q=2f+1。这里 n=4、f=1，因此 q=3。任意两组三人集合至少重叠两人，其中至少一人正确。演示两个集合 {N1,N2,N3} 与 {N2,N3,N4}，交集为 N2、N3。正确节点同一 View 只投一次票，所以同一 View 的冲突提案无法都收集到三票。提醒学生：跨 View 还需要锁定规则，单靠交集不够。

## 04 HotStuff 的关键设计

这一页给出后面观察的主线。QC 把一组投票变成可传递的证据。HighQC 帮助新 Leader 确定从哪里扩展，LockedQC 约束副本接下来接受什么。Chained HotStuff 把多阶段认证展开到连续提案中，使后继提案推动祖先达到最终性。Pacemaker 负责换届和推进，投票与锁定规则负责安全。线性通信和乐观响应性将在后面的性能原理页单独解释，不能从 Demo 的 0.8 秒动画节奏推断协议性能。

## 05 状态字段与协议含义

这里的 block 只表示协议中的提案节点，不讨论载荷或应用。View 是逻辑轮次。角色由 View 决定。HighQC 是本地已知的最高 View 证书。LockedQC 是安全投票规则所参考的锁定证书。Latest block 可能只是刚收到的提案。Commit block 则是本地最新已决定的祖先。不要将 Latest、Certified 和 Committed 混为一谈。

## 06 演示 0：初始状态

打开 http://localhost:8000。点击 Reset，确认 PAUSED · STEP 0。不要提交任何内容。指出左上方 View=1，N1 卡片标注 Leader，其余是 Replica。四个节点的 HighQC、LockedQC、Commit block 均为 B0。Start 自动推进，Pause 停止，Next Step 会暂停自动运行并恰好执行一个事件。介绍时只展示页面上半部与 Event log，后续全程按这两个区域观察。

## 07 演示 1：Leader 发出 Proposal

点击一次 Next Step。日志出现 Leader N1 proposes B1。N1 在 HighQC 认证的 B0 上创建 B1，并携带 QC(B0)。说明 B1.parent_id=B0，B1.qc=QC(B0)。提案中携带的是父节点证书，本轮还没有 QC(B1)。所有在线副本可以看到 B1，所以 Latest block 会变成 B1，但这并不表示它已认证或提交。

## 08 Vote：副本怎样决定是否投票

从 STEP 1 继续四次 Next Step，依次看到 N1、N2、N3、N4 的 vote。Leader 也可以投票。投票前检查当前 View、本轮指定 Leader、已知且有效的父 QC，以及本 View 尚未投过票。接着应用安全条件：提案扩展锁定节点，或者提案携带的 QC 的 View 严格高于本地 LockedQC。等号不够。后面的例子会展开这两个分支。当前 Demo 不主动制造恶意分叉，因此这条规则主要通过代码和案例讲解。

## 09 演示 2：投票形成 QC

累计单步到 STEP 6。如果上一页停在 STEP 5，只需再点一次。STEP 4 已经收到第三票，达到门槛。队列先处理 N4 的已排队投票，再在 STEP 6 广播 QC，因此正常场景证书列出四名 voters。三票仍是成立门槛，并非四票。解释 QC(B1) 只是认证 B1，不代表最终提交。HighQC 更新为 B1，锁与提交仍停在 B0。故障演示会明确看到恰好三名 voters。

## 10 View change：新 Leader 延续已知进度

STEP 7 进入 View 2，此时 Leader 从 N1 变成 N2。STEP 8 N2 基于 QC(B1) 提出 B2。当前实现的新 Leader 直接读取在线节点的 HighQC，挑选最高值。这等价于教学层面的 NEW-VIEW 信息交换，不是真实网络中的完整换届实现。角色切换不清空证书或锁。View 是逻辑轮次，即使没有成功提案，也可以因 timeout 增长。

## 11 演示 3：HighQC 与 LockedQC 分离

停在 STEP 13。四个节点都看到 QC(B2)。HighQC=B2 表示目前知道的最新认证进度。LockedQC=B1 表示后续投票要参考 B1 所在分支。B2 的提案中已携带 QC(B1)，因此接收 QC(B2) 时可以将父节点 B1 作为锁定依据。Commit block 仍为 B0。强调 HighQC 和 LockedQC 虽然都是 QC，但职责不同，数值不必相等。这里是当前 Demo 在收到 QC 时进行原子更新的时机。

## 12 锁定规则：什么提案还能获得投票

设本地 LockedQC 为 QC(B1)，其 View=1。第一行，提案沿 B1 分支扩展，因此可以通过安全条件。第二行，提案离开 B1 分支，携带的证书 View 不高于 1，因此拒绝。第三行，提案不扩展本地锁，但携带一个有效且 View=2 的证书，可以通过更高 QC 的分支。这里仅讨论 safeNode 条件，仍需通过 View、Leader、证书和单次投票检查。更高 QC 必须真实有效，不能用更大的数字伪造。

## 13 多阶段认证与 Chained HotStuff

Basic HotStuff 用 prepare、pre-commit、commit 三轮认证，再用 decide 通知最终决定。Chained HotStuff 将阶段推进分布到相互链接的提案上。对于 B1，后继 B2、B3 的认证逐步增加其确认深度。表格用于解释当前 Demo 的对应关系，不能把 Basic 的消息阶段与 Demo 的独立 View 生硬等同。Demo 收到本块 QC 就立即广播和更新状态，原论文的链式伪代码还有具体消息触发位置与流水线细节。

## 14 演示 4：三链触发 Commit

停在 STEP 20，日志同时出现 QC(B3) formed 和 B1 committed。B1、B2、B3 直接相连，View 分别是 1、2、3，且三者都已认证。提交最老的 B1。当前最新提案 B3 尚未提交，B2 也尚未提交。本实现要求连续 View，跳过 View 会推迟提交，直到形成新的连续三链。Commit 是对已决定历史的扩展，不能把它解释为最近收到一份 QC。

## 15 正常路径的精确停点

这是一张可以直接照着操作的讲课表。每次从 Reset 开始，始终使用 Next Step，不要混用自动运行，否则屏幕步数可能越过目标。正常一轮是七步：一次提案、四个投票、一次 QC、一次换届。STEP 20 是第三轮 QC，STEP 21 才进入 View 4。B0 是预先提交的起点，因此第一次新提交发生在 B1。让学生先预测 STEP 13 的三个字段，再点击验证。

## 16 安全性原理：交集、锁与提交证据

把前面的部件连接起来。第一，法定人数交集加同一 View 的单次投票，约束同轮冲突认证。第二，锁定规则把约束带到后续 View，仅仅轮次更大不能自动解除约束。第三，多阶段证据让足够多正确副本进入受约束的状态，从而支持不可冲突的最终决定。这里给出机制直觉，不是在证明教学代码能抵抗所有恶意攻击。完整安全性论证需要原论文的身份认证、消息规则和模型假设。

## 17 Timeout 与 Pacemaker

原理上，安全规则不能保证当前 Leader 一定发消息，因此需要推进机制。Timeout 用来怀疑当前 View 无法顺利推进，不是证明 Leader 恶意。Pacemaker 帮助正确副本进入适合推进的 View，并促使新 Leader 取得 QC 信息。教学实现用单一协调器统一推进在线副本的 View，并用三个逻辑 tick 展示等待过程。暂停时 tick 不动。不存在真实独立节点时钟、超时证书或网络分区模型。

## 18 演示 5：Leader 崩溃后继续认证

从 Reset 开始点击 Crash Leader，此操作不增加 STEP。STEP 1 观察 N1 没有提案。STEP 2、3、4 显示倒计时 3、2、1。STEP 5 进入 View 2，Leader N2。STEP 6 提出 B1，因为上一 View 没有创建提案，编号仍是 B1。STEP 7 N1 跳过投票，STEP 8–10 是 N2/N3/N4 投票，STEP 11 形成 QC(B1)，voters 为 N2、N3、N4。若继续到 STEP 25，View 2、3、4 的连续三链会提交 B1。点击 Recover Nodes，同步落后节点并清除故障。

## 19 演示 6：一个副本不投票

Reset 后在下拉框选择 Node 4 withholds votes。STEP 1 N1 提案，STEP 2–4 N1/N2/N3 投票，STEP 5 日志显示 N4 skips vote，STEP 6 形成三票 QC。让学生比较上一段正常路径的四票证书。N4 仍在线接收 QC，因此它的 HighQC 也前进。它只扣留投票，轮到它担任 Leader 时仍然发出提案。这个实验不包含双签或恶意分叉，不应声称已经测试完整拜占庭攻击模型。

## 20 故障容忍的边界

先让学生判断少一票和少两票的区别。正常情况下最多允许 f=1 个故障节点，剩余三个节点仍可形成 quorum。若既让 N1 崩溃，又让 N4 扣留投票，N2/N3 只有两票。N2 当 Leader 时会收到两票并等待超时，不应凭空形成 QC。可选操作：Reset，Crash Leader，选择 Node 4 withholds votes。到 STEP 6 是 N2 的提案，STEP 10 处理完投票，STEP 11–13 倒计时，STEP 14 换到 View 3，始终没有 QC(B1)。点击 Recover Nodes 后继续。两个故障已超过 f=1，不承诺活性。

## 21 线性通信与乐观响应性

线性通信的条件必须讲清楚。原版 HotStuff 通过 Leader 收集投票和紧凑阈值签名 QC，使阶段推进以及成功的 Leader 换届使用线性数量的认证材料。只数消息条数不足以推导总通信量，广播长 voters 列表仍有体积成本。乐观响应性指网络稳定且由正确 Leader 推进后，进度受实际收到足够响应的速度驱动，而不必在每一步等最大网络延迟。Timeout 仍然需要。当前 Demo 使用 ID 列表，无阈值签名，中心化 pacemaker 和固定播放节奏都不用于性能测量。

## 22 当前 Demo 与原协议的边界

这页帮助回答实现与论文是否完全相同。教学版保留 View、Leader、Proposal、Vote、HighQC、LockedQC、父指针和三链提交。签名只是节点 ID。NEW-VIEW 由直接读取在线节点的 HighQC 模拟。统一协调器与逻辑 tick 替代真正 pacemaker。三链规则额外要求连续 View。节点恢复通过可信同伴状态复制。实验没有涵盖任意 Byzantine 行为或网络分区，因此安全性和活性结论只能在这些模拟约束下观察。

## 23 现场演示速查

这是讲课时可以停留的操作页。每个场景都先 Reset，避免上一段故障影响下一段。第一段总共点 20 次，分别停在 1、6、13、20。第二段 Crash Leader 后停在 5 和 11，分别检查新 Leader 和新 QC，最后恢复。第三段 N4 不投票后停在 6，检查日志中 voters 为 N1、N2、N3。各场景按钮只改变控制或故障状态，不增加 STEP，只有 Next Step 或自动 tick 增加 STEP。现场网页沿用英文 Dashboard。

## 24 协议要点回顾

用问答收尾。问：为什么 QC(B1) 出现后 B1 没有立即提交？答：QC 是第一层认证，还需要后继形成提交所需的链式证据。问：新 Leader 是否从任意节点开始？答：依据 HighQC 选择扩展点，并受副本锁定规则约束。问：为什么一个节点不投票仍能继续？答：剩余三个节点达到 2f+1。问：为什么两个故障可能一直超时？答：可用票数不足 quorum。最后强调安全规则与活性推进的区别。参考原论文 §3–6 与项目 node.py、hotstuff.py。


## 参考

- [HotStuff 原论文](https://arxiv.org/html/1803.05069v6)
- [作者参考实现](https://github.com/hot-stuff/libhotstuff)
- 本项目 backend/node.py、backend/hotstuff.py 和 README.md

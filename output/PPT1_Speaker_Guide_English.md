# PPT1: HotStuff Protocol and Live Demo

Companion to `PPT1_HotStuff_Protocol_English.pptx`. Allow 25–30 minutes. These explanations also appear in the presentation speaker notes.

## 01 HotStuff

This session explains how replicas agree on the order of proposals. B0, B1 and B2 are protocol proposal nodes with parent pointers and empty payloads. Focus on View, Proposal, Vote, QC, Lock and Commit. Allow 25–30 minutes, including about eight minutes of live demonstration. The slide labels match the English dashboard controls.

## 02 Protocol Goals and Assumptions

Distinguish safety from liveness. Safety means that correct replicas do not commit conflicting histories. Liveness means that decisions eventually continue under the required network and leadership conditions. HotStuff assumes fixed membership, authenticated communication and partial synchrony, with at most f Byzantine replicas. Partial synchrony means that message delays have a bound after an unknown global stabilization time, GST. It does not mean that the network is always fast. This demo uses a deterministic message queue and cannot prove safety under arbitrary network behavior.

## 03 Why the Quorum Is Three

With n=3f+1, choose q=2f+1. Here n=4 and f=1, so q=3. Any two sets of three replicas overlap in at least two replicas, at least one of which must be correct. Compare {N1,N2,N3} with {N2,N3,N4}: the intersection is N2 and N3. A correct replica votes at most once per view, so two conflicting proposals in the same view cannot both gather three votes. Across different views, quorum intersection alone is insufficient. The locking rule carries the safety constraint forward.

## 04 HotStuff's Core Design

Use these mechanisms as the main thread of the lecture. A QC turns votes into evidence that later messages can carry. HighQC helps a new leader choose where to extend, while LockedQC constrains what each replica may accept. Chained HotStuff spreads certification across linked proposals, so successors help ancestors reach finality. The pacemaker coordinates progress and view changes. Voting and locking enforce safety. Linear communication and optimistic responsiveness are explained later. The demo's fixed 0.8-second playback interval is not a protocol performance measurement.

## 05 Node State and Its Meaning

Here, a block is only a proposal node in the consensus protocol. We do not discuss payloads or applications. View is the logical round, and the view determines the leader. HighQC is the certificate with the highest view known locally. LockedQC is the certificate used by the safety predicate. Latest block may be a proposal that just arrived. Commit block is the newest ancestor that the replica has already decided. Keep proposed, certified and committed states distinct.

## 06 Demo 0: Initial State

Open http://localhost:8000 and click Reset. Confirm PAUSED and STEP 0. Do not submit any payload. Point out View 1, N1 as Leader and the other nodes as Replica. All four replicas show B0 for HighQC, LockedQC and Commit block. Start runs automatically. Pause stops playback. Next Step pauses automatic execution and advances exactly one event. During this protocol session, focus on the upper dashboard and Event log.

## 07 Demo 1: The Leader Proposes

Click Next Step once. The log shows Leader N1 proposes B1. N1 extends B0, the node certified by its HighQC, and includes QC(B0). Explain that B1.parent_id is B0 and B1.qc is QC(B0). A proposal carries its parent's certificate. QC(B1) does not yet exist. All live replicas receive B1, so Latest block becomes B1. Receipt of a proposal does not certify or commit it.

## 08 Vote: A Replica's Acceptance Rules

From STEP 1, click Next Step four times to observe votes from N1, N2, N3 and N4. The leader also votes. Before voting, a replica checks the current view, the designated leader, a known valid parent QC and whether it has already voted in this view. The proposal must then extend the locked node or carry a justification QC whose view is strictly higher than the local LockedQC view. Equality is insufficient for the second condition. The later example explains both branches. The demo does not actively create malicious forks, so use the rule and the examples to explain that case.

## 09 Demo 2: Votes Form a QC

Advance to cumulative STEP 6. If the previous slide left the demo at STEP 5, click only once. At STEP 4, the third vote already satisfies the threshold. The queue processes N4's already-scheduled vote before broadcasting the QC at STEP 6, so the normal certificate lists four voters. The threshold is still three. QC(B1) certifies B1 but does not finalize it. HighQC advances to B1, while the lock and commit remain at B0. The fault experiment later shows a QC with exactly three voters.

## 10 View Change Preserves Known Progress

STEP 7 enters View 2 and changes the leader from N1 to N2. At STEP 8, N2 uses QC(B1) to propose B2. In this implementation, the new leader directly reads the live replicas' HighQCs and selects the highest. This represents a simplified NEW-VIEW information exchange, not a complete network implementation. Changing roles does not erase certificates or locks. A view is a logical round and may increase after a timeout even if no proposal succeeded.

## 11 Demo 3: HighQC and LockedQC Diverge

Stop at STEP 13. All four replicas have received QC(B2). HighQC=B2 describes the latest certified progress they know. LockedQC=B1 constrains subsequent votes using B1's branch. The proposal B2 already carries QC(B1), so receiving QC(B2) provides the trigger for locking its parent B1 in this demo. Commit block remains B0. HighQC and LockedQC have different responsibilities and need not be equal. The teaching implementation updates them atomically when a QC arrives.

## 12 The Lock Rule: Which Proposals Can Pass?

Assume the local lock is QC(B1) from View 1. A proposal that extends B1 passes the first safety condition. A proposal on a conflicting branch with a QC view at most 1 fails. A proposal that does not extend the local lock but carries a valid QC from View 2 can pass the newer-QC condition. This table discusses only safeNode. The current-view, leader, certificate and one-vote checks still apply. The newer QC must be valid. A larger number by itself is not evidence.

## 13 Certification in Chained HotStuff

Basic HotStuff uses prepare, pre-commit and commit certification phases, followed by a decide notification. Chained HotStuff distributes phase progress across linked proposals. For B1, certification of its successors B2 and B3 increases the depth of evidence supporting it. The table explains the correspondence in this classroom implementation. Do not equate Basic HotStuff message phases literally with the demo's separate views. The demo broadcasts a completed QC and updates state immediately. The paper's chained pseudocode also specifies its own message triggers and pipeline details.

## 14 Demo 4: The Three-Chain Commit

At STEP 20, the log shows both QC(B3) formed and B1 committed. B1, B2 and B3 are directly linked, their views are 1, 2 and 3, and all three have certificates. The oldest node, B1, commits. B2 and the latest proposal B3 remain uncommitted. This implementation requires consecutive views. Skipping a view postpones commitment until a new consecutive three-chain appears. Commit extends the history of final decisions. It has a different meaning from simply receiving the latest QC.

## 15 Normal-Path Checkpoints

Use this table as the live demonstration script. Begin with Reset and use Next Step throughout. Mixing automatic playback with manual steps can skip a planned checkpoint. A normal view takes seven steps: one proposal, four vote events, one QC event and one view change. STEP 20 is the third QC event. STEP 21 enters View 4. B0 is committed at initialization, so B1 is the first newly committed node. Ask the audience to predict the three fields at STEP 13 before advancing to it.

## 16 Safety: Intersection, Locks and Commit Evidence

Connect the mechanisms. Quorum intersection and one vote per view constrain conflicting certificates within a view. The locking rule carries a constraint into later views. A larger view number alone does not remove it. Multiple certification stages establish constraints at enough correct replicas to support compatible final decisions. This is a mechanism-level explanation, not a proof that the teaching code resists every malicious attack. A full proof depends on the authentication, message rules and model assumptions in the paper.

## 17 Timeout and the Pacemaker

Safety rules cannot force a leader to send messages, so the protocol needs a progress mechanism. A timeout signals suspicion that the current view cannot progress. It does not prove malicious behavior. The pacemaker helps correct replicas converge on suitable views and helps a new leader obtain QC information. The demo uses one coordinator to advance all live replicas and three logical ticks to show the wait. Pausing freezes the ticks. Independent node clocks, timeout certificates and network partitions are outside this simulation.

## 18 Demo 5: Progress After a Leader Crash

Begin with Reset, then click Crash Leader. The fault button does not increase STEP. At STEP 1, N1 sends no proposal. STEPS 2, 3 and 4 show countdown values 3, 2 and 1. STEP 5 enters View 2 with leader N2. STEP 6 proposes B1: no proposal existed in the previous view, so the first proposal still has ID B1. STEP 7 skips N1's vote. STEPS 8–10 are the votes from N2, N3 and N4. STEP 11 forms QC(B1) with those three voters. Continuing to STEP 25 commits B1 through consecutive Views 2, 3 and 4. Recover Nodes catches up the offline replica and clears the faults.

## 19 Demo 6: One Replica Withholds Its Vote

After Reset, choose Node 4 withholds votes. N1 proposes at STEP 1. N1, N2 and N3 vote at STEPS 2–4. STEP 5 logs that N4 skips its vote. STEP 6 forms a QC with three voters. Compare it with the four-voter certificate in the normal path. N4 still receives QCs, so its HighQC advances as well. The fault only withholds votes. N4 still proposes when it becomes leader. This experiment does not include equivocation or malicious forks and does not test the full Byzantine attack model.

## 20 The Fault-Tolerance Boundary

Ask the audience to compare losing one vote with losing two. With f=1, three remaining replicas can still form a quorum. If N1 crashes while N4 withholds votes, only N2 and N3 can vote. When N2 leads, it gathers two votes and times out. It must not invent a QC. Optional experiment: Reset, Crash Leader, select Node 4 withholds votes. N2 proposes at STEP 6. Voting finishes at STEP 10. STEPS 11–13 count down, and STEP 14 enters View 3 without a new QC. Recover Nodes clears the faults. Two failures exceed the f=1 assumption, so liveness is not guaranteed.

## 21 Linear Communication and Responsiveness

State the conditions behind linear communication. The original protocol combines a leader that collects votes with compact threshold-signature QCs. This supports linear authenticator communication for phase progress and successful leader replacement. Counting messages alone does not determine their total size: broadcasting a long voter list still carries a size cost. Optimistic responsiveness means that after the network stabilizes and a correct leader takes over, progress follows actual responses rather than waiting the worst-case network delay at each phase. Timeouts remain necessary. This demo has no threshold signatures and uses a central pacemaker and fixed playback timing, so it is not a performance benchmark.

## 22 The Demo's Simplifications

Use this slide to distinguish the implementation from the paper. The teaching version retains views, leaders, proposals, votes, HighQC, LockedQC, parent pointers and three-chain commits. Node IDs replace real signatures. A direct read of live replicas' HighQCs stands in for NEW-VIEW exchange. One coordinator and logical ticks replace a complete pacemaker. The commit rule requires consecutive views. A recovering node copies state from a trusted peer. Arbitrary Byzantine behavior and network partitions are not modeled, so the experiments illustrate behavior within these simulation constraints.

## 23 Live Demo Cue Sheet

Keep this slide visible while running the live demo. Reset before every scenario so that one experiment does not leave faults active in the next. For the normal path, stop at cumulative STEPS 1, 6, 13 and 20. For the leader crash, stop at STEPS 5 and 11 to inspect the new leader and QC, then recover the nodes. For the withheld-vote case, stop at STEP 6 and inspect the log for voters N1, N2 and N3. Fault and control buttons do not add to STEP. Only Next Step and automatic execution ticks advance it. The dashboard labels are in English.

## 24 Protocol Recap

Close with questions. Why does QC(B1) not immediately commit B1? It is the first layer of evidence, and certification of successors supplies the remaining commit evidence. Can a new leader start from any node? It selects an extension point using HighQC, and replicas still enforce their locking rule. Why can one replica withhold a vote without stopping progress? Three remaining votes meet 2f+1. Why can two failures cause repeated timeouts? There are too few votes for a quorum. Finish by distinguishing safety constraints from the mechanisms that drive liveness. Refer to Sections 3–6 of the paper and to node.py and hotstuff.py in this project.

## References

- [HotStuff paper](https://arxiv.org/html/1803.05069v6)
- [Authors' reference implementation](https://github.com/hot-stuff/libhotstuff)
- Project sources: backend/node.py, backend/hotstuff.py and README.md

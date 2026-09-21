"""Deterministic event queue. One step is one visible protocol action.

Transport and the timeout pacemaker are simulated by this coordinator. Votes,
locks, blocks, committed chains and account execution remain per-node state.
"""
from collections import deque
from copy import deepcopy
from dataclasses import asdict

from .blockchain import INITIAL_BALANCES
from .models import Block, QC, Transaction
from .node import Node


class HotStuffDemo:
    NODE_COUNT = 4
    QUORUM = 3
    TIMEOUT_TICKS = 3

    def __init__(self):
        self.reset()

    @property
    def leader_id(self):
        return (self.view - 1) % self.NODE_COUNT + 1

    def log(self, message: str, kind: str = "info"):
        self.log_sequence += 1
        self.logs.append({"id": self.log_sequence, "step": self.steps,
                          "view": self.view, "kind": kind, "message": message})

    def reset(self):
        genesis = Block("B0", None, 0, 0)
        genesis_qc = QC("B0", 0, (1, 2, 3, 4))
        self.view = 1
        self.nodes = [Node(i, genesis, genesis_qc) for i in range(1, 5)]
        self.blocks = {genesis.id: genesis}
        self.qcs = {genesis.id: genesis_qc}
        self.transactions: dict[str, Transaction] = {}
        self.mempool: list[str] = []
        self.votes: dict[str, set[int]] = {}
        self.qc_scheduled: set[str] = set()
        self.events = deque([("propose", None)])
        self.logs = deque(maxlen=400)
        self.log_sequence = 0
        self.steps = 0
        self.running = False
        self.phase = "Ready for proposal"
        self.log("Genesis B0 committed · Enter View 1 · Leader N1", "view")

    def submit(self, sender: str, receiver: str, amount: int) -> Transaction:
        if sender not in INITIAL_BALANCES or receiver not in INITIAL_BALANCES:
            raise ValueError("Choose Alice, Bob, or Charlie")
        if type(amount) is not int or not 1 <= amount <= 1_000_000:
            raise ValueError("Amount must be an integer between 1 and 1000000")
        tx = Transaction(f"Tx{len(self.transactions) + 1}", sender, receiver, amount)
        self.transactions[tx.id] = tx
        self.mempool.append(tx.id)
        self.log(f"{tx.id} enters mempool: {sender} → {receiver} : {amount}", "tx")
        return tx

    def step(self):
        if not self.events:
            self.events.append(("propose", None))
        action, data = self.events.popleft()
        self.steps += 1
        {"propose": self.propose, "vote": self.vote, "qc": self.form_qc,
         "next_view": self.next_view, "timeout": self.timeout}[action](data)

    def propose(self, _):
        leader = self.nodes[self.leader_id - 1]
        if leader.crashed:
            self.phase = "Waiting for timeout"
            self.log(f"Leader N{leader.id} is crashed; no proposal", "fault")
            self.events.append(("timeout", self.TIMEOUT_TICKS))
            return
        # Simplified NEW-VIEW exchange: collect live peers' HighQCs.
        peers = [n for n in self.nodes if not n.crashed]
        best = max(peers, key=lambda n: n.high_qc.view)
        leader.blocks.update(best.blocks)
        leader.high_qc = best.high_qc
        parent = leader.blocks[leader.high_qc.block_id]
        already_proposed = set()
        cursor = parent
        while cursor:
            already_proposed.update(tx.id for tx in cursor.transactions)
            cursor = leader.blocks.get(cursor.parent_id)
        # Keep transactions in the mempool until commit. Orphaned proposals
        # therefore never lose transactions; ancestors are not packed twice.
        batch = [self.transactions[tx_id] for tx_id in self.mempool
                 if tx_id not in already_proposed][:5]
        block = Block(f"B{len(self.blocks)}", parent.id, self.view,
                      leader.id, batch, leader.high_qc)
        self.blocks[block.id] = block
        self.votes[block.id] = set()
        for node in peers:
            node.blocks.update(leader.blocks)
            node.blocks[block.id] = block
        self.phase = f"Proposal {block.id}"
        self.log(f"Leader N{leader.id} proposes {block.id} → parent {parent.id} "
                 f"({len(batch)} tx)", "proposal")
        for node in self.nodes:
            self.events.append(("vote", (node.id, block.id)))

    def vote(self, data):
        node_id, block_id = data
        node = self.nodes[node_id - 1]
        block = self.blocks[block_id]
        # A certificate is trusted only if it is in the simulated QC registry.
        valid = (block.qc == self.qcs.get(block.parent_id)
                 and block.qc is not None and block.qc.view < block.view
                 and block.proposer == self.leader_id)
        if valid and node.can_vote(block):
            node.last_voted_view = block.view
            self.votes[block_id].add(node.id)
            self.phase = f"Votes {block_id}: {len(self.votes[block_id])}/3"
            self.log(f"N{node.id} votes {block_id} "
                     f"({len(self.votes[block_id])}/{self.QUORUM})", "vote")
            if len(self.votes[block_id]) >= self.QUORUM and block_id not in self.qc_scheduled:
                self.qc_scheduled.add(block_id)
                self.events.append(("qc", block_id))
        else:
            reason = "crashed" if node.crashed else "withholds vote" if node.withhold_vote else "unsafe / already voted"
            self.log(f"N{node.id} skips vote for {block_id}: {reason}", "fault")
        if not self.events:
            self.phase = "Waiting for timeout"
            self.events.append(("timeout", self.TIMEOUT_TICKS))

    def form_qc(self, block_id):
        block = self.blocks[block_id]
        if self.nodes[block.proposer - 1].crashed:
            self.log(f"Leader N{block.proposer} crashed before broadcasting QC({block_id})", "fault")
            self.events.append(("timeout", self.TIMEOUT_TICKS))
            return
        voters = tuple(sorted(self.votes[block_id]))
        if len(voters) < self.QUORUM:
            raise RuntimeError("QC requires three distinct votes")
        qc = QC(block_id, block.view, voters)
        self.qcs[block_id] = qc
        self.phase = f"QC({block_id}) formed"
        self.log(f"QC({block_id}) formed · voters " + ", ".join(f"N{i}" for i in voters), "qc")
        newly_committed = set()
        for node in self.nodes:
            newly_committed.update(node.receive_qc(qc))
        for committed_id in sorted(newly_committed, key=lambda b: self.blocks[b].view):
            self.log(f"{committed_id} committed · certified 3-chain ends at {block_id}", "commit")
            live = next(n for n in self.nodes if not n.crashed)
            for tx in self.blocks[committed_id].transactions:
                if tx.id in self.mempool:
                    self.mempool.remove(tx.id)
                receipt = live.machine.receipts[tx.id]
                self.log(f"{tx.id} {receipt['status']}" +
                         (f": {receipt['error']}" if receipt['error'] else
                          f": {tx.sender} → {tx.receiver} : {tx.amount}"), "tx")
        self.events.append(("next_view", "QC"))

    def timeout(self, remaining):
        self.phase = f"Timeout: {remaining} tick(s)"
        self.log(f"View {self.view} timeout countdown: {remaining}", "timeout")
        if remaining > 1:
            self.events.append(("timeout", remaining - 1))
        else:
            self.log(f"Timeout in View {self.view}; rotate leader", "timeout")
            self.events.append(("next_view", "timeout"))

    def next_view(self, reason):
        self.view += 1
        for node in self.nodes:
            node.enter_view(self.view, self.leader_id)
        self.phase = "Ready for proposal"
        self.log(f"Enter View {self.view} · Leader N{self.leader_id} · {reason}", "view")
        self.events.append(("propose", None))

    def crash_leader(self):
        leader = self.nodes[self.leader_id - 1]
        if not leader.crashed:
            leader.crashed = True
            self.log(f"Leader N{leader.id} crashed", "fault")

    def set_byzantine(self, node_id: int | None):
        if node_id is not None and node_id not in range(1, 5):
            raise ValueError("Node ID must be 1–4")
        for node in self.nodes:
            node.withhold_vote = node.id == node_id
        self.log(f"N{node_id} Byzantine: withholds votes only" if node_id else
                 "All nodes vote normally", "fault")

    def recover(self):
        peers = [node for node in self.nodes if not node.crashed]
        source = max(peers or self.nodes, key=lambda n: (n.high_qc.view, len(n.committed_blocks)))
        for node in self.nodes:
            if node.crashed:
                node.blocks = source.blocks.copy()
                node.high_qc = source.high_qc
                node.locked_qc = source.locked_qc
                node.committed_blocks = source.committed_blocks.copy()
                node.machine = deepcopy(source.machine)
                node.crashed = False
            node.withhold_vote = False
            node.enter_view(self.view, self.leader_id)
        self.log("Recover Nodes · catch up blocks, QCs and committed state from peer", "recovery")

    def snapshot(self):
        source = max(self.nodes, key=lambda n: len(n.committed_blocks))
        committed = set(source.committed_blocks)
        node_states = []
        for node in self.nodes:
            node_states.append({
                "id": node.id, "view": node.view, "role": node.role,
                "crashed": node.crashed, "withhold_vote": node.withhold_vote,
                "high_qc": asdict(node.high_qc), "locked_qc": asdict(node.locked_qc),
                "latest_block": max(node.blocks.values(), key=lambda b: b.view).id,
                "committed_blocks": node.committed_blocks.copy(),
                "accounts": node.machine.accounts.copy(),
            })
        blocks = [{**asdict(block), "certificate": asdict(self.qcs[block.id]) if block.id in self.qcs else None,
                   "committed": block.id in committed,
                   "votes": sorted(self.votes.get(block.id, []))}
                  for block in self.blocks.values()]
        transactions = [{**asdict(tx), **source.machine.receipts.get(tx.id, {"status": "pending", "error": None})}
                        for tx in self.transactions.values()]
        live = [n for n in self.nodes if not n.crashed]
        consistent = bool(live) and all(n.machine.accounts == live[0].machine.accounts
                                       and n.committed_blocks == live[0].committed_blocks for n in live)
        return {"view": self.view, "leader_id": self.leader_id, "running": self.running,
                "steps": self.steps, "phase": self.phase, "nodes": node_states,
                "blocks": blocks, "mempool": [asdict(self.transactions[t]) for t in self.mempool],
                "transactions": transactions, "accounts": source.machine.accounts.copy(),
                "committed_chain": source.committed_blocks.copy(), "consistent": consistent,
                "logs": list(self.logs), "quorum": self.QUORUM,
                "next_event": self.events[0][0] if self.events else "propose"}

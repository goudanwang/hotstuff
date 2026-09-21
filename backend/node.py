from .blockchain import StateMachine
from .models import Block, QC


class Node:
    def __init__(self, node_id: int, genesis: Block, genesis_qc: QC):
        self.id = node_id
        self.view = 1
        self.role = "Leader" if node_id == 1 else "Replica"
        self.high_qc = genesis_qc
        self.locked_qc = genesis_qc
        self.blocks = {genesis.id: genesis}
        self.committed_blocks = [genesis.id]
        self.machine = StateMachine()
        self.last_voted_view = 0
        self.crashed = False
        self.withhold_vote = False

    def enter_view(self, view: int, leader_id: int):
        if not self.crashed:
            self.view = view
            self.role = "Leader" if self.id == leader_id else "Replica"

    def extends(self, block_id: str, ancestor_id: str) -> bool:
        while block_id in self.blocks:
            if block_id == ancestor_id:
                return True
            parent = self.blocks[block_id].parent_id
            if parent is None:
                break
            block_id = parent
        return False

    def can_vote(self, block: Block) -> bool:
        if self.crashed or self.withhold_vote or block.view != self.view:
            return False
        if block.view <= self.last_voted_view or block.qc is None:
            return False
        # HotStuff safe-node rule: extend the lock, or carry a newer QC.
        return (self.extends(block.parent_id, self.locked_qc.block_id)
                or block.qc.view > self.locked_qc.view)

    def receive_qc(self, qc: QC) -> list[str]:
        """Advance HighQC, lock the certified parent, commit a 3-chain ancestor."""
        if self.crashed:
            return []
        block = self.blocks[qc.block_id]
        if qc.view > self.high_qc.view:
            self.high_qc = qc
        if block.qc and block.qc.view > self.locked_qc.view:
            self.locked_qc = block.qc
        parent = self.blocks.get(block.parent_id)
        grandparent = self.blocks.get(parent.parent_id) if parent else None
        if not parent or not grandparent or not block.qc or not parent.qc:
            return []
        # Three certified, directly linked blocks in consecutive views.
        if not (block.qc.block_id == parent.id
                and parent.qc.block_id == grandparent.id
                and grandparent.view + 1 == parent.view
                and parent.view + 1 == block.view):
            return []
        path = []
        cursor = grandparent
        while cursor.id not in self.committed_blocks:
            path.append(cursor)
            cursor = self.blocks[cursor.parent_id]
        committed = []
        for ancestor in reversed(path):
            self.committed_blocks.append(ancestor.id)
            for tx in ancestor.transactions:
                self.machine.apply(tx)
            committed.append(ancestor.id)
        return committed

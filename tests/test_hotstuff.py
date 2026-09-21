import unittest

from backend.hotstuff import HotStuffDemo
from backend.models import Block, QC


class HotStuffTests(unittest.TestCase):
    def setUp(self):
        self.demo = HotStuffDemo()

    def advance_until(self, predicate, limit=300):
        for _ in range(limit):
            if predicate():
                return
            self.demo.step()
        self.fail("Protocol did not reach expected state")

    def assert_agreement(self):
        live = [node for node in self.demo.nodes if not node.crashed]
        for node in live[1:]:
            self.assertEqual(node.committed_blocks, live[0].committed_blocks)
            self.assertEqual(node.machine.accounts, live[0].machine.accounts)
            self.assertEqual(node.machine.receipts, live[0].machine.receipts)
        for qc in self.demo.qcs.values():
            self.assertGreaterEqual(len(set(qc.voters)), 3)

    def test_three_chain_and_transfer(self):
        tx = self.demo.submit("Alice", "Bob", 10)
        self.advance_until(lambda: "B2" in self.demo.qcs)
        for node in self.demo.nodes:
            self.assertEqual(node.machine.accounts["Alice"], 100)
            self.assertEqual(node.locked_qc.block_id, "B1")
            self.assertEqual(node.high_qc.block_id, "B2")
        self.advance_until(lambda: "B3" in self.demo.qcs)
        for node in self.demo.nodes:
            self.assertIn("B1", node.committed_blocks)
            self.assertNotIn("B2", node.committed_blocks)
            self.assertEqual(node.machine.accounts, {"Alice": 90, "Bob": 110, "Charlie": 100})
        self.assertNotIn(tx.id, self.demo.mempool)
        for _ in range(60):
            self.demo.step()
        self.assertEqual(self.demo.nodes[0].machine.accounts["Alice"], 90)
        self.assert_agreement()

    def test_crash_leader_timeout_and_recovery(self):
        self.demo.crash_leader()
        self.demo.submit("Alice", "Bob", 10)
        self.advance_until(lambda: self.demo.view == 2)
        self.assertEqual(self.demo.leader_id, 2)
        self.assertEqual(self.demo.nodes[0].view, 1)
        self.advance_until(lambda: self.demo.nodes[1].machine.accounts["Alice"] == 90)
        self.assertEqual(self.demo.nodes[0].machine.accounts["Alice"], 100)
        self.assert_agreement()
        self.demo.recover()
        self.assertTrue(all(not node.crashed for node in self.demo.nodes))
        self.assert_agreement()

    def test_one_byzantine_replica_and_leader_rotation(self):
        self.demo.set_byzantine(4)
        self.demo.submit("Alice", "Bob", 10)
        self.advance_until(lambda: self.demo.view >= 6)
        for block_id, qc in self.demo.qcs.items():
            if block_id != "B0":
                self.assertEqual(qc.voters, (1, 2, 3))
        self.assertEqual(self.demo.nodes[3].machine.accounts["Alice"], 90)
        self.assert_agreement()

    def test_two_unavailable_voters_stall_without_false_qc(self):
        self.demo.crash_leader()
        self.demo.set_byzantine(4)
        for _ in range(60):
            self.demo.step()
        self.assertGreater(self.demo.view, 2)
        self.assertEqual(list(self.demo.qcs), ["B0"])
        self.assert_agreement()

    def test_orphaned_transaction_is_reproposed(self):
        tx = self.demo.submit("Alice", "Bob", 10)
        self.demo.step()  # B1 proposed, but its leader dies before QC.
        self.demo.crash_leader()
        self.advance_until(lambda: self.demo.nodes[1].machine.accounts["Alice"] == 90)
        self.assertNotIn("B1", self.demo.qcs)
        self.assertIn(tx, self.demo.blocks["B2"].transactions)
        self.assertNotIn(tx.id, self.demo.mempool)
        self.demo.recover()
        self.assert_agreement()

    def test_insufficient_funds_rejected_at_commit(self):
        self.demo.submit("Alice", "Bob", 80)
        self.demo.submit("Alice", "Charlie", 80)
        self.advance_until(lambda: not self.demo.mempool)
        for node in self.demo.nodes:
            self.assertEqual(node.machine.accounts, {"Alice": 20, "Bob": 180, "Charlie": 100})
            self.assertEqual(node.machine.receipts["Tx2"]["status"], "rejected")
        self.assert_agreement()

    def test_lock_and_one_vote_per_view(self):
        node = self.demo.nodes[0]
        node.view = 3
        node.blocks["A"] = Block("A", "B0", 1, 1, [], self.demo.qcs["B0"])
        node.locked_qc = QC("A", 1, (1, 2, 3))
        fork = Block("F", "B0", 3, 3, [], self.demo.qcs["B0"])
        self.assertFalse(node.can_vote(fork))
        extension = Block("E", "A", 3, 3, [], node.locked_qc)
        self.assertTrue(node.can_vote(extension))
        node.last_voted_view = 3
        self.assertFalse(node.can_vote(extension))

    def test_view_gap_delays_commit_until_consecutive_chain(self):
        self.advance_until(lambda: self.demo.view == 2)
        self.demo.crash_leader()  # Skip view 2; next chain has views 1,3,4.
        self.advance_until(lambda: self.demo.view == 5)
        self.assertEqual(self.demo.nodes[0].committed_blocks, ["B0"])
        self.advance_until(lambda: self.demo.view == 6)
        # The 3,4,5 chain commits view 3 and also its view 1 ancestor.
        self.assertEqual(self.demo.nodes[0].committed_blocks, ["B0", "B1", "B2"])
        self.assert_agreement()

    def test_batching_and_ancestor_deduplication(self):
        for _ in range(7):
            self.demo.submit("Alice", "Bob", 1)
        self.advance_until(lambda: not self.demo.mempool)
        self.assertEqual(len(self.demo.blocks["B1"].transactions), 5)
        self.assertEqual(len(self.demo.blocks["B2"].transactions), 2)
        self.assertEqual(self.demo.nodes[0].machine.accounts["Alice"], 93)
        self.assert_agreement()

    def test_reset_clears_faults_events_and_accounts(self):
        self.demo.submit("Alice", "Bob", 10)
        self.demo.step()
        self.demo.set_byzantine(4)
        self.demo.crash_leader()
        self.demo.running = True
        self.demo.reset()
        self.assertEqual(self.demo.view, 1)
        self.assertEqual(self.demo.steps, 0)
        self.assertEqual(len(self.demo.blocks), 1)
        self.assertFalse(self.demo.running)
        self.assertFalse(self.demo.mempool)
        self.assertTrue(all(not n.crashed and not n.withhold_vote for n in self.demo.nodes))
        self.assert_agreement()

    def test_invalid_transaction_inputs(self):
        for amount in (0, -1, 1.5, True, 1_000_001):
            with self.assertRaises(ValueError):
                self.demo.submit("Alice", "Bob", amount)
        with self.assertRaises(ValueError):
            self.demo.submit("Unknown", "Bob", 1)


if __name__ == "__main__":
    unittest.main()

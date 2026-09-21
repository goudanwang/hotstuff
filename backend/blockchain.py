from .models import Transaction


INITIAL_BALANCES = {"Alice": 100, "Bob": 100, "Charlie": 100}


class StateMachine:
    def __init__(self):
        self.accounts = INITIAL_BALANCES.copy()
        # Receipts also make execution idempotent across catch-up and retries.
        self.receipts: dict[str, dict] = {}

    def apply(self, tx: Transaction) -> dict:
        if tx.id in self.receipts:
            return self.receipts[tx.id]
        error = None
        if tx.sender not in self.accounts or tx.receiver not in self.accounts:
            error = "Unknown account"
        elif type(tx.amount) is not int or tx.amount <= 0:
            error = "Amount must be a positive integer"
        elif self.accounts[tx.sender] < tx.amount:
            error = "Insufficient balance at commit"
        if error is None:
            self.accounts[tx.sender] -= tx.amount
            self.accounts[tx.receiver] += tx.amount
        receipt = {"status": "rejected" if error else "committed", "error": error}
        self.receipts[tx.id] = receipt
        return receipt

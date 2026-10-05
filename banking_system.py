
# Import
import pickle
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional

import numpy as np

DATA_FILE = "bank_data.pkl" 


# Custom Exceptions
class BankError(Exception):
    """Base class for all bank-system errors."""
    pass


class AccountNotFoundError(BankError):
    """Used when an account is not found"""
    pass


class InvalidAmountError(BankError):
    """used when amount is not valid"""
    pass


class InsufficientFundsError(BankError):
    """used when amount is not enough balance"""
    pass


class AuthenticationError(BankError):
    """Used when the password is incorrect"""
    pass


# Data Model
@dataclass
class Transaction:
    """Stores details of one transaction"""
    timestamp: str
    ttype: str            # deposit | withdrawal | transfer_out | transfer_in
    amount: float
    balance_after: float
    counterparty: Optional[str] = None   # other account number for transfers

    def to_row(self):
        """Convert the trasaction details into a tuple"""
        return (self.timestamp, self.ttype, self.amount, self.balance_after, self.counterparty)


@dataclass
class Account:
    """Stores account details and transaction history"""
    account_number: str
    holder_name: str
    account_type: str                 # savings | current
    balance: float
    username: Optional[str] = None
    password: Optional[str] = None
    transactions: List[Transaction] = field(default_factory=list)

    def add_transaction(self, ttype: str, amount: float, counterparty: Optional[str] = None):
        self.transactions.append(
            Transaction(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ttype=ttype,
                amount=amount,
                balance_after=self.balance,
                counterparty=counterparty,
            )
        )


# File handling
def load_accounts(filepath: str = DATA_FILE) -> Dict[str, Account]:
    """Load the accounts dict from a pickle file and returns {} if no file exists yet"""
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "rb") as f:
            data = pickle.load(f)
            return data if isinstance(data, dict) else {}
    except (pickle.UnpicklingError, EOFError):
        # Corrupt or empty file: fail safe with an empty store rather than crashing.
        print(f"Warning: {filepath!r} could not be read; starting with an empty store.")
        return {}


def save_accounts(accounts: Dict[str, Account], filepath: str = DATA_FILE) -> None:
    """save accounts to the pickle file"""
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "wb") as f:
        pickle.dump(accounts, f)
    os.replace(tmp_path, filepath)   


# Account management
def generate_account_number(accounts: Dict[str, Account]) -> str:
    """Auto-generate the next account number..."""
    if not accounts:
        return "ACC1001"
    max_num = max(int(acc_no.replace("ACC", "")) for acc_no in accounts.keys())
    return f"ACC{max_num + 1}"


def create_account(accounts: Dict[str, Account], holder_name: str, account_type: str,
                    initial_balance: float, username: Optional[str] = None,
                    password: Optional[str] = None) -> str:
    """Create a new account and returns its account number"""

    if not holder_name or not holder_name.strip():
        raise ValueError("Account holder name cannot be empty")
    if account_type.lower() not in ("savings", "current"):
        raise ValueError("Account type must be savings or current")
    if initial_balance < 0:
        raise InvalidAmountError("Initial balance cannot be negative")

    acc_no = generate_account_number(accounts)
    account = Account(
        account_number=acc_no,
        holder_name=holder_name.strip(),
        account_type=account_type.lower(),
        balance=round(float(initial_balance), 2),
        username=username,
        password=password,
    )
    if initial_balance > 0:
        account.add_transaction("deposit", round(float(initial_balance), 2))
    accounts[acc_no] = account
    return acc_no


def get_account(accounts: Dict[str, Account], account_number: str) -> Account:
    """Find an account using account number"""
    if account_number not in accounts:
        raise AccountNotFoundError(f"No account found with number {account_number!r}.")
    return accounts[account_number]


def get_account_details(accounts: Dict[str, Account], account_number: str) -> dict:
    """Return the main details of an account"""
    acc = get_account(accounts, account_number)
    return {
        "account_number": acc.account_number,
        "holder_name": acc.holder_name,
        "account_type": acc.account_type,
        "balance": round(acc.balance, 2),
        "num_transactions": len(acc.transactions),
    }


def print_account_details(accounts: Dict[str, Account], account_number: str) -> None:
    d = get_account_details(accounts, account_number)
    print("-" * 42)
    print(" Account Number : " + str(d["account_number"]))
    print(" Holder Name    : " + str(d["holder_name"]))
    print(" Account Type   : " + str(d["account_type"]).capitalize())
    print(f" Balance        : Rs. {d['balance']:,.2f}")
    print(" Transactions   : " + str(d["num_transactions"]))
    print("-" * 42)


# Transactions
def _validate_amount(amount: float) -> float:
    """Check if the amount is valid"""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise InvalidAmountError("Amount must be a number")
    if amount != amount or amount in (float("inf"), float("-inf")):   # ccheck for Nan or infinity
        raise InvalidAmountError("Amount must be a finite number")
    if amount <= 0:
        raise InvalidAmountError("Amount must be strictly greater than zero")
    return round(amount, 2)


def deposit(accounts: Dict[str, Account], account_number: str, amount: float) -> float:
    """Deposit money and returns the new balance"""
    amount = _validate_amount(amount)
    acc = get_account(accounts, account_number)
    acc.balance = round(acc.balance + amount, 2)
    acc.add_transaction("deposit", amount)
    return acc.balance


def withdraw(accounts: Dict[str, Account], account_number: str, amount: float) -> float:
    """Withdraw money and returns the new balance"""
    amount = _validate_amount(amount)
    acc = get_account(accounts, account_number)
    if amount > acc.balance:
        raise InsufficientFundsError(
            f"Withdrawal of Rs. {amount:,.2f} exceeds available balance of Rs. {acc.balance:,.2f}."
        )
    acc.balance = round(acc.balance - amount, 2)
    acc.add_transaction("withdrawal", amount)
    return acc.balance


def transfer(accounts: Dict[str, Account], from_account: str, to_account: str, amount: float) -> tuple:
    """Transfer money between two accounts and return their balances"""
    amount = _validate_amount(amount)
    if from_account == to_account:
        raise ValueError("Cannot transfer to the same account")

    src = get_account(accounts, from_account)   # raises AccountNotFoundError if missing
    dst = get_account(accounts, to_account)      # raises AccountNotFoundError if missing

    if amount > src.balance:
        raise InsufficientFundsError(
            f"Transfer of Rs. {amount:,.2f} exceeds available balance of Rs. {src.balance:,.2f}."
        )

    # Mutate both sides only after both accounts are confirmed valid and funds are sufficient
    src.balance = round(src.balance - amount, 2)
    dst.balance = round(dst.balance + amount, 2)
    src.add_transaction("transfer_out", amount, counterparty=to_account)
    dst.add_transaction("transfer_in", amount, counterparty=from_account)
    return src.balance, dst.balance


# Reports and statistics
def transaction_history(accounts: Dict[str, Account], account_number: str) -> None:
    """Show a transaction history of an account"""
    acc = get_account(accounts, account_number)
    if not acc.transactions:
        print(f"No transactions yet for {account_number}.")
        return

    print(f"\nTransaction History -- {account_number} ({acc.holder_name})")
    header = "{:<20}{:<15}{:>12}{:>16}{:>15}".format("Date", "Type", "Amount", "Balance After", "Counterparty")
    print(header)
    print("-" * 78)
    for t in acc.transactions:
        cp = t.counterparty or "-"
        row = "{:<20}{:<15}{:>12,.2f}{:>16,.2f}{:>15}".format(t.timestamp, t.ttype, t.amount, t.balance_after, cp)
        print(row)


def account_summary_stats(accounts: Dict[str, Account], account_number: str) -> dict:
    """Calculate summary statistics using NumPy"""
    acc = get_account(accounts, account_number)

    
    is_deposit = lambda t: t.ttype == "deposit"
    is_withdrawal = lambda t: t.ttype in ("withdrawal", "transfer_out")
    is_inflow = lambda t: t.ttype in ("deposit", "transfer_in")

    deposits = np.array([t.amount for t in acc.transactions if is_deposit(t)], dtype=float)
    withdrawals = np.array([t.amount for t in acc.transactions if is_withdrawal(t)], dtype=float)
    all_amounts = np.array([t.amount for t in acc.transactions if is_inflow(t) or is_withdrawal(t)], dtype=float)

    stats = {
        "total_deposits": float(np.sum(deposits)) if deposits.size else 0.0,
        "total_withdrawals": float(np.sum(withdrawals)) if withdrawals.size else 0.0,
        "avg_transaction_amount": float(np.mean(all_amounts)) if all_amounts.size else 0.0,
        "max_transaction_amount": float(np.max(all_amounts)) if all_amounts.size else 0.0,
        "std_transaction_amount": float(np.std(all_amounts)) if all_amounts.size else 0.0,
        "transaction_count": int(all_amounts.size),
    }
    return stats


def print_summary_stats(accounts: Dict[str, Account], account_number: str) -> None:
    s = account_summary_stats(accounts, account_number)
    print(f"\nSummary Statistics -- {account_number}")
    print("-" * 42)
    print(f" Total Deposits          : Rs. {s['total_deposits']:,.2f}")
    print(f" Total Withdrawals       : Rs. {s['total_withdrawals']:,.2f}")
    print(f" Average Txn Amount      : Rs. {s['avg_transaction_amount']:,.2f}")
    print(f" Largest Txn Amount      : Rs. {s['max_transaction_amount']:,.2f}")
    print(f" Txn Amount Std. Dev.    : Rs. {s['std_transaction_amount']:,.2f}")
    print(" Total Transaction Count : " + str(s["transaction_count"]))
    print("-" * 42)


# Login support
def authenticate(accounts: Dict[str, Account], account_number: str, password: str) -> bool:
    """Return True if the password is correct"""
    
    acc = get_account(accounts, account_number)

    if acc.password is None:
        raise AuthenticationError(f"Account {account_number} has no password configured.")
    if acc.password != password:
        raise AuthenticationError("Incorrect password.")
    return True


# Main Menu
def _prompt_float(msg: str) -> float:
    while True:
        raw = input(msg).strip()
        try:
            return float(raw)
        except ValueError:
            print("Please enter a valid number.")


def main_menu(accounts: Optional[Dict[str, Account]] = None, filepath: str = DATA_FILE) -> Dict[str, Account]:
    """Run the main menu and returns the final accounts dict"""
    if accounts is None:
        accounts = load_accounts(filepath)

    MENU = """
============================================
   BANK ACCOUNT MANAGEMENT SYSTEM
============================================
 1. Open a new account
 2. View account details
 3. Deposit
 4. Withdraw
 5. Transfer funds
 6. View transaction history
 7. View summary statistics
 8. Exit
============================================"""

    while True:
        print(MENU)
        choice = input("Select an option (1-8): ").strip()

        try:
            if choice == "1":
                name = input("Account holder's name: ")
                atype = input("Account type (savings/current): ")
                bal = _prompt_float("Initial balance: ")
                acc_no = create_account(accounts, name, atype, bal)
                print(f"Account created successfully. Account number: {acc_no}")

            elif choice == "2":
                acc_no = input("Account number: ").strip()
                print_account_details(accounts, acc_no)

            elif choice == "3":
                acc_no = input("Account number: ").strip()
                amt = _prompt_float("Deposit amount: ")
                new_bal = deposit(accounts, acc_no, amt)
                print(f"Deposit successful. New balance: Rs. {new_bal:,.2f}")

            elif choice == "4":
                acc_no = input("Account number: ").strip()
                amt = _prompt_float("Withdrawal amount: ")
                new_bal = withdraw(accounts, acc_no, amt)
                print(f"Withdrawal successful. New balance: Rs. {new_bal:,.2f}")

            elif choice == "5":
                src = input("From account number: ").strip()
                dst = input("To account number: ").strip()
                amt = _prompt_float("Transfer amount: ")
                b1, b2 = transfer(accounts, src, dst, amt)
                print(f"Transfer successful. {src} balance: Rs. {b1:,.2f} | {dst} balance: Rs. {b2:,.2f}")

            elif choice == "6":
                acc_no = input("Account number: ").strip()
                transaction_history(accounts, acc_no)

            elif choice == "7":
                acc_no = input("Account number: ").strip()
                print_summary_stats(accounts, acc_no)

            elif choice == "8":
                save_accounts(accounts, filepath)
                print("Data saved. Goodbye!")
                break

            else:
                print("Invalid option. Please choose 1-8.")

        except BankError as e:
            print(f"Error: {e}")
        except ValueError as e:
            print(f"Invalid input: {e}")

        # persist after every mutating action so no work is lost on crash/interrupt
        save_accounts(accounts, filepath)

    return accounts


# Pandas Groupby analysis
def transactions_to_dataframe(accounts: Dict[str, Account]):
    """ Convert all transactions into a Dataframe"""
    import pandas as pd
    rows = []
    for acc_no, acc in accounts.items():
        for t in acc.transactions:
            rows.append({
                "account_number": acc_no,
                "holder_name": acc.holder_name,
                "account_type": acc.account_type,
                "timestamp": t.timestamp,
                "type": t.ttype,
                "amount": t.amount,
                "balance_after": t.balance_after,
                "counterparty": t.counterparty,
            })
    return pd.DataFrame(rows)


accounts = load_accounts()
accounts = main_menu(accounts)
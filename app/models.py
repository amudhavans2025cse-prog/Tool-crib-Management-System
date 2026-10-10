from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: str
    name: str
    role: str
    phone: str
    membership_status: str

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        return cls(
            id=row['id'],
            name=row['name'],
            role=row['role'],
            phone=row['phone'],
            membership_status=row['membership_status']
        )


@dataclass
class Item:
    id: str
    title: str
    category: str
    active: int
    available: int
    created_at: str

    @property
    def is_active(self) -> bool:
        return self.active == 1

    @property
    def is_available(self) -> bool:
        return self.available == 1

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        return cls(
            id=row['id'],
            title=row['title'],
            category=row['category'],
            active=row['active'],
            available=row['available'],
            created_at=row['created_at']
        )


@dataclass
class LoanRequest:
    id: str
    member_id: str
    item_id: str
    status: str
    created_at: str
    item_title: Optional[str] = None
    member_name: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        keys = row.keys()
        return cls(
            id=row['id'],
            member_id=row['member_id'],
            item_id=row['item_id'],
            status=row['status'],
            created_at=row['created_at'],
            item_title=row['item_title'] if 'item_title' in keys else None,
            member_name=row['member_name'] if 'member_name' in keys else None
        )


@dataclass
class Loan:
    id: str
    request_id: Optional[str]
    member_id: str
    item_id: str
    item_title_snapshot: str
    issue_date: str
    due_date: str
    return_date: Optional[str]
    status: str
    fine_amount: float = 0.0
    overdue_days: int = 0
    member_name: Optional[str] = None

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        keys = row.keys()
        return cls(
            id=row['id'],
            request_id=row['request_id'],
            member_id=row['member_id'],
            item_id=row['item_id'],
            item_title_snapshot=row['item_title_snapshot'],
            issue_date=row['issue_date'],
            due_date=row['due_date'],
            return_date=row['return_date'],
            status=row['status'],
            member_name=row['member_name'] if 'member_name' in keys else None
        )


@dataclass
class LoanStatusHistory:
    id: int
    reference_id: str
    actor_id: str
    old_status: Optional[str]
    new_status: str
    event_at: str

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        return cls(
            id=row['id'],
            reference_id=row['reference_id'],
            actor_id=row['actor_id'],
            old_status=row['old_status'],
            new_status=row['new_status'],
            event_at=row['event_at']
        )

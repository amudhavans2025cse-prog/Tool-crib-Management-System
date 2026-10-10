import re
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from app.database import get_db_connection
from app.models import User, Item, LoanRequest, Loan
from app.services.loan_service import calculate_fine


class MemberService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_connection(self):
        return get_db_connection(self.db_path)

    @staticmethod
    def validate_member_details(user: Optional[User]) -> Tuple[bool, str]:
        """
        Validates member details according to BR7:
        - Member ID cannot be blank.
        - Name cannot be blank.
        - Phone must contain exactly 10 digits.
        - Membership status must be 'ACTIVE'.
        """
        if not user:
            return False, "Member not found."
        if not user.id or not str(user.id).strip():
            return False, "Member ID cannot be blank."
        if not user.name or not str(user.name).strip():
            return False, "Member name cannot be blank."
        if not user.phone or not re.match(r'^\d{10}$', str(user.phone).strip()):
            return False, "Phone number must contain exactly 10 digits."
        if user.membership_status != 'ACTIVE':
            return False, f"Membership is not active (current status: {user.membership_status})."
        return True, ""

    def get_member(self, member_id: str) -> Optional[User]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (member_id,))
            row = cursor.fetchone()
            return User.from_row(row) if row else None
        finally:
            conn.close()

    def search_tools(self, query: str = '', category: str = '', availability: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        FR1: Display and search active tools by ID, title/name, category, and availability.
        Includes current borrower and due date info when a tool is currently issued.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT i.*,
                       (SELECT u.name FROM loans l JOIN users u ON l.member_id = u.id WHERE l.item_id = i.id AND l.status = 'ISSUED' LIMIT 1) as current_borrower_name,
                       (SELECT l.due_date FROM loans l WHERE l.item_id = i.id AND l.status = 'ISSUED' LIMIT 1) as current_due_date,
                       (SELECT l.id FROM loans l WHERE l.item_id = i.id AND l.status = 'ISSUED' LIMIT 1) as active_loan_id
                FROM items i
                WHERE i.active = 1
            """
            params = []

            if query:
                q = f"%{query.strip()}%"
                sql += " AND (i.id LIKE ? OR i.title LIKE ?)"
                params.extend([q, q])

            if category:
                sql += " AND i.category = ?"
                params.append(category.strip())

            if availability is not None and availability != '':
                sql += " AND i.available = ?"
                params.append(int(availability))

            sql += " ORDER BY i.id ASC"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_categories(self) -> List[str]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT category FROM items WHERE active = 1 ORDER BY category ASC")
            return [row['category'] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_tool_by_id(self, item_id: str) -> Optional[Item]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            return Item.from_row(row) if row else None
        finally:
            conn.close()

    def create_issue_request(self, member_id: str, item_id: str) -> Tuple[bool, str, Optional[str]]:
        """
        FR2: Allow members to create issue requests.
        Enforces BR2, BR7, and prevents duplicate or invalid requests (T1, T3).
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # 1. Validate Member
            cursor.execute("SELECT * FROM users WHERE id = ?", (member_id,))
            user_row = cursor.fetchone()
            user = User.from_row(user_row)
            valid, err = self.validate_member_details(user)
            if not valid:
                return False, f"Validation failed: {err}", None
            if user.role != 'Member':
                return False, "Only members can create issue requests.", None

            # 2. Check active loans limit (BR1)
            cursor.execute("SELECT COUNT(*) FROM loans WHERE member_id = ? AND status = 'ISSUED'", (member_id,))
            active_loans = cursor.fetchone()[0]
            if active_loans >= 5:
                return False, f"Active loan limit reached ({active_loans}/5). You cannot request more tools.", None

            # 3. Validate Tool Existence and Availability (BR2, T3)
            cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
            item_row = cursor.fetchone()
            if not item_row:
                return False, f"Tool with ID '{item_id}' not found.", None
            item = Item.from_row(item_row)
            if not item.is_active:
                return False, f"Tool '{item.title}' is inactive and cannot be requested.", None
            if not item.is_available:
                return False, f"Tool '{item.title}' is currently unavailable.", None

            # 4. Check for duplicate pending request for same item (FR2, T1)
            cursor.execute("""
                SELECT COUNT(*) FROM loan_requests 
                WHERE member_id = ? AND item_id = ? AND status = 'REQUESTED'
            """, (member_id, item_id))
            if cursor.fetchone()[0] > 0:
                return False, f"You already have an active pending request for tool '{item.title}'.", None

            # 5. Check if member already has this item currently issued
            cursor.execute("""
                SELECT COUNT(*) FROM loans 
                WHERE member_id = ? AND item_id = ? AND status = 'ISSUED'
            """, (member_id, item_id))
            if cursor.fetchone()[0] > 0:
                return False, f"You already hold an active loan for tool '{item.title}'.", None

            # 6. Generate request ID and insert
            req_id = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("""
                INSERT INTO loan_requests (id, member_id, item_id, status, created_at)
                VALUES (?, ?, ?, 'REQUESTED', ?)
            """, (req_id, member_id, item_id, now_str))

            # Record in loan_status_history
            cursor.execute("""
                INSERT INTO loan_status_history (reference_id, actor_id, old_status, new_status, event_at)
                VALUES (?, ?, NULL, 'REQUESTED', ?)
            """, (req_id, member_id, now_str))

            conn.commit()
            return True, f"Issue request '{req_id}' created successfully for {item.title}.", req_id
        except Exception as e:
            conn.rollback()
            return False, f"Error creating request: {str(e)}", None
        finally:
            conn.close()

    def cancel_issue_request(self, request_id: str, member_id: str) -> Tuple[bool, str]:
        """
        FR2, BR10, BR12: Members may cancel their own REQUESTED request.
        Ownership and status sequence strictly enforced.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM loan_requests WHERE id = ?", (request_id,))
            req_row = cursor.fetchone()
            if not req_row:
                return False, "Request not found."

            # Ownership check (BR12, FR6)
            if req_row['member_id'] != member_id:
                return False, "Unauthorized: You can only cancel your own requests."

            # Status check (BR10)
            if req_row['status'] != 'REQUESTED':
                return False, f"Cannot cancel request with status '{req_row['status']}'. Only 'REQUESTED' can be cancelled."

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("""
                UPDATE loan_requests SET status = 'CANCELLED' WHERE id = ?
            """, (request_id,))

            cursor.execute("""
                INSERT INTO loan_status_history (reference_id, actor_id, old_status, new_status, event_at)
                VALUES (?, ?, 'REQUESTED', 'CANCELLED', ?)
            """, (request_id, member_id, now_str))

            conn.commit()
            return True, f"Request '{request_id}' has been cancelled."
        except Exception as e:
            conn.rollback()
            return False, f"Error cancelling request: {str(e)}"
        finally:
            conn.close()

    def get_member_requests(self, member_id: str) -> List[Dict[str, Any]]:
        """FR6: Show member only their own requests."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.member_id, r.item_id, r.status, r.created_at,
                       i.title as item_title, i.category as item_category, i.available as item_available
                FROM loan_requests r
                LEFT JOIN items i ON r.item_id = i.id
                WHERE r.member_id = ?
                ORDER BY r.created_at DESC
            """, (member_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_member_loans(self, member_id: str, as_of_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """FR3, FR6: Show member only their own loans with dates and calculated fines."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.*, u.name as member_name
                FROM loans l
                LEFT JOIN users u ON l.member_id = u.id
                WHERE l.member_id = ?
                ORDER BY l.issue_date DESC, l.id DESC
            """, (member_id,))
            rows = cursor.fetchall()
            loans = []
            for row in rows:
                loan_dict = dict(row)
                fine_info = calculate_fine(
                    due_date_str=loan_dict['due_date'],
                    return_date_str=loan_dict['return_date'],
                    as_of_date_str=as_of_date
                )
                loan_dict.update(fine_info)
                loans.append(loan_dict)
            return loans
        finally:
            conn.close()

    def get_member_loan_details(self, loan_id: str, member_id: str, as_of_date: Optional[str] = None, is_admin: bool = False) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """FR3, FR6, T8: Validates ownership before returning loan details (unless actor is Administrator)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.*, u.name as member_name, u.phone as member_phone,
                       i.category as item_category, i.available as current_tool_available
                FROM loans l
                LEFT JOIN users u ON l.member_id = u.id
                LEFT JOIN items i ON l.item_id = i.id
                WHERE l.id = ?
            """, (loan_id,))
            row = cursor.fetchone()
            if not row:
                return False, None, "Loan record not found."
            loan_dict = dict(row)
            if not is_admin and loan_dict['member_id'] != member_id:
                return False, None, "Unauthorized: You cannot access another member's loan record."

            fine_info = calculate_fine(
                due_date_str=loan_dict['due_date'],
                return_date_str=loan_dict['return_date'],
                as_of_date_str=as_of_date
            )
            loan_dict.update(fine_info)
            return True, loan_dict, ""
        finally:
            conn.close()

import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from app.database import get_db_connection
from app.models import User, Item, Loan, LoanRequest, LoanStatusHistory


def calculate_fine(due_date_str: str, return_date_str: Optional[str] = None, as_of_date_str: Optional[str] = None) -> Dict[str, Any]:
    """
    BR5 & BR6:
    Standard loan period = 14 days.
    Fine = ₹5 per overdue day, calculated ONLY after the due date.
    Formula:
    If return_date is present: overdue_days = max(0, (return_date - due_date).days)
    If active (no return_date): overdue_days = max(0, (as_of_date - due_date).days)
    """
    try:
        due_date = datetime.strptime(due_date_str[:10], '%Y-%m-%d').date()

        if return_date_str:
            comp_date = datetime.strptime(return_date_str[:10], '%Y-%m-%d').date()
        elif as_of_date_str:
            comp_date = datetime.strptime(as_of_date_str[:10], '%Y-%m-%d').date()
        else:
            comp_date = datetime.now().date()

        overdue_days = max(0, (comp_date - due_date).days)
        fine_amount = overdue_days * 5.0
        return {
            "overdue_days": overdue_days,
            "fine_amount": fine_amount,
            "is_overdue": overdue_days > 0,
            "calculation_date": comp_date.strftime('%Y-%m-%d')
        }
    except Exception as e:
        return {
            "overdue_days": 0,
            "fine_amount": 0.0,
            "is_overdue": False,
            "calculation_date": str(e)
        }


class LoanService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def get_connection(self):
        return get_db_connection(self.db_path)

    def validate_admin_actor(self, actor_id: str) -> Tuple[bool, str]:
        """BR12: Only administrator may confirm issues or process returns."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (actor_id,))
            user = cursor.fetchone()
            if not user:
                return False, "Actor user not found."
            if user['role'] != 'Admin':
                return False, "Unauthorized: Only administrators/librarians can perform this operation."
            return True, ""
        finally:
            conn.close()

    def get_active_loans_count(self, member_id: str) -> int:
        """BR1: Count currently active (ISSUED) loans for a member."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM loans WHERE member_id = ? AND status = 'ISSUED'", (member_id,))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def confirm_issue_request(
        self,
        request_id: str,
        admin_id: str,
        issue_date_str: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        FR4, FR5, BR1, BR2, BR3, BR4, BR5, BR7, BR8, BR9, BR12:
        Validates member, membership status, phone number, active-loan count, tool activity, and current availability.
        Atomically creates loan, updates request, marks tool unavailable, and records status history.
        """
        # Validate administrator authority
        is_admin, admin_err = self.validate_admin_actor(admin_id)
        if not is_admin:
            return False, admin_err, None

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            # 1. Fetch Request
            cursor.execute("SELECT * FROM loan_requests WHERE id = ?", (request_id,))
            req = cursor.fetchone()
            if not req:
                conn.rollback()
                return False, f"Request '{request_id}' not found.", None

            if req['status'] != 'REQUESTED':
                conn.rollback()
                return False, f"Cannot issue request with status '{req['status']}'. Status must be 'REQUESTED'.", None

            member_id = req['member_id']
            item_id = req['item_id']

            # 2. Re-validate Member details & status (BR7, FR4, T6)
            cursor.execute("SELECT * FROM users WHERE id = ?", (member_id,))
            member = cursor.fetchone()
            if not member:
                conn.rollback()
                return False, "Member not found.", None

            if not member['id'] or not str(member['id']).strip():
                conn.rollback()
                return False, "Validation failed: Member ID cannot be blank.", None

            if not member['name'] or not str(member['name']).strip():
                conn.rollback()
                return False, "Validation failed: Member name cannot be blank.", None

            if not member['phone'] or not re.match(r'^\d{10}$', str(member['phone']).strip()):
                conn.rollback()
                return False, "Validation failed: Phone number must contain exactly 10 digits.", None

            if member['membership_status'] != 'ACTIVE':
                conn.rollback()
                return False, f"Validation failed: Member status is '{member['membership_status']}' (must be 'ACTIVE').", None

            # 3. Recheck Active Loans Count (BR1, BR3, T2)
            cursor.execute("SELECT COUNT(*) FROM loans WHERE member_id = ? AND status = 'ISSUED'", (member_id,))
            active_count = cursor.fetchone()[0]
            if active_count >= 5:
                conn.rollback()
                return False, f"Active loan limit exceeded: Member already has {active_count} active loans (maximum allowed is 5).", None

            # 4. Recheck Tool Activity and Availability (BR2, BR3, T3, T7)
            cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
            item = cursor.fetchone()
            if not item:
                conn.rollback()
                return False, f"Tool '{item_id}' not found.", None

            if item['active'] != 1:
                conn.rollback()
                return False, f"Tool '{item['title']}' is inactive and cannot be issued.", None

            if item['available'] != 1:
                conn.rollback()
                return False, f"Tool '{item['title']}' is currently unavailable (already issued or checked out).", None

            # 5. Calculate issue and due dates (BR5)
            if issue_date_str:
                issue_dt = datetime.strptime(issue_date_str[:10], '%Y-%m-%d')
            else:
                issue_dt = datetime.now()

            issue_date = issue_dt.strftime('%Y-%m-%d')
            due_date = (issue_dt + timedelta(days=14)).strftime('%Y-%m-%d')
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 6. Snapshot Tool Title (BR4, T12)
            item_title_snapshot = item['title']

            # 7. Generate Loan ID
            loan_id = f"LN-{issue_dt.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

            # 8. Atomic Database Operations (BR9)
            # Create ISSUED loan
            cursor.execute("""
                INSERT INTO loans (
                    id, request_id, member_id, item_id, item_title_snapshot,
                    issue_date, due_date, return_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'ISSUED')
            """, (loan_id, request_id, member_id, item_id, item_title_snapshot, issue_date, due_date))

            # Mark request as ISSUED
            cursor.execute("""
                UPDATE loan_requests SET status = 'ISSUED' WHERE id = ?
            """, (request_id,))

            # Mark tool as unavailable
            cursor.execute("""
                UPDATE items SET available = 0 WHERE id = ?
            """, (item_id,))

            # Record status history
            cursor.execute("""
                INSERT INTO loan_status_history (reference_id, actor_id, old_status, new_status, event_at)
                VALUES (?, ?, 'REQUESTED', 'ISSUED', ?)
            """, (loan_id, admin_id, now_str))

            conn.commit()
            return True, f"Loan '{loan_id}' successfully issued to {member['name']}. Due date: {due_date}.", loan_id
        except Exception as e:
            conn.rollback()
            return False, f"Transaction failed: {str(e)}", None
        finally:
            conn.close()

    def process_return(
        self,
        loan_id: str,
        admin_id: str,
        return_date_str: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        FR7, FR8, BR6, BR10, BR11, BR12, T9, T10:
        Process tool return:
        - Validates loan status is ISSUED.
        - Changes status to RETURNED.
        - Sets return_date.
        - Restores tool availability to 1 exactly once.
        - Repeated returns must be rejected and must not change availability again.
        - Records history atomically.
        """
        # Validate administrator authority
        is_admin, admin_err = self.validate_admin_actor(admin_id)
        if not is_admin:
            return False, admin_err, None

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            # 1. Fetch Loan
            cursor.execute("SELECT * FROM loans WHERE id = ?", (loan_id,))
            loan = cursor.fetchone()
            if not loan:
                conn.rollback()
                return False, f"Loan record '{loan_id}' not found.", None

            # 2. Check current status (BR10, BR11, T9, T10)
            if loan['status'] == 'RETURNED':
                conn.rollback()
                return False, f"Loan '{loan_id}' has already been returned on {loan['return_date']}. Repeated returns are rejected.", None

            if loan['status'] != 'ISSUED':
                conn.rollback()
                return False, f"Invalid status transition: Cannot return a loan with status '{loan['status']}'.", None

            # 3. Determine return date
            if return_date_str:
                return_date = return_date_str[:10]
            else:
                return_date = datetime.now().strftime('%Y-%m-%d')

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            item_id = loan['item_id']

            # 4. Update Loan Status and return date
            cursor.execute("""
                UPDATE loans 
                SET status = 'RETURNED', return_date = ? 
                WHERE id = ?
            """, (return_date, loan_id))

            # 5. Restore Tool Availability exactly once (BR11, FR8)
            cursor.execute("""
                UPDATE items SET available = 1 WHERE id = ?
            """, (item_id,))

            # 6. Record Status History
            cursor.execute("""
                INSERT INTO loan_status_history (reference_id, actor_id, old_status, new_status, event_at)
                VALUES (?, ?, 'ISSUED', 'RETURNED', ?)
            """, (loan_id, admin_id, now_str))

            conn.commit()

            # Calculate fine at return
            fine_info = calculate_fine(due_date_str=loan['due_date'], return_date_str=return_date)
            return True, f"Tool returned successfully. Availability restored. Overdue fine: ₹{fine_info['fine_amount']:.2f}.", fine_info
        except Exception as e:
            conn.rollback()
            return False, f"Return processing error: {str(e)}", None
        finally:
            conn.close()

    def reject_issue_request(self, request_id: str, admin_id: str, reason: str = '') -> Tuple[bool, str]:
        """FR7, BR10, BR12: Administrator rejects an invalid/unfulfillable request."""
        is_admin, admin_err = self.validate_admin_actor(admin_id)
        if not is_admin:
            return False, admin_err

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            cursor.execute("SELECT * FROM loan_requests WHERE id = ?", (request_id,))
            req = cursor.fetchone()
            if not req:
                conn.rollback()
                return False, f"Request '{request_id}' not found."

            if req['status'] != 'REQUESTED':
                conn.rollback()
                return False, f"Cannot reject request with status '{req['status']}'. Status must be 'REQUESTED'."

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("UPDATE loan_requests SET status = 'REJECTED' WHERE id = ?", (request_id,))
            cursor.execute("""
                INSERT INTO loan_status_history (reference_id, actor_id, old_status, new_status, event_at)
                VALUES (?, ?, 'REQUESTED', 'REJECTED', ?)
            """, (request_id, admin_id, now_str))

            conn.commit()
            msg = f"Request '{request_id}' has been rejected."
            if reason:
                msg += f" Reason: {reason}"
            return True, msg
        except Exception as e:
            conn.rollback()
            return False, f"Error rejecting request: {str(e)}"
        finally:
            conn.close()

    def get_all_requests(self) -> List[Dict[str, Any]]:
        """FR7: Admin view of all requests with member active loans count."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, u.name as member_name, u.phone as member_phone, u.membership_status,
                       i.title as item_title, i.category as item_category, i.available as item_available,
                       (SELECT COUNT(*) FROM loans l WHERE l.member_id = r.member_id AND l.status = 'ISSUED') as member_active_loans
                FROM loan_requests r
                LEFT JOIN users u ON r.member_id = u.id
                LEFT JOIN items i ON r.item_id = i.id
                ORDER BY r.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_loans(self, as_of_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """FR3, FR7: Admin view of all loans with fine calculations."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.*, u.name as member_name, u.phone as member_phone,
                       i.title as current_item_title, i.available as current_tool_available
                FROM loans l
                LEFT JOIN users u ON l.member_id = u.id
                LEFT JOIN items i ON l.item_id = i.id
                ORDER BY l.issue_date DESC, l.id DESC
            """)
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

    def get_loan_by_id(self, loan_id: str, as_of_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """FR3: Fetch detailed loan record."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT l.*, u.name as member_name, u.phone as member_phone, u.membership_status,
                       i.title as current_item_title, i.category as item_category, i.available as current_tool_available
                FROM loans l
                LEFT JOIN users u ON l.member_id = u.id
                LEFT JOIN items i ON l.item_id = i.id
                WHERE l.id = ?
            """, (loan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            loan_dict = dict(row)
            fine_info = calculate_fine(
                due_date_str=loan_dict['due_date'],
                return_date_str=loan_dict['return_date'],
                as_of_date_str=as_of_date
            )
            loan_dict.update(fine_info)
            return loan_dict
        finally:
            conn.close()

    def get_status_history(self, reference_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Audit trail of status transitions (FR5, FR10)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            if reference_id:
                cursor.execute("""
                    SELECT h.*, u.name as actor_name, u.role as actor_role
                    FROM loan_status_history h
                    LEFT JOIN users u ON h.actor_id = u.id
                    WHERE h.reference_id = ?
                    ORDER BY h.id DESC
                """, (reference_id,))
            else:
                cursor.execute("""
                    SELECT h.*, u.name as actor_name, u.role as actor_role
                    FROM loan_status_history h
                    LEFT JOIN users u ON h.actor_id = u.id
                    ORDER BY h.id DESC
                """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Summaries for dashboard views."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM items WHERE active = 1")
            total_items = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM items WHERE active = 1 AND available = 1")
            available_items = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM loan_requests WHERE status = 'REQUESTED'")
            pending_requests = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM loans WHERE status = 'ISSUED'")
            active_loans = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM loans WHERE status = 'RETURNED'")
            returned_loans = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'Member'")
            total_members = cursor.fetchone()[0]

            return {
                "total_items": total_items,
                "available_items": available_items,
                "unavailable_items": total_items - available_items,
                "pending_requests": pending_requests,
                "active_loans": active_loans,
                "returned_loans": returned_loans,
                "total_members": total_members
            }
        finally:
            conn.close()

    def reset_sample_data(self, admin_id: str) -> Tuple[bool, str]:
        """Resets the database to the initial required assessment sample data."""
        is_admin, admin_err = self.validate_admin_actor(admin_id)
        if not is_admin:
            return False, admin_err

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")

            # Clear transactions
            cursor.execute("DELETE FROM loans")
            cursor.execute("DELETE FROM loan_requests")
            cursor.execute("DELETE FROM loan_status_history")

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Re-seed users
            users_data = [
                ('M101', 'Alice Johnson', 'Member', '9876543210', 'ACTIVE'),
                ('M102', 'Bob Smith', 'Member', '9123456780', 'ACTIVE'),
                ('A101', 'Librarian Admin', 'Admin', '9000000000', 'ACTIVE')
            ]
            cursor.executemany("""
                INSERT OR REPLACE INTO users (id, name, role, phone, membership_status)
                VALUES (?, ?, ?, ?, ?)
            """, users_data)

            # Re-seed required tools: I101 (Available), I102 (Available), I103 (Unavailable), I104 (Available)
            items_data = [
                ('I101', 'Tool A', 'Precision Hand Tools', 1, 1, now_str),
                ('I102', 'Tool B', 'Measuring Instruments', 1, 1, now_str),
                ('I103', 'Tool C', 'Machining & Diagnostic', 1, 0, now_str),
                ('I104', 'Tool D', 'Cutting & Fabrication', 1, 1, now_str)
            ]
            cursor.executemany("""
                INSERT OR REPLACE INTO items (id, title, category, active, available, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, items_data)

            cursor.execute("""
                INSERT INTO loan_status_history (reference_id, actor_id, old_status, new_status, event_at)
                VALUES ('SYSTEM-RESET', ?, NULL, 'INITIALIZED', ?)
            """, (admin_id, now_str))

            conn.commit()
            return True, "Database successfully reset to initial assessment sample state."
        except Exception as e:
            conn.rollback()
            return False, f"Error resetting database: {str(e)}"
        finally:
            conn.close()

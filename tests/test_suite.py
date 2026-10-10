import sqlite3
from datetime import datetime, timedelta
import pytest

from app.database import get_db_connection, init_db, seed_db
from app.services.member_service import MemberService
from app.services.loan_service import LoanService, calculate_fine


# ==============================================================================
# T1: Request the same item twice
# ==============================================================================
def test_t1_request_same_item_twice(member_service, test_db):
    """
    T1: Attempting to create duplicate requests for the same tool must be rejected.
    """
    member_id = "M101"
    item_id = "I101"

    # First request must succeed
    success1, msg1, req_id1 = member_service.create_issue_request(member_id, item_id)
    assert success1 is True
    assert req_id1 is not None

    # Database state check: exactly 1 request exists
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM loan_requests WHERE member_id = ? AND item_id = ? AND status = 'REQUESTED'", (member_id, item_id))
    assert cursor.fetchone()[0] == 1
    conn.close()

    # Second request for the same tool must be rejected
    success2, msg2, req_id2 = member_service.create_issue_request(member_id, item_id)
    assert success2 is False
    assert req_id2 is None
    assert "already have an active pending request" in msg2

    # Database state after rejection: still exactly 1 request
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM loan_requests WHERE member_id = ? AND item_id = ? AND status = 'REQUESTED'", (member_id, item_id))
    assert cursor.fetchone()[0] == 1
    conn.close()


# ==============================================================================
# T2: Active-loan counts of 4, 5, and 6
# ==============================================================================
def test_t2_active_loan_counts(loan_service, test_db):
    """
    T2: Enforce active loan limits (BR1). Max 5 active loans.
    A member holding 4 active loans can be issued a 5th.
    A member holding 5 active loans cannot be issued a 6th.
    """
    member_id = "M101"
    admin_id = "A101"
    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    # Create 6 extra test tools (T201 to T206)
    for i in range(1, 7):
        cursor.execute("""
            INSERT OR REPLACE INTO items (id, title, category, active, available, created_at)
            VALUES (?, ?, 'Test Tools', 1, 1, '2026-10-10 10:00:00')
        """, (f"T20{i}", f"Extra Tool {i}"))

    # Seed 4 active loans for M101
    for i in range(1, 5):
        tool_id = f"T20{i}"
        req_id = f"REQ-T2-{i}"
        loan_id = f"LN-T2-{i}"
        cursor.execute("INSERT INTO loan_requests VALUES (?, ?, ?, 'ISSUED', '2026-10-10 10:00:00')",
                       (req_id, member_id, tool_id))
        cursor.execute("""
            INSERT INTO loans VALUES (?, ?, ?, ?, ?, '2026-10-01', '2026-10-15', NULL, 'ISSUED')
        """, (loan_id, req_id, member_id, tool_id, f"Extra Tool {i}"))
        cursor.execute("UPDATE items SET available = 0 WHERE id = ?", (tool_id,))
    conn.commit()
    conn.close()

    # Active loan count should be 4
    assert loan_service.get_active_loans_count(member_id) == 4

    # 5th issue request for T205
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO loan_requests VALUES ('REQ-5TH', ?, 'T205', 'REQUESTED', '2026-10-10 10:00:00')", (member_id,))
    conn.commit()
    conn.close()

    success_5th, msg_5th, loan_5th = loan_service.confirm_issue_request("REQ-5TH", admin_id)
    assert success_5th is True
    assert loan_5th is not None
    assert loan_service.get_active_loans_count(member_id) == 5

    # 6th issue request for T206 - MUST BE REJECTED!
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO loan_requests VALUES ('REQ-6TH', ?, 'T206', 'REQUESTED', '2026-10-10 10:00:00')", (member_id,))
    conn.commit()
    conn.close()

    success_6th, msg_6th, loan_6th = loan_service.confirm_issue_request("REQ-6TH", admin_id)
    assert success_6th is False
    assert loan_6th is None
    assert "Active loan limit exceeded" in msg_6th or "5 active loans" in msg_6th

    # Verify database state after rejected 6th loan:
    # 1. Tool T206 remains available (available = 1)
    # 2. Member active loan count remains 5
    # 3. Request REQ-6TH remains in REQUESTED status (not ISSUED)
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT available FROM items WHERE id = 'T206'")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT status FROM loan_requests WHERE id = 'REQ-6TH'")
    assert cursor.fetchone()[0] == 'REQUESTED'
    conn.close()
    assert loan_service.get_active_loans_count(member_id) == 5


# ==============================================================================
# T3: Request unavailable I103
# ==============================================================================
def test_t3_request_unavailable_tool(member_service, loan_service, test_db):
    """
    T3: Tool C (I103) is seeded as Unavailable.
    Creating a request for it or attempting to confirm issue must fail.
    """
    member_id = "M101"
    item_id = "I103"  # Tool C, seeded available = 0

    # Attempt to create request via member service
    success, msg, req_id = member_service.create_issue_request(member_id, item_id)
    assert success is False
    assert req_id is None
    assert "currently unavailable" in msg

    # Even if an admin tries to confirm a forged request for an unavailable item, it must fail
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO loan_requests VALUES ('REQ-FORGED-I103', ?, 'I103', 'REQUESTED', '2026-10-10 10:00:00')", (member_id,))
    conn.commit()
    conn.close()

    success_issue, msg_issue, loan_id = loan_service.confirm_issue_request("REQ-FORGED-I103", "A101")
    assert success_issue is False
    assert loan_id is None
    assert "currently unavailable" in msg_issue

    # Verify tool I103 remains unavailable and no loan created
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT available FROM items WHERE id = 'I103'")
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT COUNT(*) FROM loans WHERE item_id = 'I103'")
    assert cursor.fetchone()[0] == 0
    conn.close()


# ==============================================================================
# T4: Fine calculation before, on, and after the due date
# ==============================================================================
def test_t4_fine_calculation():
    """
    T4: Standard loan period = 14 days.
    Fine = ₹5 per overdue day, calculated ONLY after the due date (BR5, BR6).
    """
    due_date = "2026-10-15"

    # Case 1: 5 days before due date (2026-10-10) -> Overdue: 0 days, Fine: ₹0
    result_before = calculate_fine(due_date_str=due_date, as_of_date_str="2026-10-10")
    assert result_before["overdue_days"] == 0
    assert result_before["fine_amount"] == 0.0
    assert result_before["is_overdue"] is False

    # Case 2: On the exact due date (2026-10-15) -> Overdue: 0 days, Fine: ₹0
    result_on = calculate_fine(due_date_str=due_date, as_of_date_str="2026-10-15")
    assert result_on["overdue_days"] == 0
    assert result_on["fine_amount"] == 0.0
    assert result_on["is_overdue"] is False

    # Case 3: 1 day after due date (2026-10-16) -> Overdue: 1 day, Fine: ₹5
    result_after_1 = calculate_fine(due_date_str=due_date, as_of_date_str="2026-10-16")
    assert result_after_1["overdue_days"] == 1
    assert result_after_1["fine_amount"] == 5.0
    assert result_after_1["is_overdue"] is True

    # Case 4: 7 days after due date (2026-10-22) -> Overdue: 7 days, Fine: ₹35
    result_after_7 = calculate_fine(due_date_str=due_date, as_of_date_str="2026-10-22")
    assert result_after_7["overdue_days"] == 7
    assert result_after_7["fine_amount"] == 35.0
    assert result_after_7["is_overdue"] is True

    # Case 5: When returned with return_date 4 days overdue -> Fine = 4 * 5 = ₹20
    result_returned = calculate_fine(due_date_str=due_date, return_date_str="2026-10-19")
    assert result_returned["overdue_days"] == 4
    assert result_returned["fine_amount"] == 20.0


# ==============================================================================
# T5: Successful issue with correct database updates
# ==============================================================================
def test_t5_successful_issue_with_database_updates(member_service, loan_service, test_db):
    """
    T5: Create request, confirm issue. Verify:
    1. Uniquely identified ISSUED loan.
    2. Snapshot of tool details saved.
    3. Dates calculated (due date = issue date + 14 days).
    4. Tool marked unavailable.
    5. Status history recorded atomically.
    """
    member_id = "M101"
    item_id = "I104"  # Tool D
    admin_id = "A101"

    # Member creates request
    req_success, req_msg, req_id = member_service.create_issue_request(member_id, item_id)
    assert req_success is True

    # Admin confirms issue on a specific date
    issue_date = "2026-10-10"
    expected_due_date = "2026-10-24"

    issue_success, issue_msg, loan_id = loan_service.confirm_issue_request(
        request_id=req_id,
        admin_id=admin_id,
        issue_date_str=issue_date
    )
    assert issue_success is True
    assert loan_id is not None

    # Check database updates
    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    # 1. Loan record
    cursor.execute("SELECT * FROM loans WHERE id = ?", (loan_id,))
    loan = cursor.fetchone()
    assert loan is not None
    assert loan['member_id'] == member_id
    assert loan['item_id'] == item_id
    assert loan['item_title_snapshot'] == 'Tool D'
    assert loan['issue_date'] == issue_date
    assert loan['due_date'] == expected_due_date
    assert loan['status'] == 'ISSUED'
    assert loan['return_date'] is None

    # 2. Tool availability updated to 0
    cursor.execute("SELECT available FROM items WHERE id = ?", (item_id,))
    assert cursor.fetchone()[0] == 0

    # 3. Request status updated to ISSUED
    cursor.execute("SELECT status FROM loan_requests WHERE id = ?", (req_id,))
    assert cursor.fetchone()[0] == 'ISSUED'

    # 4. Status history recorded
    cursor.execute("""
        SELECT * FROM loan_status_history 
        WHERE reference_id = ? AND new_status = 'ISSUED'
    """, (loan_id,))
    history = cursor.fetchone()
    assert history is not None
    assert history['actor_id'] == admin_id
    assert history['old_status'] == 'REQUESTED'
    conn.close()


# ==============================================================================
# T6: Invalid member details and inactive membership
# ==============================================================================
def test_t6_invalid_member_details_and_inactive_membership(loan_service, test_db):
    """
    T6: Member details validation (BR7):
    - Blank ID/name, non-10 digit phone, or inactive membership must fail validation.
    - No loan created, no tool availability change.
    """
    conn = get_db_connection(test_db)
    cursor = conn.cursor()

    # Add invalid members
    cursor.execute("INSERT INTO users VALUES ('M-INV1', '', 'Member', '9876543210', 'ACTIVE')")  # Blank name
    cursor.execute("INSERT INTO users VALUES ('M-INV2', 'Bad Phone', 'Member', '12345', 'ACTIVE')")  # 5 digit phone
    cursor.execute("INSERT INTO users VALUES ('M-INV3', 'Inactive User', 'Member', '9876543210', 'INACTIVE')")  # Inactive status
    conn.commit()

    # Pre-test tool I102 state
    cursor.execute("SELECT available FROM items WHERE id = 'I102'")
    assert cursor.fetchone()[0] == 1
    conn.close()

    # Sub-case A: Inactive member tries to issue
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO loan_requests VALUES ('REQ-INACT', 'M-INV3', 'I102', 'REQUESTED', '2026-10-10 10:00:00')")
    conn.commit()
    conn.close()

    success, msg, loan_id = loan_service.confirm_issue_request('REQ-INACT', 'A101')
    assert success is False
    assert loan_id is None
    assert "Member status is 'INACTIVE'" in msg

    # Sub-case B: Invalid phone member tries to issue
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO loan_requests VALUES ('REQ-BADPHONE', 'M-INV2', 'I102', 'REQUESTED', '2026-10-10 10:00:00')")
    conn.commit()
    conn.close()

    success2, msg2, loan_id2 = loan_service.confirm_issue_request('REQ-BADPHONE', 'A101')
    assert success2 is False
    assert loan_id2 is None
    assert "Phone number must contain exactly 10 digits" in msg2

    # Verify tool I102 is STILL available and no loan was created
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT available FROM items WHERE id = 'I102'")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT COUNT(*) FROM loans WHERE item_id = 'I102'")
    assert cursor.fetchone()[0] == 0
    conn.close()


# ==============================================================================
# T7: Tool availability changes before issue confirmation
# ==============================================================================
def test_t7_tool_availability_changes_before_issue(loan_service, member_service, test_db):
    """
    T7: Race condition / availability change before confirmation.
    Request created while tool is available. Before confirmation, tool becomes unavailable.
    Confirmation must be rejected and database remains consistent (BR3, BR8).
    """
    member_id = "M101"
    item_id = "I102"  # Tool B (currently available)

    # 1. Request created while tool is available
    req_success, req_msg, req_id = member_service.create_issue_request(member_id, item_id)
    assert req_success is True

    # 2. Tool availability changes before admin confirms (e.g. marked unavailable / damaged)
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET available = 0 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

    # 3. Admin attempts to confirm issue
    success, msg, loan_id = loan_service.confirm_issue_request(req_id, "A101")
    assert success is False
    assert loan_id is None
    assert "currently unavailable" in msg

    # 4. Verify request remains unconfirmed, tool remains unavailable, no loan created
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM loan_requests WHERE id = ?", (req_id,))
    assert cursor.fetchone()[0] == 'REQUESTED'
    cursor.execute("SELECT COUNT(*) FROM loans WHERE request_id = ?", (req_id,))
    assert cursor.fetchone()[0] == 0
    conn.close()


# ==============================================================================
# T8: Unauthorized access to another member's loan and administrator actions
# ==============================================================================
def test_t8_unauthorized_access(member_service, loan_service, test_db):
    """
    T8: Security and role enforcement (BR12, FR6):
    - Member M101 cannot access Member M102's loan details.
    - Member M101 cannot cancel Member M102's request.
    - Member M101 cannot perform administrator actions (confirm issue, process return).
    """
    # 1. Create a loan for M102
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO loan_requests VALUES ('REQ-M102', 'M102', 'I101', 'REQUESTED', '2026-10-10 10:00:00')")
    cursor.execute("""
        INSERT INTO loans VALUES ('LN-M102-1', 'REQ-M102', 'M102', 'I101', 'Tool A', '2026-10-01', '2026-10-15', NULL, 'ISSUED')
    """)
    conn.commit()
    conn.close()

    # Member M101 attempts to view M102's loan details
    success_view, loan_data, err_view = member_service.get_member_loan_details('LN-M102-1', member_id='M101')
    assert success_view is False
    assert loan_data is None
    assert "Unauthorized" in err_view

    # Member M101 attempts to cancel M102's request
    success_cancel, err_cancel = member_service.cancel_issue_request('REQ-M102', member_id='M101')
    assert success_cancel is False
    assert "Unauthorized" in err_cancel

    # Member M101 attempts to perform administrator confirmation
    success_confirm, err_confirm, _ = loan_service.confirm_issue_request('REQ-M102', admin_id='M101')
    assert success_confirm is False
    assert "Unauthorized: Only administrators" in err_confirm

    # Member M101 attempts to process return
    success_return, err_return, _ = loan_service.process_return('LN-M102-1', admin_id='M101')
    assert success_return is False
    assert "Unauthorized: Only administrators" in err_return


# ==============================================================================
# T9: Valid status sequence and attempted status skipping
# ==============================================================================
def test_t9_valid_status_sequence_and_status_skipping(loan_service, member_service, test_db):
    """
    T9: Loan status sequence: REQUESTED -> ISSUED -> RETURNED.
    Skipping states (e.g. issuing a cancelled request, returning a non-issued request) must be rejected.
    """
    # 1. Create and cancel a request
    success_req, _, req_id = member_service.create_issue_request("M101", "I101")
    assert success_req is True

    success_cancel, _ = member_service.cancel_issue_request(req_id, "M101")
    assert success_cancel is True

    # Attempting to confirm an already CANCELLED request must be rejected
    success_issue, msg_issue, _ = loan_service.confirm_issue_request(req_id, "A101")
    assert success_issue is False
    assert "Cannot issue request with status 'CANCELLED'" in msg_issue

    # Attempting to return a non-existent or invalid loan
    success_return, msg_return, _ = loan_service.process_return("LN-NONEXISTENT", "A101")
    assert success_return is False
    assert "not found" in msg_return


# ==============================================================================
# T10: Return the same tool twice
# ==============================================================================
def test_t10_return_same_tool_twice(loan_service, test_db):
    """
    T10: Process return: changes loan status to RETURNED and restores availability exactly once.
    Repeated return attempts must be rejected and must NOT change availability again (BR11).
    """
    admin_id = "A101"
    # Seed an issued loan
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET available = 0 WHERE id = 'I101'")
    cursor.execute("""
        INSERT INTO loans VALUES ('LN-RET-1', NULL, 'M101', 'I101', 'Tool A', '2026-10-01', '2026-10-15', NULL, 'ISSUED')
    """)
    conn.commit()
    conn.close()

    # First return: must succeed
    success1, msg1, fine_info1 = loan_service.process_return('LN-RET-1', admin_id, return_date_str='2026-10-16')
    assert success1 is True
    assert "Tool returned successfully" in msg1

    # Verify tool I101 is available = 1, loan status = RETURNED
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT available FROM items WHERE id = 'I101'")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT status, return_date FROM loans WHERE id = 'LN-RET-1'")
    loan_row = cursor.fetchone()
    assert loan_row['status'] == 'RETURNED'
    assert loan_row['return_date'] == '2026-10-16'

    # Count status history records
    cursor.execute("SELECT COUNT(*) FROM loan_status_history WHERE reference_id = 'LN-RET-1'")
    history_count_before = cursor.fetchone()[0]
    conn.close()

    # Second return attempt on the same loan: MUST BE REJECTED
    success2, msg2, fine_info2 = loan_service.process_return('LN-RET-1', admin_id, return_date_str='2026-10-18')
    assert success2 is False
    assert fine_info2 is None
    assert "already been returned" in msg2

    # Verify tool availability is still 1 and not altered, history count did not increment
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT available FROM items WHERE id = 'I101'")
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT COUNT(*) FROM loan_status_history WHERE reference_id = 'LN-RET-1'")
    history_count_after = cursor.fetchone()[0]
    assert history_count_after == history_count_before
    conn.close()


# ==============================================================================
# T11: Restart application and verify persistent records
# ==============================================================================
def test_t11_restart_application_and_verify_persistent_records(test_db):
    """
    T11: Data persistence (FR10):
    Insert records, simulate application restart (close connection, re-initialize new service instances),
    and verify that all records survive without data loss.
    """
    # 1. Create a request and issue a loan
    srv1_member = MemberService(db_path=test_db)
    srv1_loan = LoanService(db_path=test_db)

    success_req, _, req_id = srv1_member.create_issue_request("M101", "I101")
    assert success_req is True

    success_issue, _, loan_id = srv1_loan.confirm_issue_request(req_id, "A101")
    assert success_issue is True

    # 2. Simulate Application Restart:
    # Completely destroy old service instances and re-instantiate from the persistent database file
    del srv1_member
    del srv1_loan

    srv2_member = MemberService(db_path=test_db)
    srv2_loan = LoanService(db_path=test_db)

    # 3. Verify persistent records
    tool = srv2_member.get_tool_by_id("I101")
    assert tool is not None
    assert tool.available == 0  # Still unavailable

    loan = srv2_loan.get_loan_by_id(loan_id)
    assert loan is not None
    assert loan['id'] == loan_id
    assert loan['member_id'] == 'M101'
    assert loan['item_id'] == 'I101'
    assert loan['status'] == 'ISSUED'

    history = srv2_loan.get_status_history(reference_id=loan_id)
    assert len(history) >= 1
    assert history[0]['new_status'] == 'ISSUED'


# ==============================================================================
# T12: Change tool master data and verify the historical snapshot
# ==============================================================================
def test_t12_change_tool_master_data_and_verify_snapshot(member_service, loan_service, test_db):
    """
    T12: Tool snapshot preservation (BR4):
    Issue a loan for tool "Tool A". Snapshot is "Tool A".
    Update tool title in `items` table to "Tool A - Modified Pro".
    Verify loan record retains the original historical snapshot "Tool A".
    """
    # 1. Issue Tool A (I101)
    req_success, _, req_id = member_service.create_issue_request("M101", "I101")
    assert req_success is True

    issue_success, _, loan_id = loan_service.confirm_issue_request(req_id, "A101")
    assert issue_success is True

    # Verify initial snapshot
    loan_initial = loan_service.get_loan_by_id(loan_id)
    assert loan_initial['item_title_snapshot'] == 'Tool A'

    # 2. Change tool master data in `items` table
    conn = get_db_connection(test_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET title = 'Tool A - Modified Pro' WHERE id = 'I101'")
    conn.commit()
    conn.close()

    # 3. Re-fetch loan and verify snapshot remains unchanged
    loan_after = loan_service.get_loan_by_id(loan_id)
    assert loan_after['item_title_snapshot'] == 'Tool A'  # Preserved original snapshot!
    assert loan_after['current_item_title'] == 'Tool A - Modified Pro'  # Master data is updated

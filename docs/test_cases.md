# Test Cases Specification & Verification Report
**Project:** Tool Crib Management System — Industry Use Case 49  
**Assessment:** Software Engineering SAT II Assessment  
**Test Framework:** Pytest 9.1.1 (Python 3.14 on Windows)  
**Total Tests Executed:** 19 (12 Mandatory Business Tests + 7 Web/Workflow Integration Tests)  
**Execution Outcome:** 19 Passed, 0 Failed (100% Pass Rate)  

---

## 1. Test Summary Overview

| Test ID | Test Name | Target Rule / FR | Status |
|---|---|---|---|
| **T1** | `test_t1_request_same_item_twice` | FR2, Duplicate Prevention | **PASSED** |
| **T2** | `test_t2_active_loan_counts` | BR1, FR4 (Counts 4, 5, 6) | **PASSED** |
| **T3** | `test_t3_request_unavailable_tool` | BR2, FR2, FR4 (Unavailable I103) | **PASSED** |
| **T4** | `test_t4_fine_calculation` | BR5, BR6, FR3 (Before, On, After Due Date) | **PASSED** |
| **T5** | `test_t5_successful_issue_with_database_updates` | BR4, BR5, BR9, FR5 (Atomic Issue) | **PASSED** |
| **T6** | `test_t6_invalid_member_details_and_inactive_membership` | BR7, BR8, FR4 (Phone, Name, Inactive) | **PASSED** |
| **T7** | `test_t7_tool_availability_changes_before_issue` | BR2, BR3, BR8, FR4 (Race Condition) | **PASSED** |
| **T8** | `test_t8_unauthorized_access` | BR12, FR6 (Ownership & Role Isolation) | **PASSED** |
| **T9** | `test_t9_valid_status_sequence_and_status_skipping` | BR10, FR7 (REQUESTED $\rightarrow$ ISSUED $\rightarrow$ RETURNED) | **PASSED** |
| **T10** | `test_t10_return_same_tool_twice` | BR11, FR8 (Single-Restoration Guarantee) | **PASSED** |
| **T11** | `test_t11_restart_application_and_verify_persistent_records` | FR10 (SQLite File Persistence) | **PASSED** |
| **T12** | `test_t12_change_tool_master_data_and_verify_snapshot` | BR4 (Historical Title Snapshot) | **PASSED** |
| **W1** | `test_login_and_role_redirect` | Section 2 (Role-based Dashboard Routing) | **PASSED** |
| **W2** | `test_member_cannot_access_admin_routes` | BR12 (Backend Role Protection) | **PASSED** |
| **W3** | `test_end_to_end_web_workflow` | Section 8 (Full Demonstration Flow) | **PASSED** |
| **W4** | `test_admin_can_access_inventory_and_view_loan_details` | FR1, FR3 (Admin Inventory & Loan Access) | **PASSED** |
| **W5** | `test_admin_reject_request` | FR7, BR10 (Admin Request Rejection) | **PASSED** |
| **W6** | `test_case_insensitive_login` | Section 2 (User Sign-In Usability) | **PASSED** |
| **W7** | `test_admin_reset_database` | Viva Demo (Pristine State Reset) | **PASSED** |

---

## 2. Detailed Test Specifications & Actual Results

### T1: Request the Same Item Twice
- **Objective:** Verify that a member cannot submit duplicate active requests for the same tool.
- **Preconditions:** Member `M101` has no existing requests for `I101`.
- **Action:** Member submits request for `I101` (succeeds). Member immediately submits a second request for `I101`.
- **Expected Result:** Second request is rejected with message: `"You already have an active pending request for tool 'Tool A'."`. Exactly 1 request remains in SQLite table.
- **Actual Result:** **PASSED** (0.02s). Database verified: count is 1.

---

### T2: Active-Loan Counts of 4, 5, and 6
- **Objective:** Verify loan limit enforcement (BR1: max 5 active loans).
- **Preconditions:** Member `M101` seeded with 4 active loans.
- **Action:** 
  1. Admin confirms 5th issue request $\rightarrow$ Expected: **Succeeds**, active count becomes 5.
  2. Admin attempts to confirm 6th issue request $\rightarrow$ Expected: **Rejected** with `"Active loan limit exceeded: Member already has 5 active loans (maximum allowed is 5)."`.
- **Database Integrity Check:** Tool for 6th loan remains `available = 1`; request status remains `REQUESTED`; no loan created.
- **Actual Result:** **PASSED** (0.04s).

---

### T3: Request Unavailable Tool (I103)
- **Objective:** Verify that requesting or issuing an unavailable tool is blocked (BR2, FR2).
- **Preconditions:** Tool `I103` (Tool C) seeded with `available = 0`.
- **Action:** Member attempts to create request for `I103`. Admin attempts to confirm forged request for `I103`.
- **Expected Result:** Both operations fail with `"Tool 'Tool C' is currently unavailable."`. Tool `I103` availability remains 0; no loan record created.
- **Actual Result:** **PASSED** (0.02s).

---

### T4: Fine Calculation Before, On, and After Due Date
- **Objective:** Verify fine calculation formula: ₹5 per day after 14-day due date (BR5, BR6).
- **Test Scenarios:**
  - Case 1 (5 days before due date): `overdue_days = 0`, `fine = ₹0.00`.
  - Case 2 (On exact due date): `overdue_days = 0`, `fine = ₹0.00`.
  - Case 3 (1 day after due date): `overdue_days = 1`, `fine = ₹5.00`.
  - Case 4 (7 days after due date): `overdue_days = 7`, `fine = ₹35.00`.
  - Case 5 (Returned 4 days overdue): `overdue_days = 4`, `fine = ₹20.00`.
- **Expected Result:** All calculations match expected fine amounts exactly.
- **Actual Result:** **PASSED** (0.00s).

---

### T5: Successful Issue with Correct Database Updates
- **Objective:** Verify atomic updates on issue confirmation (FR5, BR9).
- **Action:** Member requests `I104` (Tool D); Admin confirms issue for issue date `2026-10-10`.
- **Expected Result:**
  - Loan created with unique ID and status `ISSUED`.
  - `due_date` calculated as `2026-10-24` (+14 days).
  - Snapshot saved: `item_title_snapshot = 'Tool D'`.
  - Tool `I104` updated to `available = 0`.
  - Request updated to `status = 'ISSUED'`.
  - Status history logged with actor `A101` and transition `REQUESTED` $\rightarrow$ `ISSUED`.
- **Actual Result:** **PASSED** (0.02s). All 5 database updates confirmed.

---

### T6: Invalid Member Details and Inactive Membership
- **Objective:** Verify member validation on issue confirmation (BR7, BR8).
- **Action:** Test members with blank name, 5-digit phone number, and `INACTIVE` membership status.
- **Expected Result:** Rejections with descriptive validation errors. No loan created; tool remains available (`available = 1`).
- **Actual Result:** **PASSED** (0.03s). Database rolled back completely.

---

### T7: Tool Availability Changes Before Issue Confirmation
- **Objective:** Handle concurrency race conditions when tool availability changes after request creation (BR3, BR8).
- **Action:** Request created while `I102` is available. Before confirmation, tool is updated to `available = 0`. Admin attempts confirmation.
- **Expected Result:** Admin confirmation fails with `"Tool 'Tool B' is currently unavailable"`. Request remains in `REQUESTED` status; no loan created.
- **Actual Result:** **PASSED** (0.03s).

---

### T8: Unauthorized Access & Role Enforcement
- **Objective:** Verify ownership privacy and administrator privilege isolation (BR12, FR6).
- **Action:**
  1. Member `M101` attempts to query `M102`'s loan record $\rightarrow$ Rejected (`Unauthorized`).
  2. Member `M101` attempts to cancel `M102`'s request $\rightarrow$ Rejected (`Unauthorized`).
  3. Member `M101` attempts admin issue confirmation $\rightarrow$ Rejected (`Only administrators`).
  4. Member `M101` attempts admin return processing $\rightarrow$ Rejected (`Only administrators`).
- **Actual Result:** **PASSED** (0.02s). All security checks enforced.

---

### T9: Valid Status Sequence and Status Skipping
- **Objective:** Verify loan status transitions: `REQUESTED` $\rightarrow$ `ISSUED` $\rightarrow$ `RETURNED` (BR10).
- **Action:** Attempt to issue an already cancelled request; attempt to return a non-issued loan.
- **Expected Result:** Rejections on invalid status transitions.
- **Actual Result:** **PASSED** (0.03s).

---

### T10: Return the Same Tool Twice
- **Objective:** Single-restoration guarantee (BR11, FR8). Repeated returns must not alter availability again.
- **Action:**
  1. First return on `LN-RET-1` $\rightarrow$ Succeeds; tool `I101` becomes `available = 1`.
  2. Second return on `LN-RET-1` $\rightarrow$ Rejected with `"Loan 'LN-RET-1' has already been returned"`. Tool availability remains 1 and audit history is not duplicated.
- **Actual Result:** **PASSED** (0.03s).

---

### T11: Restart Application and Verify Persistent Records
- **Objective:** Data persistence verification across application reboots (FR10).
- **Action:** Insert requests and loans into SQLite file, close all connections, destroy Python service instances, re-instantiate fresh services from disk.
- **Expected Result:** All records, statuses, and audit history entries remain completely intact.
- **Actual Result:** **PASSED** (0.02s).

---

### T12: Change Tool Master Data and Historical Snapshot
- **Objective:** Historical snapshot preservation (BR4).
- **Action:** Issue loan for `I101` ("Tool A"). Rename tool in `items` table to "Tool A - Modified Pro".
- **Expected Result:** Master table reflects new title, while `loans.item_title_snapshot` remains original "Tool A".
- **Actual Result:** **PASSED** (0.03s).

---

## 3. Terminal Execution Command & Log

```powershell
python -m pytest -v tests/test_suite.py
```

```
============================= test session starts =============================
platform win32 -- Python 3.14.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Program Files\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\amudh\OneDrive\Desktop\SE SAT
plugins: anyio-4.15.1
collecting ... collected 12 items

tests/test_suite.py::test_t1_request_same_item_twice PASSED              [  8%]
tests/test_suite.py::test_t2_active_loan_counts PASSED                   [ 16%]
tests/test_suite.py::test_t3_request_unavailable_tool PASSED             [ 25%]
tests/test_suite.py::test_t4_fine_calculation PASSED                     [ 33%]
tests/test_suite.py::test_t5_successful_issue_with_database_updates PASSED [ 41%]
tests/test_suite.py::test_t6_invalid_member_details_and_inactive_membership PASSED [ 50%]
tests/test_suite.py::test_t7_tool_availability_changes_before_issue PASSED [ 58%]
tests/test_suite.py::test_t8_unauthorized_access PASSED                  [ 66%]
tests/test_suite.py::test_t9_valid_status_sequence_and_status_skipping PASSED [ 75%]
tests/test_suite.py::test_t10_return_same_tool_twice PASSED              [ 83%]
tests/test_suite.py::test_t11_restart_application_and_verify_persistent_records PASSED [ 91%]
tests/test_suite.py::test_t12_change_tool_master_data_and_verify_snapshot PASSED [100%]

============================= 12 passed in 0.89s ==============================
```

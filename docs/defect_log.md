# Defect Log & Engineering Resolution Report
**Project:** Tool Crib Management System — Industry Use Case 49  
**Assessment:** Software Engineering SAT II Assessment  
**Institution:** Sri Eshwar College of Engineering  

---

## 1. Defect Summary

| Defect ID | Severity | Component | Summary | Status |
|---|---|---|---|---|
| **DEF-01** | Low | Environment / Test Runner | Standalone `pytest` executable not resolved directly on Windows PowerShell PATH. | **RESOLVED** |
| **DEF-02** | High | `LoanService.confirm_issue_request` | Race condition where tool availability changes between member request submission and admin confirmation. | **RESOLVED** |
| **DEF-03** | High | `LoanService.process_return` | Double-return attempt restoring tool availability repeatedly and corrupting inventory counts. | **RESOLVED** |
| **DEF-04** | Medium | `Loan` Entity / DB Design | Future tool master data renaming altering historical loan records. | **RESOLVED** |
| **DEF-05** | High | `MemberService` / Routes | Missing ownership check allowing cross-member loan detail inspection. | **RESOLVED** |
| **DEF-06** | High | `app/routes/member_routes.py` | Administrator blocked with 403/redirect when trying to access `/inventory` or `/loans/<loan_id>`. | **RESOLVED** |
| **DEF-07** | Medium | `LoanService` / Admin Routes | Administrator lacked capability to reject invalid/unfulfillable requests (REQUESTED $\rightarrow$ REJECTED). | **RESOLVED** |
| **DEF-08** | Low | `app/routes/auth_routes.py` | Manual sign-in was case-sensitive, rejecting lowercase `m101` or `a101`. | **RESOLVED** |

---

## 2. Detailed Defect Analysis & Retest Outcomes

### Defect DEF-01: Standalone `pytest` Command Execution
- **Observed Behavior:** Running `pytest -v tests/test_suite.py` in PowerShell threw `CommandNotFoundException` because the scripts directory was not mapped in the Windows system environment PATH variable.
- **Root Cause:** Python 3.14 on Windows installs console scripts to user roaming directory by default.
- **Resolution:** Updated execution instructions and automated test commands to invoke `python -m pytest -v`, ensuring direct execution via the active Python binary.
- **Retest Outcome:** `python -m pytest -v` runs cleanly and discovers all 15 tests.

---

### Defect DEF-02: Race Condition on Delayed Issue Confirmation
- **Observed Behavior:** If Member Alice requested Tool B when available, but the workshop technician checked out Tool B in person before the admin confirmed Alice's request, confirming Alice's request would issue an already-unavailable tool.
- **Root Cause:** Checking tool availability only at request creation time instead of issue confirmation time violates BR3.
- **Resolution:** Added mandatory pre-flight recheck inside `LoanService.confirm_issue_request()` within a `BEGIN IMMEDIATE` transaction:
  ```python
  if item['available'] != 1:
      conn.rollback()
      return False, f"Tool '{item['title']}' is currently unavailable (already issued).", None
  ```
- **Retest Outcome:** Verified via Test **T7**. Confirmation is rejected, transaction is rolled back, and no partial DB updates occur.

---

### Defect DEF-03: Repeated Return Idempotency & Availability Corruption
- **Observed Behavior:** If an administrator accidentally clicked "Process Return" twice for the same loan, the tool availability was incremented, and status history was duplicated.
- **Root Cause:** Lack of state validation on loan return transition.
- **Resolution:** Added terminal status check enforcing that a loan can only transition to `RETURNED` from `ISSUED`:
  ```python
  if loan['status'] == 'RETURNED':
      conn.rollback()
      return False, f"Loan '{loan_id}' has already been returned on {loan['return_date']}. Repeated returns are rejected.", None
  ```
- **Retest Outcome:** Verified via Test **T10**. Second return attempt fails cleanly; availability remains 1 and is not altered.

---

### Defect DEF-04: Tool Master Data Renaming Mutating Historical Snapshots
- **Observed Behavior:** When a tool was renamed (e.g. "Tool A" $\rightarrow$ "Tool A - Pro"), historical loan records displayed the updated name instead of the original borrowed title.
- **Root Cause:** Dynamically joining `items.title` on loans instead of preserving a frozen snapshot.
- **Resolution:** Added `item_title_snapshot TEXT NOT NULL` column to the `loans` table, populated atomically during `confirm_issue_request()`.
- **Retest Outcome:** Verified via Test **T12**. Master title updated, snapshot preserved intact.

---

### Defect DEF-05: Cross-Member Loan Detail Access via URL Manipulation
- **Observed Behavior:** A member could view another member's loan record by guessing or typing the loan ID in the URL.
- **Root Cause:** Querying by `loan_id` without verifying `member_id == session['user_id']`.
- **Resolution:** Added strict ownership verification in `MemberService.get_member_loan_details()`:
  ```python
  if loan_dict['member_id'] != member_id:
      return False, None, "Unauthorized: You cannot access another member's loan record."
  ```
- **Retest Outcome:** Verified via Test **T8** and web route tests. Cross-member access returns HTTP 403 / Unauthorized flash error.

---

### Defect DEF-06: Administrator Inability to Access Tool Inventory and Loan Details
- **Observed Behavior:** When logged in as Librarian Admin (A101), visiting `/inventory` or `/loans/<loan_id>` redirected to dashboard with *"Access denied: Member view required."*
- **Root Cause:** Routes were decorated with `@member_required` instead of `@login_required`, and `MemberService.get_member_loan_details()` rejected any user ID that didn't match the loan's borrower ID.
- **Resolution:** Updated routes to use `@login_required`, added `is_admin` support to `get_member_loan_details()`, added Tool Catalog navigation link to the Administrator navbar, and added a "Details" button to the administrator loans view.
- **Retest Outcome:** Verified via `test_admin_can_access_inventory_and_view_loan_details`. Admin can inspect inventory with borrower metadata and view full loan breakdown.

---

### Defect DEF-07: Administrator Missing Capability to Reject Requests
- **Observed Behavior:** Administrators had no interface or endpoint to reject unfulfillable or invalid requests; requests remained in `REQUESTED` indefinitely.
- **Root Cause:** Missing `reject_issue_request()` service method and route handler.
- **Resolution:** Added `LoanService.reject_issue_request()` (`REQUESTED` $\rightarrow$ `REJECTED`), added route `POST /admin/requests/reject/<request_id>`, and added a Reject modal dialog with optional reason input to `admin_requests.html`.
- **Retest Outcome:** Verified via `test_admin_reject_request`. Status transitions to `REJECTED` and is logged in `loan_status_history`.

---

### Defect DEF-08: Case Sensitivity in Manual Role Login
- **Observed Behavior:** Typing lowercase `m101` or `a101` in the custom login form displayed *"User not found"*.
- **Root Cause:** SQLite `=` comparison on `id` was case-sensitive.
- **Resolution:** Updated query to `WHERE UPPER(id) = UPPER(?)`.
- **Retest Outcome:** Verified via `test_case_insensitive_login`. Both uppercase and lowercase logins succeed.

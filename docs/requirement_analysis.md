# Software Requirement Analysis & Specification
**Project:** Tool Crib Management System — Industry Use Case 49  
**Assessment:** Software Engineering SAT II Assessment  
**Institution:** Sri Eshwar College of Engineering  

---

## 1. Problem Statement
In industrial workshops and academic engineering laboratories, shared machine tools, precision calipers, diagnostic instruments, and specialized equipment are held within a central "tool crib". Without an automated tracking system, workshops experience lost inventory, unreturned or hoarding of tools, lack of audit trails, and untracked overdue penalties. 

The **Tool Crib Management System** provides an assessment-ready, reliable, and transactionally safe management solution enabling members to browse and request tools, while administrators enforce membership validation, 14-day loan limits, atomic issue operations, overdue fines (₹5/day), single-restoration returns, and immutable transaction status auditing.

---

## 2. Actors & System Roles
1. **Member (Borrower)**
   - Synthetic Accounts: `M101` (Alice Johnson), `M102` (Bob Smith).
   - Searches and browses active tools and real-time availability.
   - Creates and cancels their own borrowing requests.
   - Views own requests, loans, issue dates, due dates, and fine calculations.
   - Strictly restricted from accessing other members' data or performing administrator operations.
2. **Librarian / Administrator**
   - Synthetic Account: `A101` (Librarian Admin).
   - Oversees all inventory records, member requests, and loan statuses.
   - Re-validates member credentials, active-loan limit, and availability prior to confirming issues.
   - Processes tool returns, restoring inventory availability exactly once.
   - Audits historical transactions.

---

## 3. Functional Requirements (FR1 – FR10)

| Requirement ID | Title | Description |
|---|---|---|
| **FR1** | Tool Search | Display and search active tools by Tool ID, Title/Name, Category, and Availability status. |
| **FR2** | Issue Requests | Allow members to create and cancel their own requests. Prevent duplicate pending requests or requests for unavailable tools. A request does not guarantee issue confirmation. |
| **FR3** | Loan Details | Display issue date, due date (14 days), return date where applicable, loan status, and fine calculation breakdown. |
| **FR4** | Pre-Issue Validation | Before confirming an issue, re-validate member identity, active membership status, 10-digit phone, active-loan count (< 5), tool active flag, and current availability. |
| **FR5** | Successful Issue | Create one uniquely identified `ISSUED` loan, preserve a snapshot of the tool title, calculate 14-day due date, mark the tool unavailable, and record status history atomically. |
| **FR6** | Member Records Privacy | Ensure backend ownership filtering so each member only accesses their own requests and loans. |
| **FR7** | Status Management | Allow the administrator to perform only valid status transitions (`REQUESTED` $\rightarrow$ `ISSUED` $\rightarrow$ `RETURNED`). Reject status skipping. |
| **FR8** | Returns Processing | Process returns, calculate applicable overdue fine, set loan status to `RETURNED`, and restore tool availability exactly once. Prevent repeated returns. |
| **FR9** | Error Handling | Display clear notifications and return actionable validation errors for invalid details, unavailable tools, exceeded loan limits, unauthorized access, and invalid status transitions. |
| **FR10** | Database Persistence | Store users, items, requests, loans, and status history in a persistent SQLite database surviving application restarts. |

---

## 4. Exact Business Rules (BR1 – BR12)

1. **BR1 — Maximum Active Loan Limit:** A member may hold a maximum of **5 active loans** (`status = 'ISSUED'`). A sixth issue attempt must be rejected.
2. **BR2 — Tool Eligibility:** A tool can be issued only if it is active (`active = 1`) and available (`available = 1`).
3. **BR3 — Confirmation Recheck:** Tool availability and the member's loan limit must be re-checked at the exact moment of issue confirmation, preventing race conditions.
4. **BR4 — Historical Snapshot Preservation:** The original tool identifier, title, and issue conditions must be stored in the loan snapshot (`item_title_snapshot`), preserving historical integrity if master data changes later.
5. **BR5 — Standard Loan Period:** Standard loan period is exactly **14 days** (`due_date = issue_date + 14 days`).
6. **BR6 — Overdue Fine Calculation:** Fine = **₹5 per overdue day**, calculated strictly after the due date has passed. Loans returned on or before due date incur ₹0.00 fine.
7. **BR7 — Member Data Integrity:** Member ID and name cannot be blank. Phone must contain exactly 10 digits (`^\d{10}$`). Membership status must be `'ACTIVE'`.
8. **BR8 — Rollback on Validation Failure:** If validation fails, no loan is created, tool availability is unchanged, and transaction rolls back completely.
9. **BR9 — Atomic Confirmation Transaction:** Successful issue must create one `ISSUED` loan, preserve snapshot and dates, update availability (`available = 0`), and log status history in a single atomic database transaction.
10. **BR10 — Status Sequence Invariant:** Valid lifecycle is `REQUESTED` $\rightarrow$ `ISSUED` $\rightarrow$ `RETURNED`. A member may cancel their own `REQUESTED` request (`REQUESTED` $\rightarrow$ `CANCELLED`). Status skipping is rejected.
11. **BR11 — Single-Restoration Return:** Returning a tool marks status `RETURNED` and restores availability to 1 exactly once. Repeated returns are rejected and do not touch availability again.
12. **BR12 — Role Authorization Invariant:** Only administrators may confirm issues or process returns. Members may view or cancel only their own records.

---

## 5. Non-Functional Requirements (NFRs)
- **NFR1 — Data Consistency & Concurrency:** ACID transactions using SQLite immediate locks (`BEGIN IMMEDIATE`) to prevent concurrent double-booking of tools.
- **NFR2 — Security & Authorization:** Backend verification on every route and service call; role verification cannot be bypassed via direct URL requests.
- **NFR3 — Usability & Aesthetics:** Blue-and-white professional design built with Bootstrap 5, clear badges, intuitive tabular views, and responsive mobile-ready layout.
- **NFR4 — Testability:** 100% testable via automated pytest suite with zero external internet dependencies during test execution.

---

## 6. Assumptions & Scope
- **Scope:** Complete tool crib lifecycle for educational workshops: inventory catalog, borrow requests, approval confirmation, return tracking, overdue fines, and audit trail.
- **Assumptions:** 
  - Simulated authentication is sufficient for the SAT II academic assessment without requiring external SMTP or OAuth services.
  - Date manipulation for assessment viva is facilitated through interactive date simulation parameters.

---

## 7. Requirement Traceability Matrix (RTM)

| FR ID | Requirement Description | UML Element | Implementation Component | Test Case ID |
|---|---|---|---|---|
| **FR1** | Tool Search & Catalog | UC-02, `Item` | `MemberService.search_tools()`, `inventory.html` | T3, Web Tests |
| **FR2** | Issue Request Creation & Cancel | UC-03, UC-04, `LoanRequest` | `MemberService.create_issue_request()`, `MemberService.cancel_issue_request()` | T1, T3, T9 |
| **FR3** | Loan Details & Fines | UC-06, UC-07, `Loan` | `calculate_fine()`, `loan_detail.html` | T4 |
| **FR4** | Pre-issue Validation | UC-09, `User`, `Item` | `LoanService.confirm_issue_request()`, `MemberService.validate_member_details()` | T2, T6, T7 |
| **FR5** | Successful Atomic Issue | UC-10, `Loan`, `LoanStatusHistory` | `LoanService.confirm_issue_request()` | T5 |
| **FR6** | Member Records Privacy | UC-05, UC-06, `MemberService` | `MemberService.get_member_loan_details()`, `auth_helpers.py` | T8 |
| **FR7** | Status Management | UC-08, UC-10, `LoanService` | `LoanService.confirm_issue_request()`, `admin_routes.py` | T7, T9 |
| **FR8** | Single-Restoration Returns | UC-11, `Loan`, `Item` | `LoanService.process_return()` | T10 |
| **FR9** | Error Handling & Alerts | UC-09, UC-10, Flash UI | Service exception handling, flash banners | T1, T2, T3, T6, T8, T9, T10 |
| **FR10** | Persistent SQLite Storage | `database.py`, All Tables | `init_db()`, `seed_db()`, SQLite schema | T11, T12 |

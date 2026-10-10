# Tool Crib Management System — Industry Use Case 49
**Software Engineering SAT II Assessment**  
**Institution:** Sri Eshwar College of Engineering  
**Technology Stack:** Python Flask, SQLite, HTML5, CSS3, JavaScript, Bootstrap 5, Pytest  

---

## 1. Project Overview
The **Tool Crib Management System** is a full-stack, assessment-ready web application designed to regulate, track, and manage shared workshop tools in accordance with industrial standards and software engineering best practices.

The system strictly implements:
- **Two User Roles:** Member (Student/Technician) and Librarian/Administrator.
- **Persistent SQLite Database:** ACID transactions with `PRAGMA foreign_keys = ON;`.
- **Atomic Multi-Table Updates:** Concurrent loan issuance and return processing.
- **Exact Business Rules (BR1–BR12):** 5-loan maximum, 14-day standard borrowing period, ₹5/day overdue fines, 10-digit phone verification, historical snapshots, and single-restoration returns.
- **Complete Test Suite (T1–T12 & W1–W7):** 19 automated pytest tests passing with 100% success rate.

---

## 2. Sample Accounts & Seeded Data

### 2.1 Synthetic User Accounts
The system provides simulated, passwordless login for assessment demonstration:

| User ID | Full Name | System Role | Phone Number | Membership Status | Permissions |
|---|---|---|---|---|---|
| **M101** | Alice Johnson | **Member** | `9876543210` | `ACTIVE` | Search tools, create/cancel requests, view own loans & fines |
| **M102** | Bob Smith | **Member** | `9123456780` | `ACTIVE` | Verify data privacy & independent borrowing limit |
| **A101** | Librarian Admin | **Admin** | `9000000000` | `ACTIVE` | Confirm issue requests, process returns, view all history |

### 2.2 Initial Tool Master Records

| Tool ID | Tool Name | Category | Status | Initial Availability |
|---|---|---|---|---|
| **I101** | Tool A | Precision Hand Tools | Active | **Available** |
| **I102** | Tool B | Measuring Instruments | Active | **Available** |
| **I103** | Tool C | Machining & Diagnostic | Active | **Unavailable** |
| **I104** | Tool D | Cutting & Fabrication | Active | **Available** |

---

## 3. Quick Setup & Execution (Windows PowerShell)

### Prerequisites
- Python 3.10+ (Tested on Python 3.14.0)

### Step 1: Install Dependencies
Open Windows PowerShell in the project directory:
```powershell
pip install -r requirements.txt
```

### Step 2: Run All 15 Automated Tests
Execute the full pytest test suite (including all 12 mandatory assessment tests):
```powershell
python -m pytest -v
```

### Step 3: Start the Flask Application
Run the local server:
```powershell
python run.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 4. Assessment Demonstration Walkthrough

Follow this step-by-step walkthrough to demonstrate all functional requirements during the assessment and viva:

### Step 4.1: The Primary Demonstration Flow
1. **Login as Member Alice (M101):**
   - Click **"Log In as Alice"** on the home screen.
2. **Search Tools (FR1):**
   - Navigate to **"Tool Catalog"**.
   - Search for `"Tool A"` or filter by `"Available"`. Notice `I101` is Available and `I103` is Unavailable.
3. **Submit Issue Request (FR2):**
   - Click **"Request Tool"** next to `I101` (Tool A).
   - Confirmation notification appears: `Issue request 'REQ-...' created successfully`.
4. **Switch to Librarian Admin (A101):**
   - Use the top-right user switcher to log in as **Librarian Admin (A101)**.
5. **Confirm Issue Request (FR4, FR5, FR7):**
   - Navigate to **"Issue Requests"**.
   - Click **"Confirm Issue"** for Alice's request.
   - Pre-flight checks execute atomically: loan is created, tool `I101` is marked **Unavailable**, due date is set to +14 days, and history is logged.
6. **Verify Loan Details (FR3, FR6):**
   - Switch back to Alice (`M101`).
   - Go to **"My Loans"** and click **"View"** on the new loan.
   - Observe the **14-day due date**, the **Tool Snapshot (BR4)**, and fine breakdown.
7. **Simulate Overdue Fine (BR6 Viva Demo):**
   - On the "My Loans" page, use the **"Simulate Date"** picker to choose a date 16 days ahead (2 days past due date).
   - Notice the fine updates instantly to **₹10.00** ($2 \text{ days} \times ₹5.00$).
8. **Process Return (FR8, BR11):**
   - Switch to **Admin (A101)** and navigate to **"Active Loans & Returns"**.
   - Click **"Process Return"**.
   - Observe: Loan status becomes `RETURNED`, fine is computed, and tool `I101` availability is restored to **Available**.
9. **Verify Audit Trail (FR10):**
   - Navigate to **"Audit Trail"** to view the immutable event sequence (`REQUESTED` $\rightarrow$ `ISSUED` $\rightarrow$ `RETURNED`).

---

### Step 4.2: Demonstrating Negative & Invariant Tests
During the assessment viva, demonstrate how the system prevents invalid actions:

1. **Reject Duplicate Request (T1):**
   - While Alice has an active request for a tool, submitting another request for the same tool displays:
     *`"You already have an active pending request for tool..."`*
2. **Reject Request for Unavailable Tool I103 (T3):**
   - Attempting to request Tool C (`I103`) is rejected:
     *`"Tool 'Tool C' is currently unavailable."`*
3. **Reject 6th Active Loan (T2):**
   - A member holding 5 active loans cannot be issued another tool. The admin confirmation is aborted with zero database changes.
4. **Reject Unauthorized Access (T8):**
   - Alice cannot access Bob's loans or cancel Bob's requests. Typing an admin URL as a member triggers:
     *`"Access denied: Administrator privileges required."`*
5. **Reject Repeated Returns (T10):**
   - Attempting to return an already returned loan is rejected:
     *`"Loan has already been returned. Repeated returns are rejected."`*

---

## 5. Exact Business Rules Reference

| Rule ID | Rule Statement | Implementation Location |
|---|---|---|
| **BR1** | Max 5 active loans per member. 6th rejected. | `LoanService.confirm_issue_request()` |
| **BR2** | Tool issued only if active and available. | `MemberService.create_issue_request()`, `LoanService` |
| **BR3** | Recheck availability & limit at confirmation. | `LoanService.confirm_issue_request()` |
| **BR4** | Preserve immutable snapshot of tool title. | `loans.item_title_snapshot` |
| **BR5** | Standard loan period = 14 days. | `due_date = issue_date + timedelta(days=14)` |
| **BR6** | Overdue fine = ₹5 per overdue day after due date. | `calculate_fine()` |
| **BR7** | Member ID/Name not blank; 10-digit phone; ACTIVE. | `MemberService.validate_member_details()` |
| **BR8** | Complete rollback on validation failure. | SQLite transaction rollback |
| **BR9** | Atomic loan creation, availability update & history. | SQLite `BEGIN IMMEDIATE` |
| **BR10** | Lifecycle: REQUESTED $\rightarrow$ ISSUED $\rightarrow$ RETURNED. | Status transition checks |
| **BR11** | Return restores availability exactly once; no repeat. | `LoanService.process_return()` |
| **BR12** | Admin confirms/returns; Member views only own. | Route decorators & ownership checks |

---

## 6. Project Architecture & Directory Structure

```
SE SAT/
├── app/
│   ├── __init__.py              # Flask app factory, session context, template filters
│   ├── database.py              # SQLite connection, schema initialization, sample data
│   ├── models.py                # Data models: User, Item, LoanRequest, Loan, History
│   ├── services/
│   │   ├── __init__.py
│   │   ├── member_service.py    # Tool search, requests, ownership-filtered loans
│   │   └── loan_service.py      # Issue confirmation, return processing, fine calculator
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth_helpers.py      # Role & ownership authorization decorators
│   │   ├── auth_routes.py       # Simulated login, role switcher, logout
│   │   ├── member_routes.py     # Inventory, requests, my-loans, loan details
│   │   └── admin_routes.py      # Requests review, loan returns, audit history
│   ├── static/
│   │   └── css/
│   │       └── custom.css       # Blue-and-white responsive theme
│   └── templates/
│       ├── base.html            # Layout with navigation and flash messages
│       ├── login.html           # Role selection and login page
│       ├── dashboard.html       # Member and Admin dashboard views
│       ├── inventory.html       # Tool search and catalog (FR1)
│       ├── member_requests.html # Member request management (FR2, FR6)
│       ├── member_loans.html    # Member loan history and fine calculation (FR3, FR6)
│       ├── loan_detail.html     # Loan snapshot and fine breakdown (FR3)
│       ├── admin_requests.html  # Admin issue request confirmation (FR4, FR5, FR7)
│       ├── admin_loans.html     # Admin loan management and returns (FR7, FR8)
│       └── status_history.html  # Transaction audit history (FR5, FR10)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures and isolated temporary SQLite DB
│   ├── test_suite.py            # All 12 mandatory assessment tests (T1 to T12)
│   └── test_web_routes.py       # Integration tests for web routes & workflows
├── docs/
│   ├── requirement_analysis.md  # Detailed requirements, FR1–FR10, NFRs, RTM
│   ├── use_case_diagram.md      # Mermaid Use Case Diagram and descriptions
│   ├── class_diagram.md         # Mermaid Class Diagram and relationships
│   ├── database_schema.md       # SQLite schema, ER diagram, table dictionaries
│   ├── test_cases.md            # Test specifications and verified execution logs
│   ├── defect_log.md            # Observed defects, root causes, fixes, retests
│   └── ai_test_report.md        # AI usage documentation, metrics, limitations
├── run.py                       # Application execution entry point
├── requirements.txt             # Project dependencies
└── README.md                    # System documentation and execution guide
```

---

## 7. Documentation Index
The `docs/` folder contains comprehensive documentation ready for submission and viva:
- [Requirement Analysis & RTM](docs/requirement_analysis.md)
- [Use Case Diagram](docs/use_case_diagram.md)
- [Class Diagram](docs/class_diagram.md)
- [Database Schema Specification](docs/database_schema.md)
- [Test Cases & Verified Execution Log](docs/test_cases.md)
- [Defect Log](docs/defect_log.md)
- [AI Test & Engineering Report](docs/ai_test_report.md)

---

## 8. Limitations & Production Considerations
- **Simulated Authentication:** Built with single-click role switching for quick assessment demonstration. A production environment should integrate Active Directory / LDAP or bcrypt hashed credentials.
- **Physical Barcode / RFID Integration:** In a physical tool crib, barcode scanners can be connected to the tool ID search field for instant lookup.
- **Automated Alerts:** Celery or cron-based jobs can be scheduled to automatically notify members 2 days prior to loan expiration.
#   T o o l - c r i b - M a n a g e m e n t - S y s t e m  
 
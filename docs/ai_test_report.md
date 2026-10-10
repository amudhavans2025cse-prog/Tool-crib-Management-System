# AI Engineering & Automated Test Report
**Project:** Tool Crib Management System — Industry Use Case 49  
**Assessment:** Software Engineering SAT II Assessment  
**Institution:** Sri Eshwar College of Engineering  

---

## 1. AI Usage & Assistance Summary
During the development of the Tool Crib Management System, generative AI was utilized under strict architectural constraints to accelerate boilerplate scaffolding, construct deterministic automated test cases, and enforce formal verification against the SAT II assessment specification.

### Key Contributions of AI Pair-Programming:
1. **Architectural Partitioning:** Generated a clean MVC/Service separation (routes, models, services, templates, tests) preventing monolithic spaghetti code.
2. **Deterministic Test Construction:** Designed test cases T1 through T12 with strict database state assertions before and after rejected operations.
3. **Transaction Safety Formalization:** Recommended SQLite `BEGIN IMMEDIATE` transaction blocks to ensure atomic updates across 4 separate tables on issue confirmation.
4. **Interactive Viva Tools:** Designed dynamic date simulation query mechanisms allowing assessors to test overdue fine calculation on any arbitrary date without modifying the system clock.

---

## 2. Review of AI Suggestions & Human Oversight Decisions

| AI Proposal | Architectural Review & Decision | Rationale |
|---|---|---|
| Use external ORM (SQLAlchemy) | **Rejected**; used native `sqlite3` standard library with `sqlite3.Row` and `PRAGMA foreign_keys = ON;`. | Minimizes external dependency bloat, guarantees fast startup on Windows, and ensures exact control over atomic SQL transactions. |
| Store loan duration in days only | **Accepted with enhancement**; computed exact ISO dates (`issue_date`, `due_date = +14 days`). | Ensures deterministic, auditable date math and clean fine calculations across calendar months. |
| Use client-side JavaScript button hiding for role safety | **Rejected**; implemented backend role decorators (`@admin_required`, `@member_required`) and ownership checks. | Assessment requirement BR12 mandates backend security enforcement that cannot be bypassed via URL tampering. |
| Automatic password hashing (bcrypt) | **Simplified to simulated session login** with dropdown picker. | The SAT II assessment guidelines explicitly stated: *"A simple role selector or simulated login is sufficient for the assessment. Document the demo login process."* |

---

## 3. Test Counts & Execution Metrics

- **Unit & Business Logic Tests:** 12 tests (`tests/test_suite.py`)
- **Web Route & Integration Tests:** 7 tests (`tests/test_web_routes.py`)
- **Total Test Count:** **19 tests**
- **Passing Tests:** **19 (100%)**
- **Failing Tests:** **0**
- **Code Coverage Target Areas:**
  - Active loan count limit (4, 5, 6)
  - Duplicate request prevention
  - Unavailable tool blocking (I103)
  - Fine calculation (before, on, 1 day, 7 days overdue)
  - Atomic multi-table updates (Item, Request, Loan, History)
  - Member data validation (blank ID/name, phone regex, inactive status)
  - Concurrency & availability change before confirmation
  - Unauthorized access & ownership isolation
  - Status transition invariants & skipping rejection
  - Single-restoration return idempotency
  - SQLite disk file persistence across reboots
  - Historical tool snapshot immutability
  - Role-based dashboard routing & URL protection
  - Administrator request rejection & database reset

---

## 4. Defects Detected and Corrected
- **Defects Identified:** 8 defects (detailed in `docs/defect_log.md`).
- **Defect Resolution Rate:** 100% resolved and verified via automated test cases.
- **Key Vulnerability Fixed:** Concurrency race condition where tool availability changes between member request submission and admin confirmation (resolved with `BEGIN IMMEDIATE` re-check).

---

## 5. Limitations & Future Scope
1. **Authentication:** Simulated login is designed specifically for academic evaluation; in a production deployment, OAuth 2.0 / SSO or hashed password authentication with 2FA should be integrated.
2. **Tool Categorization:** Current system stores single-string categories; multi-level hierarchical categories or barcode/RFID scanner inputs could be added for industrial warehouse integration.
3. **Automated Reminders:** SMS or email overdue alerts can be scheduled via Celery/Redis background jobs.

# Class Diagram — Tool Crib Management System
**Industry Use Case 49 | Software Engineering SAT II Assessment**  
**Institution:** Sri Eshwar College of Engineering  

---

## 1. Overview
The Class Diagram models the core domain entities, data attributes, service boundaries, business methods, and relationship multiplicities implemented in the system.

---

## 2. Mermaid Class Diagram

```mermaid
classDiagram
    %% Domain Entities
    class User {
        +String id
        +String name
        +String role
        +String phone
        +String membership_status
        +from_row(row) User
    }

    class Item {
        +String id
        +String title
        +String category
        +int active
        +int available
        +String created_at
        +is_active() bool
        +is_available() bool
        +from_row(row) Item
    }

    class LoanRequest {
        +String id
        +String member_id
        +String item_id
        +String status
        +String created_at
        +from_row(row) LoanRequest
    }

    class Loan {
        +String id
        +String request_id
        +String member_id
        +String item_id
        +String item_title_snapshot
        +String issue_date
        +String due_date
        +String return_date
        +String status
        +float fine_amount
        +int overdue_days
        +from_row(row) Loan
    }

    class LoanStatusHistory {
        +int id
        +String reference_id
        +String actor_id
        +String old_status
        +String new_status
        +String event_at
        +from_row(row) LoanStatusHistory
    }

    %% Service Layer
    class MemberService {
        -String db_path
        +get_connection() Connection
        +validate_member_details(User) Tuple~bool, str~
        +get_member(String member_id) User
        +search_tools(String query, String category, String availability) List~dict~
        +get_categories() List~str~
        +get_tool_by_id(String item_id) Item
        +create_issue_request(String member_id, String item_id) Tuple~bool, str, str~
        +cancel_issue_request(String request_id, String member_id) Tuple~bool, str~
        +get_member_requests(String member_id) List~dict~
        +get_member_loans(String member_id, String as_of_date) List~dict~
        +get_member_loan_details(String loan_id, String member_id, String as_of_date) Tuple~bool, dict, str~
    }

    class LoanService {
        -String db_path
        +get_connection() Connection
        +validate_admin_actor(String actor_id) Tuple~bool, str~
        +get_active_loans_count(String member_id) int
        +confirm_issue_request(String request_id, String admin_id, String issue_date) Tuple~bool, str, str~
        +process_return(String loan_id, String admin_id, String return_date) Tuple~bool, str, dict~
        +get_all_requests() List~dict~
        +get_all_loans(String as_of_date) List~dict~
        +get_loan_by_id(String loan_id, String as_of_date) dict
        +get_status_history(String reference_id) List~dict~
        +get_dashboard_stats() dict
    }

    %% Relationships and Multiplicities
    User "1" <-- "0..*" LoanRequest : places
    Item "1" <-- "0..*" LoanRequest : references
    User "1" <-- "0..5" Loan : borrows (max 5 active)
    Item "1" <-- "0..*" Loan : tracks
    LoanRequest "0..1" <-- "0..1" Loan : originates_from
    User "1" <-- "0..*" LoanStatusHistory : acts_as
    
    MemberService ..> User : manages
    MemberService ..> Item : queries
    MemberService ..> LoanRequest : creates/cancels
    MemberService ..> Loan : reads

    LoanService ..> Loan : confirms/returns
    LoanService ..> LoanRequest : updates
    LoanService ..> Item : updates_availability
    LoanService ..> LoanStatusHistory : records
```

---

## 3. Class Attributes and Responsibilities Summary

1. **User**: Represents participants (Member, Admin). Enforces non-blank ID/name, exactly 10 digits for phone, and `ACTIVE` membership status.
2. **Item**: Master inventory record. Holds `active` flag (1=active, 0=inactive) and `available` flag (1=available, 0=unavailable).
3. **LoanRequest**: Pre-issue borrowing request. Status transitions: `REQUESTED` $\rightarrow$ `ISSUED` or `CANCELLED`.
4. **Loan**: Official loan record. Captures `item_title_snapshot` at issuance (BR4) to safeguard audit integrity against future master data renaming. Computes due date (`issue_date + 14 days`) and fine (`₹5 / overdue day`).
5. **LoanStatusHistory**: Immutable event log tracking every transition (`reference_id`, `actor_id`, `old_status`, `new_status`, `event_at`).
6. **MemberService**: Encapsulates all member operations, search filters, and strict ownership validation (`member_id` match required for data access).
7. **LoanService**: Encapsulates administrator operations, atomic issue confirmation transactions, 5-loan maximum check (BR1), single-return restoration guarantee (BR11), and fine calculation engine.

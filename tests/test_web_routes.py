import pytest
from app import create_app
from app.database import init_db, seed_db, get_db_connection


@pytest.fixture
def client(test_db):
    app = create_app({
        'TESTING': True,
        'DATABASE': test_db,
        'SECRET_KEY': 'test-secret'
    })
    with app.test_client() as client:
        yield client


def test_login_and_role_redirect(client):
    # Unauthenticated access to member dashboard redirects to login
    response = client.get('/dashboard')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

    # Log in as Member M101
    response = client.post('/login', data={'user_id': 'M101'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Alice Johnson" in response.data

    # Log in as Admin A101
    response = client.post('/login', data={'user_id': 'A101'}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Librarian Administrator Portal" in response.data


def test_member_cannot_access_admin_routes(client):
    # Log in as Member M101
    client.post('/login', data={'user_id': 'M101'}, follow_redirects=True)

    # Attempt to access admin requests page
    response = client.get('/admin/requests', follow_redirects=True)
    assert b"Access denied: Administrator privileges required." in response.data
    assert response.status_code == 200


def test_end_to_end_web_workflow(client):
    """
    Demonstration Workflow:
    Search Tool -> Create Request -> Admin Confirms -> View Loan -> Process Return -> Verify History
    """
    # 1. Member M101 logs in and browses tools
    client.post('/login', data={'user_id': 'M101'}, follow_redirects=True)
    res_inv = client.get('/inventory?q=Tool+A')
    assert b"Tool A" in res_inv.data

    # 2. Member creates request for I101 (Tool A)
    res_req = client.post('/requests/create', data={'item_id': 'I101'}, follow_redirects=True)
    assert b"created successfully" in res_req.data

    # 3. Admin A101 logs in and confirms request
    client.post('/login', data={'user_id': 'A101'}, follow_redirects=True)
    res_admin_req = client.get('/admin/requests')
    assert b"Tool A" in res_admin_req.data

    # Fetch request ID from db
    app_ctx_client = client
    # Find request id
    from app.database import get_db_connection
    # Extract request ID from page or query db
    res_confirm = None
    # Let's inspect loan_requests
    # We can confirm via admin route:
    import re
    match = re.search(r'action="/admin/requests/confirm/([^"]+)"', res_admin_req.data.decode('utf-8'))
    assert match is not None
    req_id = match.group(1)

    res_confirm = client.post(f'/admin/requests/confirm/{req_id}', follow_redirects=True)
    assert b"successfully issued" in res_confirm.data

    # 4. Member M101 logs in and checks loan details
    client.post('/login', data={'user_id': 'M101'}, follow_redirects=True)
    res_loans = client.get('/my-loans')
    assert b"Tool A" in res_loans.data

    loan_match = re.search(r'href="/loans/([^"?]+)', res_loans.data.decode('utf-8'))
    assert loan_match is not None
    loan_id = loan_match.group(1)

    res_detail = client.get(f'/loans/{loan_id}')
    assert b"Loan Lifecycle Dates" in res_detail.data
    assert b"Overdue Fine Breakdown" in res_detail.data

    # 5. Admin processes return
    client.post('/login', data={'user_id': 'A101'}, follow_redirects=True)
    res_return = client.post(f'/admin/loans/return/{loan_id}', follow_redirects=True)
    assert b"Tool returned successfully. Availability restored." in res_return.data

    # 6. Verify audit history
    res_history = client.get('/admin/history')
    assert loan_id.encode('utf-8') in res_history.data
    assert b"RETURNED" in res_history.data


def test_admin_can_access_inventory_and_view_loan_details(client):
    # 1. Member creates request and admin confirms it
    client.post('/login', data={'user_id': 'M101'}, follow_redirects=True)
    client.post('/requests/create', data={'item_id': 'I102'}, follow_redirects=True)

    client.post('/login', data={'user_id': 'A101'}, follow_redirects=True)
    res_admin_req = client.get('/admin/requests')
    import re
    match = re.search(r'action="/admin/requests/confirm/([^"]+)"', res_admin_req.data.decode('utf-8'))
    assert match is not None
    req_id = match.group(1)
    client.post(f'/admin/requests/confirm/{req_id}', follow_redirects=True)

    # 2. Admin can access inventory without being redirected away!
    res_inv = client.get('/inventory')
    assert res_inv.status_code == 200
    assert b"Borrowed by:" in res_inv.data
    assert b"Alice Johnson" in res_inv.data

    # 3. Admin can view loan details
    res_admin_loans = client.get('/admin/loans')
    loan_match = re.search(r'href="/loans/([^"?]+)', res_admin_loans.data.decode('utf-8'))
    assert loan_match is not None
    loan_id = loan_match.group(1)

    res_detail = client.get(f'/loans/{loan_id}')
    assert res_detail.status_code == 200
    assert b"Back to All Loans" in res_detail.data
    assert b"Tool B" in res_detail.data


def test_admin_reject_request(client):
    # Member M102 creates request for I104
    client.post('/login', data={'user_id': 'M102'}, follow_redirects=True)
    client.post('/requests/create', data={'item_id': 'I104'}, follow_redirects=True)

    # Admin rejects it
    client.post('/login', data={'user_id': 'A101'}, follow_redirects=True)
    res_admin_req = client.get('/admin/requests')
    import re
    match = re.search(r'action="/admin/requests/reject/([^"]+)"', res_admin_req.data.decode('utf-8'))
    assert match is not None
    req_id = match.group(1)

    res_reject = client.post(f'/admin/requests/reject/{req_id}', data={'reason': 'Maintenance scheduled'}, follow_redirects=True)
    assert b"has been rejected" in res_reject.data


def test_case_insensitive_login(client):
    # Lowercase m101
    res1 = client.post('/login', data={'user_id': 'm101'}, follow_redirects=True)
    assert res1.status_code == 200
    assert b"Alice Johnson" in res1.data

    # Lowercase a101
    res2 = client.post('/login', data={'user_id': 'a101'}, follow_redirects=True)
    assert res2.status_code == 200
    assert b"Librarian Administrator Portal" in res2.data


def test_admin_reset_database(client):
    # Admin resets database
    client.post('/login', data={'user_id': 'A101'}, follow_redirects=True)
    res_reset = client.post('/admin/reset-database', follow_redirects=True)
    assert res_reset.status_code == 200
    assert b"Database successfully reset" in res_reset.data

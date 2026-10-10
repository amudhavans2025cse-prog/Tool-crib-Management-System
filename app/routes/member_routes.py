from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from app.routes.auth_helpers import member_required, login_required
from app.services.member_service import MemberService
from app.services.loan_service import LoanService

member_bp = Blueprint('member', __name__)


def get_services():
    db_path = current_app.config['DATABASE']
    return MemberService(db_path), LoanService(db_path)


@member_bp.route('/dashboard')
@member_required
def dashboard():
    member_service, loan_service = get_services()
    member_id = session.get('user_id')

    requests = member_service.get_member_requests(member_id)
    loans = member_service.get_member_loans(member_id)
    stats = loan_service.get_dashboard_stats()

    active_loans_count = sum(1 for l in loans if l['status'] == 'ISSUED')
    pending_requests_count = sum(1 for r in requests if r['status'] == 'REQUESTED')
    total_fines = sum(l['fine_amount'] for l in loans if l['status'] == 'ISSUED')

    return render_template(
        'dashboard.html',
        role='Member',
        requests=requests[:5],
        loans=loans[:5],
        stats=stats,
        active_loans_count=active_loans_count,
        pending_requests_count=pending_requests_count,
        total_fines=total_fines
    )


@member_bp.route('/inventory')
@login_required
def inventory():
    """FR1: Display and search active tools by ID, title/name, category, and availability."""
    member_service, _ = get_services()
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    availability = request.args.get('availability', '').strip()

    tools = member_service.search_tools(query=query, category=category, availability=availability)
    categories = member_service.get_categories()

    return render_template(
        'inventory.html',
        tools=tools,
        categories=categories,
        current_query=query,
        current_category=category,
        current_availability=availability
    )


@member_bp.route('/requests')
@member_required
def requests_list():
    """FR2, FR6: Show member their own requests."""
    member_service, _ = get_services()
    member_id = session.get('user_id')
    my_requests = member_service.get_member_requests(member_id)
    available_tools = member_service.search_tools(availability='1')

    return render_template('member_requests.html', requests=my_requests, available_tools=available_tools)


@member_bp.route('/requests/create', methods=['POST'])
@member_required
def create_request():
    """FR2: Create issue request with validation."""
    member_service, _ = get_services()
    member_id = session.get('user_id')
    item_id = request.form.get('item_id', '').strip()

    if not item_id:
        flash("Please select a tool to request.", "danger")
        return redirect(url_for('member.requests_list'))

    success, message, req_id = member_service.create_issue_request(member_id, item_id)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('member.requests_list'))


@member_bp.route('/requests/cancel/<request_id>', methods=['POST'])
@member_required
def cancel_request(request_id):
    """FR2, BR10, BR12: Members may cancel their own REQUESTED request."""
    member_service, _ = get_services()
    member_id = session.get('user_id')

    success, message = member_service.cancel_issue_request(request_id, member_id)
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('member.requests_list'))


@member_bp.route('/my-loans')
@member_required
def my_loans():
    """FR3, FR6: Show member only their own loans with dates and calculated fines."""
    member_service, _ = get_services()
    member_id = session.get('user_id')
    simulated_date = request.args.get('as_of_date', '').strip() or None

    loans = member_service.get_member_loans(member_id, as_of_date=simulated_date)
    return render_template('member_loans.html', loans=loans, simulated_date=simulated_date)


@member_bp.route('/loans/<loan_id>')
@login_required
def loan_detail(loan_id):
    """FR3, FR6: Loan details with due date, return date, status, and fine."""
    member_service, _ = get_services()
    user_id = session.get('user_id')
    role = session.get('role')
    simulated_date = request.args.get('as_of_date', '').strip() or None

    is_admin = (role == 'Admin')
    success, loan, err = member_service.get_member_loan_details(
        loan_id=loan_id,
        member_id=user_id,
        as_of_date=simulated_date,
        is_admin=is_admin
    )
    if not success:
        flash(err, "danger")
        return redirect(url_for('admin.loans_management') if is_admin else url_for('member.my_loans'))

    return render_template('loan_detail.html', loan=loan, simulated_date=simulated_date)

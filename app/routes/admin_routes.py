from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from app.routes.auth_helpers import admin_required
from app.services.member_service import MemberService
from app.services.loan_service import LoanService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def get_services():
    db_path = current_app.config['DATABASE']
    return MemberService(db_path), LoanService(db_path)


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    _, loan_service = get_services()
    stats = loan_service.get_dashboard_stats()
    requests = loan_service.get_all_requests()[:5]
    loans = loan_service.get_all_loans()[:5]

    return render_template(
        'dashboard.html',
        role='Admin',
        stats=stats,
        requests=requests,
        loans=loans
    )


@admin_bp.route('/requests')
@admin_required
def requests_management():
    """FR7: View all requests and manage their statuses."""
    _, loan_service = get_services()
    all_requests = loan_service.get_all_requests()
    status_filter = request.args.get('status', '').strip()

    if status_filter:
        filtered_requests = [r for r in all_requests if r['status'] == status_filter]
    else:
        filtered_requests = all_requests

    return render_template(
        'admin_requests.html',
        requests=filtered_requests,
        current_status=status_filter
    )


@admin_bp.route('/requests/confirm/<request_id>', methods=['POST'])
@admin_required
def confirm_request(request_id):
    """FR4, FR5, FR7: Confirm valid issue request."""
    _, loan_service = get_services()
    admin_id = session.get('user_id')
    issue_date = request.form.get('issue_date', '').strip() or None

    success, message, loan_id = loan_service.confirm_issue_request(
        request_id=request_id,
        admin_id=admin_id,
        issue_date_str=issue_date
    )

    if success:
        flash(message, "success")
    else:
        flash(f"Confirmation Rejected: {message}", "danger")

    return redirect(url_for('admin.requests_management'))


@admin_bp.route('/requests/reject/<request_id>', methods=['POST'])
@admin_required
def reject_request(request_id):
    """FR7, BR10, BR12: Reject an invalid or unfulfillable issue request."""
    _, loan_service = get_services()
    admin_id = session.get('user_id')
    reason = request.form.get('reason', '').strip()

    success, message = loan_service.reject_issue_request(
        request_id=request_id,
        admin_id=admin_id,
        reason=reason
    )

    if success:
        flash(message, "info")
    else:
        flash(f"Rejection Failed: {message}", "danger")

    return redirect(url_for('admin.requests_management'))


@admin_bp.route('/reset-database', methods=['POST'])
@admin_required
def reset_database():
    """Reset database to initial sample data."""
    _, loan_service = get_services()
    admin_id = session.get('user_id')
    success, message = loan_service.reset_sample_data(admin_id=admin_id)

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/loans')
@admin_required
def loans_management():
    """FR7, FR8: Manage loans and return processing."""
    _, loan_service = get_services()
    simulated_date = request.args.get('as_of_date', '').strip() or None
    status_filter = request.args.get('status', '').strip()

    all_loans = loan_service.get_all_loans(as_of_date=simulated_date)
    if status_filter:
        filtered_loans = [l for l in all_loans if l['status'] == status_filter]
    else:
        filtered_loans = all_loans

    return render_template(
        'admin_loans.html',
        loans=filtered_loans,
        current_status=status_filter,
        simulated_date=simulated_date
    )


@admin_bp.route('/loans/return/<loan_id>', methods=['POST'])
@admin_required
def return_loan(loan_id):
    """FR8, BR11: Process return and restore tool availability exactly once."""
    _, loan_service = get_services()
    admin_id = session.get('user_id')
    return_date = request.form.get('return_date', '').strip() or None

    success, message, fine_info = loan_service.process_return(
        loan_id=loan_id,
        admin_id=admin_id,
        return_date_str=return_date
    )

    if success:
        flash(message, "success")
    else:
        flash(f"Return Rejected: {message}", "danger")

    return redirect(url_for('admin.loans_management'))


@admin_bp.route('/history')
@admin_required
def status_history():
    """FR5, FR10: Audit trail of all transactions and status transitions."""
    _, loan_service = get_services()
    ref_id = request.args.get('ref_id', '').strip() or None
    history = loan_service.get_status_history(reference_id=ref_id)

    return render_template(
        'status_history.html',
        history=history,
        ref_id=ref_id
    )

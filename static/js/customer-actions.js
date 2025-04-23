// Customer Actions JavaScript

// Handle form submissions
document.addEventListener('DOMContentLoaded', function() {
    // Deposit form
    const depositForm = document.querySelector('form[action*="deposit"]');
    if (depositForm) {
        depositForm.addEventListener('submit', function(e) {
            e.preventDefault();
            handleFormSubmission(this, 'deposit');
        });
    }

    // Withdraw form
    const withdrawForm = document.querySelector('form[action*="withdraw"]');
    if (withdrawForm) {
        withdrawForm.addEventListener('submit', function(e) {
            e.preventDefault();
            handleFormSubmission(this, 'withdraw');
        });
    }

    // Transfer form
    const transferForm = document.querySelector('form[action*="transfer"]');
    if (transferForm) {
        transferForm.addEventListener('submit', function(e) {
            e.preventDefault();
            handleFormSubmission(this, 'transfer');
        });
    }
});

// Handle form submission
function handleFormSubmission(form, action) {
    const formData = new FormData(form);
    const amount = parseFloat(formData.get('amount'));
    
    // Validate amount
    if (!amount || amount <= 0) {
        showAlert('Please enter a valid amount', 'error');
        return;
    }

    // Get CSRF token
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;

    // Submit form with fetch
    fetch(form.action, {
        method: 'POST',
        headers: {
            'X-CSRF-TOKEN': csrfToken,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            // Reload page after successful transaction
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showAlert(data.message || 'Transaction failed', 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert('An error occurred while processing your request', 'error');
    });
}

// Show alert message
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Insert alert at the top of the content
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);

    // Auto dismiss after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Handle account status changes
function handleAccountStatus(action, customerId) {
    const modal = document.getElementById(`${action}Modal`);
    const modalInstance = bootstrap.Modal.getInstance(modal);
    const notes = document.getElementById(`${action}Notes`).value;
    const reason = action === 'deactivate' ? document.getElementById('deactivationReason').value : '';

    fetch(`/admin/customer/${customerId}/${action}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-TOKEN': document.querySelector('input[name="csrf_token"]').value
        },
        body: JSON.stringify({ 
            notes: notes,
            reason: reason 
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            showAlert(data.message || `Failed to ${action} account`, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert(`An error occurred while ${action}ing the account`, 'error');
    })
    .finally(() => {
        modalInstance.hide();
    });
}

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(amount);
}

// Update balance display
function updateBalance(newBalance) {
    const balanceElement = document.querySelector('.current-balance');
    if (balanceElement) {
        balanceElement.textContent = formatCurrency(newBalance);
    }
} 
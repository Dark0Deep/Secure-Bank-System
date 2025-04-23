// Form validation
document.addEventListener('DOMContentLoaded', function() {
    // Password confirmation validation
    const passwordForm = document.querySelector('form');
    if (passwordForm) {
        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirm_password');
        
        if (password && confirmPassword) {
            passwordForm.addEventListener('submit', function(e) {
                if (password.value !== confirmPassword.value) {
                    e.preventDefault();
                    alert('Passwords do not match!');
                }
            });
        }
    }
    
    // Amount validation
    const amountInputs = document.querySelectorAll('input[type="number"]');
    amountInputs.forEach(input => {
        input.addEventListener('input', function() {
            if (this.value < 0) {
                this.value = 0;
            }
        });
    });
    
    // Auto-dismiss alerts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    });
});

// Format currency
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(amount);
}

// Confirm actions
function confirmAction(message) {
    return confirm(message);
}

// Handle loan application
document.addEventListener('DOMContentLoaded', function() {
    const loanForm = document.querySelector('.loan-form form');
    if (loanForm) {
        loanForm.addEventListener('submit', function(e) {
            const amount = document.getElementById('amount').value;
            const income = document.getElementById('income').value;
            
            if (amount > income * 12) {
                e.preventDefault();
                alert('Loan amount cannot exceed your annual income!');
            }
        });
    }
});

// Handle transfer confirmation
document.addEventListener('DOMContentLoaded', function() {
    const transferForm = document.querySelector('form[action*="transfer"]');
    if (transferForm) {
        transferForm.addEventListener('submit', function(e) {
            const amount = document.getElementById('amount').value;
            const recipient = document.getElementById('recipient').value;
            
            if (!confirm(`Are you sure you want to transfer ₹${amount} to ${recipient}?`)) {
                e.preventDefault();
            }
        });
    }
}); 
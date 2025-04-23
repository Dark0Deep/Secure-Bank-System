from app import mongo, app
from bson.objectid import ObjectId
import datetime
from werkzeug.security import generate_password_hash

def init_db():
    with app.app_context():
        # Check if admin user exists
        admin = mongo.db.users.find_one({'role': 'admin'})
        if not admin:
            # Create admin user
            admin_id = mongo.db.users.insert_one({
                'username': 'admin',
                'email': 'admin@example.com',
                'password': generate_password_hash('admin123'),
                'role': 'admin',
                'created_at': datetime.datetime.now()
            }).inserted_id
            print(f"Created admin user with ID: {admin_id}")
        
        # Create sample customers if none exist
        customers = list(mongo.db.users.find({'role': 'customer'}))
        if len(customers) == 0:
            # Create sample customers
            sample_customers = [
                {
                    'username': 'customer1',
                    'email': 'customer1@example.com',
                    'password': generate_password_hash('password123'),
                    'role': 'customer',
                    'created_at': datetime.datetime.now() - datetime.timedelta(days=5)
                },
                {
                    'username': 'customer2',
                    'email': 'customer2@example.com',
                    'password': generate_password_hash('password123'),
                    'role': 'customer',
                    'created_at': datetime.datetime.now() - datetime.timedelta(days=3)
                },
                {
                    'username': 'customer3',
                    'email': 'customer3@example.com',
                    'password': generate_password_hash('password123'),
                    'role': 'customer',
                    'created_at': datetime.datetime.now() - datetime.timedelta(days=1)
                }
            ]
            
            for customer in sample_customers:
                customer_id = mongo.db.users.insert_one(customer).inserted_id
                print(f"Created customer: {customer['username']} with ID: {customer_id}")
                
                # Create account for customer
                account_id = mongo.db.accounts.insert_one({
                    'user_id': customer_id,
                    'account_number': f"ACC{customer_id}",
                    'balance': 1000.00,
                    'created_at': datetime.datetime.now()
                }).inserted_id
                print(f"Created account for {customer['username']} with ID: {account_id}")
                
                # Create sample transactions
                transaction_types = ['deposit', 'withdrawal', 'transfer']
                for i in range(5):
                    transaction_type = transaction_types[i % 3]
                    amount = 100.00 * (i + 1)
                    
                    transaction_id = mongo.db.transactions.insert_one({
                        'user_id': customer_id,
                        'type': transaction_type,
                        'amount': amount,
                        'description': f'Sample {transaction_type} transaction',
                        'status': 'completed',
                        'created_at': datetime.datetime.now() - datetime.timedelta(days=i)
                    }).inserted_id
                    print(f"Created transaction for {customer['username']} with ID: {transaction_id}")
        
        print("Database initialization complete!")

if __name__ == "__main__":
    init_db() 
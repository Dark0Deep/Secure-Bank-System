from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os

def update_user_status():
    try:
        # Load environment variables
        load_dotenv()
        
        # Get MongoDB URI from environment variables, default to localhost if not found
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/bankdb')
        print(f"Attempting to connect to MongoDB at: {mongo_uri}")
        
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        
        # Test connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
        
        # Get database and collection
        db = client['bankdb']
        users = db['users']
        
        # Find the user first
        user_id = "67fe78aebe57baa12518a727"
        user = users.find_one({"_id": ObjectId(user_id)})
        
        if user:
            print(f"Found user: {user.get('username', 'N/A')}")
            print(f"Current active status: {user.get('is_active', False)}")
            
            # Update user status
            result = users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": True}}
            )
            
            if result.modified_count > 0:
                print("Successfully updated user status to active!")
            else:
                print("No update was needed - user might already be active")
                
            # Verify the update
            updated_user = users.find_one({"_id": ObjectId(user_id)})
            print(f"Current user status: {updated_user.get('is_active', False)}")
        else:
            print(f"No user found with ID: {user_id}")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed")

if __name__ == "__main__":
    update_user_status() 
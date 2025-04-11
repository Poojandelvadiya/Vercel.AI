import json
import os
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
import sys

def load_config():
    """Load the database configuration from JSON file"""
    try:
        with open('db_init.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Error: db_init.json file not found!")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON format in db_init.json!")
        sys.exit(1)

def connect_to_mongodb():
    """Establish connection to MongoDB Atlas"""
    load_dotenv()
    mongo_uri = os.getenv('MONGODB_URI')
    db_name = os.getenv('MONGODB_DB', 'Vercel')

    if not mongo_uri:
        print("Error: MONGODB_URI not found in .env file!")
        sys.exit(1)

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        # Test connection
        client.server_info()
        print(f"Successfully connected to MongoDB Atlas - Database: {db_name}")
        return db, client
    except ServerSelectionTimeoutError:
        print("Error: Could not connect to MongoDB Atlas. Please check your connection string and network connection.")
        sys.exit(1)
    except ConfigurationError as e:
        print(f"Error: MongoDB configuration error - {str(e)}")
        sys.exit(1)
    except OperationFailure as e:
        print(f"Error: Authentication failed - {str(e)}")
        sys.exit(1)

def create_collections_and_indexes(db, config):
    """Create collections and set up indexes"""
    try:
        # Create collections and insert data
        for collection_name, documents in config['collections'].items():
            if documents:  # Only create if there's data or it's explicitly defined
                print(f"Creating collection: {collection_name}")
                collection = db[collection_name]
                if documents:
                    collection.insert_many(documents)
                print(f"Successfully inserted {len(documents)} documents into {collection_name}")

        # Create indexes
        for collection_name, indexes in config['indexes'].items():
            collection = db[collection_name]
            for index in indexes:
                print(f"Creating index {index['name']} on {collection_name}")
                collection.create_index(
                    [(k, v) for k, v in index['key'].items()],
                    name=index['name'],
                    unique=index.get('unique', False),
                    expireAfterSeconds=index.get('expireAfterSeconds')
                )

        print("Successfully created all collections and indexes!")

    except Exception as e:
        print(f"Error during database initialization: {str(e)}")
        return False
    return True

def main():
    """Main function to initialize the database"""
    print("Starting database initialization...")
    
    # Load configuration
    config = load_config()
    
    # Connect to MongoDB
    db, client = connect_to_mongodb()
    
    try:
        # Initialize database
        success = create_collections_and_indexes(db, config)
        
        if success:
            print("\nDatabase initialization completed successfully!")
        else:
            print("\nDatabase initialization failed!")
            
    finally:
        # Close connection
        client.close()
        print("Database connection closed.")

if __name__ == "__main__":
    main() 
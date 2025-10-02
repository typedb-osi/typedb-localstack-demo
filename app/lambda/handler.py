import json
import sys
import time
import logging
import os
from datetime import datetime

from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType, TransactionOptions

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Timing decorator for functions
def log_execution_time(func_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000  # Convert to milliseconds
                logger.debug(f"Completed {func_name} in {duration:.2f}ms")
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.debug(f"Failed {func_name} after {duration:.2f}ms: {str(e)}")
                raise
        return wrapper
    return decorator


db_name = "test-db"
server_host = "typedb.localhost.localstack.cloud:4566"

# Global driver instance for reuse across Lambda invocations
_global_driver = None
_driver_created_at = None
_driver_timeout = 300  # 5 minutes timeout for driver reuse

def _transaction_options():
    """Get transaction options with configured timeout"""
    return TransactionOptions(transaction_timeout_millis=20_000)

def _cors_response(status_code, body):
    """Create a response with CORS headers"""
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization"
        },
        "body": json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    }

def handler(event, context):
    handler_start = time.time()
    logger.debug(f"Lambda invoked with event: {json.dumps(event, default=str)}")
    
    _create_database_and_schema()
    
    method = event["httpMethod"]
    path = event.get("path", "")
    
    # Handle CORS preflight requests
    if method == "OPTIONS":
        response = _cors_response(200, "")
    else:
        try:
            response = handle_request(event, method, path)
        except Exception as e:
            response = _cors_response(400, {"error": str(e)})
        
    handler_duration = (time.time() - handler_start) * 1000
    logger.debug(f"✅ Lambda handler completed in {handler_duration:.2f}ms")
    return response

def handle_request(event, method, path):
    # Route based on path and method
    if path == "/users":
        if method == "GET":
            result = list_users()
            return _cors_response(200, result)
        elif method == "POST":
            payload = json.loads(event["body"])
            result = create_user(payload)
            return _cors_response(201, result)
    elif path == "/groups":
        if method == "GET":
            result = list_groups()
            return _cors_response(200, result)
        elif method == "POST":
            payload = json.loads(event["body"])
            result = create_group(payload)
            return _cors_response(201, result)
    elif path.startswith("/groups/") and path.endswith("/members"):
        # Extract group_name from path like /groups/{group_name}/members
        group_name = path.split("/")[2]
        if method == "GET":
            result = list_direct_group_members(group_name)
            return _cors_response(200, result)
        elif method == "POST":
            payload = json.loads(event["body"])
            result = add_member_to_group(group_name, payload)
            return _cors_response(201, result)
    elif path.startswith("/groups/") and path.endswith("/all-members"):
        # Extract group_name from path like /groups/{group_name}/all-members
        group_name = path.split("/")[2]
        if method == "GET":
            result = list_all_group_members(group_name)
            return _cors_response(200, result)
    elif path.startswith("/users/") and path.endswith("/groups"):
        # Extract username from path like /users/{username}/groups
        username = path.split("/")[2]
        if method == "GET":
            result = list_principal_groups(username, "user")
            return _cors_response(200, result)
    elif path.startswith("/users/") and path.endswith("/all-groups"):
        # Extract username from path like /users/{username}/all-groups
        username = path.split("/")[2]
        if method == "GET":
            result = list_all_principal_groups(username, "user")
            return _cors_response(200, result)
    elif path.startswith("/groups/") and path.endswith("/groups"):
        # Extract group_name from path like /groups/{group_name}/groups
        group_name = path.split("/")[2]
        if method == "GET":
            result = list_principal_groups(group_name, "group")
            return _cors_response(200, result)
    elif path.startswith("/groups/") and path.endswith("/all-groups"):
        # Extract group_name from path like /groups/{group_name}/all-groups
        group_name = path.split("/")[2]
        if method == "GET":
            result = list_all_principal_groups(group_name, "group")
            return _cors_response(200, result)
    elif path == "/reset":
        if method == "POST":
            result = reset_database()
            return _cors_response(200, result)

    logger.debug(f"No route found for {method} request to {path}")
    return _cors_response(404, {"error": "Not found"})

@log_execution_time("create_user")
def create_user(payload: dict):
    logger.debug(f"Creating user")
    # Validate required fields
    if "username" not in payload:
        raise ValueError("Username is required")
    if "email" not in payload or not payload["email"]:
        raise ValueError("At least one email is required")
    
    username = payload["username"]
    emails = payload["email"]
    
    # Ensure emails is a list
    if isinstance(emails, str):
        emails = [emails]
    
    # Optional fields
    profile_picture_uri = payload.get("profile_picture_uri", "")
    
    try:
        with _driver().transaction(db_name, TransactionType.WRITE, _transaction_options()) as tx:
            # Create user with username
            query = f"insert $u isa user, has user-name '{username}'"
            
            # Add all emails
            for email in emails:
                query += f", has email '{email}'"
            
            # Add profile picture if provided - check if it's HTTP URL or S3 identifier
            if profile_picture_uri:
                if profile_picture_uri.startswith("http"):
                    query += f", has profile-picture-url '{profile_picture_uri}'"
                else:
                    query += f", has profile-picture-s3-uri '{profile_picture_uri}'"
            
            query += ";"
            
            tx.query(query).resolve()
            tx.commit()
        
        return {"message": "User created successfully", "username": username, "email": emails}
    
    except Exception as e:
        error_msg = str(e)
        if "DVL9" in error_msg and "key constraint violation" in error_msg:
            raise ValueError(f"User '{username}' already exists")
        else:
            raise e


@log_execution_time("create_group")
def create_group(payload: dict):
    logger.debug(f"Creating group")
    # Validate required fields
    if "group_name" not in payload:
        raise ValueError("Group name is required")
    
    group_name = payload["group_name"]
    
    try:
        with _driver().transaction(db_name, TransactionType.WRITE, _transaction_options()) as tx:
            # Create group with group name
            query = f"insert $g isa group, has group-name '{group_name}';"
            
            tx.query(query).resolve()
            tx.commit()
        
        return {"message": "Group created successfully", "group_name": group_name}
    
    except Exception as e:
        error_msg = str(e)
        if "DVL9" in error_msg and "key constraint violation" in error_msg:
            raise ValueError(f"Group '{group_name}' already exists")
        else:
            raise e


@log_execution_time("list_users")
def list_users():
    logger.debug("Listing users")
    driver_start = time.time()
    logger.debug("Listing users - opened driver")
    
    tx_start = time.time()
    with _driver().transaction(db_name, TransactionType.READ, _transaction_options()) as tx:
        
        query_start = time.time()
        result = tx.query(
            'match $u isa user; '
            'fetch {'
            '  "username": $u.user-name, '
            '  "email": [$u.email], '
            '  "profile_picture_url": $u.profile-picture-url, '
            '  "profile_picture_s3_uri": $u.profile-picture-s3-uri'
            '};'
        ).resolve().as_concept_documents()
        query_duration = (time.time() - query_start) * 1000
        
        list_start = time.time()
        result = list(result)
        list_duration = (time.time() - list_start) * 1000
        
    return result


@log_execution_time("list_groups")
def list_groups():
    logger.debug("Listing groups")
    with _driver().transaction(db_name, TransactionType.READ, _transaction_options()) as tx:
        result = tx.query(
            'match $g isa group; '
            'fetch {'
            '  "group_name": $g.group-name'
            '};'
        ).resolve().as_concept_documents()
        result = list(result)
    
    return result


@log_execution_time("add_member_to_group")
def add_member_to_group(group_name: str, payload: dict):
    logger.debug(f"Adding member to group")

    # Validate required fields - either username or group_name must be provided
    if "username" not in payload and "group_name" not in payload:
        raise ValueError("Either 'username' or 'group_name' is required")
    
    if "username" in payload and "group_name" in payload:
        raise ValueError("Provide either 'username' or 'group_name', not both")
    
    with _driver().transaction(db_name, TransactionType.WRITE, _transaction_options()) as tx:
            if "username" in payload:
                # Adding a user to the group
                username = payload["username"]
                query = (
                    f"match "
                    f"  $member isa user, has user-name '{username}'; "
                    f"  $group isa group, has group-name '{group_name}'; "
                    f"put "
                    f"  $membership isa membership (container: $group, member: $member);"
                )
                member_type = "user"
                member_name = username
            else:
                # Adding a group to the group
                member_group_name = payload["group_name"]
                query = (
                    f"match "
                    f"  $member isa group, has group-name '{member_group_name}'; "
                    f"  $group isa group, has group-name '{group_name}'; "
                    f"put "
                    f"  $membership isa membership (container: $group, member: $member);"
                )
                member_type = "group"
                member_name = member_group_name
        
            tx.query(query).resolve()
            tx.commit()
        
    return {
        "message": f"{member_type.capitalize()} added to group successfully", 
        "group_name": group_name, 
        "member_type": member_type,
        "member_name": member_name
    }

@log_execution_time("list_direct_group_members")
def list_direct_group_members(group_name: str):
    logger.debug(f"Listing direct group members for {group_name}")
    with _driver().transaction(db_name, TransactionType.READ, _transaction_options()) as tx:
            result = tx.query(
                f'match '
                f'  $group isa group, has group-name "{group_name}"; '
                f'  $membership isa membership (container: $group, member: $member); '
                f'  $member isa! $member-type; '
                f'fetch {{'
                f'  "member_name": $member.name, '
                f'  "group_name": $group.group-name,'
                f'  "member_type": $member-type'
                f'}};'
            ).resolve().as_concept_documents()
            result = list(result)
        
    return result

@log_execution_time("list_all_group_members")
def list_all_group_members(group_name: str):
    logger.debug(f"Listing all group members for {group_name}")
    with _driver().transaction(db_name, TransactionType.READ, _transaction_options()) as tx:
        # Use the group-members function from the schema to get all members recursively
        result = tx.query(
            f'match '
            f'  $group isa group, has group-name "{group_name}"; '
            f'  let $members in group-members($group); '
            f'  $member isa! $member-type; '
            f'fetch {{'
            f'  "member_type": $member-type, '
            f'  "member_name": $members.name, '
            f'  "group_name": $group.group-name'
            f'}};'
        ).resolve().as_concept_documents()
        result = list(result)
    
    return result


@log_execution_time("list_principal_groups")
def list_principal_groups(principal_name: str, principal_type: str):
    """List direct groups for either a user or group principal"""
    logger.debug(f"Listing direct groups for {principal_name} of type {principal_type}")
    with _driver().transaction(db_name, TransactionType.READ, _transaction_options()) as tx:
        if principal_type == "user":
            name_attr = "user-name"
        else:  # group
            name_attr = "group-name"
            
        result = tx.query(
            f'match '
            f'  $principal isa {principal_type}, has {name_attr} "{principal_name}"; '
            f'  membership (member: $principal, container: $group); '
            f'  $group isa group; '
            f'fetch {{'
            f'  "group_name": $group.group-name'
            f'}};'
        ).resolve().as_concept_documents()
        result = list(result)
    
    return result


@log_execution_time("list_all_principal_groups")
def list_all_principal_groups(principal_name: str, principal_type: str):
    """List all groups (transitive) for either a user or group principal"""
    logger.debug(f"Listing all groups for {principal_name} of type {principal_type}")
    with _driver().transaction(db_name, TransactionType.READ, _transaction_options()) as tx:
        if principal_type == "user":
            name_attr = "user-name"
        else:  # group
            name_attr = "group-name"
            
        # Use the get-groups function from the schema to get all groups transitively
        result = tx.query(
            f'match '
            f'  $principal isa {principal_type}, has {name_attr} "{principal_name}"; '
            f'  let $groups in get-groups($principal); '
            f'fetch {{'
            f'  "group_name": $groups.group-name'
            f'}};'
        ).resolve().as_concept_documents()
        result = list(result)
    
    return result


@log_execution_time("reset_database")
def reset_database():
    """Reset the database by deleting it and recreating it with schema"""
    logger.debug("Resetting database")
    
    driver = _driver()
    # Delete database if it exists
    if driver.databases.contains(db_name):
        driver.databases.get(db_name).delete()
        logger.debug(f"Database '{db_name}' deleted")

    _create_database_and_schema()
    
    return {"message": "Database reset successfully"}


@log_execution_time("_create_database_and_schema")
def _create_database_and_schema():
    driver = _driver()
    # Check if database exists, create only if it doesn't
    if db_name not in [db.name for db in driver.databases.all()]:
        driver.databases.create(db_name)
    
    entity_type_count = 0
    # Check if schema already exists by looking for user type
    schema_check_start = time.time()
    with _driver().transaction(db_name, TransactionType.READ, _transaction_options()) as tx:
        check_start = time.time()
        row = list(tx.query("match entity $t; reduce $count = count;").resolve().as_concept_rows())[0]
        check_duration = (time.time() - check_start) * 1000
    schema_check_duration = (time.time() - schema_check_start) * 1000
    logger.debug(f"📋 Schema check transaction completed in {schema_check_duration:.2f}ms")

    if row.get("count").get() == 0:
        logger.debug("Loading schema from file")
        schema_load_start = time.time()
        with _driver().transaction(db_name, TransactionType.SCHEMA, _transaction_options()) as schema_tx:
            # Load schema from file
            file_start = time.time()
            with open("schema.tql", "r") as f:
                schema_content = f.read()
            file_duration = (time.time() - file_start) * 1000
            
            query_start = time.time()
            schema_tx.query(schema_content).resolve()
            query_duration = (time.time() - query_start) * 1000
            
            commit_start = time.time()
            schema_tx.commit()
            commit_duration = (time.time() - commit_start) * 1000
        schema_load_duration = (time.time() - schema_load_start) * 1000
        logger.debug(f" --> Schema loaded successfully in {schema_load_duration:.2f}ms")
    else:
        logger.debug(" --> Schema already exists.")


def _driver():
    """Get or create a reusable TypeDB driver with connection pooling"""
    global _global_driver, _driver_created_at
    
    current_time = time.time()
    
    expired = _driver_created_at is not None and (current_time - _driver_created_at) > _driver_timeout
    # Check if we have a valid driver and it's not expired
    if _global_driver is not None and not expired:
        logger.debug(f"♻️  Reusing existing driver")
        return _global_driver
    elif expired:
        _cleanup_driver()
    
    # Create new driver or existing one is expired
    driver_start = time.time()
    try:
        _global_driver = TypeDB.driver(
            server_host,
            Credentials("admin", "password"),
            DriverOptions(is_tls_enabled=False),
        )
        _driver_created_at = current_time
        driver_duration = (time.time() - driver_start) * 1000
        logger.debug(f"✅ New driver created in {driver_duration:.2f}ms")
        return _global_driver
        
    except Exception as e:
        driver_duration = (time.time() - driver_start) * 1000
        logger.debug(f"❌ Failed to create driver after {driver_duration:.2f}ms: {str(e)}")
        # Clean up on failure
        _global_driver = None
        _driver_created_at = None
        raise


def _cleanup_driver():
    """Clean up the global driver - useful for testing or forced cleanup"""
    global _global_driver, _driver_created_at
    
    if _global_driver is not None:
        logger.debug("🧹 Cleaning up global driver")
        try:
            # TypeDB drivers don't have explicit close methods in the Python API
            # The connections will be cleaned up when the driver object is GC'd
            _global_driver = None
            _driver_created_at = None
            logger.debug("✅ Global driver cleaned up")
        except Exception as e:
            logger.debug(f"⚠️  Error cleaning up driver: {str(e)}")

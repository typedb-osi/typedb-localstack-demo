import json

from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType

db_name = "test-db"
server_host = "typedb.localhost.localstack.cloud:4566"


def handler(event, context):
    _create_database_and_schema()
    method = event["httpMethod"]
    path = event.get("path", "")
    
    try:
        # Route based on path and method
        if path == "/users":
            if method == "GET":
                result = list_users()
                return {"statusCode": 200, "body": json.dumps(result)}
            elif method == "POST":
                payload = json.loads(event["body"])
                result = create_user(payload)
                return {"statusCode": 201, "body": json.dumps(result)}
        elif path == "/groups":
            if method == "GET":
                result = list_groups()
                return {"statusCode": 200, "body": json.dumps(result)}
            elif method == "POST":
                payload = json.loads(event["body"])
                result = create_group(payload)
                return {"statusCode": 201, "body": json.dumps(result)}
        elif path.startswith("/groups/") and path.endswith("/members"):
            # Extract group_name from path like /groups/{group_name}/members
            group_name = path.split("/")[2]
            if method == "GET":
                result = list_direct_group_members(group_name)
                return {"statusCode": 200, "body": json.dumps(result)}
            elif method == "POST":
                payload = json.loads(event["body"])
                result = add_member_to_group(group_name, payload)
                return {"statusCode": 201, "body": json.dumps(result)}
        elif path.startswith("/groups/") and path.endswith("/all-members"):
            # Extract group_name from path like /groups/{group_name}/all-members
            group_name = path.split("/")[2]
            if method == "GET":
                result = list_all_group_members(group_name)
                return {"statusCode": 200, "body": json.dumps(result)}
        elif path.startswith("/users/") and path.endswith("/groups"):
            # Extract username from path like /users/{username}/groups
            username = path.split("/")[2]
            if method == "GET":
                result = list_principal_groups(username, "user")
                return {"statusCode": 200, "body": json.dumps(result)}
        elif path.startswith("/users/") and path.endswith("/all-groups"):
            # Extract username from path like /users/{username}/all-groups
            username = path.split("/")[2]
            if method == "GET":
                result = list_all_principal_groups(username, "user")
                return {"statusCode": 200, "body": json.dumps(result)}
        elif path.startswith("/groups/") and path.endswith("/groups"):
            # Extract group_name from path like /groups/{group_name}/groups
            group_name = path.split("/")[2]
            if method == "GET":
                result = list_principal_groups(group_name, "group")
                return {"statusCode": 200, "body": json.dumps(result)}
        elif path.startswith("/groups/") and path.endswith("/all-groups"):
            # Extract group_name from path like /groups/{group_name}/all-groups
            group_name = path.split("/")[2]
            if method == "GET":
                result = list_all_principal_groups(group_name, "group")
                return {"statusCode": 200, "body": json.dumps(result)}
        
        return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}
    except Exception as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


def create_user(payload: dict):
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
    
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.WRITE) as tx:
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


def create_group(payload: dict):
    # Validate required fields
    if "group_name" not in payload:
        raise ValueError("Group name is required")
    
    group_name = payload["group_name"]
    
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.WRITE) as tx:
            # Create group with group name
            query = f"insert $g isa group, has group-name '{group_name}';"
            
            tx.query(query).resolve()
            tx.commit()
    
    return {"message": "Group created successfully", "group_name": group_name}


def list_users():
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.READ) as tx:
            result = tx.query(
                'match $u isa user; '
                'fetch {'
                '  "username": $u.user-name, '
                '  "email": [$u.email], '
                '  "profile_picture_url": $u.profile-picture-url, '
                '  "profile_picture_s3_uri": $u.profile-picture-s3-uri'
                '};'
            ).resolve()
            result = list(result)
    return result


def list_groups():
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.READ) as tx:
            result = tx.query(
                'match $g isa group; '
                'fetch {'
                '  "group_name": $g.group-name'
                '};'
            ).resolve()
            result = list(result)
    return result


def add_member_to_group(group_name: str, payload: dict):
    # Validate required fields - either username or group_name must be provided
    if "username" not in payload and "group_name" not in payload:
        raise ValueError("Either 'username' or 'group_name' is required")
    
    if "username" in payload and "group_name" in payload:
        raise ValueError("Provide either 'username' or 'group_name', not both")
    
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.WRITE) as tx:
            if "username" in payload:
                # Adding a user to the group
                username = payload["username"]
                query = (
                    f"match "
                    f"  $member isa user, has user-name '{username}'; "
                    f"  $group isa group, has group-name '{group_name}'; "
                    f"put "
                    f"  $membership (container: $group, member: $member) isa membership;"
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
                    f"  $membership (container: $group, member: $member) isa membership;"
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


def list_direct_group_members(group_name: str):
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.READ) as tx:
            result = tx.query(
                f'match '
                f'  $group isa group, has group-name "{group_name}"; '
                f'  membership (container: $group, member: $member); '
                f'fetch {{'
                f'  "member_type": $member.isa, '
                f'  "member_name": $member.name, '
                f'  "group_name": $member.group-name'
                f'}};'
            ).resolve()
            result = list(result)
    return result


def list_all_group_members(group_name: str):
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.READ) as tx:
            # Use the group-members function from the schema to get all members recursively
            result = tx.query(
                f'match '
                f'  $group isa group, has group-name "{group_name}"; '
                f'  let $members in group-members($group); '
                f'fetch {{'
                f'  "member_type": $members.isa, '
                f'  "member_name": $members.name, '
                f'  "group_name": $members.group-name'
                f'}};'
            ).resolve()
            result = list(result)
    return result


def list_principal_groups(principal_name: str, principal_type: str):
    """List direct groups for either a user or group principal"""
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.READ) as tx:
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
            ).resolve()
            result = list(result)
    return result


def list_all_principal_groups(principal_name: str, principal_type: str):
    """List all groups (transitive) for either a user or group principal"""
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.READ) as tx:
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
            ).resolve()
            result = list(result)
    return result


def _create_database_and_schema():
    with _driver() as driver:
        # Check if database exists, create only if it doesn't
        if db_name not in [db.name for db in driver.databases.all()]:
            driver.databases.create(db_name)
        
        entity_type_count = 0
        # Check if schema already exists by looking for user type
        with driver.transaction(db_name, TransactionType.READ) as tx:
            entity_type_count = list(tx.query("match entity $t;").resolve().as_concept_rows()).len()

        if entity_type_count == 0:
            with driver.transaction(db_name, TransactionType.SCHEMA) as schema_tx:
                # Load schema from file
                with open("schema.tql", "r") as f:
                    schema_content = f.read()
                schema_tx.query(schema_content).resolve()
                schema_tx.commit()


def _driver():
    return TypeDB.driver(
        server_host,
        # TODO: make configurable
        Credentials("admin", "password"),
        DriverOptions(is_tls_enabled=False),
    )

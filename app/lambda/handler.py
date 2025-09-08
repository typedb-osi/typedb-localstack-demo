import json

from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType

db_name = "test-db"
server_host = "typedb.localhost.localstack.cloud:4566"


def handler(event, context):
    _create_database_and_schema()
    method = event["httpMethod"]
    result = {}
    if method == "GET":
        result = list_users()
    elif method == "POST":
        payload = json.loads(event["body"])
        result = create_user(payload)
    return {"statusCode": 200, "body": json.dumps(result)}


def create_user(payload: dict):
    user_name = payload["name"]
    user_age = payload["age"]
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.WRITE) as tx:
            query = f"insert $p isa person, has name '{user_name}', has age {user_age};"
            tx.query(query).resolve()
            tx.commit()


def list_users():
    with _driver() as driver:
        with driver.transaction(db_name, TransactionType.READ) as tx:
            result = tx.query(
                'match $p isa person; fetch {"name": $p.name, "age": $p.age};'
            ).resolve()
            result = list(result)
    return result


def _create_database_and_schema():
    with _driver() as driver:
        driver.databases.create(db_name)
        with driver.transaction(db_name, TransactionType.SCHEMA) as tx:
            tx.query("define entity person;").resolve()
            tx.query("define attribute name, value string; person owns name;").resolve()
            tx.query("define attribute age, value integer; person owns age;").resolve()
            tx.commit()


def _driver():
    return TypeDB.driver(
        server_host,
        # TODO: make configurable
        Credentials("admin", "password"),
        DriverOptions(is_tls_enabled=False),
    )

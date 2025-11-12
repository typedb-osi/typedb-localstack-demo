"""
HTTP-based TypeDB driver for Python
Ported from TypeScript implementation for lambda usage
"""

import json
import logging
import time
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class DriverParams:
    """Driver connection parameters"""
    username: str
    password: str
    addresses: List[str]


@dataclass
class TransactionOptions:
    """Transaction configuration options"""
    schema_lock_acquire_timeout_millis: Optional[int] = None
    transaction_timeout_millis: Optional[int] = None


@dataclass
class QueryOptions:
    """Query execution options"""
    include_instance_types: Optional[bool] = None
    answer_count_limit: Optional[int] = None


class TypeDBHttpError(Exception):
    """Base exception for TypeDB HTTP driver errors"""
    def __init__(self, message: str, code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class TypeDBHttpDriver:
    """HTTP-based TypeDB driver"""
    
    def __init__(self, params: DriverParams):
        self.params = params
        self.token: Optional[str] = None
        self.base_url = f"http://{params.addresses[0]}"
        
        # Setup HTTP session with retry strategy - optimized for Lambda
        self.session = requests.Session()
        
        # Lighter retry strategy for Lambda (fewer retries)
        retry_strategy = Retry(
            total=2,  # Reduced from 3
            backoff_factor=0.5,  # Faster backoff
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Pre-authenticate to reduce cold start time
        self._get_token()
    
    def _get_token(self) -> str:
        """Get authentication token, refreshing if necessary"""
        if self.token:
            return self.token
        
        return self._refresh_token()
    
    def _refresh_token(self) -> str:
        """Refresh authentication token"""
        url = f"{self.base_url}/v1/signin"
        payload = {
            "username": self.params.username,
            "password": self.params.password
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            self.token = data["token"]
            return self.token
            
        except requests.exceptions.RequestException as e:
            raise TypeDBHttpError(f"Failed to authenticate: {str(e)}")
    
    def _make_request(self, method: str, path: str, data: Optional[Dict] = None, 
                     params: Optional[Dict] = None) -> requests.Response:
        """Make authenticated HTTP request with automatic token refresh"""
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json"
        }
        
        try:
            response = self.session.request(
                method, url, json=data, params=params, headers=headers, timeout=30
            )
            
            # Handle token expiration
            if response.status_code == 401:
                self.token = None  # Clear expired token
                headers["Authorization"] = f"Bearer {self._get_token()}"
                response = self.session.request(
                    method, url, json=data, params=params, headers=headers, timeout=30
                )
            
            return response
            
        except requests.exceptions.RequestException as e:
            raise TypeDBHttpError(f"HTTP request failed: {str(e)}")
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle HTTP response and extract JSON data"""
        try:
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                error_code = error_data.get("code", None)
                raise TypeDBHttpError(error_msg, code=error_code, status_code=response.status_code)
            
            # Handle empty responses
            if not response.content:
                return {}
            
            return response.json()
            
        except json.JSONDecodeError as e:
            raise TypeDBHttpError(f"Invalid JSON response: {str(e)}")
    
    # Database operations
    def get_databases(self) -> List[Dict[str, str]]:
        """Get list of all databases"""
        response = self._make_request("GET", "/v1/databases")
        data = self._handle_response(response)
        return data.get("databases", [])
    
    def create_database(self, name: str) -> None:
        """Create a new database"""
        response = self._make_request("POST", f"/v1/databases/{name}", {})
        self._handle_response(response)
    
    def delete_database(self, name: str) -> None:
        """Delete a database"""
        response = self._make_request("DELETE", f"/v1/databases/{name}")
        self._handle_response(response)
    
    def database_exists(self, name: str) -> bool:
        """Check if a database exists"""
        databases = self.get_databases()
        return any(db["name"] == name for db in databases)
    
    # Transaction operations
    def open_transaction(self, database_name: str, transaction_type: str, 
                        options: Optional[TransactionOptions] = None) -> str:
        """Open a transaction and return transaction ID"""
        payload = {
            "databaseName": database_name,
            "transactionType": transaction_type
        }
        
        if options:
            transaction_options = {}
            if options.schema_lock_acquire_timeout_millis is not None:
                transaction_options["schemaLockAcquireTimeoutMillis"] = options.schema_lock_acquire_timeout_millis
            if options.transaction_timeout_millis is not None:
                transaction_options["transactionTimeoutMillis"] = options.transaction_timeout_millis
            payload["transactionOptions"] = transaction_options
        
        response = self._make_request("POST", "/v1/transactions/open", payload)
        data = self._handle_response(response)
        return data["transactionId"]
    
    def commit_transaction(self, transaction_id: str) -> None:
        """Commit a transaction"""
        response = self._make_request("POST", f"/v1/transactions/{transaction_id}/commit", {})
        self._handle_response(response)
    
    def close_transaction(self, transaction_id: str) -> None:
        """Close a transaction"""
        response = self._make_request("POST", f"/v1/transactions/{transaction_id}/close", {})
        self._handle_response(response)
    
    def rollback_transaction(self, transaction_id: str) -> None:
        """Rollback a transaction"""
        response = self._make_request("POST", f"/v1/transactions/{transaction_id}/rollback", {})
        self._handle_response(response)
    
    # Query operations
    def query(self, transaction_id: str, query: str, 
              options: Optional[QueryOptions] = None) -> Dict[str, Any]:
        """Execute a query in a transaction"""
        payload = {"query": query}
        
        if options:
            query_options = {}
            if options.include_instance_types is not None:
                query_options["includeInstanceTypes"] = options.include_instance_types
            if options.answer_count_limit is not None:
                query_options["answerCountLimit"] = options.answer_count_limit
            payload["queryOptions"] = query_options
        
        response = self._make_request("POST", f"/v1/transactions/{transaction_id}/query", payload)
        return self._handle_response(response)
    
    def one_shot_query(self, query: str, commit: bool, database_name: str, 
                      transaction_type: str, transaction_options: Optional[TransactionOptions] = None,
                      query_options: Optional[QueryOptions] = None) -> Dict[str, Any]:
        """Execute a one-shot query"""
        payload = {
            "query": query,
            "commit": commit,
            "databaseName": database_name,
            "transactionType": transaction_type
        }
        
        if transaction_options:
            tx_opts = {}
            if transaction_options.schema_lock_acquire_timeout_millis is not None:
                tx_opts["schemaLockAcquireTimeoutMillis"] = transaction_options.schema_lock_acquire_timeout_millis
            if transaction_options.transaction_timeout_millis is not None:
                tx_opts["transactionTimeoutMillis"] = transaction_options.transaction_timeout_millis
            payload["transactionOptions"] = tx_opts
        
        if query_options:
            q_opts = {}
            if query_options.include_instance_types is not None:
                q_opts["includeInstanceTypes"] = query_options.include_instance_types
            if query_options.answer_count_limit is not None:
                q_opts["answerCountLimit"] = query_options.answer_count_limit
            payload["queryOptions"] = q_opts
        
        response = self._make_request("POST", "/v1/query", payload)
        return self._handle_response(response)
    
    def close(self):
        """Close the driver and cleanup resources"""
        if hasattr(self, 'session'):
            self.session.close()


class Transaction:
    """Transaction context manager"""
    
    def __init__(self, driver: TypeDBHttpDriver, database_name: str, 
                 transaction_type: str, options: Optional[TransactionOptions] = None):
        self.driver = driver
        self.database_name = database_name
        self.transaction_type = transaction_type
        self.options = options
        self.transaction_id: Optional[str] = None
    
    def __enter__(self):
        self.transaction_id = self.driver.open_transaction(
            self.database_name, self.transaction_type, self.options
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.transaction_id:
            self.driver.close_transaction(self.transaction_id)
    
    def query(self, query: str, options: Optional[QueryOptions] = None) -> 'QueryResult':
        """Execute a query in this transaction"""
        if not self.transaction_id:
            raise TypeDBHttpError("Transaction not open")
        
        response = self.driver.query(self.transaction_id, query, options)
        return QueryResult(response)
    
    def commit(self):
        """Commit this transaction"""
        if not self.transaction_id:
            raise TypeDBHttpError("Transaction not open")
        
        self.driver.commit_transaction(self.transaction_id)
    
    def rollback(self):
        """Rollback this transaction"""
        if not self.transaction_id:
            raise TypeDBHttpError("Transaction not open")
        
        self.driver.rollback_transaction(self.transaction_id)


class QueryResult:
    """Query result wrapper with convenience methods"""
    
    def __init__(self, response: Dict[str, Any]):
        self.response = response
        self.answer_type = response.get("answerType", "ok")
        self.query_type = response.get("queryType", "read")
        self.comment = response.get("comment")
        self.query = response.get("query")
        self.answers = response.get("answers", [])
    
    def resolve(self) -> 'QueryResult':
        """Resolve the query result (for compatibility with GRPC driver)"""
        return self
    
    def as_concept_documents(self) -> List[Dict[str, Any]]:
        """Get results as concept documents"""
        if self.answer_type != "conceptDocuments":
            raise TypeDBHttpError(f"Cannot get concept documents from {self.answer_type} response")
        return self.answers
    
    def as_concept_rows(self) -> List[Dict[str, Any]]:
        """Get results as concept rows"""
        if self.answer_type != "conceptRows":
            raise TypeDBHttpError(f"Cannot get concept rows from {self.answer_type} response")
        return self.answers


# Convenience functions for compatibility with GRPC driver
def driver(address: str, credentials: 'Credentials', options: Optional[Dict] = None) -> TypeDBHttpDriver:
    """Create a TypeDB HTTP driver (compatibility function)"""
    params = DriverParams(
        username=credentials.username,
        password=credentials.password,
        addresses=[address]
    )
    return TypeDBHttpDriver(params)


# Transaction type constants for compatibility
class TransactionType:
    READ = "read"
    WRITE = "write"
    SCHEMA = "schema"


# Driver options for compatibility
class DriverOptions:
    def __init__(self, is_tls_enabled: bool = False):
        self.is_tls_enabled = is_tls_enabled


# Credentials for compatibility
class Credentials:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

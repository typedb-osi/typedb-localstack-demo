import requests
import json
import pytest
from time import sleep

class TestLambdaAPI:
    """Test the Lambda-based HTTP API endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test - ensure clean state"""
        self.base_url = "http://users-api.execute-api.localhost.localstack.cloud:4566/test"
        self.users_endpoint = f"{self.base_url}/users"
        self.groups_endpoint = f"{self.base_url}/groups"
        self.reset_endpoint = f"{self.base_url}/reset"
        
        # Reset database before each test
        self.reset_database()
    
    def reset_database(self):
        """Reset the database to ensure clean test state"""
        # Resetting database...
        response = requests.post(self.reset_endpoint)
        assert response.status_code == 200
        # Reset response processed
        
    def test_create_and_list_users(self):
        """Test creating users and listing them """
        # Creating user alice...
        alice_data = {
            "username": "alice",
            "email": ["alice@example.com", "alice.work@company.com"],
            "profile_picture_uri": "https://example.com/alice.jpg"
        }
        response = requests.post(
            self.users_endpoint,
            headers={'content-type': 'application/json'},
            json=alice_data
        )
        # Response processed
        assert response.status_code == 201
        assert response.json()["username"] == "alice"
        
        # Creating user bob...
        bob_data = {
            "username": "bob",
            "email": "bob@example.com"
        }
        response = requests.post(
            self.users_endpoint,
            headers={'content-type': 'application/json'},
            json=bob_data
        )
        # Response processed
        assert response.status_code == 201
        assert response.json()["username"] == "bob"
        
        # Listing all users...
        response = requests.get(self.users_endpoint)
        # Response processed
        assert response.status_code == 200
        
        users = response.json()
        assert len(users) == 2
        
        # Check alice
        alice = next(u for u in users if u["username"] == "alice")
        assert "alice@example.com" in alice["email"]
        assert "alice.work@company.com" in alice["email"]
        assert alice["profile_picture_url"] == "https://example.com/alice.jpg"
        assert alice["profile_picture_s3_uri"] is None
        
        # Check bob
        bob = next(u for u in users if u["username"] == "bob")
        assert bob["email"] == ["bob@example.com"]
        assert bob["profile_picture_url"] is None
        assert bob["profile_picture_s3_uri"] is None

    def test_duplicate_user_error(self):
        """Test that creating a duplicate user returns a proper error message"""
        user_data = {
            "username": "testuser",
            "email": "test@example.com"
        }
        
        # Create user first time - should succeed
        response = requests.post(
            self.users_endpoint,
            headers={'content-type': 'application/json'},
            json=user_data
        )
        assert response.status_code == 201
        
        # Try to create same user again - should fail with proper error
        response = requests.post(
            self.users_endpoint,
            headers={'content-type': 'application/json'},
            json=user_data
        )
        assert response.status_code == 400
        error_response = response.json()
        assert "already exists" in error_response["error"]
        assert "testuser" in error_response["error"]

    def test_create_and_list_groups(self):
        """Test creating groups and listing them"""
        # Creating group developers...
        group_data = {"group_name": "developers"}
        response = requests.post(
            self.groups_endpoint,
            headers={'content-type': 'application/json'},
            json=group_data
        )
        # Response processed
        assert response.status_code == 201
        assert response.json()["group_name"] == "developers"
        
        # Creating group managers...
        group_data = {"group_name": "managers"}
        response = requests.post(
            self.groups_endpoint,
            headers={'content-type': 'application/json'},
            json=group_data
        )
        # Response processed
        assert response.status_code == 201
        
        # Listing all groups...
        response = requests.get(self.groups_endpoint)
        # Response processed
        assert response.status_code == 200
        
        groups = response.json()
        assert len(groups) == 2
        group_names = [g["group_name"] for g in groups]
        assert "developers" in group_names
        assert "managers" in group_names

    def test_duplicate_group_error(self):
        """Test that creating a duplicate group returns a proper error message"""
        group_data = {"group_name": "testgroup"}
        
        # Create group first time - should succeed
        response = requests.post(
            self.groups_endpoint,
            headers={'content-type': 'application/json'},
            json=group_data
        )
        assert response.status_code == 201
        
        # Try to create same group again - should fail with proper error
        response = requests.post(
            self.groups_endpoint,
            headers={'content-type': 'application/json'},
            json=group_data
        )
        assert response.status_code == 400
        error_response = response.json()
        assert "already exists" in error_response["error"]
        assert "testgroup" in error_response["error"]

    def test_add_users_to_group(self):
        """Test adding users to groups"""
        # First create a user and group
        user_data = {"username": "groupuser", "email": "groupuser@example.com"}
        requests.post(self.users_endpoint, json=user_data, headers={'content-type': 'application/json'})
        
        group_data = {"group_name": "testgroup"}
        requests.post(self.groups_endpoint, json=group_data, headers={'content-type': 'application/json'})
        
        # Add user to group
        member_data = {"username": "groupuser"}
        response = requests.post(
            f"{self.base_url}/groups/testgroup/members",
            headers={'content-type': 'application/json'},
            json=member_data
        )
        assert response.status_code == 201
        assert "added to group successfully" in response.json()["message"]
        
        # List group members
        response = requests.get(f"{self.base_url}/groups/testgroup/members")
        assert response.status_code == 200
        members = response.json()
        assert len(members) == 1
        assert members[0]["member_name"] == "groupuser"
        assert members[0]["member_type"]["label"] == "user"

    def test_complex_workflow(self):
        """Test a more complex workflow: create users, groups, add members, check relationships"""
        # Complex Workflow Test
        
        # Create users
        users_data = [
            {"username": "alice", "email": "alice@company.com"},
            {"username": "bob", "email": "bob@company.com"},
            {"username": "charlie", "email": "charlie@company.com"}
        ]
        
        for user_data in users_data:
            response = requests.post(self.users_endpoint, json=user_data, headers={'content-type': 'application/json'})
            assert response.status_code == 201
            # User created
        
        # Create groups
        groups_data = [
            {"group_name": "developers"},
            {"group_name": "managers"},
            {"group_name": "seniors"}
        ]
        
        for group_data in groups_data:
            response = requests.post(self.groups_endpoint, json=group_data, headers={'content-type': 'application/json'})
            assert response.status_code == 201
            # Group created
        
        # Add users to groups
        memberships = [
            ("developers", "alice"),
            ("developers", "bob"),
            ("managers", "charlie"),
            ("seniors", "alice")
        ]
        
        for group_name, username in memberships:
            member_data = {"username": username}
            response = requests.post(
                f"{self.base_url}/groups/{group_name}/members",
                json=member_data,
                headers={'content-type': 'application/json'}
            )
            assert response.status_code == 201
            # User added to group
        
        # Verify memberships
        for group_name, expected_members in [("developers", ["alice", "bob"]), ("managers", ["charlie"]), ("seniors", ["alice"])]:
            response = requests.get(f"{self.base_url}/groups/{group_name}/members")
            assert response.status_code == 200
            members = response.json()
            member_names = [m["member_name"] for m in members]
            assert set(member_names) == set(expected_members)
            # Membership verified
        
        # Complex Workflow Test Complete

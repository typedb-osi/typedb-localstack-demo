// TypeDB User & Group Management Interface JavaScript

// Configuration
const API_BASE_URL = 'http://users-api.execute-api.localhost.localstack.cloud:4566/test';

// Global state
let currentUser = null;
let currentGroup = null;
let users = [];
let groups = [];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadInitialData();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Add user form submission
    document.getElementById('add-user-form').addEventListener('submit', handleAddUser);
    
    // Add group form submission
    document.getElementById('add-group-form').addEventListener('submit', handleAddGroup);
}

// Tab switching
function showTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab content
    document.getElementById(tabName + '-tab').classList.add('active');
    
    // Add active class to clicked button
    event.target.classList.add('active');
    
    // Clear main content
    clearMainContent();
}

// Clear main content
function clearMainContent() {
    document.getElementById('welcome-message').style.display = 'block';
    document.getElementById('user-details').style.display = 'none';
    document.getElementById('group-details').style.display = 'none';
    currentUser = null;
    currentGroup = null;
}

// API Functions
async function apiRequest(endpoint, method = 'GET', data = null) {
    const url = `${API_BASE_URL}${endpoint}`;
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        }
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    // Start timing
    const startTime = performance.now();
    const timestamp = new Date().toISOString();
    
    try {
        console.log(`🚀 API Request [${timestamp}]: ${method} ${endpoint}`, data ? { data } : '');
        const response = await fetch(url, options);
        const result = await response.json();
        
        // Calculate duration
        const duration = performance.now() - startTime;
        
        if (!response.ok) {
            console.error(`❌ API Error [${duration.toFixed(2)}ms]: ${method} ${endpoint}`, result.error || `HTTP ${response.status}`);
            throw new Error(result.error || `HTTP ${response.status}`);
        }
        
        console.log(`✅ API Success [${duration.toFixed(2)}ms]: ${method} ${endpoint}`, {
            status: response.status,
            dataSize: JSON.stringify(result).length + ' bytes',
            result: result
        });
        
        return result;
    } catch (error) {
        const duration = performance.now() - startTime;
        console.error(`❌ API Error [${duration.toFixed(2)}ms]: ${method} ${endpoint}`, error);
        throw error;
    }
}

// Load initial data concurrently
async function loadInitialData() {
    try {
        const startTime = performance.now();
        console.log('🔄 Loading initial data concurrently...');
        
        // Load users and groups in parallel
        const [usersData, groupsData] = await Promise.all([
            apiRequest('/users'),
            apiRequest('/groups')
        ]);
        
        users = usersData;
        groups = groupsData;
        
        // Render both lists
        renderUsersList();
        renderGroupsList();
        
        const totalDuration = performance.now() - startTime;
        console.log(`✅ Initial data loaded successfully in ${totalDuration.toFixed(2)}ms (concurrent loading)`);
    } catch (error) {
        console.error('Failed to load initial data:', error);
        showError('Failed to load data: ' + error.message);
    }
}

// Load users (for individual reloads)
async function loadUsers() {
    try {
        users = await apiRequest('/users');
        renderUsersList();
    } catch (error) {
        console.error('Failed to load users:', error);
        showError('Failed to load users: ' + error.message);
    }
}

// Load groups (for individual reloads)
async function loadGroups() {
    try {
        groups = await apiRequest('/groups');
        renderGroupsList();
    } catch (error) {
        console.error('Failed to load groups:', error);
        showError('Failed to load groups: ' + error.message);
    }
}

// Render users list
function renderUsersList() {
    const usersList = document.getElementById('users-list');
    usersList.innerHTML = '';
    
    users.forEach(user => {
        const userItem = document.createElement('div');
        userItem.className = 'list-item';
        userItem.textContent = user.username;
        userItem.onclick = () => selectUser(user);
        usersList.appendChild(userItem);
    });
}

// Render groups list
function renderGroupsList() {
    const groupsList = document.getElementById('groups-list');
    groupsList.innerHTML = '';
    
    groups.forEach(group => {
        const groupItem = document.createElement('div');
        groupItem.className = 'list-item';
        groupItem.textContent = group.group_name;
        groupItem.onclick = () => selectGroup(group);
        groupsList.appendChild(groupItem);
    });
}

// Select user
async function selectUser(user) {
    // Update UI state
    document.querySelectorAll('#users-list .list-item').forEach(item => {
        item.classList.remove('selected');
    });
    event.target.classList.add('selected');
    
    // Clear group details
    document.getElementById('group-details').style.display = 'none';
    
    // Show user details
    document.getElementById('welcome-message').style.display = 'none';
    document.getElementById('user-details').style.display = 'block';
    
    currentUser = user;
    
    // Update user name
    document.getElementById('user-name').textContent = user.username;
    
    // Update user info
    const userInfo = document.getElementById('user-info');
    userInfo.innerHTML = `
        <div class="detail-item">
            <span class="detail-label">Username:</span>
            <span class="detail-value">${user.username}</span>
        </div>
        <div class="detail-item">
            <span class="detail-label">Email:</span>
            <span class="detail-value">${Array.isArray(user.email) ? user.email.join(', ') : user.email}</span>
        </div>
        ${user.profile_picture_url ? `
        <div class="detail-item">
            <span class="detail-label">Profile Picture:</span>
            <span class="detail-value">${user.profile_picture_url}</span>
        </div>
        ` : ''}
    `;
    
    // Load user groups
    await loadUserGroups(user.username);
}

// Load user groups
async function loadUserGroups(username) {
    try {
        const startTime = performance.now();
        console.log(`🔄 Loading user groups concurrently for ${username}...`);
        
        // Load direct groups and all groups in parallel
        const [directGroups, allGroups] = await Promise.all([
            apiRequest(`/users/${username}/groups`),
            apiRequest(`/users/${username}/all-groups`)
        ]);
        
        // Render direct groups
        const directGroupsDiv = document.getElementById('user-direct-groups');
        if (directGroups.length > 0) {
            directGroupsDiv.innerHTML = directGroups.map(group => 
                `<span class="group-tag">${group.group_name}</span>`
            ).join('');
        } else {
            directGroupsDiv.innerHTML = '<span class="group-tag empty">No direct groups</span>';
        }
        
        // Render all groups
        const allGroupsDiv = document.getElementById('user-all-groups');
        if (allGroups.length > 0) {
            allGroupsDiv.innerHTML = allGroups.map(group => 
                `<span class="group-tag">${group.group_name}</span>`
            ).join('');
        } else {
            allGroupsDiv.innerHTML = '<span class="group-tag empty">No groups</span>';
        }
        
        const totalDuration = performance.now() - startTime;
        console.log(`✅ User groups loaded successfully for ${username} in ${totalDuration.toFixed(2)}ms (concurrent loading)`);
    } catch (error) {
        console.error('Failed to load user groups:', error);
        document.getElementById('user-direct-groups').innerHTML = '<span class="error">Failed to load groups</span>';
        document.getElementById('user-all-groups').innerHTML = '<span class="error">Failed to load groups</span>';
    }
}

// Select group
async function selectGroup(group) {
    // Update UI state
    document.querySelectorAll('#groups-list .list-item').forEach(item => {
        item.classList.remove('selected');
    });
    event.target.classList.add('selected');
    
    // Clear user details
    document.getElementById('user-details').style.display = 'none';
    
    // Show group details
    document.getElementById('welcome-message').style.display = 'none';
    document.getElementById('group-details').style.display = 'block';
    
    currentGroup = group;
    
    // Update group name
    document.getElementById('group-name').textContent = group.group_name;
    
    // Update group info
    const groupInfo = document.getElementById('group-info');
    groupInfo.innerHTML = `
        <div class="detail-item">
            <span class="detail-label">Group Name:</span>
            <span class="detail-value">${group.group_name}</span>
        </div>
    `;
    
    // Load group relationships
    await loadGroupRelationships(group.group_name);
}

// Load group relationships
async function loadGroupRelationships(groupName) {
    try {
        const startTime = performance.now();
        console.log(`🔄 Loading relationships concurrently for group: ${groupName}`);
        
        // Load all group relationship data in parallel
        const [parentGroups, allParentGroups, directMembers, allMembers] = await Promise.all([
            apiRequest(`/groups/${groupName}/groups`),
            apiRequest(`/groups/${groupName}/all-groups`),
            apiRequest(`/groups/${groupName}/members`),
            apiRequest(`/groups/${groupName}/all-members`)
        ]);
        
        console.log(`Direct parent groups for ${groupName}:`, parentGroups);
        console.log(`All parent groups for ${groupName}:`, allParentGroups);
        console.log(`Direct members for ${groupName}:`, directMembers);
        console.log(`All members for ${groupName}:`, allMembers);
        
        // Render parent groups (direct)
        const parentGroupsDiv = document.getElementById('group-parent-groups');
        if (parentGroups.length > 0) {
            parentGroupsDiv.innerHTML = parentGroups.map(group => 
                `<span class="group-tag">${group.group_name}</span>`
            ).join('');
        } else {
            parentGroupsDiv.innerHTML = '<span class="group-tag empty">Not a member of any groups</span>';
        }
        
        // Render parent groups (all including indirect)
        const allParentGroupsDiv = document.getElementById('group-all-parent-groups');
        if (allParentGroups.length > 0) {
            allParentGroupsDiv.innerHTML = allParentGroups.map(group => 
                `<span class="group-tag">${group.group_name}</span>`
            ).join('');
        } else {
            allParentGroupsDiv.innerHTML = '<span class="group-tag empty">Not a member of any groups</span>';
        }
        
        // Filter and render direct child groups
        const childGroups = directMembers.filter(member => member.member_type.label === 'group');
        console.log(`Direct child groups for ${groupName}:`, childGroups);
        const childGroupsDiv = document.getElementById('group-child-groups');
        if (childGroups.length > 0) {
            childGroupsDiv.innerHTML = childGroups.map(member => 
                `<span class="group-tag">${member.member_name}</span>`
            ).join('');
        } else {
            childGroupsDiv.innerHTML = '<span class="group-tag empty">No direct groups</span>';
        }
        
        // Filter and render all child groups (including indirect)
        const allChildGroups = allMembers.filter(member => member.member_type.label === 'group');
        console.log(`All child groups for ${groupName}:`, allChildGroups);
        const allChildGroupsDiv = document.getElementById('group-all-child-groups');
        if (allChildGroups.length > 0) {
            allChildGroupsDiv.innerHTML = allChildGroups.map(member => 
                `<span class="group-tag">${member.member_name}</span>`
            ).join('');
        } else {
            allChildGroupsDiv.innerHTML = '<span class="group-tag empty">No groups</span>';
        }
        
        const totalDuration = performance.now() - startTime;
        console.log(`✅ Group relationships loaded successfully for ${groupName} in ${totalDuration.toFixed(2)}ms (concurrent loading)`);
    } catch (error) {
        console.error('Failed to load group relationships:', error);
        showError('Failed to load group relationships: ' + error.message);
    }
}

// Modal functions
function showAddUserForm() {
    document.getElementById('add-user-modal').style.display = 'block';
}

function showAddGroupForm() {
    document.getElementById('add-group-modal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
    // Clear form
    if (modalId === 'add-user-modal') {
        document.getElementById('add-user-form').reset();
    } else if (modalId === 'add-group-modal') {
        document.getElementById('add-group-form').reset();
    }
}

// Handle add user
async function handleAddUser(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const userData = {
        username: formData.get('username'),
        email: formData.get('email'),
    };
    
    if (formData.get('profile-picture')) {
        userData.profile_picture_uri = formData.get('profile-picture');
    }
    
    try {
        await apiRequest('/users', 'POST', userData);
        closeModal('add-user-modal');
        await loadUsers(); // Reload users list
        showSuccess('User created successfully!');
    } catch (error) {
        showError('Failed to create user: ' + error.message);
    }
}

// Handle add group
async function handleAddGroup(event) {
    event.preventDefault();
    
    const formData = new FormData(event.target);
    const groupData = {
        group_name: formData.get('group-name')
    };
    
    try {
        await apiRequest('/groups', 'POST', groupData);
        closeModal('add-group-modal');
        await loadGroups(); // Reload groups list
        showSuccess('Group created successfully!');
    } catch (error) {
        showError('Failed to create group: ' + error.message);
    }
}

// Utility functions
function showError(message) {
    // Simple error display - could be enhanced with a proper notification system
    alert('Error: ' + message);
}

function showSuccess(message) {
    // Simple success display - could be enhanced with a proper notification system
    alert('Success: ' + message);
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    });
}

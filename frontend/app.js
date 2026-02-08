// Configuration
const CONFIG = {
    BACKEND_URL: 'https://chatbot-backend-795588981144.us-central1.run.app',
    FIREBASE_CONFIG: {
        apiKey: "AIzaSyDummy", // Placeholder - will work without valid key for read access with security rules
        authDomain: "helpful-charmer-485315-j7.firebaseapp.com",
        projectId: "helpful-charmer-485315-j7",
    }
};

// Initialize Firebase
let db = null;
try {
    firebase.initializeApp(CONFIG.FIREBASE_CONFIG);
    db = firebase.firestore();
    console.log('✅ Firebase initialized successfully');
} catch (error) {
    console.error('❌ Firebase initialization failed:', error);
    console.warn('⚠️ Will fall back to polling if needed');
}

// State
let sessionId = null;
let currentRequestId = null;
let extractedEntities = {};
let statusListener = null;  // Firestore listener unsubscribe function

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const sessionIdDisplay = document.getElementById('sessionId');
const sessionStatusDisplay = document.getElementById('sessionStatus');
const statusText = document.getElementById('statusText');
const infoList = document.getElementById('infoList');

// Initialize
function init() {
    sessionId = generateSessionId();
    sessionIdDisplay.textContent = sessionId; // Show full session ID

    chatForm.addEventListener('submit', handleSubmit);

    console.log('Chat initialized with session ID:', sessionId);
}

// Generate a unique session ID
function generateSessionId() {
    return 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

// Handle form submission
async function handleSubmit(e) {
    e.preventDefault();

    const message = messageInput.value.trim();
    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');
    messageInput.value = '';

    // Disable input while processing
    setLoading(true);

    try {
        // Send to backend
        const response = await fetch(`${CONFIG.BACKEND_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                session_id: sessionId,
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Add bot response
        addMessage(data.message, 'bot');

        // Update session info
        updateSessionInfo(data);

        // If processing, subscribe to real-time status updates
        if (data.status === 'processing' && data.request_id) {
            currentRequestId = data.request_id;
            subscribeToStatus(data.request_id);
        }

    } catch (error) {
        console.error('Error sending message:', error);
        addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        statusText.textContent = 'Error: ' + error.message;
    } finally {
        setLoading(false);
    }
}

// Add message to chat
function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Parse markdown-style formatting
    contentDiv.innerHTML = formatMessage(text);

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Format message with basic markdown
function formatMessage(text) {
    // Convert URLs to links
    text = text.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');

    // Convert checkmarks
    text = text.replace(/✓/g, '✓');
    text = text.replace(/✅/g, '✅');

    // Convert line breaks
    text = text.replace(/\n/g, '<br>');

    return text;
}

// Update session information
function updateSessionInfo(data) {
    sessionStatusDisplay.textContent = data.status || 'active';

    if (data.extracted_entities && Object.keys(data.extracted_entities).length > 0) {
        extractedEntities = data.extracted_entities;
        updateInfoDisplay();
    }

    statusText.textContent = `Status: ${data.status}`;
}

// Update the collected information display
function updateInfoDisplay() {
    const hasInfo = Object.keys(extractedEntities).length > 0;

    if (!hasInfo) {
        infoList.innerHTML = '<p class="empty-state">No information collected yet</p>';
        return;
    }

    infoList.innerHTML = '';

    for (const [key, value] of Object.entries(extractedEntities)) {
        if (!value) continue;

        const itemDiv = document.createElement('div');
        itemDiv.className = 'info-item';

        let displayValue = value;
        if (typeof value === 'object') {
            displayValue = Object.entries(value)
                .map(([k, v]) => `${k}:${v}`)
                .join(', ');
        }

        itemDiv.innerHTML = `<strong>${formatFieldName(key)}:</strong> ${displayValue}`;
        infoList.appendChild(itemDiv);
    }
}

// Format field names for display
function formatFieldName(field) {
    return field
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

// Set loading state
function setLoading(loading) {
    sendButton.disabled = loading;
    messageInput.disabled = loading;

    if (loading) {
        sendButton.innerHTML = '<span class="loading"></span>';
        statusText.textContent = 'Processing...';
    } else {
        sendButton.innerHTML = '<span id="sendIcon">Send</span>';
        statusText.textContent = 'Ready';
    }
}

// Subscribe to PR status updates via Firestore
function subscribeToStatus(requestId) {
    // Unsubscribe from any previous listener
    if (statusListener) {
        console.log('🔇 Unsubscribing from previous status listener');
        statusListener();
        statusListener = null;
    }

    if (!db) {
        console.warn('⚠️ Firebase not initialized, falling back to polling');
        startStatusPolling(requestId);
        return;
    }

    console.log(`🔔 Subscribing to real-time updates for request: ${requestId}`);

    // Subscribe to the pr_requests document
    statusListener = db.collection('pr_requests').doc(requestId)
        .onSnapshot((doc) => {
            if (!doc.exists) {
                console.warn(`⚠️ Document ${requestId} does not exist yet`);
                return;
            }

            const data = doc.data();
            console.log('📊 Received real-time update:', data);

            // Update session status display
            if (data.status === 'pending' || data.status === 'processing') {
                sessionStatusDisplay.textContent = 'Processing...';
                statusText.textContent = 'Creating Pull Request...';
            } else if (data.status === 'completed' && data.pr_url) {
                console.log('✅ PR COMPLETED! URL:', data.pr_url);
                sessionStatusDisplay.textContent = 'Completed ✓';
                statusText.textContent = 'PR Created Successfully';
                addMessage(
                    `🎉 Success! Your Pull Request has been created:\n\n${data.pr_url}\n\nYou can review and merge it when ready!`,
                    'bot'
                );
                // Unsubscribe - request complete
                if (statusListener) {
                    statusListener();
                    statusListener = null;
                }
            } else if (data.status === 'failed') {
                console.log('❌ PR FAILED:', data.error);
                sessionStatusDisplay.textContent = 'Failed ✗';
                statusText.textContent = 'PR Creation Failed';
                addMessage(
                    `❌ Sorry, there was an error creating the PR:\n${data.error || 'Unknown error'}`,
                    'bot'
                );
                // Unsubscribe - request failed
                if (statusListener) {
                    statusListener();
                    statusListener = null;
                }
            }
        }, (error) => {
            console.error('💥 Error in Firestore listener:', error);
            // Fall back to polling on error
            console.warn('⚠️ Falling back to polling due to listener error');
            startStatusPolling(requestId);
        });
}

// Fallback: Poll for PR creation status (legacy backup)
async function startStatusPolling(requestId) {
    console.log(`🔄 Starting fallback polling for request: ${requestId}`);

    const POLL_INTERVAL = 2000; // 2 seconds
    let attempts = 0;
    const MAX_ATTEMPTS = 60; // 2 minutes max

    const pollStatus = async () => {
        if (attempts >= MAX_ATTEMPTS) {
            console.log('⏱️ Polling timeout reached');
            addMessage('⚠️ Status check timed out. Please check the backend logs.', 'bot');
            return;
        }

        attempts++;

        try {
            console.log(`📡 Polling status (attempt ${attempts}): ${requestId}`);
            const response = await fetch(`${CONFIG.BACKEND_URL}/status/${requestId}`);

            if (!response.ok) {
                console.error('❌ Status check failed:', response.status);
                setTimeout(pollStatus, POLL_INTERVAL);
                return;
            }

            const data = await response.json();
            console.log('📊 Status poll result:', data);

            if (data.status === 'processing' || data.status === 'pending') {
                sessionStatusDisplay.textContent = 'Processing...';
                statusText.textContent = 'Creating Pull Request...';
                setTimeout(pollStatus, POLL_INTERVAL);
            } else if (data.status === 'completed' && data.pr_url) {
                console.log('✅ PR COMPLETED! URL:', data.pr_url);
                sessionStatusDisplay.textContent = 'Completed ✓';
                statusText.textContent = 'PR Created Successfully';
                addMessage(
                    `🎉 Success! Your Pull Request has been created:\n\n${data.pr_url}\n\nYou can review and merge it when ready!`,
                    'bot'
                );
            } else if (data.status === 'failed') {
                console.log('❌ PR FAILED:', data.error);
                sessionStatusDisplay.textContent = 'Failed ✗';
                statusText.textContent = 'PR Creation Failed';
                addMessage(
                    `❌ Sorry, there was an error creating the PR:\n${data.error || 'Unknown error'}`,
                    'bot'
                );
            } else {
                console.warn('⚠️ Unknown status:', data.status);
                setTimeout(pollStatus, POLL_INTERVAL);
            }

        } catch (error) {
            console.error('💥 Error polling status:', error);
            setTimeout(pollStatus, POLL_INTERVAL);
        }
    };

    // Start polling immediately
    pollStatus();
}


// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    init();
});

// Also initialize immediately in case DOMContentLoaded already fired
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    // DOM already loaded
    init();
}

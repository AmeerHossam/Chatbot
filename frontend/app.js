// Configuration
const CONFIG = {
    BACKEND_URL: 'https://chatbot-backend-795588981144.us-central1.run.app',
    POLL_INTERVAL: 1000, // Poll for PR status every 1 seconds
};


// State
let sessionId = null;
let currentRequestId = null;
let extractedEntities = {};
let isPolling = false;  // Global flag to track if polling is active
let pollingTimeoutId = null;  // Store timeout ID to cancel if needed

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

        // If processing, start polling for status
        if (data.status === 'processing' && data.request_id) {
            currentRequestId = data.request_id;
            startStatusPolling(data.request_id);
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

// Poll for PR creation status
async function startStatusPolling(requestId) {
    // Stop any existing polling
    if (isPolling) {
        console.log('Stopping previous polling instance');
        if (pollingTimeoutId) {
            clearTimeout(pollingTimeoutId);
            pollingTimeoutId = null;
        }
    }

    isPolling = true;
    console.log(`🔄 Starting status polling for request: ${requestId}`);

    const pollStatus = async () => {
        // Check if this polling instance should still be running
        if (!isPolling || currentRequestId !== requestId) {
            console.log(`⏹️ Polling stopped (isPolling: ${isPolling}, current: ${currentRequestId}, polling: ${requestId})`);
            return;
        }

        try {
            console.log(`📡 Polling status for: ${requestId}`);
            const response = await fetch(`${CONFIG.BACKEND_URL}/status/${requestId}`);

            if (!response.ok) {
                console.error('❌ Status check failed:', response.status);
                // Continue polling even if check fails
                pollingTimeoutId = setTimeout(pollStatus, CONFIG.POLL_INTERVAL);
                return;
            }

            const data = await response.json();
            console.log('📊 Status poll result:', data);

            // Update session status display
            if (data.status === 'processing') {
                sessionStatusDisplay.textContent = 'Processing...';
                statusText.textContent = 'Creating Pull Request...';
                // Continue polling
                pollingTimeoutId = setTimeout(pollStatus, CONFIG.POLL_INTERVAL);
            } else if (data.status === 'completed' && data.pr_url) {
                console.log('✅ PR COMPLETED! URL:', data.pr_url);
                isPolling = false;  //  Stop polling
                sessionStatusDisplay.textContent = 'Completed ✓';
                statusText.textContent = 'PR Created Successfully';
                addMessage(
                    `🎉 Success! Your Pull Request has been created:\n\n${data.pr_url}\n\nYou can review and merge it when ready!`,
                    'bot'
                );
                // Stop polling - request complete
            } else if (data.status === 'failed') {
                console.log('❌ PR FAILED:', data.error);
                isPolling = false;  // Stop polling
                sessionStatusDisplay.textContent = 'Failed ✗';
                statusText.textContent = 'PR Creation Failed';
                addMessage(
                    `❌ Sorry, there was an error creating the PR:\n${data.error || 'Unknown error'}`,
                    'bot'
                );
                // Stop polling - request failed
            } else {
                // Unknown status, continue polling
                console.warn('⚠️ Unknown status:', data.status);
                pollingTimeoutId = setTimeout(pollStatus, CONFIG.POLL_INTERVAL);
            }

        } catch (error) {
            console.error('💥 Error polling status:', error);
            // Continue polling even on error
            pollingTimeoutId = setTimeout(pollStatus, CONFIG.POLL_INTERVAL);
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

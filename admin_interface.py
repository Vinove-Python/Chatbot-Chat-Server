HTML_ADMIN_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Admin Chat</title>
    <style>
        body { font-family: Arial, sans-serif; display: flex; height: 100vh; margin: 0; background-color: #f0f0f0; }
        .sidebar { width: 250px; background: #333; color: white; padding: 15px; overflow-y: auto; border-right: 1px solid #444; }
        .main-content { flex: 1; display: flex; flex-direction: column; background: #fff; }
        .header { padding: 15px; background: #f8f9fa; border-bottom: 1px solid #ddd; }
        .header h1 { margin: 0; font-size: 1.5em; }
        .status-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;}
        #adminStatus { padding: 5px 10px; border-radius: 4px; font-size: 0.9em; }
        #adminStatus.connected { background: #28a745; color: white; }
        #adminStatus.disconnected { background: #dc3545; color: white; }
        .clients-count { font-size: 0.9em; background: #e9ecef; padding: 5px 10px; border-radius: 4px; }
        .sidebar h2 { font-size: 1.2em; margin-top: 0; border-bottom: 1px solid #555; padding-bottom: 10px; }
        .client-list { list-style: none; padding: 0; margin: 0; }
        .client-list li {
            padding: 10px;
            cursor: pointer;
            border-bottom: 1px solid #444;
            transition: background-color 0.2s;
            font-size: 0.9em;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .client-list li:hover { background: #555; }
        .client-list li.active { background: #007bff; color: white; }
        .client-list li .unread-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #ffc107; /* Yellow for unread */
            margin-right: 8px;
            visibility: hidden; /* Hidden by default */
        }
        .client-list li.has-unread .unread-indicator {
            visibility: visible;
        }
        .chat-area { flex: 1; display: flex; flex-direction: column; padding: 0; overflow: scroll;}
        .chat-header {
            padding: 10px 15px;
            background: #e9ecef;
            border-bottom: 1px solid #ddd;
            font-weight: bold;
            color: #333;
        }
        #currentChatClient { font-style: italic; }
        .chat-messages { flex: 1; padding: 15px; overflow-y: auto; background: #fdfdfd; overflow-y: scroll; height: 100%; }
        .message { margin: 8px 0; padding: 8px 12px; border-radius: 12px; word-wrap: break-word; }
        .message.admin { background: #e9ecef; color: #333; margin-right: auto; }
        .message.user { background: #28a745; color: white; margin-right: auto; }
        .message.assistant { background: #e9ecef; color: #333; margin-right: auto; }
        .message.system { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; margin: 10px auto; text-align: center; font-style: italic; max-width: 90%;}
        .message-sender { font-size: 10px; opacity: 0.7; margin-bottom: 4px; display: block; }
        .message-content { font-size: 14px; }
        .message-time { font-size: 10px; opacity: 0.5; margin-top: 4px; }
        .chat-input-area { display: flex; padding: 15px; background: #f8f9fa; border-top: 1px solid #ddd; gap: 10px;}
        .chat-input { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 20px; outline: none; font-size: 14px;}
        .chat-input:focus { border-color: #007bff; }
        .send-btn { background: #007bff; color: white; border: none; border-radius: 20px; padding: 10px 20px; cursor: pointer; font-size: 14px;}
        .send-btn:hover { background: #0056b3; }
        .send-btn:disabled { background: #ccc; cursor: not-allowed; }
        .loading-indicator { text-align: center; padding: 20px; color: #666; font-style: italic; }
        .notification-area {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 300px;
            z-index: 1000;
        }
        .notification {
            background: #28a745; color: white; padding: 15px; margin-bottom: 10px;
            border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            font-size: 0.9em;
        }
        .notification.request { background: #17a2b8; }
        .notification.error { background: #dc3545; }
        .notification .actions button {
            background: white; color: #333; border: 1px solid #ccc;
            padding: 5px 8px; margin-left: 5px; border-radius: 3px; cursor: pointer;
        }
        #noRequestsMessage {
            padding: 10px; text-align: center; color: #777; font-style: italic; font-size: 0.9em;
        }
        .main-layout-container {
            display: flex;
            flex-direction: column; /* Stack header and content vertically */
            flex: 1;
            max-height: 90vh;
            overflow: hidden;
        }
        .content-below-header {
            display: flex; /* This will make connection requests and chat side-by-side */
            flex: 1;
            max-height: 90vh;
            overflow: hidden;
        }
        .connection-requests-panel {
            width: 250px; /* Fixed width or flex-basis */
            padding: 15px;
            border-right: 1px solid #ddd;
            background: #f8f9fa;
            overflow-y: scroll;
        }
        .connection-requests-panel h2 {
            margin-top:0; font-size: 1.2em;
        }
        .notification-card {
            background: #e3f2fd; border: 1px solid #2196f3; border-radius: 4px;
            padding: 10px; margin-bottom: 10px; font-size: 0.9em;
        }
        .notification-card strong { display: block; margin-bottom: 5px; }
        .notification-card small { display: block; color: #555; margin-bottom: 3px; word-break: break-all;}
        .notification-card .actions { margin-top: 8px; text-align: right; }
        .notification-card .actions button {
            padding: 5px 10px; font-size: 0.85em; margin-left: 5px;
            border: none; border-radius: 3px; cursor: pointer;
        }
        .accept-btn { background: #28a745; color: white; }
        .reject-btn { background: #dc3545; color: white; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h2>Connected Clients</h2>
        <ul id="clientList" class="client-list">
            </ul>
        <div id="noClientsMessage" style="padding: 10px; text-align: center; color: #aaa; font-style: italic;">
            No clients connected.
        </div>
    </div>

    <div class="main-content">
        <div class="header">
            <h1>Human Agent Dashboard</h1>
            <div class="status-bar">
                <div id="adminStatus" class="status disconnected">Admin: Disconnected</div>
                <div class="clients-count">Total Active Clients: <span id="totalClientCount">0</span></div>
            </div>
        </div>

        <div class="main-layout-container">
             <div class="content-below-header">
                <div class="connection-requests-panel">
                    <h2>Connection Requests</h2>
                    <div id="connectionRequests">
                        </div>
                    <div id="noRequestsMessage">No pending connection requests.</div>
                </div>

                <div class="chat-area">
                    <div class="chat-header">
                        Chatting with: <span id="currentChatClient">No client selected</span>
                    </div>
                    <div class="chat-messages" id="chatMessages">
                         <div class="message system">
                            <div class="message-content">Select a client from the list to start chatting or view pending requests.</div>
                        </div>
                    </div>
                    <div class="chat-input-area">
                        <input type="text" class="chat-input" id="chatInput" placeholder="Type message..." maxlength="500">
                        <button class="send-btn" id="sendBtn" onclick="sendMessageToClient()" disabled>Send</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div id="notificationArea" class="notification-area"></div>

    <script>
        let adminWs = null;
        let currentChatTargetClientId = null;
        let chatHistories = {}; // { clientId: [messages] }
        let clientInfoMap = {}; // { clientId: {user_agent: "...", client_ip: "...", conversation_id: "..."}}
        let unreadMessages = new Set(); // Set of clientIds with unread messages
        let isLoadingHistory = false; // Prevent multiple simultaneous loads
        let apiHistoryLoaded = new Set(); // Track which clients have had their API history loaded

        function connectAdmin() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            adminWs = new WebSocket(`${protocol}//${window.location.host}/admin`);

            adminWs.onopen = () => {
                updateAdminStatus(true);
                adminWs.send(JSON.stringify({ type: "get_client_list" })); // Request client list on connect
                adminWs.send(JSON.stringify({ type: "get_pending_requests" })); // Request pending requests
            };

            adminWs.onclose = () => {
                updateAdminStatus(false);
                setTimeout(connectAdmin, 3000);
            };

            adminWs.onmessage = (event) => {
                const data = JSON.parse(event.data);
                logger.log("Admin received:", data);

                switch (data.type) {
                    case 'connection_request':
                        showConnectionRequest(data.request_id, data.client_info);
                        break;
                    case 'pending_requests_list':
                        updatePendingRequestsList(data.requests);
                        break;
                    case 'client_list_update':
                        updateClientList(data.clients);
                        document.getElementById('totalClientCount').textContent = data.clients.length;
                        break;
                    case 'user_message':
                        handleUserMessage(data.client_id, data.message, data.client_info);
                        break;
                    case 'client_connected_notification': // For admin notification
                        showToastNotification(`Client connected: ${data.client_info.user_agent.substring(0,30)}...`);
                        break;
                    case 'client_disconnected_notification': // For admin notification
                        showToastNotification(`Client disconnected: ${data.client_id.substring(0,8)}...`);
                        // Clean up when client disconnects
                        apiHistoryLoaded.delete(data.client_id);
                        if (currentChatTargetClientId === data.client_id) {
                            addSystemMessageToChatHistory(data.client_id, "Client has disconnected.");
                            if(document.getElementById(`client-${data.client_id}`)){
                                displayChatForClient(currentChatTargetClientId); // Refresh chat view
                            }
                        }
                        break;
                    case 'chat_history_loaded':
                        handleChatHistoryLoaded(data.client_id, data.history);
                        break;
                    case 'chat_history_error':
                        handleChatHistoryError(data.client_id, data.error);
                        break;
                }
                updateSendButtonState();
            };
        }

        function updateAdminStatus(isConnected) {
            const statusEl = document.getElementById('adminStatus');
            if (isConnected) {
                statusEl.textContent = 'Admin: Connected';
                statusEl.className = 'status connected';
            } else {
                statusEl.textContent = 'Admin: Disconnected';
                statusEl.className = 'status disconnected';
                currentChatTargetClientId = null;
                updateClientList([]); // Clear client list on disconnect
                document.getElementById('totalClientCount').textContent = 0;
                updateChatUIForNoSelection();
            }
            updateSendButtonState();
        }
        
        function updatePendingRequestsList(requests) {
            const requestsDiv = document.getElementById('connectionRequests');
            const noRequestsMsg = document.getElementById('noRequestsMessage');
            requestsDiv.innerHTML = ''; // Clear existing

            if (requests && requests.length > 0) {
                noRequestsMsg.style.display = 'none';
                requests.forEach(req => showConnectionRequest(req.request_id, req.client_info));
            } else {
                noRequestsMsg.style.display = 'block';
            }
        }

        function showConnectionRequest(requestId, clientInfo) {
            const notificationsDiv = document.getElementById('connectionRequests');
            const noRequestsMsg = document.getElementById('noRequestsMessage');
            noRequestsMsg.style.display = 'none';

            const existingNotification = document.getElementById(`req-${requestId}`);
            if (existingNotification) return; // Avoid duplicates

            const conversationId = clientInfo.conversation_id || 'N/A';
            const card = document.createElement('div');
            card.className = 'notification-card';
            card.id = `req-${requestId}`;
            card.innerHTML = `
                <strong>New Request</strong>
                <small>ID: ${requestId.substring(0,8)}...</small>
                <small>Conversation: ${escapeHtml(conversationId.substring(0,8))}...</small>
                <small>Agent: ${escapeHtml(clientInfo.user_agent) || 'Unknown'}</small>
                <small>IP: ${escapeHtml(clientInfo.client_ip) || 'Unknown'}</small>
                <div class="actions">
                    <button class="accept-btn" onclick="handleConnectionResponse('${requestId}', 'accept')">Accept</button>
                    <button class="reject-btn" onclick="handleConnectionResponse('${requestId}', 'reject')">Reject</button>
                </div>
            `;
            notificationsDiv.appendChild(card);
        }

        function handleConnectionResponse(requestId, action) {
            if (adminWs && adminWs.readyState === WebSocket.OPEN) {
                adminWs.send(JSON.stringify({
                    type: 'connection_response',
                    request_id: requestId,
                    action: action
                }));
                const notificationCard = document.getElementById(`req-${requestId}`);
                if (notificationCard) notificationCard.remove();

                if (document.getElementById('connectionRequests').children.length === 0) {
                    document.getElementById('noRequestsMessage').style.display = 'block';
                }
            }
        }

        function updateClientList(clients) {
            const clientListEl = document.getElementById('clientList');
            const noClientsMsg = document.getElementById('noClientsMessage');
            clientListEl.innerHTML = ''; // Clear existing list

            clientInfoMap = {}; // Reset map

            if (clients && clients.length > 0) {
                noClientsMsg.style.display = 'none';
                clients.forEach(client => {
                    clientInfoMap[client.id] = client.info; // Store client info
                    const listItem = document.createElement('li');
                    listItem.id = `client-${client.id}`;
                    const conversationId = client.info.conversation_id || 'N/A';
                    listItem.textContent = `${client.info.user_agent ? client.info.user_agent.substring(0, 20) : 'Unknown Client'}... (${conversationId.substring(0,4)})`;
                    listItem.onclick = () => selectClientForChat(client.id);

                    const unreadIndicator = document.createElement('span');
                    unreadIndicator.className = 'unread-indicator';
                    listItem.prepend(unreadIndicator); // Add indicator at the beginning

                    clientListEl.appendChild(listItem);
                    if (unreadMessages.has(client.id)) {
                        listItem.classList.add('has-unread');
                    }
                });
            } else {
                noClientsMsg.style.display = 'block';
            }

            // Reselect current client if still in list, otherwise clear chat
            if (currentChatTargetClientId && clientInfoMap[currentChatTargetClientId]) {
                const currentClientItem = document.getElementById(`client-${currentChatTargetClientId}`);
                if (currentClientItem) currentClientItem.classList.add('active');
                 updateChatUIForClient(currentChatTargetClientId);
            } else if (currentChatTargetClientId) { // Current client disconnected
                currentChatTargetClientId = null;
                updateChatUIForNoSelection();
            }
             updateSendButtonState();
        }

        async function selectClientForChat(clientId) {
            if (currentChatTargetClientId === clientId) return; // Already selected
            if (isLoadingHistory) return; // Prevent concurrent loads

            if (currentChatTargetClientId) {
                const prevActiveItem = document.getElementById(`client-${currentChatTargetClientId}`);
                if (prevActiveItem) prevActiveItem.classList.remove('active');
            }

            currentChatTargetClientId = clientId;
            const activeItem = document.getElementById(`client-${clientId}`);
            if (activeItem) {
                activeItem.classList.add('active');
                activeItem.classList.remove('has-unread'); // Mark as read
            }
            unreadMessages.delete(clientId);

            updateChatUIForClient(clientId);
            
            // Check if we need to load API history for this client
            if (!apiHistoryLoaded.has(clientId)) {
                // Load chat history from API first
                await loadChatHistory(clientId);
            } else {
                // API history already loaded, just display current chat
                displayChatForClient(clientId);
            }
            
            updateSendButtonState();
            document.getElementById('chatInput').focus();
        }

        async function loadChatHistory(clientId) {
            const clientInfo = clientInfoMap[clientId];
            if (!clientInfo || !clientInfo.conversation_id) {
                logger.log(`No conversation ID for client ${clientId}`);
                apiHistoryLoaded.add(clientId); // Mark as attempted even if no conversation ID
                displayChatForClient(clientId);
                return;
            }

            isLoadingHistory = true;
            showLoadingIndicator();

            try {
                const response = await fetch(`http://127.0.0.1:8000/api/conversation/${clientInfo.conversation_id}/`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const history = await response.json();
                handleChatHistoryLoaded(clientId, history);
            } catch (error) {
                logger.error(`Failed to load chat history for client ${clientId}:`, error);
                handleChatHistoryError(clientId, error.message);
                apiHistoryLoaded.add(clientId); // Mark as attempted even on error
            } finally {
                isLoadingHistory = false;
            }
        }

        function handleChatHistoryLoaded(clientId, history) {
            if (!chatHistories[clientId]) {
                chatHistories[clientId] = [];
            }

            // Convert API history to our format
            const convertedHistory = history.map(msg => ({
                senderType: msg.role === 'user' ? 'user' : 'assistant',
                text: msg.content,
                senderName: msg.role === 'user' ? 'User' : 'AI Assistant',
                time: msg.time,
                isHistorical: true
            }));

            // Find the split point - where historical messages end and real-time messages begin
            const realtimeMessages = chatHistories[clientId].filter(msg => !msg.isHistorical);
            
            // Rebuild the chat history: API history first, then real-time messages
            chatHistories[clientId] = [...convertedHistory, ...realtimeMessages];
            
            // Mark this client's API history as loaded
            apiHistoryLoaded.add(clientId);

            if (currentChatTargetClientId === clientId) {
                displayChatForClient(clientId);
            }

            logger.log(`Loaded ${history.length} historical messages for client ${clientId}`);
        }

        function handleChatHistoryError(clientId, error) {
            logger.error(`Chat history error for client ${clientId}:`, error);
            
            if (currentChatTargetClientId === clientId) {
                addSystemMessageToChatHistory(clientId, `Failed to load chat history: ${error}`);
                displayChatForClient(clientId);
            }
            
            showToastNotification(`Failed to load chat history: ${error}`, 'error');
        }

        function showLoadingIndicator() {
            const chatMessagesEl = document.getElementById('chatMessages');
            chatMessagesEl.innerHTML = '<div class="loading-indicator">Loading chat history...</div>';
        }

        function updateChatUIForClient(clientId) {
            const clientInfo = clientInfoMap[clientId];
            const clientName = clientInfo ? (clientInfo.user_agent ? clientInfo.user_agent.substring(0,30) : 'Unknown Client') : 'Selected Client';
            const conversationId = clientInfo ? (clientInfo.conversation_id || 'N/A') : 'N/A';
            document.getElementById('currentChatClient').textContent = `${clientName}... (${conversationId.substring(0,8)})`;
        }

        function updateChatUIForNoSelection() {
            document.getElementById('currentChatClient').textContent = 'No client selected';
            document.getElementById('chatMessages').innerHTML = `
                <div class="message system">
                    <div class="message-content">Select a client from the list to start chatting or view pending requests.</div>
                </div>`;
        }

        function displayChatForClient(clientId) {
            const chatMessagesEl = document.getElementById('chatMessages');
            chatMessagesEl.innerHTML = ''; // Clear current messages

            const history = chatHistories[clientId] || [];
            history.forEach(msg => {
                const messageDiv = createMessageDiv(msg.senderType, msg.text, msg.senderName, msg.clientInfo, msg.time, msg.isHistorical);
                chatMessagesEl.appendChild(messageDiv);
            });
            chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
        }

        function sendMessageToClient() {
            const input = document.getElementById('chatInput');
            const messageText = input.value.trim();

            if (messageText && currentChatTargetClientId && adminWs && adminWs.readyState === WebSocket.OPEN) {
                const messageData = {
                    type: 'admin_message_to_client',
                    target_client_id: currentChatTargetClientId,
                    message: messageText
                };
                adminWs.send(JSON.stringify(messageData));

                addMessageToChatHistory(currentChatTargetClientId, 'admin', messageText, "Admin");
                displayChatForClient(currentChatTargetClientId); // Refresh view
                input.value = '';
            }
            updateSendButtonState();
        }

        function handleUserMessage(clientId, messageText, clientInfo) {
            const senderName = clientInfo ? (clientInfo.user_agent ? clientInfo.user_agent.substring(0,20) : 'Client') : 'Client';
            addMessageToChatHistory(clientId, 'user', messageText, senderName, clientInfo);

            if (clientId === currentChatTargetClientId) {
                displayChatForClient(clientId); // Refresh view if current
            } else {
                // Mark as unread
                unreadMessages.add(clientId);
                const clientListItem = document.getElementById(`client-${clientId}`);
                if (clientListItem) {
                    clientListItem.classList.add('has-unread');
                }
                showToastNotification(`New message from ${clientInfo.user_agent.substring(0,20)}...`, 'info');
            }
        }
        
        function addSystemMessageToChatHistory(clientId, text) {
            if (!chatHistories[clientId]) {
                chatHistories[clientId] = [];
            }
            chatHistories[clientId].push({ senderType: 'system', text: text });
        }

        function addMessageToChatHistory(clientId, senderType, text, senderName, clientInfoDetails = null) {
            if (!chatHistories[clientId]) {
                chatHistories[clientId] = [];
            }
            chatHistories[clientId].push({ 
                senderType, 
                text, 
                senderName, 
                clientInfo: clientInfoDetails,
                time: new Date().toISOString(),
                isHistorical: false
            });
        }

        function createMessageDiv(senderType, text, senderName, clientInfo = null, time = null, isHistorical = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${senderType}`;
            
            let displayName = senderName;
            if (senderType === 'user' && clientInfo) {
                 displayName = `${clientInfo.user_agent ? clientInfo.user_agent.substring(0,20) : 'Client'}... (${clientInfo.client_ip || 'N/A'})`;
            } else if (senderType === 'admin') {
                displayName = 'Admin (You)';
            } else if (senderType === 'assistant') {
                displayName = 'AI Assistant';
            }

            let timeDisplay = '';
            if (time) {
                const date = new Date(time);
                timeDisplay = `<div class="message-time">${date.toLocaleString()}</div>`;
            }

            if (senderType !== 'system') {
                 messageDiv.innerHTML = `
                    <span class="message-sender">${escapeHtml(displayName)}${isHistorical ? ' (Historical)' : ''}</span>
                    <div class="message-content">${escapeHtml(text)}</div>
                    ${timeDisplay}
                `;
            } else {
                 messageDiv.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
            }
            return messageDiv;
        }

        function updateSendButtonState() {
            const sendBtn = document.getElementById('sendBtn');
            const chatInput = document.getElementById('chatInput');
            const isAdminConnected = adminWs && adminWs.readyState === WebSocket.OPEN;
            
            sendBtn.disabled = !isAdminConnected || !currentChatTargetClientId || chatInput.value.trim() === "";
            
            if (!isAdminConnected) {
                sendBtn.textContent = 'Disconnected';
                chatInput.placeholder = 'Admin disconnected';
            } else if (!currentChatTargetClientId) {
                sendBtn.textContent = 'Select Client';
                chatInput.placeholder = 'Select a client to chat with';
            } else {
                sendBtn.textContent = 'Send';
                chatInput.placeholder = 'Type message...';
            }
        }
        
        document.getElementById('chatInput').addEventListener('input', updateSendButtonState);
        document.getElementById('chatInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !document.getElementById('sendBtn').disabled) {
                sendMessageToClient();
            }
        });

        function escapeHtml(unsafe) {
            if (unsafe === null || typeof unsafe === 'undefined') return '';
            return unsafe
                .toString()
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function showToastNotification(message, type = 'success') { // type can be 'success', 'info', 'error'
            const area = document.getElementById('notificationArea');
            const toast = document.createElement('div');
            toast.className = `notification ${type}`;
            toast.textContent = message;
            area.appendChild(toast);
            setTimeout(() => {
                toast.remove();
            }, 5000);
        }
        
        const logger = {
            log: (message, ...optionalParams) => console.log("[AdminWS]", message, ...optionalParams),
            error: (message, ...optionalParams) => console.error("[AdminWS]", message, ...optionalParams)
        };

        connectAdmin();
    </script>
</body>
</html>
"""
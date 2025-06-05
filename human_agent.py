from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Set, Dict, Optional, List, Any
import uuid, json, logging
from admin_interface import HTML_ADMIN_INTERFACE

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

@app.get("/", response_class=HTMLResponse)
async def get_admin_interface():
    """Serve the admin interface"""
    return HTML_ADMIN_INTERFACE

class ConnectionManager:
    def __init__(self):
        # Active client WebSockets: {client_id: {"ws": WebSocket, "info": client_info}}
        self.active_clients: Dict[str, Dict[str, Any]] = {}
        # Pending connection requests: {request_id: {"ws": WebSocket, "info": client_info}}
        self.pending_connections: Dict[str, Dict[str, Any]] = {}
        self.admin_websocket: Optional[WebSocket] = None

    def _get_client_info(self, websocket: WebSocket) -> Dict[str, str]:
        return {
            "user_agent": websocket.headers.get("user-agent", "Unknown"),
            "client_ip": websocket.client.host if websocket.client else "Unknown"
        }

    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.admin_websocket = websocket
        logger.info("Admin connected.")
        await self.send_client_list_to_admin()
        await self.send_pending_requests_to_admin()


    async def disconnect_admin(self):
        self.admin_websocket = None
        logger.info("Admin disconnected.")

    async def request_connection(self, websocket: WebSocket) -> str:
        """A client requests to connect. They are put in pending."""
        await websocket.accept() # Accept WS connection first to get info & communicate
        request_id = str(uuid.uuid4())
        conversation_id = websocket.query_params.get('conversation_id', 'No conversation ID provided')
        client_info = self._get_client_info(websocket)
        client_info['conversation_id'] = conversation_id
        self.pending_connections[request_id] = {"ws": websocket, "info": client_info}

        if self.admin_websocket:
            await self.send_to_admin_socket(self.admin_websocket, {
                "type": "connection_request",
                "request_id": request_id,
                "conversation_id" : conversation_id,
                "client_info": client_info
            })
        logger.info(f"Connection request {request_id} from {client_info['client_ip']}. Pending admin approval.")
        return request_id

    async def handle_admin_response(self, request_id: str, action: str):
        if request_id not in self.pending_connections:
            logger.warning(f"Request ID {request_id} not found in pending connections for action: {action}")
            if self.admin_websocket:
                 await self.send_to_admin_socket(self.admin_websocket, {"type": "error", "message": f"Request {request_id} not found."})
            return

        pending_client_data = self.pending_connections.pop(request_id)
        client_websocket = pending_client_data["ws"]
        client_info = pending_client_data["info"]

        try:
            if action == "accept":
                self.active_clients[request_id] = {"ws": client_websocket, "info": client_info, "id": request_id}
                await client_websocket.send_text(json.dumps({
                    "type": "connection_approved",
                    "client_id": request_id,
                    "message": "Connection approved by admin."
                }))
                logger.info(f"Connection {request_id} approved for {client_info['client_ip']}.")
                await self.send_client_list_to_admin() # Update admin's list
                if self.admin_websocket: # Notify admin specifically about this connection
                     await self.send_to_admin_socket(self.admin_websocket, {
                        "type": "client_connected_notification",
                        "client_id": request_id,
                        "client_info": client_info
                    })

            elif action == "reject":
                await client_websocket.send_text(json.dumps({
                    "type": "connection_rejected",
                    "message": "Connection rejected by admin."
                }))
                await client_websocket.close(code=4001) # Custom close code
                logger.info(f"Connection {request_id} rejected for {client_info['client_ip']}.")
            else:
                 logger.warning(f"Unknown action '{action}' for request {request_id}")

        except Exception as e:
            logger.error(f"Error handling admin response for {request_id}: {e}")
            # Ensure client is removed if error occurs after pop
            if action == "accept" and request_id in self.active_clients:
                del self.active_clients[request_id]
            await self.send_client_list_to_admin() # Resync admin

    async def disconnect_client(self, websocket: WebSocket, client_id: Optional[str] = None):
        """Handles client disconnection, whether from pending or active."""
        disconnected_client_id = None
        client_ip_for_log = websocket.client.host if websocket.client else "Unknown"

        if client_id and client_id in self.pending_connections:
            if self.pending_connections[client_id]["ws"] == websocket:
                del self.pending_connections[client_id]
                logger.info(f"Pending client {client_id} ({client_ip_for_log}) disconnected.")
                await self.send_pending_requests_to_admin() # Update admin about pending list change
                return # No further action needed for pending that disconnects

        # Find client_id if not provided (e.g., unexpected disconnect)
        if not client_id:
            for cid, data in list(self.active_clients.items()):
                if data["ws"] == websocket:
                    client_id = cid
                    break
            if not client_id: # Check pending if not found in active
                 for cid, data in list(self.pending_connections.items()):
                    if data["ws"] == websocket:
                        del self.pending_connections[cid] # Remove if it was pending
                        logger.info(f"Orphaned pending client ({client_ip_for_log}) disconnected before ID assignment.")
                        await self.send_pending_requests_to_admin()
                        return


        if client_id and client_id in self.active_clients:
            if self.active_clients[client_id]["ws"] == websocket:
                del self.active_clients[client_id]
                disconnected_client_id = client_id
                logger.info(f"Active client {client_id} ({client_ip_for_log}) disconnected.")
                await self.send_client_list_to_admin()
                if self.admin_websocket:
                    await self.send_to_admin_socket(self.admin_websocket, {
                        "type": "client_disconnected_notification",
                        "client_id": disconnected_client_id,
                    })
        elif client_id:
             logger.info(f"Client {client_id} ({client_ip_for_log}) disconnected, was not in active list. May have been pending or already removed.")


    async def send_to_admin_socket(self, admin_ws: WebSocket, data: dict):
        try:
            await admin_ws.send_text(json.dumps(data))
        except Exception as e:
            logger.warning(f"Failed to send message to admin: {e}. Admin might have disconnected.")
            # Potentially handle admin disconnect here if self.admin_websocket == admin_ws

    async def send_client_list_to_admin(self):
        if self.admin_websocket:
            clients_data = [
                {"id": cid, "info": cdata["info"]}
                for cid, cdata in self.active_clients.items()
            ]
            await self.send_to_admin_socket(self.admin_websocket, {"type": "client_list_update", "clients": clients_data})

    async def send_pending_requests_to_admin(self):
        if self.admin_websocket:
            pending_data = [
                {"request_id": rid, "info": rdata["info"]}
                for rid, rdata in self.pending_connections.items()
            ]
            await self.send_to_admin_socket(self.admin_websocket, {"type": "pending_requests_list", "requests": pending_data})


    async def forward_user_message_to_admin(self, client_id: str, message: str):
        if self.admin_websocket and client_id in self.active_clients:
            client_info = self.active_clients[client_id]["info"]
            await self.send_to_admin_socket(self.admin_websocket, {
                "type": "user_message",
                "client_id": client_id,
                "message": message,
                "client_info": client_info
            })

    async def forward_admin_message_to_client(self, target_client_id: str, message: str):
        if target_client_id in self.active_clients:
            client_data = self.active_clients[target_client_id]
            try:
                await client_data["ws"].send_text(json.dumps({
                    "type": "admin_message",
                    "message": message
                }))
                logger.info(f"Admin message sent to client {target_client_id}")
            except Exception as e:
                logger.error(f"Failed to send admin message to client {target_client_id}: {e}")
                # Consider this client disconnected and clean up
                await self.disconnect_client(client_data["ws"], target_client_id)
        else:
            logger.warning(f"Admin tried to send message to non-existent/inactive client ID: {target_client_id}")
            if self.admin_websocket:
                await self.send_to_admin_socket(self.admin_websocket, {
                    "type": "error", # Or a specific "client_not_found" type
                    "message": f"Client {target_client_id} not found or is not active."
                })


    def is_client_pending(self, websocket: WebSocket) -> bool:
        for data in self.pending_connections.values():
            if data["ws"] == websocket:
                return True
        return False

    def is_client_active(self, websocket: WebSocket) -> Optional[str]:
        for client_id, data in self.active_clients.items():
            if data["ws"] == websocket:
                return client_id
        return None

manager = ConnectionManager()

@app.websocket("/admin")
async def admin_websocket_endpoint(websocket: WebSocket):
    await manager.connect_admin(websocket)
    try:
        while True:
            message_text = await websocket.receive_text()
            data = json.loads(message_text)
            logger.info(f"Admin received: {data}")

            if data["type"] == "connection_response":
                await manager.handle_admin_response(data["request_id"], data["action"])
            elif data["type"] == "admin_message_to_client":
                await manager.forward_admin_message_to_client(data["target_client_id"], data["message"])
            elif data["type"] == "get_client_list": # For explicit request if needed
                await manager.send_client_list_to_admin()
            elif data["type"] == "get_pending_requests":
                await manager.send_pending_requests_to_admin()

    except WebSocketDisconnect:
        logger.info("Admin WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Error in admin WebSocket: {e}", exc_info=True)
    finally:
        await manager.disconnect_admin()

@app.websocket("/ws")
async def client_websocket_endpoint(websocket: WebSocket):
    # Client connects, put into pending until admin approves.
    # The request_id will become the client_id upon approval.
    client_id_pending = await manager.request_connection(websocket)
    is_approved = False
    current_client_id = client_id_pending # Temporarily, will be confirmed or client will disconnect

    try:
        while True:
            # Wait for admin approval or messages
            message_text = await websocket.receive_text()

            if not manager.is_client_active(websocket):
                # Check if it's still pending or got rejected and is about to be closed
                if manager.is_client_pending(websocket):
                    await websocket.send_text(json.dumps({
                        "type": "status_update",
                        "message": "Connection request pending admin approval. Please wait."
                    }))
                    logger.info(f"Client {current_client_id} sent message while pending.")
                else: # No longer pending, might have been rejected or an issue
                    logger.info(f"Client {current_client_id} sent message but is not active or pending. Connection might be stale.")
                    # Optionally send a message indicating this state, then break or let disconnect handle.
                    await websocket.send_text(json.dumps({"type": "error", "message": "Connection not active."}))
                    break # Exit loop, connection will close.
                continue # Don't process message further if not approved


            # If loop continues, client is approved. Update current_client_id if it wasn't already set by approval message
            active_id = manager.is_client_active(websocket)
            if active_id:
                current_client_id = active_id # This is the true ID now
                is_approved = True
            else: # Should not happen if logic is correct, but as a safeguard
                logger.error(f"Client {current_client_id} passed active check but no ID found. Forcing disconnect.")
                await websocket.send_text(json.dumps({"type": "error", "message": "Internal server error. Please reconnect."}))
                break


            # Process client's message
            logger.info(f"Client {current_client_id} sent: {message_text}")
            # Assume plain text for simplicity from client, or simple JSON like {"message": "..."}
            # For this example, we'll assume it's plain text to be forwarded.
            # If you expect JSON from clients:
            # try:
            #     parsed_msg = json.loads(message_text)
            #     actual_message = parsed_msg.get("message", message_text)
            # except json.JSONDecodeError:
            #     actual_message = message_text
            actual_message = message_text # Keep it simple for now

            await manager.forward_user_message_to_admin(current_client_id, actual_message)

    except WebSocketDisconnect:
        logger.info(f"Client {current_client_id} (IP: {websocket.client.host if websocket.client else 'N/A'}) disconnected.")
    except Exception as e:
        logger.error(f"Error in client WebSocket {current_client_id} (IP: {websocket.client.host if websocket.client else 'N/A'}): {e}", exc_info=True)
    finally:
        # The client_id passed here might be the initial pending_id or the confirmed active_id
        await manager.disconnect_client(websocket, current_client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
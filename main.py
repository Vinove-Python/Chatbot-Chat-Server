from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.templating import Jinja2Templates
from typing import Set, Dict, Optional, List, Any
import uuid, json, logging, hashlib, secrets, os
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncpg
import jwt
from admin_interface import HTML_ADMIN_INTERFACE
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", None)
SECRET_KEY = os.getenv("SECRET_KEY", "this-is-temp-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 500

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await init_db()
    yield
    # Shutdown logic
    if db_pool:
        await db_pool.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
templates = Jinja2Templates(directory="templates")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

async def init_db():
    """Initialize database connection and create tables"""
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with db_pool.acquire() as conn:
        # Create users table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS chatserver_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Create sessions table for token management
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS chatserver_user_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES chatserver_users(id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create default admin user if not exists
        admin_exists = await conn.fetchval("SELECT COUNT(*) FROM chatserver_users WHERE username = 'admin'")
        if admin_exists == 0:
            admin_password = hash_password("admin123")  # Change this in production!
            await conn.execute('''
                INSERT INTO chatserver_users (username, email, password_hash, is_admin)
                VALUES ($1, $2, $3, $4)
            ''', "admin", "admin@example.com", admin_password, True)
            logger.info("Default admin user created (username: admin, password: admin123)")

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hash_password(password) == hashed

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM chatserver_users WHERE username = $1", username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Check if token is still valid in sessions table
        token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        session = await conn.fetchrow(
            "SELECT * FROM chatserver_user_sessions WHERE user_id = $1 AND token_hash = $2 AND expires_at > NOW()",
            user['id'], token_hash
        )
        if session is None:
            raise HTTPException(status_code=401, detail="Token expired or invalid")
    
    return dict(user)

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    """Ensure current user is admin"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# HTML Templates
LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 400px; 
            margin: 100px auto; 
            padding: 20px;
            background-color: #f5f5f5;
        }
        .form-container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"], input[type="email"] { 
            width: 100%; 
            padding: 10px; 
            border: 1px solid #ddd; 
            border-radius: 4px;
            box-sizing: border-box;
        }
        button { 
            width: 100%; 
            padding: 12px; 
            background: #1D1E20; 
            color: white; 
            border: none; 
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
        }
        .toggle-link { 
            text-align: center; 
            margin-top: 15px; 
            color: #555;
        }
        .toggle-link a { 
            color: #0d6efd; 
            text-decoration: none;
            font-weight: bold;
        }
        .error { 
            color: red; 
            margin-bottom: 15px; 
            text-align: center;
        }
        h2 { text-align: center; margin-bottom: 30px; color: #333; }
    </style>
</head>
<body>
    <div class="form-container">
        <h2 id="form-title">Admin Login</h2>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form id="auth-form" method="post">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            
            <div class="form-group" id="email-group" style="display: none;">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email">
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" id="submit-btn">Login</button>
        </form>
        
        <div class="toggle-link">
            <span>Don't have an account?</span> <a href="#" id="toggle-link">Register here</a>
        </div>
    </div>

    <script>
        let isLogin = true;
        const form = document.getElementById('auth-form');
        const title = document.getElementById('form-title');
        const submitBtn = document.getElementById('submit-btn');
        const toggleLink = document.getElementById('toggle-link');
        const emailGroup = document.getElementById('email-group');
        const emailInput = document.getElementById('email');
        const spanEle = document.querySelector('.toggle-link span');

        toggleLink.addEventListener('click', function(e) {
            e.preventDefault();
            isLogin = !isLogin;
            
            if (isLogin) {
                title.textContent = 'Admin Login';
                submitBtn.textContent = 'Login';
                toggleLink.textContent = "Register here";
                spanEle.textContent = "Don't have an account?";
                emailGroup.style.display = 'none';
                emailInput.required = false;
                form.action = '/login';
            } else {
                title.textContent = 'Admin Register';
                submitBtn.textContent = 'Register';
                toggleLink.textContent = 'Login here';
                spanEle.textContent = 'Already have an account?';
                emailGroup.style.display = 'block';
                emailInput.required = true;
                form.action = '/register';
            }
        });

        // Set initial form action
        form.action = '/login';
    </script>
</body>
</html>
'''

# @app.on_event("startup")
# async def startup():
#     await init_db()

# @app.on_event("shutdown")
# async def shutdown():
#     if db_pool:
#         await db_pool.close()

@app.get("/login")
async def login_page(request: Request, error: str = None):
    """Serve login page"""
    return HTMLResponse(LOGIN_HTML.replace("{% if error %}", "")
                                 .replace("{{ error }}", error or "")
                                 .replace("{% endif %}", ""))

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """Handle login"""
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM chatserver_users WHERE username = $1", username
        )
        
        if not user or not verify_password(password, user['password_hash']):
            return HTMLResponse(
                LOGIN_HTML.replace("{% if error %}", "").replace("{{ error }}", "Invalid username or password").replace("{% endif %}", ""),
                status_code=400
            )
        
        if not user['is_admin']:
            return HTMLResponse(
                LOGIN_HTML.replace("{% if error %}", "").replace("{{ error }}", "Admin access required").replace("{% endif %}", ""),
                status_code=403
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['username']}, expires_delta=access_token_expires
        )
        
        # Store session in database
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        expires_at = datetime.now() + access_token_expires
        await conn.execute(
            "INSERT INTO chatserver_user_sessions (user_id, token_hash, expires_at) VALUES ($1, $2, $3)",
            user['id'], token_hash, expires_at
        )
        
        # Update last login
        await conn.execute(
            "UPDATE chatserver_users SET last_login = CURRENT_TIMESTAMP WHERE id = $1",
            user['id']
        )
        print('------------------')
        print(f"Bearer {access_token}")
        print('------------------')
        # Redirect to admin interface with token in cookie
        response = RedirectResponse(url="/", status_code=302)
        print(f"access_token: {access_token}, type: {type(access_token)}")
        response.set_cookie(
            key="access_token", 
            value=f"Bearer {access_token}",
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            httponly=False
        )
        return response

@app.post("/register")
async def register(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    """Handle registration"""
    async with db_pool.acquire() as conn:
        # Check if user already exists
        existing_user = await conn.fetchrow(
            "SELECT id FROM chatserver_users WHERE username = $1 OR email = $2", username, email
        )
        
        if existing_user:
            return HTMLResponse(
                LOGIN_HTML.replace("{% if error %}", "").replace("{{ error }}", "Username or email already exists").replace("{% endif %}", ""),
                status_code=400
            )
        
        # Create new user
        password_hash = hash_password(password)
        await conn.execute(
            "INSERT INTO chatserver_users (username, email, password_hash, is_admin) VALUES ($1, $2, $3, $4)",
            username, email, password_hash, True  # Making all registered users admin for this example
        )
        
        logger.info(f"New admin user registered: {username}")
        
        # Redirect to login
        return RedirectResponse(url="/login", status_code=302)

@app.get("/logout")
async def logout():
    """Handle logout"""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="access_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def get_admin_interface(request: Request):
    """Serve the admin interface - requires authentication"""
    # Check for token in cookie
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    
    try:
        # Remove "Bearer " prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        if not username:
            return RedirectResponse(url="/login", status_code=302)
        
        # Verify user exists and is admin
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM chatserver_users WHERE username = $1 AND is_admin = TRUE", username
            )
            if not user:
                return RedirectResponse(url="/login", status_code=302)
            
            # Check session validity
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            session = await conn.fetchrow(
                "SELECT * FROM chatserver_user_sessions WHERE user_id = $1 AND token_hash = $2 AND expires_at > NOW()",
                user['id'], token_hash
            )
            if not session:
                return RedirectResponse(url="/login", status_code=302)
        
        # Add logout button to admin interface
        admin_html = HTML_ADMIN_INTERFACE.replace(
            "Welcome, ' +username+ '",
            "Welcome, " + username
        )
        
        return HTMLResponse(admin_html)
        
    except jwt.PyJWTError:
        return RedirectResponse(url="/login", status_code=302)

class ConnectionManager:
    def __init__(self):
        # Active client WebSockets: {client_id: {"ws": WebSocket, "info": client_info}}
        self.active_clients: Dict[str, Dict[str, Any]] = {}
        # Pending connection requests: {request_id: {"ws": WebSocket, "info": client_info}}
        self.pending_connections: Dict[str, Dict[str, Any]] = {}
        self.admin_websocket: Optional[WebSocket] = None
        self.authenticated_admin: Optional[dict] = None

    def _get_client_info(self, websocket: WebSocket) -> Dict[str, str]:
        return {
            "user_agent": websocket.headers.get("user-agent", "Unknown"),
            "client_ip": websocket.client.host if websocket.client else "Unknown"
        }

    async def connect_admin(self, websocket: WebSocket, admin_user: dict):
        await websocket.accept()
        self.admin_websocket = websocket
        self.authenticated_admin = admin_user
        logger.info(f"Admin {admin_user['username']} connected.")
        await self.send_client_list_to_admin()
        await self.send_pending_requests_to_admin()

    async def disconnect_admin(self):
        if self.authenticated_admin:
            logger.info(f"Admin {self.authenticated_admin['username']} disconnected.")
        self.admin_websocket = None
        self.authenticated_admin = None

    async def request_connection(self, websocket: WebSocket) -> str:
        """A client requests to connect. They are put in pending."""
        await websocket.accept()
        request_id = str(uuid.uuid4())
        conversation_id = websocket.query_params.get('conversation_id', 'No conversation ID provided')
        client_info = self._get_client_info(websocket)
        client_info['conversation_id'] = conversation_id
        self.pending_connections[request_id] = {"ws": websocket, "info": client_info}

        if self.admin_websocket:
            await self.send_to_admin_socket(self.admin_websocket, {
                "type": "connection_request",
                "request_id": request_id,
                "conversation_id": conversation_id,
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
                await self.send_client_list_to_admin()
                if self.admin_websocket:
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
                await client_websocket.close(code=4001)
                logger.info(f"Connection {request_id} rejected for {client_info['client_ip']}.")
            else:
                logger.warning(f"Unknown action '{action}' for request {request_id}")

        except Exception as e:
            logger.error(f"Error handling admin response for {request_id}: {e}")
            if action == "accept" and request_id in self.active_clients:
                del self.active_clients[request_id]
            await self.send_client_list_to_admin()

    async def disconnect_client(self, websocket: WebSocket, client_id: Optional[str] = None):
        """Handles client disconnection, whether from pending or active."""
        disconnected_client_id = None
        client_ip_for_log = websocket.client.host if websocket.client else "Unknown"

        if client_id and client_id in self.pending_connections:
            if self.pending_connections[client_id]["ws"] == websocket:
                del self.pending_connections[client_id]
                logger.info(f"Pending client {client_id} ({client_ip_for_log}) disconnected.")
                await self.send_pending_requests_to_admin()
                return

        if not client_id:
            for cid, data in list(self.active_clients.items()):
                if data["ws"] == websocket:
                    client_id = cid
                    break
            if not client_id:
                for cid, data in list(self.pending_connections.items()):
                    if data["ws"] == websocket:
                        del self.pending_connections[cid]
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
                await self.disconnect_client(client_data["ws"], target_client_id)
        else:
            logger.warning(f"Admin tried to send message to non-existent/inactive client ID: {target_client_id}")
            if self.admin_websocket:
                await self.send_to_admin_socket(self.admin_websocket, {
                    "type": "error",
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
    # Get token from query parameters or headers
    token = None
    
    # Try to get token from query parameters
    if "token" in websocket.query_params:
        token = websocket.query_params["token"]
    
    # Try to get token from headers
    if not token and "authorization" in websocket.headers:
        auth_header = websocket.headers["authorization"]
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        if not username:
            await websocket.close(code=4001, reason="Invalid token")
            return
        
        # Get user from database
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM chatserver_users WHERE username = $1 AND is_admin = TRUE", username
            )
            if not user:
                await websocket.close(code=4001, reason="Admin access required")
                return
            
            # Verify session
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            session = await conn.fetchrow(
                "SELECT * FROM chatserver_user_sessions WHERE user_id = $1 AND token_hash = $2 AND expires_at > NOW()",
                user['id'], token_hash
            )
            if not session:
                await websocket.close(code=4001, reason="Session expired")
                return
        
        await manager.connect_admin(websocket, dict(user))
        
        try:
            while True:
                message_text = await websocket.receive_text()
                data = json.loads(message_text)
                logger.info(f"Admin {user['username']} received: {data}")

                if data["type"] == "connection_response":
                    await manager.handle_admin_response(data["request_id"], data["action"])
                elif data["type"] == "admin_message_to_client":
                    await manager.forward_admin_message_to_client(data["target_client_id"], data["message"])
                elif data["type"] == "get_client_list":
                    await manager.send_client_list_to_admin()
                elif data["type"] == "get_pending_requests":
                    await manager.send_pending_requests_to_admin()

        except WebSocketDisconnect:
            logger.info(f"Admin {user['username']} WebSocket disconnected.")
        except Exception as e:
            logger.error(f"Error in admin WebSocket: {e}", exc_info=True)
        finally:
            await manager.disconnect_admin()
            
    except jwt.PyJWTError:
        await websocket.close(code=4001, reason="Invalid token")

@app.websocket("/ws")
async def client_websocket_endpoint(websocket: WebSocket):
    client_id_pending = await manager.request_connection(websocket)
    is_approved = False
    current_client_id = client_id_pending

    try:
        while True:
            message_text = await websocket.receive_text()

            if not manager.is_client_active(websocket):
                if manager.is_client_pending(websocket):
                    await websocket.send_text(json.dumps({
                        "type": "status_update",
                        "message": "Connection request pending admin approval. Please wait."
                    }))
                    logger.info(f"Client {current_client_id} sent message while pending.")
                else:
                    logger.info(f"Client {current_client_id} sent message but is not active or pending. Connection might be stale.")
                    await websocket.send_text(json.dumps({"type": "error", "message": "Connection not active."}))
                    break
                continue

            active_id = manager.is_client_active(websocket)
            if active_id:
                current_client_id = active_id
                is_approved = True
            else:
                logger.error(f"Client {current_client_id} passed active check but no ID found. Forcing disconnect.")
                await websocket.send_text(json.dumps({"type": "error", "message": "Internal server error. Please reconnect."}))
                break

            logger.info(f"Client {current_client_id} sent: {message_text}")
            actual_message = message_text
            await manager.forward_user_message_to_admin(current_client_id, actual_message)

    except WebSocketDisconnect:
        logger.info(f"Client {current_client_id} (IP: {websocket.client.host if websocket.client else 'N/A'}) disconnected.")
    except Exception as e:
        logger.error(f"Error in client WebSocket {current_client_id} (IP: {websocket.client.host if websocket.client else 'N/A'}): {e}", exc_info=True)
    finally:
        await manager.disconnect_client(websocket, current_client_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from passlib.hash import pbkdf2_sha256
from datetime import datetime, timedelta
import os
import secrets
import json
import asyncio
import websockets
from concurrent.futures import ThreadPoolExecutor

# 导入数据库模型
from models import db, User, Project, CollaborationSession

# 导入日志配置
from logging_config import logger

# 配置应用
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-for-flask-session-32bytes')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-jwt-secret-key-must-be-32-bytes-long')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化扩展
CORS(app, supports_credentials=True)
db.init_app(app)
jwt = JWTManager(app)

# JWT错误处理器
@jwt.invalid_token_loader
def invalid_token_callback(error_string):
    logger.warning(f"无效的Token: {error_string}")
    return jsonify({'error': '无效的登录凭证，请重新登录', 'code': 'INVALID_TOKEN'}), 422

@jwt.unauthorized_loader
def unauthorized_callback(error_string):
    logger.warning(f"未授权访问: {error_string}")
    return jsonify({'error': '请先登录', 'code': 'UNAUTHORIZED'}), 401

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    logger.warning(f"Token已过期")
    return jsonify({'error': '登录已过期，请重新登录', 'code': 'TOKEN_EXPIRED'}), 422

# 请求日志中间件
@app.before_request
def log_request():
    if request.path.startswith('/api/'):
        auth_header = request.headers.get('Authorization', 'None')
        logger.info(f"请求: {request.method} {request.path}, Auth: {auth_header[:50] if auth_header else 'None'}...")

# WebSocket连接管理
class ConnectionManager:
    """
    WebSocket连接管理器
    
    新的同步机制（类似Git）：
    1. 本地操作只记录，不实时发送
    2. 用户点击"同步"按钮时，上传本地修改并拉取他人修改
    3. 新用户加入时，从服务器获取项目快照
    """
    def __init__(self):
        self.active_connections = {}
        self.project_connections = {}
        self.user_connections = {}
        # 项目快照存储 {project_token: {projectJSON, timestamp, userId}}
        self.project_snapshots = {}

    async def connect(self, websocket, project_token, user_id):
        connection_id = id(websocket)
        self.active_connections[connection_id] = {
            'websocket': websocket,
            'project_token': project_token,
            'user_id': user_id
        }
        # 按项目分组
        if project_token not in self.project_connections:
            self.project_connections[project_token] = set()
        self.project_connections[project_token].add(connection_id)
        # 按用户ID分组
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        # 通知其他用户有新用户加入
        await self.broadcast(project_token, {
            'type': 'user_joined',
            'user_id': user_id
        }, exclude=connection_id)
        
        logger.info(f"用户 {user_id} 连接到项目 {project_token}")

    def disconnect(self, websocket):
        connection_id = id(websocket)
        if connection_id in self.active_connections:
            project_token = self.active_connections[connection_id]['project_token']
            user_id = self.active_connections[connection_id]['user_id']
            # 从项目分组中移除
            if project_token in self.project_connections:
                self.project_connections[project_token].discard(connection_id)
                if not self.project_connections[project_token]:
                    del self.project_connections[project_token]
                    # 项目无人时清理快照
                    if project_token in self.project_snapshots:
                        del self.project_snapshots[project_token]
                        logger.info(f"清理项目 {project_token} 的快照")
            # 从用户分组中移除
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            # 移除连接
            del self.active_connections[connection_id]
            # 通知其他用户有用户离开
            asyncio.create_task(self.broadcast(project_token, {
                'type': 'user_left',
                'user_id': user_id
            }))
            logger.info(f"用户 {user_id} 断开连接")

    async def broadcast(self, project_token, message, exclude=None):
        """广播消息给项目内所有用户"""
        if project_token in self.project_connections:
            for connection_id in self.project_connections[project_token]:
                if connection_id != exclude and connection_id in self.active_connections:
                    try:
                        await self.active_connections[connection_id]['websocket'].send(json.dumps(message))
                    except:
                        self.disconnect(self.active_connections[connection_id]['websocket'])

    async def send_to_user(self, user_id, message):
        """发送消息给指定用户"""
        if user_id in self.user_connections:
            for connection_id in list(self.user_connections[user_id]):
                if connection_id in self.active_connections:
                    try:
                        await self.active_connections[connection_id]['websocket'].send(json.dumps(message))
                        logger.info(f"已发送消息给用户 {user_id}")
                        return True
                    except:
                        self.disconnect(self.active_connections[connection_id]['websocket'])
        logger.warning(f"找不到用户 {user_id} 的连接")
        return False

    def save_snapshot(self, project_token, projectJSON, user_id):
        """保存项目快照"""
        self.project_snapshots[project_token] = {
            'projectJSON': projectJSON,
            'timestamp': datetime.now().isoformat(),
            'userId': user_id
        }
        logger.info(f"保存项目 {project_token} 快照，用户: {user_id}")

    def get_snapshot(self, project_token):
        """获取项目快照"""
        return self.project_snapshots.get(project_token)

    async def handle_manual_sync(self, project_token, sync_data, sender_user_id):
        """
        处理手动同步请求
        
        1. 保存用户上传的项目快照
        2. 广播同步响应给所有用户（不包括发送者）
        """
        projectJSON = sync_data.get('projectJSON')
        if not projectJSON:
            logger.warning(f"同步请求缺少项目数据: {project_token}")
            return
        
        # 保存快照
        self.save_snapshot(project_token, projectJSON, sender_user_id)
        
        # 构造同步响应消息
        sync_response = {
            'type': 'sync_response',
            'data': {
                'projectJSON': projectJSON,
                'targetId': sync_data.get('targetId'),
                'timestamp': sync_data.get('timestamp'),
                'userId': sender_user_id,
                'clientId': sync_data.get('clientId')
            }
        }
        
        logger.info(f"广播 sync_response 给项目 {project_token}")
        
        # 广播同步响应给项目内所有用户
        if project_token in self.project_connections:
            for connection_id in self.project_connections[project_token]:
                if connection_id in self.active_connections:
                    try:
                        await self.active_connections[connection_id]['websocket'].send(json.dumps(sync_response))
                        logger.info(f"已发送 sync_response 给用户 {self.active_connections[connection_id]['user_id']}")
                    except Exception as e:
                        logger.error(f"发送 sync_response 失败: {e}")
        
        logger.info(f"项目 {project_token} 同步完成，用户: {sender_user_id}")

    async def handle_request_snapshot(self, project_token, user_id):
        """
        处理快照请求（新用户加入时）
        
        如果有快照，发送给请求的用户
        """
        snapshot = self.get_snapshot(project_token)
        if snapshot:
            await self.send_to_user(user_id, {
                'type': 'project_sync',
                'data': {
                    'projectJSON': snapshot['projectJSON'],
                    'timestamp': snapshot['timestamp'],
                    'forUser': user_id
                }
            })
            logger.info(f"发送快照给用户 {user_id}")
        else:
            logger.info(f"项目 {project_token} 暂无快照，用户 {user_id} 需要等待其他用户同步")

# 初始化连接管理器
manager = ConnectionManager()

# 创建数据库表
with app.app_context():
    db.create_all()

# WebSocket处理函数
async def websocket_handler(websocket, path=None):
    # 兼容不同版本 websockets 的 handler 参数与 path 获取方式
    if path is None:
        # websockets 新版本可能没有 path 参数
        if hasattr(websocket, 'path') and websocket.path:
            path = websocket.path
        elif hasattr(websocket, 'request') and getattr(websocket.request, 'path', None):
            path = websocket.request.path
        else:
            path = '/'

    project_token = path.strip('/')
    user_id = None
    
    try:
        logger.info(f"新的WebSocket连接尝试: {project_token}")
        
        # 验证连接
        auth_message = await websocket.recv()
        auth_data = json.loads(auth_message)
        
        if auth_data.get('type') == 'auth':
            token = auth_data.get('token')
            
            # 在应用上下文中执行数据库操作
            with app.app_context():
                # 验证项目token是否存在
                project = Project.query.filter_by(token=project_token).first()
                if not project:
                    logger.warning(f"无效的项目token: {project_token}")
                    await websocket.close(code=1008, reason="Invalid project token")
                    return
                
                # 处理用户认证
                if token:
                    try:
                        # 使用flask-jwt-extended的工具来验证token
                        from flask_jwt_extended import decode_token
                        decoded = decode_token(token)
                        user_id = decoded['sub']
                        logger.info(f"用户 {user_id} 尝试连接项目 {project_token}")
                        
                        # 记录协作会话
                        session = CollaborationSession(project_id=project.id, user_id=user_id)
                        db.session.add(session)
                        db.session.commit()
                    except Exception as jwt_err:
                        logger.warning(f"JWT验证失败，使用匿名连接: {jwt_err}")
                        # JWT验证失败时，允许匿名连接
                        user_id = f"anonymous_{secrets.token_hex(8)}"
                        logger.info(f"匿名用户 {user_id} 尝试连接项目 {project_token}")
                else:
                    # 匿名用户连接
                    user_id = f"anonymous_{secrets.token_hex(8)}"
                    logger.info(f"匿名用户 {user_id} 尝试连接项目 {project_token}")
                
                logger.info(f"用户 {user_id} 成功连接项目 {project_token}")
            
            # 接受连接
            await manager.connect(websocket, project_token, user_id)
            
            # 处理消息
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get('type')
                    
                    if message_type == 'manual_sync':
                        # 手动同步请求
                        sync_data = data.get('data', {})
                        await manager.handle_manual_sync(project_token, sync_data, user_id)
                        
                    elif message_type == 'request_snapshot':
                        # 请求项目快照
                        await manager.handle_request_snapshot(project_token, user_id)
                        
                    elif message_type == 'project_sync':
                        # 项目同步消息（发送给新用户）
                        sync_data = data.get('data', {})
                        for_user = sync_data.get('forUser')
                        
                        if for_user:
                            # 发送给指定用户
                            logger.info(f"转发项目同步消息给用户 {for_user}")
                            await manager.send_to_user(for_user, {
                                'type': 'project_sync',
                                'data': sync_data
                            })
                        else:
                            # 广播给所有用户
                            await manager.broadcast(project_token, data)
                            
                    else:
                        # 其他消息广播给项目内其他用户
                        await manager.broadcast(project_token, data)
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"无效的消息格式: {e}")
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
        else:
            logger.warning("缺少认证信息")
            await websocket.close(code=1008, reason="Authentication required")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.info(f"WebSocket连接关闭: {e}")
    except Exception as e:
        logger.error(f"WebSocket处理错误: {e}")
    finally:
        if websocket:
            manager.disconnect(websocket)
            logger.info(f"清理WebSocket连接: {project_token}")

# API路由
@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        logger.info(f"用户注册尝试: {email}")
        
        # 验证请求数据
        if not data:
            logger.warning("注册请求缺少数据")
            return jsonify({'error': '请求数据不能为空'}), 400
        
        # 验证邮箱格式
        if not email or not email.endswith('@163.com'):
            logger.warning(f"无效的邮箱格式: {email}")
            return jsonify({'error': '请使用163邮箱注册'}), 400
        
        # 验证密码长度
        if not password or len(password) < 6:
            logger.warning("密码长度不足")
            return jsonify({'error': '密码长度至少6位'}), 400
        
        # 检查邮箱是否已存在
        if User.query.filter_by(email=email).first():
            logger.warning(f"邮箱已注册: {email}")
            return jsonify({'error': '该邮箱已注册'}), 400
        
        # 创建新用户
        password_hash = pbkdf2_sha256.hash(password)
        new_user = User(email=email, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        
        # 生成访问令牌 (identity 必须是字符串)
        access_token = create_access_token(identity=str(new_user.id), expires_delta=timedelta(days=7))
        logger.info(f"用户注册成功: {email}, ID: {new_user.id}")
        
        return jsonify({'access_token': access_token, 'user_id': new_user.id}), 201
    except Exception as e:
        logger.error(f"注册错误: {e}")
        return jsonify({'error': '注册失败，请稍后重试'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        logger.info(f"用户登录尝试: {email}")
        
        # 验证请求数据
        if not data:
            logger.warning("登录请求缺少数据")
            return jsonify({'error': '请求数据不能为空'}), 400
        
        if not email or not password:
            logger.warning("邮箱或密码为空")
            return jsonify({'error': '邮箱和密码不能为空'}), 400
        
        # 查找用户
        user = User.query.filter_by(email=email).first()
        if not user or not pbkdf2_sha256.verify(password, user.password_hash):
            logger.warning(f"登录失败: {email}")
            return jsonify({'error': '邮箱或密码错误'}), 401
        
        # 生成访问令牌 (identity 必须是字符串)
        access_token = create_access_token(identity=str(user.id), expires_delta=timedelta(days=7))
        logger.info(f"用户登录成功: {email}, ID: {user.id}")
        
        return jsonify({'access_token': access_token, 'user_id': user.id}), 200
    except Exception as e:
        logger.error(f"登录错误: {e}")
        return jsonify({'error': '登录失败，请稍后重试'}), 500

@app.route('/api/projects', methods=['GET'])
@jwt_required()
def get_projects():
    try:
        user_id = int(get_jwt_identity())  # JWT identity 是字符串，需要转换为整数
        logger.info(f"用户 {user_id} 获取项目列表")
        
        projects = Project.query.filter_by(owner_id=user_id).all()
        project_list = [{
            'id': p.id,
            'name': p.name,
            'token': p.token,
            'created_at': p.created_at.isoformat()
        } for p in projects]
        
        logger.info(f"用户 {user_id} 项目列表获取成功，共 {len(project_list)} 个项目")
        return jsonify(project_list), 200
    except Exception as e:
        logger.error(f"获取项目列表错误: {e}")
        return jsonify({'error': '获取项目列表失败'}), 500

@app.route('/api/projects', methods=['POST'])
@jwt_required()
def create_project():
    try:
        user_id = int(get_jwt_identity())  # JWT identity 是字符串，需要转换为整数
        data = request.get_json()
        name = data.get('name')
        
        logger.info(f"用户 {user_id} 创建项目: {name}")
        
        # 验证请求数据
        if not data:
            logger.warning("创建项目请求缺少数据")
            return jsonify({'error': '请求数据不能为空'}), 400
        
        if not name or not name.strip():
            logger.warning(f"用户 {user_id} 项目名称为空")
            return jsonify({'error': '项目名称不能为空'}), 400
        
        # 生成唯一token
        token = secrets.token_urlsafe(32)
        while Project.query.filter_by(token=token).first():
            token = secrets.token_urlsafe(32)
        
        # 创建项目
        new_project = Project(name=name.strip(), owner_id=user_id, token=token)
        db.session.add(new_project)
        db.session.commit()
        
        logger.info(f"用户 {user_id} 项目创建成功: {name}, ID: {new_project.id}")
        
        return jsonify({
            'id': new_project.id,
            'name': new_project.name,
            'token': new_project.token,
            'created_at': new_project.created_at.isoformat()
        }), 201
    except Exception as e:
        logger.error(f"创建项目错误: {e}")
        return jsonify({'error': '创建项目失败，请稍后重试'}), 500

@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
@jwt_required()
def delete_project(project_id):
    try:
        user_id = int(get_jwt_identity())  # JWT identity 是字符串，需要转换为整数
        logger.info(f"用户 {user_id} 删除项目: {project_id}")
        
        project = Project.query.filter_by(id=project_id, owner_id=user_id).first()
        
        if not project:
            logger.warning(f"用户 {user_id} 尝试删除不存在的项目: {project_id}")
            return jsonify({'error': '项目不存在或无权限'}), 404
        
        db.session.delete(project)
        db.session.commit()
        
        logger.info(f"用户 {user_id} 项目删除成功: {project_id}")
        return jsonify({'message': '项目已删除'}), 200
    except Exception as e:
        logger.error(f"删除项目错误: {e}")
        return jsonify({'error': '删除项目失败，请稍后重试'}), 500

# 启动WebSocket服务器
async def websocket_server_main():
    """在事件循环中启动并保持WebSocket服务运行。"""
    async with websockets.serve(websocket_handler, "0.0.0.0", 8765):
        logger.info("WebSocket服务器已启动，监听端口 8765")
        # 持续运行直到进程退出
        await asyncio.Future()


def start_websocket_server():
    try:
        logger.info("正在启动WebSocket服务器...")
        # 在当前线程创建并运行事件循环（兼容 websockets 新版本）
        asyncio.run(websocket_server_main())
    except Exception as e:
        logger.error(f"WebSocket服务器启动失败: {e}")

if __name__ == '__main__':
    # 在后台线程中启动WebSocket服务器
    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(start_websocket_server)
    
    # 启动Flask应用
    logger.info("正在启动Flask应用...")
    app.run(debug=False, host='0.0.0.0', port=5000)
    logger.info("Flask应用已启动，监听端口 5000")

# 认证系统测试
import unittest
import json
from app import app, db
from models import User, Project

class AuthTest(unittest.TestCase):
    def setUp(self):
        # 设置测试客户端
        self.app = app.test_client()
        self.app.testing = True
        
        # 创建测试数据库
        with app.app_context():
            db.create_all()
    
    def tearDown(self):
        # 清理测试数据库
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_register(self):
        """测试用户注册"""
        response = self.app.post('/api/auth/register', data=json.dumps({
            'email': 'test@163.com',
            'password': '123456'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn('access_token', data)
        self.assertIn('user_id', data)
    
    def test_register_invalid_email(self):
        """测试无效邮箱注册"""
        response = self.app.post('/api/auth/register', data=json.dumps({
            'email': 'test@gmail.com',
            'password': '123456'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_login(self):
        """测试用户登录"""
        # 先注册一个用户
        self.app.post('/api/auth/register', data=json.dumps({
            'email': 'test@163.com',
            'password': '123456'
        }), content_type='application/json')
        
        # 然后登录
        response = self.app.post('/api/auth/login', data=json.dumps({
            'email': 'test@163.com',
            'password': '123456'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('access_token', data)
        self.assertIn('user_id', data)
    
    def test_login_invalid(self):
        """测试无效登录"""
        response = self.app.post('/api/auth/login', data=json.dumps({
            'email': 'test@163.com',
            'password': 'wrongpassword'
        }), content_type='application/json')
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_create_project(self):
        """测试创建项目"""
        # 先注册并登录
        register_response = self.app.post('/api/auth/register', data=json.dumps({
            'email': 'test@163.com',
            'password': '123456'
        }), content_type='application/json')
        
        token = json.loads(register_response.data)['access_token']
        
        # 创建项目
        response = self.app.post('/api/projects', data=json.dumps({
            'name': '测试项目'
        }), headers={
            'Authorization': f'Bearer {token}'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('token', data)
    
    def test_get_projects(self):
        """测试获取项目列表"""
        # 先注册并登录
        register_response = self.app.post('/api/auth/register', data=json.dumps({
            'email': 'test@163.com',
            'password': '123456'
        }), content_type='application/json')
        
        token = json.loads(register_response.data)['access_token']
        
        # 创建项目
        self.app.post('/api/projects', data=json.dumps({
            'name': '测试项目'
        }), headers={
            'Authorization': f'Bearer {token}'
        }, content_type='application/json')
        
        # 获取项目列表
        response = self.app.get('/api/projects', headers={
            'Authorization': f'Bearer {token}'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

if __name__ == '__main__':
    unittest.main()
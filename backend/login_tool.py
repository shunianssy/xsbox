"""
XSBox 登录和项目管理工具
用于测试和管理协作功能

使用方法:
1. 运行此脚本: python login_tool.py
2. 点击"注册"创建新用户
3. 登录后可以创建项目和获取邀请链接
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import json
import webbrowser

# API 配置
API_BASE_URL = "http://localhost:5000"

class LoginTool:
    def __init__(self, root):
        self.root = root
        self.root.title("XSBox 登录和项目管理工具")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # 当前用户信息
        self.auth_token = None
        self.user_id = None
        
        # 创建界面
        self.create_widgets()
        
    def create_widgets(self):
        # 创建笔记本（选项卡）
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 登录选项卡
        login_frame = ttk.Frame(notebook)
        notebook.add(login_frame, text='登录/注册')
        self.create_login_tab(login_frame)
        
        # 项目管理选项卡
        project_frame = ttk.Frame(notebook)
        notebook.add(project_frame, text='项目管理')
        self.create_project_tab(project_frame)
        
        # 协作测试选项卡
        collab_frame = ttk.Frame(notebook)
        notebook.add(collab_frame, text='协作测试')
        self.create_collab_tab(collab_frame)
        
        # 日志选项卡
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text='日志')
        self.create_log_tab(log_frame)
        
    def create_login_tab(self, parent):
        # 登录框架
        login_group = ttk.LabelFrame(parent, text="登录", padding=10)
        login_group.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(login_group, text="邮箱:").grid(row=0, column=0, sticky='w', pady=2)
        self.login_email = ttk.Entry(login_group, width=40)
        self.login_email.grid(row=0, column=1, pady=2, padx=5)
        
        ttk.Label(login_group, text="密码:").grid(row=1, column=0, sticky='w', pady=2)
        self.login_password = ttk.Entry(login_group, width=40, show="*")
        self.login_password.grid(row=1, column=1, pady=2, padx=5)
        
        ttk.Button(login_group, text="登录", command=self.do_login).grid(row=2, column=0, columnspan=2, pady=10)
        
        # 注册框架
        register_group = ttk.LabelFrame(parent, text="注册 (需要163邮箱)", padding=10)
        register_group.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(register_group, text="邮箱:").grid(row=0, column=0, sticky='w', pady=2)
        self.register_email = ttk.Entry(register_group, width=40)
        self.register_email.grid(row=0, column=1, pady=2, padx=5)
        self.register_email.insert(0, "@163.com")
        
        ttk.Label(register_group, text="密码:").grid(row=1, column=0, sticky='w', pady=2)
        self.register_password = ttk.Entry(register_group, width=40, show="*")
        self.register_password.grid(row=1, column=1, pady=2, padx=5)
        
        ttk.Label(register_group, text="确认密码:").grid(row=2, column=0, sticky='w', pady=2)
        self.register_password2 = ttk.Entry(register_group, width=40, show="*")
        self.register_password2.grid(row=2, column=1, pady=2, padx=5)
        
        ttk.Button(register_group, text="注册", command=self.do_register).grid(row=3, column=0, columnspan=2, pady=10)
        
        # 状态显示
        status_group = ttk.LabelFrame(parent, text="状态", padding=10)
        status_group.pack(fill='x', padx=10, pady=5)
        
        self.status_label = ttk.Label(status_group, text="未登录", foreground="red")
        self.status_label.pack()
        
    def create_project_tab(self, parent):
        # 创建项目
        create_group = ttk.LabelFrame(parent, text="创建新项目", padding=10)
        create_group.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(create_group, text="项目名称:").grid(row=0, column=0, sticky='w', pady=2)
        self.project_name = ttk.Entry(create_group, width=40)
        self.project_name.grid(row=0, column=1, pady=2, padx=5)
        
        ttk.Button(create_group, text="创建项目", command=self.create_project).grid(row=1, column=0, columnspan=2, pady=10)
        
        # 项目列表
        list_group = ttk.LabelFrame(parent, text="我的项目", padding=10)
        list_group.pack(fill='both', expand=True, padx=10, pady=5)
        
        # 项目列表树
        columns = ('id', 'name', 'token', 'created_at')
        self.project_tree = ttk.Treeview(list_group, columns=columns, show='headings', height=8)
        self.project_tree.heading('id', text='ID')
        self.project_tree.heading('name', text='名称')
        self.project_tree.heading('token', text='Token')
        self.project_tree.heading('created_at', text='创建时间')
        
        self.project_tree.column('id', width=50)
        self.project_tree.column('name', width=150)
        self.project_tree.column('token', width=200)
        self.project_tree.column('created_at', width=150)
        
        self.project_tree.pack(fill='both', expand=True)
        
        # 按钮
        btn_frame = ttk.Frame(list_group)
        btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(btn_frame, text="刷新列表", command=self.load_projects).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="复制邀请链接", command=self.copy_invite_link).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="打开协作页面", command=self.open_collab_page).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="删除项目", command=self.delete_project).pack(side='left', padx=5)
        
    def create_collab_tab(self, parent):
        # 快速创建测试环境
        test_group = ttk.LabelFrame(parent, text="快速测试", padding=10)
        test_group.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(test_group, text="快速创建测试用户和项目，用于测试协作功能").pack(pady=5)
        
        ttk.Button(test_group, text="创建测试环境", command=self.create_test_env).pack(pady=5)
        
        # 测试链接
        link_group = ttk.LabelFrame(parent, text="测试链接", padding=10)
        link_group.pack(fill='x', padx=10, pady=5)
        
        self.test_link_label = ttk.Label(link_group, text="点击上方按钮创建测试环境")
        self.test_link_label.pack()
        
        ttk.Button(link_group, text="打开测试页面", command=self.open_test_page).pack(pady=5)
        
    def create_log_tab(self, parent):
        # 日志显示
        log_group = ttk.LabelFrame(parent, text="操作日志", padding=10)
        log_group.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_group, height=20)
        self.log_text.pack(fill='both', expand=True)
        
        ttk.Button(log_group, text="清空日志", command=self.clear_log).pack(pady=5)
        
    def log(self, message):
        """添加日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert('end', f"[{timestamp}] {message}\n")
        self.log_text.see('end')
        
    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', 'end')
        
    def do_login(self):
        """执行登录"""
        email = self.login_email.get().strip()
        password = self.login_password.get()
        
        if not email or not password:
            messagebox.showerror("错误", "请输入邮箱和密码")
            return
            
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/auth/login",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('access_token')
                self.user_id = data.get('user_id')
                self.status_label.config(text=f"已登录: {email} (ID: {self.user_id})", foreground="green")
                self.log(f"登录成功: {email}")
                self.load_projects()
                messagebox.showinfo("成功", "登录成功！")
            else:
                error = response.json().get('error', '未知错误')
                self.log(f"登录失败: {error}")
                messagebox.showerror("登录失败", error)
                
        except Exception as e:
            self.log(f"登录错误: {str(e)}")
            messagebox.showerror("错误", f"连接服务器失败: {str(e)}")
            
    def do_register(self):
        """执行注册"""
        email = self.register_email.get().strip()
        password = self.register_password.get()
        password2 = self.register_password2.get()
        
        if not email or not password:
            messagebox.showerror("错误", "请输入邮箱和密码")
            return
            
        if password != password2:
            messagebox.showerror("错误", "两次密码不一致")
            return
            
        if len(password) < 6:
            messagebox.showerror("错误", "密码长度至少6位")
            return
            
        if not email.endswith('@163.com'):
            messagebox.showerror("错误", "请使用163邮箱")
            return
            
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/auth/register",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.auth_token = data.get('access_token')
                self.user_id = data.get('user_id')
                self.status_label.config(text=f"已登录: {email} (ID: {self.user_id})", foreground="green")
                self.log(f"注册成功: {email}")
                messagebox.showinfo("成功", f"注册成功！\n用户ID: {self.user_id}")
            else:
                error = response.json().get('error', '未知错误')
                self.log(f"注册失败: {error}")
                messagebox.showerror("注册失败", error)
                
        except Exception as e:
            self.log(f"注册错误: {str(e)}")
            messagebox.showerror("错误", f"连接服务器失败: {str(e)}")
            
    def load_projects(self):
        """加载项目列表"""
        if not self.auth_token:
            messagebox.showwarning("提示", "请先登录")
            return
            
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/projects",
                headers={"Authorization": f"Bearer {self.auth_token}"}
            )
            
            if response.status_code == 200:
                projects = response.json()
                
                # 清空列表
                for item in self.project_tree.get_children():
                    self.project_tree.delete(item)
                    
                # 添加项目
                for p in projects:
                    self.project_tree.insert('', 'end', values=(
                        p['id'],
                        p['name'],
                        p['token'],
                        p['created_at']
                    ))
                    
                self.log(f"加载了 {len(projects)} 个项目")
            else:
                error = response.json().get('error', '未知错误')
                self.log(f"加载项目失败: {error}")
                
        except Exception as e:
            self.log(f"加载项目错误: {str(e)}")
            
    def create_project(self):
        """创建项目"""
        if not self.auth_token:
            messagebox.showwarning("提示", "请先登录")
            return
            
        name = self.project_name.get().strip()
        if not name:
            messagebox.showerror("错误", "请输入项目名称")
            return
            
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/projects",
                json={"name": name},
                headers={"Authorization": f"Bearer {self.auth_token}"}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.log(f"创建项目成功: {name} (Token: {data['token'][:16]}...)")
                self.load_projects()
                messagebox.showinfo("成功", f"项目创建成功！\nToken: {data['token']}")
            else:
                error = response.json().get('error', '未知错误')
                self.log(f"创建项目失败: {error}")
                messagebox.showerror("创建失败", error)
                
        except Exception as e:
            self.log(f"创建项目错误: {str(e)}")
            messagebox.showerror("错误", f"连接服务器失败: {str(e)}")
            
    def copy_invite_link(self):
        """复制邀请链接"""
        selected = self.project_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个项目")
            return
            
        item = self.project_tree.item(selected[0])
        token = item['values'][2]
        
        # 复制到剪贴板
        link = f"http://localhost:8601/?invite={token}"
        self.root.clipboard_clear()
        self.root.clipboard_append(link)
        
        self.log(f"已复制邀请链接: {link}")
        messagebox.showinfo("成功", f"邀请链接已复制到剪贴板:\n{link}")
        
    def open_collab_page(self):
        """打开协作页面"""
        selected = self.project_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个项目")
            return
            
        item = self.project_tree.item(selected[0])
        token = item['values'][2]
        
        link = f"http://localhost:8601/?invite={token}"
        webbrowser.open(link)
        self.log(f"打开协作页面: {link}")
        
    def delete_project(self):
        """删除项目"""
        selected = self.project_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个项目")
            return
            
        item = self.project_tree.item(selected[0])
        project_id = item['values'][0]
        project_name = item['values'][1]
        
        if not messagebox.askyesno("确认", f"确定要删除项目 '{project_name}' 吗？"):
            return
            
        try:
            response = requests.delete(
                f"{API_BASE_URL}/api/projects/{project_id}",
                headers={"Authorization": f"Bearer {self.auth_token}"}
            )
            
            if response.status_code == 200:
                self.log(f"删除项目成功: {project_name}")
                self.load_projects()
                messagebox.showinfo("成功", "项目已删除")
            else:
                error = response.json().get('error', '未知错误')
                self.log(f"删除项目失败: {error}")
                messagebox.showerror("删除失败", error)
                
        except Exception as e:
            self.log(f"删除项目错误: {str(e)}")
            
    def create_test_env(self):
        """创建测试环境"""
        import random
        import string
        
        # 生成随机用户名
        random_str = ''.join(random.choices(string.ascii_lowercase, k=8))
        email = f"test_{random_str}@163.com"
        password = "Test123456"
        
        try:
            # 注册用户
            response = requests.post(
                f"{API_BASE_URL}/api/auth/register",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 201:
                data = response.json()
                self.auth_token = data.get('access_token')
                self.user_id = data.get('user_id')
                
                # 创建项目
                project_name = f"测试项目_{random_str}"
                response = requests.post(
                    f"{API_BASE_URL}/api/projects",
                    json={"name": project_name},
                    headers={"Authorization": f"Bearer {self.auth_token}"}
                )
                
                if response.status_code == 201:
                    project_data = response.json()
                    token = project_data['token']
                    link = f"http://localhost:8601/?invite={token}"
                    
                    self.test_link_label.config(text=f"测试链接: {link}")
                    self.status_label.config(text=f"已登录: {email}", foreground="green")
                    
                    self.log(f"测试环境创建成功!")
                    self.log(f"邮箱: {email}")
                    self.log(f"密码: {password}")
                    self.log(f"项目: {project_name}")
                    self.log(f"链接: {link}")
                    
                    self.load_projects()
                    
                    messagebox.showinfo("成功", 
                        f"测试环境创建成功！\n\n"
                        f"邮箱: {email}\n"
                        f"密码: {password}\n"
                        f"项目: {project_name}\n\n"
                        f"点击'打开测试页面'开始测试"
                    )
                else:
                    self.log("创建项目失败")
            else:
                self.log("注册用户失败")
                
        except Exception as e:
            self.log(f"创建测试环境错误: {str(e)}")
            messagebox.showerror("错误", f"创建测试环境失败: {str(e)}")
            
    def open_test_page(self):
        """打开测试页面"""
        selected = self.project_tree.selection()
        if selected:
            item = self.project_tree.item(selected[0])
            token = item['values'][2]
            link = f"http://localhost:8601/?invite={token}"
        else:
            link = "http://localhost:8601"
            
        webbrowser.open(link)
        self.log(f"打开页面: {link}")


def main():
    root = tk.Tk()
    app = LoginTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()

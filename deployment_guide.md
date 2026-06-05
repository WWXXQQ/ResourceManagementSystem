# 卡管理系统 — 云服务器正式部署指南

为了实现系统 24 小时稳定在线，不受个人电脑关机影响，建议将系统部署到云服务器（如阿里云、腾讯云、华为云等，建议最低配置：2核 4G 即可）。

本指南将分别介绍在 **Linux (以 Ubuntu 为例，推荐)** 和 **Windows Server** 环境下的专业生产级部署方案。

---

## 🔒 部署前的安全与代码准备

在部署到公网之前，需要对 Django 进行生产级安全配置：

### 1. 修改 `gpu_management/settings.py` 配置文件
打开 `gpu_management/settings.py`：
- **关闭调试模式**：
  将 `DEBUG = True` 修改为 `DEBUG = False`。
  *(注意：在 `DEBUG = False` 下，Django 默认不再自动托管静态 CSS/JS 资源，必须通过 Nginx 进行反向代理托管，详见后文。)*
- **允许的访问域名/IP**：
  将 `ALLOWED_HOSTS = ['*']` 修改为具体的云服务器公网 IP 或域名，例如：
  `ALLOWED_HOSTS = ['118.x.x.x', 'gpu.yourdomain.com', 'localhost', '127.0.0.1']`
- **生成新的密钥**：
  在生产服务器上，建议替换默认的 `SECRET_KEY` 为一串随机强密钥。

### 2. 收集静态资源文件
在个人电脑的终端里，运行以下命令将系统中所有的静态文件统一打包收集：
```bash
python manage.py collectstatic
```
这会在根目录下生成一个 `staticfiles/` 文件夹。将包含此文件夹的所有代码打包，准备传输到云服务器。

---

## 🐧 方案一：Linux 服务器部署 (Ubuntu 22.04 LTS)

推荐使用 Linux 环境，这是最稳定且占用服务器系统资源最少的方案。我们采用经典的 **Nginx + Gunicorn + Systemd + SQLite** 架构。

### 第一步：环境初始化与依赖安装
1. 更新系统软件包：
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
2. 安装 Python 3.10+、pip、virtualenv 以及 Nginx：
   ```bash
   sudo apt install python3-pip python3-venv python3-dev nginx git -y
   ```
3. 将项目打包好的压缩包上传至服务器 `/var/www/ResourceManagementSystem` 目录下并解压。

### 第二步：配置虚拟环境与数据库
1. 在项目根目录下建立并激活虚拟环境：
   ```bash
   cd /var/www/ResourceManagementSystem
   python3 -m venv venv
   source venv/bin/activate
   ```
2. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   pip install gunicorn
   ```
3. 如果需要保留个人电脑上已有的申请单和资产数据，可**直接将本地的 `db.sqlite3` 文件拷贝上传**，覆盖服务器上的同名文件；如果希望使用全新干净的数据库，请执行迁移：
   ```bash
   python manage.py migrate
   python manage.py createsuperuser  # 创建管理员账号
   ```

### 第三步：配置 Gunicorn 服务（后台守护进程）
Gunicorn 是生产级 Python Web 服务器网关，用于在后台承载 Django 运行。

1. 创建 Systemd 配置文件：
   ```bash
   sudo nano /etc/systemd/system/gpu_management.service
   ```
2. 粘贴以下配置：
   ```ini
   [Unit]
   Description=GPU Management System gunicorn daemon
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/var/www/ResourceManagementSystem
   ExecStart=/var/www/ResourceManagementSystem/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 gpu_management.wsgi:application
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
3. 启动并设置开机自启：
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start gpu_management
   sudo systemctl enable gpu_management
   ```
   *（检查状态：`sudo systemctl status gpu_management`）*

### 第四步：配置 Nginx 代理与静态资源托管
由于我们关闭了 `DEBUG` 模式，Nginx 将负责处理静态 CSS/JS 并将其它请求转发给 Gunicorn。

1. 创建 Nginx 配置文件：
   ```bash
   sudo nano /etc/nginx/sites-available/gpu_management
   ```
2. 粘贴以下代理规则（用您的域名或公网 IP 替换 `118.x.x.x`）：
   ```nginx
   server {
       listen 80;
       server_name 118.x.x.x; # 填写您的服务器公网IP或域名

       location /static/ {
           alias /var/www/ResourceManagementSystem/staticfiles/;
       }

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```
3. 启用该配置并重启 Nginx：
   ```bash
   sudo ln -s /etc/nginx/sites-available/gpu_management /etc/nginx/sites-enabled/
   sudo nginx -t  # 测试配置文件语法
   sudo systemctl restart nginx
   ```
4. 在云服务器控制台的“安全组”中，**放行 80 端口（HTTP）**。此时，所有人即可直接在浏览器输入云服务器 IP 地址访问系统，无需加端口号。

---

## 🪟 方案二：Windows Server 服务器部署

如果您的云服务器是 Windows Server，可以使用本方案。

### 第一步：服务器环境准备
1. 在云服务器上下载并安装官方 [Python 3.10+ (Windows 64-bit)](https://www.python.org/downloads/)。安装时必须勾选 **"Add python.exe to PATH"**。
2. 将本地的项目文件夹拷贝至服务器（如 `C:\ResourceManagementSystem`）。

### 第二步：安装依赖与数据库准备
1. 打开 Windows PowerShell，进入项目根目录：
   ```powershell
   cd C:\ResourceManagementSystem
   ```
2. 安装依赖：
   ```powershell
   pip install -r requirements.txt
   ```
3. 拷贝您的本地 `db.sqlite3` 覆盖至该目录下。

### 第三步：使用 NSSM 将服务注册为 Windows 系统后台服务
为了防止您关闭远程桌面（RDP）导致黑窗口程序退出，建议将运行脚本注册为系统服务。

1. 下载小巧免安装的 Windows 服务注册工具 [NSSM 官网](https://nssm.cc/download)。
2. 将解压出来的 `nssm.exe` 复制到您的 `C:\ResourceManagementSystem` 目录下。
3. 在 PowerShell 中运行配置：
   ```powershell
   .\nssm.exe install GPU_Management_Service
   ```
4. 会弹出一个图形配置界面：
   - **Path**: 选择您的 Python 执行文件（如：`C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe`）
   - **Startup directory**: 填写项目根目录：`C:\ResourceManagementSystem`
   - **Arguments**: 填写运行 parameters `manage.py runserver 0.0.0.0:8000`
5. 点击 **"Install service"**。
6. 在云服务器管理后台的安全组中，**放行 `8000` 端口**。
7. 在服务器中按 `Win + R`，输入 `services.msc` 打开 Windows 服务管理器，找到 `GPU_Management_Service` 右键点击“启动”。服务即会在后台永久静默运行，即便关闭远程桌面甚至服务器重启，服务也会自动跟随启动。

---

## 🔔 催办提醒功能（REMIND_API_URL）对接与 Payload 修改指南

卡管理系统内置了智能催办与消息路由，当申请人点击“催办”时，系统会在后台异步向配置的 API 接口发送通知数据。

### 1. 配置催办 API 接口地址
在生产服务器上，打开 `gpu_management/settings.py` 文件，找到第 78 行的 `REMIND_API_URL`：
```python
# 将其修改为您的企业微信、飞书、钉钉机器人Webhook，或者公司内部邮件/短信任命网关的真实 API 地址
REMIND_API_URL = 'https://your-company-notification-api.com/send'
```

### 2. 默认发送的 Payload 格式
系统默认会向 `REMIND_API_URL` 发起 **POST** 请求，数据以 **JSON** 格式进行传输，其 Payload 结构如下：
```json
{
    "content": "【卡管理系统提醒】您有待决策或待执行的内容。项目名称：[项目名]，申请人：[用户名]，当前环节：[待组长审批/待资源预审/待部门终审/已审批待执行]。请点击链接处理：http://[域名或IP]/approve/?tab=pending#project-[项目名]",
    "receiver": "接收用户的用户名"
}
```
*提示：如果是多名处理人（例如多位执行人），系统会在守护线程中自动为每位处理人并行分发一个 POST 请求。*

### 3. 如何修改 Payload 字段或添加身份鉴权（Headers）
如果您的企业消息网关（例如企业微信机器人或飞书 webhook）对 POST 数据格式有特殊要求，或者需要携带 Token 头进行认证，可以直接修改 [views.py](file:///d:/学习/agent/ResourceManagementSystem/resource_app/views.py#L1137-L1150) 中 `remind_view` 视图底部的 `send_remind_async` 函数。

#### 修改示例：
打开 [views.py](file:///d:/学习/agent/ResourceManagementSystem/resource_app/views.py#L1138-L1148)，将 `send_remind_async` 的逻辑修改为适配您的 API 的格式。

- **示例 A：对接飞书群机器人（自定义 Webhook，需要特定 JSON 键值）**
  ```python
  def send_remind_async(url, text, r_list):
      for r in r_list:
          try:
              # 构造飞书要求的 text 格式 payload
              data = {
                  "msg_type": "text",
                  "content": {
                      "text": f"@{r} {text}" # 附加呼叫特定接收人
                  }
              }
              requests.post(url, json=data, timeout=5)
          except Exception as e:
              print(f"[ASYNCREMIND] Failed to send to {r}: {str(e)}")
  ```

- **示例 B：API 需要自定义请求头（Headers，如 Token 认证）**
  ```python
  def send_remind_async(url, text, r_list):
      headers = {
          "Authorization": "Bearer YOUR_SECRET_TOKEN_HERE",
          "Content-Type": "application/json"
      }
      for r in r_list:
          try:
              data = {
                  'content': text,
                  'receiver_email': f"{r}@company.com" # 将用户名转换为企业邮箱
              }
              requests.post(url, json=data, headers=headers, timeout=5)
          except Exception as e:
              print(f"[ASYNCREMIND] Failed to send to {r}: {str(e)}")
  ```

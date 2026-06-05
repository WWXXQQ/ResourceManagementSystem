class ActiveRoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # 兼容读取数据库 roles 字段，转为列表
            roles_str = getattr(request.user, 'roles', '')
            roles_list = roles_str.split(',') if roles_str else ['APPLICANT']
            
            # 读取当前会话中用户指定的活跃角色
            active_role = request.session.get('active_role')
            
            if active_role and active_role in roles_list:
                request.user.role = active_role
            else:
                # 默认使用该用户的第一个角色
                request.user.role = roles_list[0] if roles_list else 'APPLICANT'
                
        return self.get_response(request)

/**
 * Chinese (Simplified) UI strings.
 * Keys are dot-namespaced; values are the canonical Chinese text.
 */
export const zh: Record<string, string> = {
  // ── Sidebar ──────────────────────────────────────────────
  "nav.search": "搜索…",
  "nav.newChat": "新建对话",
  "nav.recent": "最近",
  "nav.database": "数据库",
  "nav.news": "资讯",
  "nav.tools": "工具",
  "nav.admin": "管理员",

  // Nav item labels
  "nav.companies": "公司",
  "nav.assets": "资产",
  "nav.clinical": "临床",
  "nav.ip": "专利",
  "nav.buyers": "买方",
  "nav.deals": "交易",
  "nav.dashboard": "仪表盘",
  "nav.sell": "我要卖",
  "nav.watchlist": "关注",
  "nav.outreach": "外联",
  "nav.catalysts": "催化剂",
  "nav.reports": "报告",
  "nav.conference": "会议洞察",
  "nav.manage": "管理",
  "nav.team": "团队",
  "nav.notifications": "通知",

  // Sidebar footer
  "nav.defaultUser": "用户",
  "nav.defaultRole": "BD 专业人士",
  "nav.logoutLabel": "退出",
  "nav.logoutTitle": "退出登录",
  "nav.tagline": "生物医药BD情报",

  // AIDD button
  "nav.projectCenter": "立项中心 (AIDD)",
  "nav.projectCenterLoading": "跳转中…",
  "nav.projectCenterError": "生成跳转链接失败，请稍后重试",

  // Language toggle
  "nav.switchLang": "EN",

  // ── Login page ───────────────────────────────────────────
  "login.tab.login": "登录",
  "login.tab.register": "注册",
  "login.label.name": "姓名",
  "login.label.email": "邮箱",
  "login.label.password": "密码",
  "login.label.inviteCode": "邀请码",
  "login.placeholder.name": "请输入您的姓名",
  "login.placeholder.email": "your@email.com",
  "login.placeholder.password.login": "请输入密码",
  "login.placeholder.password.register": "至少6位字符",
  "login.placeholder.inviteCode": "请输入邀请码",
  "login.submit.login": "登录",
  "login.submit.register": "创建账户",
  "login.submit.loading": "处理中…",
  "login.switch.noAccount": "还没有账户？",
  "login.switch.hasAccount": "已有账户？",
  "login.switch.toRegister": "免费注册",
  "login.switch.toLogin": "立即登录",
  "login.forgotPassword": "忘记密码？",

  // Login validation errors
  "login.error.invalidEmail": "请输入有效的邮箱地址",
  "login.error.passwordTooShort": "密码至少需要6个字符",
  "login.error.nameRequired": "请输入您的姓名",
  "login.error.inviteRequired": "请输入邀请码",
  "login.error.fallback": "操作失败，请稍后重试",

  // ── Auth errors (AuthProvider) ───────────────────────────
  "auth.error.wrongPassword": "邮箱或密码错误，请重试",
  "auth.error.authFailed": "身份验证失败",
  "auth.error.noPermission": "没有访问权限",
  "auth.error.emailNotFound": "该邮箱未注册，请先注册账户",
  "auth.error.apiNotFound": "接口不存在",
  "auth.error.emailExists": "该邮箱已被注册",
  "auth.error.badRequest": "请求格式有误",
  "auth.error.incomplete": "填写的信息不完整",
  "auth.error.tooManyRequests": "请求过于频繁，请稍后再试",
  "auth.error.serverError": "服务暂时不可用，请稍后再试（后端异常）",
  "auth.error.networkError": "无法连接服务器，请检查网络或稍后再试",
  "auth.error.fallback": "操作失败，请稍后重试",
};

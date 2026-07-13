# TILIAN 邀请码注册方案

> 目标：将当前开放注册改为仅支持邀请码注册，由管理员生成并分发邀请码。

---

## 一、方案概述

### 1.1 核心规则

- 新用户注册时必须提供有效的邀请码
- 邀请码由管理员在后台生成
- 支持两种模式：
  - **一次性邀请码**：使用一次后自动失效
  - **多次邀请码**：可设置最大使用次数，达到上限后失效
- 邀请码可设置有效期，过期后无法使用
- 管理员可随时禁用或删除邀请码

### 1.2 邀请码格式

- 8 位字母数字组合，如 `A3B7K9P2`
- 大写字母 + 数字，避免混淆字符（0/O、1/I/L）
- 数据库唯一索引保证不重复

---

## 二、数据库设计

### 2.1 新增表：invitation_codes

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | 自增主键 |
| code | String(16) unique | 邀请码 |
| created_by | Integer FK | 创建者（管理员）用户 ID |
| max_uses | Integer | 最大使用次数，默认 1 |
| used_count | Integer | 已使用次数，默认 0 |
| is_active | Boolean | 是否启用，默认 True |
| expires_at | DateTime nullable | 过期时间，NULL 表示永不过期 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 2.2 用户表关联

为便于追踪，可在 users 表增加 `invited_by_code_id` 字段，记录用户使用的邀请码。

| 字段 | 类型 | 说明 |
|---|---|---|
| invitation_code_id | Integer FK nullable | 注册时使用的邀请码 ID |

---

## 三、后端接口设计

### 3.1 注册接口修改

`POST /api/auth/register`

请求体增加 `invitation_code` 字段：

```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "password123",
  "invitation_code": "A3B7K9P2"
}
```

验证逻辑：
1. 查找邀请码记录
2. 检查是否 `is_active=True`
3. 检查是否未过期
4. 检查 `used_count < max_uses`
5. 创建用户
6. `used_count += 1`
7. 如果 `used_count >= max_uses`，设置 `is_active=False`
8. 记录用户使用的邀请码 ID

错误响应：
- `400` 邀请码不能为空
- `400` 邀请码无效或已被使用
- `400` 邀请码已过期

### 3.2 管理员邀请码管理接口

`POST /api/admin/invitation-codes`

生成邀请码，请求体：

```json
{
  "max_uses": 1,
  "expires_at": "2026-12-31T23:59:59",
  "count": 5
}
```

响应：

```json
{
  "codes": ["A3B7K9P2", "M8N2Q5R1", "..."]
}
```

`GET /api/admin/invitation-codes`

列表查询，支持分页。

`PATCH /api/admin/invitation-codes/{code_id}`

禁用/启用邀请码。

`DELETE /api/admin/invitation-codes/{code_id}`

删除邀请码。

---

## 四、前端修改

### 4.1 注册页

在注册表单增加"邀请码"输入框：

```
用户名
邮箱
密码
确认密码
邀请码 *   ← 新增
```

### 4.2 管理员后台

在 Admin.vue 新增"邀请码管理"模块：

- 生成邀请码按钮（设置使用次数、有效期、生成数量）
- 邀请码列表（显示码、创建者、使用次数、状态、过期时间）
- 禁用/删除操作

---

## 五、部署步骤

1. 后端代码修改
2. 创建 Alembic 迁移脚本
3. 前端代码修改
4. 服务器执行数据库迁移
5. 重新构建并部署前端
6. 重启后端服务
7. 测试注册流程

---

## 六、安全考虑

1. 邀请码随机生成，避免可预测
2. 注册失败不泄露邀请码是否存在
3. 邀请码使用次数原子性更新
4. 管理员才能生成邀请码
5. 建议生产环境使用一次性邀请码

---

*文档版本：v1.0*  
*更新日期：2026-07-13*

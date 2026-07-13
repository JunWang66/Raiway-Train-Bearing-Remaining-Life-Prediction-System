# 轴承健康状态分析系统 - 数据格式说明文档

## 1. 项目概述

本系统基于 **XJTU-SY 轴承全生命周期数据集** 构建，包含西南交通大学提供的15个滚动轴承在3种工作条件下的完整寿命周期振动数据，以及Gearbox数据集的补充数据。

### 1.1 数据集概况

| 数据集 | 轴承数量 | 工作条件 | 数据点总数 |
|--------|----------|----------|------------|
| XJTU-SY | 15 | 3种 | ~2.8亿 |
| Gearbox | 20 | 2种 | ~2亿 |
| 测试样本 | 7 | 3种 | ~70万 |
| **合计** | **42** | **5种** | **3.02亿** |

### 1.2 XJTU-SY工作条件

| 条件编号 | 径向载荷 | 转速 | 采样频率 |
|----------|----------|------|----------|
| Condition_1 | 12kN | 2100rpm (35Hz) | 25.6kHz |
| Condition_2 | 11kN | 2250rpm (37.5Hz) | 25.6kHz |
| Condition_3 | 10kN | 2400rpm (40Hz) | 25.6kHz |

---

## 2. 数据结构

### 2.1 轴承编号规则

**XJTU-SY数据集命名规则：** `Bearing{工况}_{序号}`

- 工况：1=35Hz12kN, 2=37.5Hz11kN, 3=40Hz10kN
- 序号：1-5（每个工况5个轴承）

示例：`Bearing1_1` 表示工况1下的第1个轴承

**Gearbox数据集命名规则：** `Gearbox_{故障类型}_{转速}`

示例：`Gearbox_ball_20` 表示滚珠故障，转速20Hz

### 2.2 传感器维度

每个数据点包含两个传感器通道：

| 通道 | 字段名 | 数据类型 | 说明 |
|------|--------|----------|------|
| 水平振动 | horizontal_vibration | REAL (float64) | X方向振动加速度 |
| 垂直振动 | vertical_vibration | REAL (float64) | Y方向振动加速度 |

### 2.3 时间序列格式

| 字段 | 格式 | 说明 |
|------|------|------|
| sample_index | INTEGER | 采样批次序号（从1开始递增） |
| timestamp | TEXT (ISO 8601) | 采样时间戳，格式：`YYYY-MM-DDTHH:mm:ss` |

**时间间隔：** 每60秒采样一次，每次采样32768个数据点

---

## 3. 数据库设计

### 3.1 数据库类型

SQLite，数据库文件路径：`database/bearing_data.db`

### 3.2 表结构

#### 3.2.1 operating_condition（工作条件表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 主键 |
| condition_name | TEXT | UNIQUE | 条件名称（如Condition_1） |
| radial_force_kN | REAL | | 径向载荷（kN） |
| rotating_speed_rpm | INTEGER | | 转速（rpm） |
| sampling_frequency_hz | INTEGER | | 采样频率（Hz） |
| sampling_points | INTEGER | | 每批次采样点数 |
| sampling_period_min | INTEGER | | 采样周期（分钟） |
| description | TEXT | | 描述信息 |

#### 3.2.2 bearing_info（轴承信息表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 主键 |
| bearing_no | TEXT | UNIQUE | 轴承编号 |
| condition_id | INTEGER | FOREIGN KEY | 关联工作条件 |
| total_csv_files | INTEGER | | CSV文件总数 |
| total_data_points | INTEGER | | 数据点总数 |
| lifetime_minutes | REAL | | 寿命时长（分钟） |
| fault_element | TEXT | | 故障元件 |
| fault_type | TEXT | | 故障类型 |

#### 3.2.3 vibration_data（振动数据表）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 主键 |
| bearing_id | INTEGER | FOREIGN KEY | 关联轴承 |
| sample_index | INTEGER | | 采样批次序号 |
| timestamp | TEXT | | 采样时间戳 |
| horizontal_vibration | REAL | | 水平振动加速度 |
| vertical_vibration | REAL | | 垂直振动加速度 |

---

## 4. API接口说明

### 4.1 基础URL

```
http://localhost:5000/api
```

### 4.2 接口列表

#### 4.2.1 获取轴承列表

**GET** `/api/bearings`

**请求参数：** 无

**响应格式：**
```json
{
  "bearings": [
    {
      "id": 1,
      "bearing_no": "Bearing1_1",
      "total_csv_files": 93,
      "lifetime_minutes": 93.0,
      "fault_element": null,
      "fault_type": "XJTU-SY dataset",
      "condition": "Condition_1",
      "radial_force_kN": 12.0,
      "rotating_speed_rpm": 2100
    }
  ]
}
```

#### 4.2.2 获取轴承详情

**GET** `/api/bearing/<bearing_no>`

**请求参数：**
- `bearing_no`: 轴承编号（路径参数）

**响应格式：**
```json
{
  "bearing_no": "Bearing1_1",
  "total_csv_files": 93,
  "lifetime_minutes": 93.0,
  "fault_element": null,
  "fault_type": "XJTU-SY dataset",
  "condition_name": "Condition_1",
  "radial_force_kN": 12.0,
  "rotating_speed_rpm": 2100,
  "sampling_frequency_hz": 25600,
  "sampling_points": 32768,
  "sampling_period_min": 1
}
```

#### 4.2.3 获取振动数据（核心接口）

**GET** `/api/vibration_data`

**请求参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bearing_no | string | 是 | - | 轴承编号 |
| start_time | string | 否 | - | 开始时间（ISO格式） |
| end_time | string | 否 | - | 结束时间（ISO格式） |
| start_sample | integer | 否 | - | 起始采样批次 |
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 100 | 每页数量 |

**响应格式：**
```json
{
  "data": [
    {
      "timestamp": "2021-01-01T00:01:00",
      "sample_index": 1,
      "horizontal_vibration": -0.3964,
      "vertical_vibration": -0.0387
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 4030464,
  "total_pages": 40305
}
```

**使用示例：**
```
GET /api/vibration_data?bearing_no=Bearing1_1&page=1&page_size=1000
GET /api/vibration_data?bearing_no=Bearing1_1&start_sample=100&page_size=500
GET /api/vibration_data?bearing_no=Bearing1_1&start_time=2021-01-01T00:00:00&end_time=2021-01-01T01:00:00
```

#### 4.2.4 获取工作条件列表

**GET** `/api/operating_conditions`

**请求参数：** 无

**响应格式：**
```json
{
  "conditions": [
    {
      "id": 1,
      "condition_name": "Condition_1",
      "radial_force_kN": 12.0,
      "rotating_speed_rpm": 2100,
      "sampling_frequency_hz": 25600,
      "sampling_points": 32768,
      "sampling_period_min": 1,
      "description": "35Hz 12kN"
    }
  ]
}
```

#### 4.2.5 获取统计数据

**GET** `/api/statistics`

**请求参数：** 无

**响应格式：**
```json
{
  "bearing_count": 42,
  "total_points": 302069188,
  "condition_count": 5
}
```

#### 4.2.6 健康检查

**GET** `/api/health`

**请求参数：** 无

**响应格式：**
```json
{
  "status": "healthy",
  "bearing_count": 42
}
```

---

## 5. 数据格式适配说明

### 5.1 CORS支持

API已配置跨域访问支持，响应头包含：
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type, Authorization`

### 5.2 数据类型说明

| 字段 | API返回类型 | 前端处理建议 |
|------|-------------|--------------|
| horizontal_vibration | number | 浮点数，范围约[-5, 5] |
| vertical_vibration | number | 浮点数，范围约[-5, 5] |
| sample_index | number | 整数，从1开始递增 |
| timestamp | string | ISO 8601格式，可直接解析 |

### 5.3 分页建议

- 单次查询建议 `page_size <= 1000`，避免响应过大
- 历史数据查询建议按 `sample_index` 分段获取
- 实时数据查询可配合 `start_time`/`end_time` 筛选

### 5.4 时间序列特性

- 采样间隔：每批次间隔60秒
- 每批次点数：32768个数据点（XJTU-SY）
- 时间戳精度：分钟级

---

## 6. 数据处理脚本

### 6.1 数据库创建

```bash
python scripts/create_database.py
```

### 6.2 数据导入

```bash
python scripts/data_parser.py
```

### 6.3 数据库检查

```bash
python scripts/check_database.py
```

### 6.4 API测试

```bash
python scripts/test_api.py
```

---

## 7. 项目文件结构

```
railway-bearing/
├── api/
│   └── app.py              # Flask API服务
├── database/
│   └── bearing_data.db     # SQLite数据库文件
├── data/
│   └── raw/
│       ├── XJTU-SY/        # XJTU-SY原始数据
│       └── Mechanical-datasets-master/  # Gearbox数据
├── docs/
│   └── data_format_spec.md # 数据格式说明（本文档）
├── scripts/
│   ├── create_database.py  # 数据库创建脚本
│   ├── data_parser.py      # 数据解析导入脚本
│   ├── check_database.py   # 数据库检查脚本
│   └── test_api.py         # API测试脚本
└── frontend/               # 前端界面（非本职责范围）
    ├── login.html
    └── dashboard.html
```

---

## 8. 联调注意事项

1. **API服务启动：** 运行 `python api/app.py` 启动服务，默认端口5000
2. **数据量较大：** 单轴承可达千万级数据点，前端需注意分页加载
3. **时间戳格式：** 使用ISO 8601格式，前端可直接用于图表展示
4. **振动数据范围：** 正常范围约[-2, 2]，故障时可达[-5, 5]
5. **筛选建议：** 优先使用 `start_sample` 参数进行分段查询，性能更好

---

**文档版本：** v1.0  
**生成日期：** 2026-07-13  
**适用场景：** 前后端联调、数据格式对接
import requests

BASE_URL = 'http://localhost:5000/api'

def test_bearings():
    print("测试 /api/bearings 接口...")
    try:
        response = requests.get(f'{BASE_URL}/bearings')
        data = response.json()
        print(f"  状态码: {response.status_code}")
        print(f"  返回轴承数: {len(data['bearings'])}")
        if data['bearings']:
            print(f"  第一个轴承: {data['bearings'][0]['bearing_no']}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

def test_bearing_detail():
    print("测试 /api/bearing/<bearing_no> 接口...")
    try:
        response = requests.get(f'{BASE_URL}/bearing/Bearing1_1')
        data = response.json()
        print(f"  状态码: {response.status_code}")
        print(f"  轴承编号: {data['bearing_no']}")
        print(f"  故障类型: {data['fault_type']}")
        print(f"  工作条件: {data['condition_name']}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

def test_vibration_data():
    print("测试 /api/vibration_data 接口...")
    try:
        response = requests.get(f'{BASE_URL}/vibration_data?bearing_no=Bearing1_1&page=1&page_size=10')
        data = response.json()
        print(f"  状态码: {response.status_code}")
        print(f"  返回数据数: {len(data['data'])}")
        print(f"  总数据数: {data['total']}")
        print(f"  总页数: {data['total_pages']}")
        if data['data']:
            print(f"  第一条数据: sample_index={data['data'][0]['sample_index']}, h={data['data'][0]['horizontal_vibration']:.4f}, v={data['data'][0]['vertical_vibration']:.4f}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

def test_vibration_data_with_filter():
    print("测试 /api/vibration_data 带筛选条件...")
    try:
        response = requests.get(f'{BASE_URL}/vibration_data?bearing_no=Bearing1_1&start_sample=100&page=1&page_size=5')
        data = response.json()
        print(f"  状态码: {response.status_code}")
        print(f"  返回数据数: {len(data['data'])}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

def test_operating_conditions():
    print("测试 /api/operating_conditions 接口...")
    try:
        response = requests.get(f'{BASE_URL}/operating_conditions')
        data = response.json()
        print(f"  状态码: {response.status_code}")
        print(f"  返回条件数: {len(data['conditions'])}")
        for cond in data['conditions']:
            print(f"  - {cond['condition_name']}: {cond['radial_force_kN']}kN, {cond['rotating_speed_rpm']}rpm")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

def test_statistics():
    print("测试 /api/statistics 接口...")
    try:
        response = requests.get(f'{BASE_URL}/statistics')
        data = response.json()
        print(f"  状态码: {response.status_code}")
        print(f"  轴承数: {data['bearing_count']}")
        print(f"  数据点数: {data['total_points']:,}")
        print(f"  条件数: {data['condition_count']}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

def test_health():
    print("测试 /api/health 接口...")
    try:
        response = requests.get(f'{BASE_URL}/health')
        data = response.json()
        print(f"  状态码: {response.status_code}")
        print(f"  状态: {data['status']}")
        print(f"  轴承数: {data['bearing_count']}")
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

print("=" * 60)
print("API接口测试")
print("=" * 60)

results = []
results.append(("轴承列表", test_bearings()))
results.append(("轴承详情", test_bearing_detail()))
results.append(("振动数据", test_vibration_data()))
results.append(("振动数据(筛选)", test_vibration_data_with_filter()))
results.append(("工作条件", test_operating_conditions()))
results.append(("统计数据", test_statistics()))
results.append(("健康检查", test_health()))

print("\n" + "=" * 60)
print("测试结果汇总")
print("=" * 60)
all_pass = True
for name, passed in results:
    status = "✓ 通过" if passed else "✗ 失败"
    print(f"{name:15} {status}")
    if not passed:
        all_pass = False

print("\n" + ("所有测试通过！" if all_pass else "部分测试失败，请检查！"))
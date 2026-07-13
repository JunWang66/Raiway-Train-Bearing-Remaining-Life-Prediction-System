import os
import sys
import math
import hashlib
from functools import wraps

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
app.secret_key = 'railway-bearing-health-analysis-2026-secret-key'

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database/bearing_data.db')

# ============================================================
# Mock user database (prototype system)
# ============================================================
USERS = {
    'admin': {
        'password': hashlib.sha256('admin123'.encode()).hexdigest(),
        'name': '系统管理员',
        'role': 'admin'
    },
    'engineer': {
        'password': hashlib.sha256('engineer123'.encode()).hexdigest(),
        'name': '检修工程师',
        'role': 'engineer'
    },
    'viewer': {
        'password': hashlib.sha256('viewer123'.encode()).hexdigest(),
        'name': '数据分析师',
        'role': 'viewer'
    }
}


# ============================================================
# Auth decorator
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized', 'need_login': True}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# CORS middleware
# ============================================================
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


# ============================================================
# Database helper
# ============================================================
def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    # Register SQRT function (not available in all SQLite builds)
    conn.create_function("SQRT", 1, math.sqrt)
    return conn


def ensure_indexes():
    """Create performance indexes if they don't exist. Best-effort: fails silently if DB locked."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.create_function("SQRT", 1, math.sqrt)
        cursor = conn.cursor()
        # Critical: composite index for GROUP BY sample_index queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_vibration_bearing_sample
            ON vibration_data(bearing_id, sample_index)
        ''')
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass  # DB locked or other transient issue — indexes may already exist

# Create indexes at startup
ensure_indexes()


# ============================================================
# Page routes
# ============================================================
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=session.get('user', {}))


@app.route('/bearing/<bearing_no>')
@login_required
def bearing_detail(bearing_no):
    return render_template('bearing_detail.html', bearing_no=bearing_no, user=session.get('user', {}))


@app.route('/comparison')
@login_required
def comparison():
    return render_template('comparison.html', user=session.get('user', {}))


# ============================================================
# Auth API
# ============================================================
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'success': False, 'error': '请输入用户名和密码'}), 400

    user = USERS.get(username)
    if not user:
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

    if user['password'] != hashlib.sha256(password.encode()).hexdigest():
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

    session['user'] = {
        'username': username,
        'name': user['name'],
        'role': user['role']
    }

    return jsonify({
        'success': True,
        'user': session['user'],
        'redirect': url_for('dashboard')
    })


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.pop('user', None)
    return jsonify({'success': True, 'redirect': url_for('login_page')})


@app.route('/api/auth/status', methods=['GET'])
def api_auth_status():
    if 'user' in session:
        return jsonify({'authenticated': True, 'user': session['user']})
    return jsonify({'authenticated': False})


# ============================================================
# Data API - Bearings
# ============================================================
@app.route('/api/bearings', methods=['GET'])
def get_bearings():
    conn = get_db_connection()
    cursor = conn.cursor()

    dataset = request.args.get('dataset', 'all')  # xjtu, gearbox, test, all
    fault_type = request.args.get('fault_type', '')
    search = request.args.get('search', '')

    query = '''
        SELECT bi.id, bi.bearing_no, bi.total_csv_files, bi.lifetime_minutes, bi.fault_element, bi.fault_type,
               oc.condition_name, oc.radial_force_kN, oc.rotating_speed_rpm
        FROM bearing_info bi
        JOIN operating_condition oc ON bi.condition_id = oc.id
        WHERE 1=1
    '''
    params = []

    if dataset == 'xjtu':
        query += " AND bi.bearing_no LIKE 'Bearing%' AND bi.bearing_no NOT LIKE 'Bearing\\_%' ESCAPE '\\'"
    elif dataset == 'gearbox':
        query += " AND bi.bearing_no LIKE 'Gearbox%'"
    elif dataset == 'test':
        query += " AND bi.bearing_no LIKE 'Bearing\\_%' ESCAPE '\\'"

    if fault_type:
        query += ' AND bi.fault_type = ?'
        params.append(fault_type)

    if search:
        query += ' AND bi.bearing_no LIKE ?'
        params.append(f'%{search}%')

    query += ' ORDER BY bi.bearing_no'

    cursor.execute(query, params)

    bearings = []
    for row in cursor.fetchall():
        bearings.append({
            'id': row['id'],
            'bearing_no': row['bearing_no'],
            'total_csv_files': row['total_csv_files'],
            'lifetime_minutes': row['lifetime_minutes'],
            'fault_element': row['fault_element'],
            'fault_type': row['fault_type'],
            'condition': row['condition_name'],
            'radial_force_kN': row['radial_force_kN'],
            'rotating_speed_rpm': row['rotating_speed_rpm']
        })

    conn.close()
    return jsonify({'bearings': bearings})


@app.route('/api/bearing/<bearing_no>', methods=['GET'])
def get_bearing_detail(bearing_no):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT bi.*, oc.condition_name, oc.radial_force_kN, oc.rotating_speed_rpm,
               oc.sampling_frequency_hz, oc.sampling_points, oc.sampling_period_min,
               COALESCE(vd_stats.data_points, 0) as data_points,
               vd_stats.start_time,
               vd_stats.end_time,
               COALESCE(vd_stats.total_samples, 0) as total_samples
        FROM bearing_info bi
        JOIN operating_condition oc ON bi.condition_id = oc.id
        LEFT JOIN (
            SELECT bearing_id,
                   COUNT(*) as data_points,
                   MIN(timestamp) as start_time,
                   MAX(timestamp) as end_time,
                   COUNT(DISTINCT sample_index) as total_samples
            FROM vibration_data
            WHERE bearing_id = (SELECT id FROM bearing_info WHERE bearing_no = ?)
        ) vd_stats ON vd_stats.bearing_id = bi.id
        WHERE bi.bearing_no = ?
    ''', (bearing_no, bearing_no))

    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Bearing not found'}), 404

    bearing = {
        'id': row['id'],
        'bearing_no': row['bearing_no'],
        'total_csv_files': row['total_csv_files'],
        'lifetime_minutes': row['lifetime_minutes'],
        'fault_element': row['fault_element'],
        'fault_type': row['fault_type'],
        'condition_name': row['condition_name'],
        'radial_force_kN': row['radial_force_kN'],
        'rotating_speed_rpm': row['rotating_speed_rpm'],
        'sampling_frequency_hz': row['sampling_frequency_hz'],
        'sampling_points': row['sampling_points'],
        'sampling_period_min': row['sampling_period_min'],
        'data_points': row['data_points'],
        'start_time': row['start_time'],
        'end_time': row['end_time'],
        'total_samples': row['total_samples']
    }

    conn.close()
    return jsonify(bearing)


# ============================================================
# Data API - Vibration Data (optimized for charts)
# ============================================================
@app.route('/api/vibration_data', methods=['GET'])
def get_vibration_data():
    bearing_no = request.args.get('bearing_no')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    start_sample = request.args.get('start_sample')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 100))
    mode = request.args.get('mode', 'raw')  # raw, aggregated, sampled

    conn = get_db_connection()
    cursor = conn.cursor()

    # First get bearing_id
    cursor.execute('SELECT id FROM bearing_info WHERE bearing_no = ?', (bearing_no,))
    bearing_row = cursor.fetchone()
    if not bearing_row:
        conn.close()
        return jsonify({'error': 'Bearing not found'}), 404
    bearing_id = bearing_row['id']

    if mode == 'aggregated':
        # Return RMS values per sample_index
        query = '''
            SELECT sample_index, timestamp,
                   SQRT(AVG(horizontal_vibration * horizontal_vibration)) as h_rms,
                   SQRT(AVG(vertical_vibration * vertical_vibration)) as v_rms,
                   MAX(horizontal_vibration) as h_max,
                   MIN(horizontal_vibration) as h_min,
                   MAX(vertical_vibration) as v_max,
                   MIN(vertical_vibration) as v_min,
                   MAX(ABS(horizontal_vibration)) as h_peak,
                   MAX(ABS(vertical_vibration)) as v_peak,
                   COUNT(*) as cnt
            FROM vibration_data
            WHERE bearing_id = ?
        '''
        params = [bearing_id]

        if start_sample:
            query += ' AND sample_index >= ?'
            params.append(int(start_sample))
        if start_time:
            query += ' AND timestamp >= ?'
            params.append(start_time)
        if end_time:
            query += ' AND timestamp <= ?'
            params.append(end_time)

        query += ' GROUP BY sample_index ORDER BY sample_index ASC LIMIT ? OFFSET ?'
        params.extend([page_size, (page - 1) * page_size])

    elif mode == 'sampled':
        # Sample every Nth point for large datasets
        # Get total count first
        count_q = 'SELECT COUNT(*) as cnt FROM vibration_data WHERE bearing_id = ?'
        c_params = [bearing_id]
        cursor.execute(count_q, c_params)
        total = cursor.fetchone()['cnt']

        # Determine step size to get roughly 2000 points total
        step = max(1, total // 2000)

        query = '''
            SELECT sample_index, timestamp, horizontal_vibration, vertical_vibration
            FROM vibration_data
            WHERE bearing_id = ? AND rowid % ? = 0
        '''
        params = [bearing_id, step]

        if start_sample:
            query += ' AND sample_index >= ?'
            params.append(int(start_sample))
        if start_time:
            query += ' AND timestamp >= ?'
            params.append(start_time)
        if end_time:
            query += ' AND timestamp <= ?'
            params.append(end_time)

        query += ' ORDER BY sample_index ASC, id ASC LIMIT ? OFFSET ?'
        params.extend([page_size, (page - 1) * page_size])

    else:
        query = '''
            SELECT vd.timestamp, vd.horizontal_vibration, vd.vertical_vibration, vd.sample_index
            FROM vibration_data vd
            WHERE vd.bearing_id = ?
        '''
        params = [bearing_id]

        if start_sample:
            query += ' AND vd.sample_index >= ?'
            params.append(int(start_sample))
        if start_time:
            query += ' AND vd.timestamp >= ?'
            params.append(start_time)
        if end_time:
            query += ' AND vd.timestamp <= ?'
            params.append(end_time)

        query += ' ORDER BY vd.sample_index ASC, vd.id ASC LIMIT ? OFFSET ?'
        params.extend([page_size, (page - 1) * page_size])

    cursor.execute(query, params)

    data = []
    for row in cursor.fetchall():
        if mode == 'aggregated':
            data.append({
                'sample_index': row['sample_index'],
                'timestamp': row['timestamp'],
                'h_rms': round(row['h_rms'], 6),
                'v_rms': round(row['v_rms'], 6),
                'h_max': round(row['h_max'], 6),
                'h_min': round(row['h_min'], 6),
                'v_max': round(row['v_max'], 6),
                'v_min': round(row['v_min'], 6),
                'h_peak': round(row['h_peak'], 6),
                'v_peak': round(row['v_peak'], 6),
                'point_count': row['cnt']
            })
        else:
            data.append({
                'timestamp': row['timestamp'],
                'sample_index': row['sample_index'],
                'horizontal_vibration': round(row['horizontal_vibration'], 6),
                'vertical_vibration': round(row['vertical_vibration'], 6)
            })

    # Count query
    count_query = '''
        SELECT COUNT(*) as total
        FROM vibration_data vd
        WHERE vd.bearing_id = ?
    '''
    count_params = [bearing_id]

    if start_sample:
        count_query += ' AND vd.sample_index >= ?'
        count_params.append(int(start_sample))
    if start_time:
        count_query += ' AND vd.timestamp >= ?'
        count_params.append(start_time)
    if end_time:
        count_query += ' AND vd.timestamp <= ?'
        count_params.append(end_time)

    if mode == 'aggregated':
        count_query = '''
            SELECT COUNT(DISTINCT sample_index) as total
            FROM vibration_data vd
            WHERE vd.bearing_id = ?
        '''
        if start_sample:
            count_query += ' AND vd.sample_index >= ?'
        if start_time:
            count_query += ' AND vd.timestamp >= ?'
        if end_time:
            count_query += ' AND vd.timestamp <= ?'

    cursor.execute(count_query, count_params)
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'data': data,
        'page': page,
        'page_size': page_size,
        'total': total,
        'total_pages': max(1, (total + page_size - 1) // page_size)
    })


# ============================================================
# Analytics API - Aggregate Statistics per sample
# ============================================================
@app.route('/api/bearing/<bearing_no>/aggregate_stats', methods=['GET'])
def get_aggregate_stats(bearing_no):
    """Get per-sample aggregate statistics: RMS, peak, crest factor, etc."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM bearing_info WHERE bearing_no = ?', (bearing_no,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Bearing not found'}), 404
    bearing_id = row['id']

    limit = request.args.get('limit', 500)

    cursor.execute('''
        SELECT sample_index,
               MIN(timestamp) as timestamp,
               SQRT(AVG(horizontal_vibration * horizontal_vibration)) as h_rms,
               SQRT(AVG(vertical_vibration * vertical_vibration)) as v_rms,
               MAX(ABS(horizontal_vibration)) as h_peak,
               MAX(ABS(vertical_vibration)) as v_peak,
               MAX(horizontal_vibration) - MIN(horizontal_vibration) as h_pp,
               MAX(vertical_vibration) - MIN(vertical_vibration) as v_pp,
               AVG(horizontal_vibration) as h_mean,
               AVG(vertical_vibration) as v_mean,
               COUNT(*) as point_count
        FROM vibration_data
        WHERE bearing_id = ?
        GROUP BY sample_index
        ORDER BY sample_index ASC
        LIMIT ?
    ''', (bearing_id, int(limit)))

    stats = []
    for r in cursor.fetchall():
        h_rms = r['h_rms'] or 0
        v_rms = r['v_rms'] or 0
        h_peak = r['h_peak'] or 0
        v_peak = r['v_peak'] or 0
        h_crest = round(h_peak / h_rms, 4) if h_rms > 0 else 0
        v_crest = round(v_peak / v_rms, 4) if v_rms > 0 else 0

        stats.append({
            'sample_index': r['sample_index'],
            'timestamp': r['timestamp'],
            'h_rms': round(h_rms, 6),
            'v_rms': round(v_rms, 6),
            'h_peak': round(h_peak, 6),
            'v_peak': round(v_peak, 6),
            'h_pp': round(r['h_pp'], 6),
            'v_pp': round(r['v_pp'], 6),
            'h_mean': round(r['h_mean'], 6),
            'v_mean': round(r['v_mean'], 6),
            'h_crest_factor': h_crest,
            'v_crest_factor': v_crest,
            'point_count': r['point_count']
        })

    conn.close()
    return jsonify({'stats': stats, 'bearing_no': bearing_no})


# ============================================================
# Analytics API - Health Score
# ============================================================
@app.route('/api/bearing/<bearing_no>/health_score', methods=['GET'])
def get_health_score(bearing_no):
    """Calculate bearing health score based on vibration characteristics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM bearing_info WHERE bearing_no = ?', (bearing_no,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Bearing not found'}), 404
    bearing_id = row['id']

    limit = request.args.get('limit', 500)

    # Step 1: Compute baseline RMS once (samples 1-2)
    cursor.execute('''
        SELECT
            SQRT(AVG(horizontal_vibration * horizontal_vibration)) as baseline_h_rms,
            SQRT(AVG(vertical_vibration * vertical_vibration)) as baseline_v_rms
        FROM vibration_data
        WHERE bearing_id = ? AND sample_index <= 2
    ''', (bearing_id,))
    baseline = cursor.fetchone()
    baseline_h = baseline['baseline_h_rms'] or 0
    baseline_v = baseline['baseline_v_rms'] or 0

    # Step 2: Per-sample RMS (no correlated subqueries)
    cursor.execute('''
        SELECT sample_index,
               MIN(timestamp) as timestamp,
               SQRT(AVG(horizontal_vibration * horizontal_vibration)) as h_rms,
               SQRT(AVG(vertical_vibration * vertical_vibration)) as v_rms,
               MAX(ABS(horizontal_vibration)) as h_peak,
               MAX(ABS(vertical_vibration)) as v_peak
        FROM vibration_data
        WHERE bearing_id = ?
        GROUP BY sample_index
        ORDER BY sample_index ASC
        LIMIT ?
    ''', (bearing_id, int(limit)))

    health_data = []
    for r in cursor.fetchall():
        h_rms = r['h_rms'] or 0
        v_rms = r['v_rms'] or 0

        # Use pre-computed baseline (from Step 1) — no per-row correlated subquery
        bh = baseline_h or h_rms or 1
        bv = baseline_v or v_rms or 1

        # Health score: 100 = healthy, 0 = severe degradation
        # Based on RMS deviation from baseline
        h_deviation = abs(h_rms - bh) / bh if bh > 0 else 0
        v_deviation = abs(v_rms - bv) / bv if bv > 0 else 0
        deviation = max(h_deviation, v_deviation)

        # Scoring formula: exponential decay
        health_score = round(100 * math.exp(-deviation * 3), 1)
        health_score = max(0, min(100, health_score))

        # Health category
        if health_score >= 80:
            category = 'healthy'
            category_cn = '健康'
            color = '#52c41a'
        elif health_score >= 60:
            category = 'slight_degradation'
            category_cn = '轻微退化'
            color = '#faad14'
        elif health_score >= 40:
            category = 'moderate_degradation'
            category_cn = '中度退化'
            color = '#fa8c16'
        elif health_score >= 20:
            category = 'severe_degradation'
            category_cn = '严重退化'
            color = '#f5222d'
        else:
            category = 'critical'
            category_cn = '危险'
            color = '#cf1322'

        health_data.append({
            'sample_index': r['sample_index'],
            'timestamp': r['timestamp'],
            'health_score': health_score,
            'category': category,
            'category_cn': category_cn,
            'color': color,
            'h_rms': round(h_rms, 6),
            'v_rms': round(v_rms, 6),
            'h_deviation_pct': round(h_deviation * 100, 2),
            'v_deviation_pct': round(v_deviation * 100, 2)
        })

    conn.close()
    return jsonify({
        'health_data': health_data,
        'bearing_no': bearing_no
    })


# ============================================================
# Analytics API - Overall bearing health summary
# ============================================================
@app.route('/api/bearing/<bearing_no>/health_summary', methods=['GET'])
def get_health_summary(bearing_no):
    """Get overall health summary for a bearing."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT bi.*, oc.condition_name, oc.radial_force_kN, oc.rotating_speed_rpm,
               oc.sampling_frequency_hz,
               COALESCE(vd_stats.data_points, 0) as total_samples,
               vd_stats.start_time,
               vd_stats.end_time,
               vd_stats.max_sample
        FROM bearing_info bi
        JOIN operating_condition oc ON bi.condition_id = oc.id
        LEFT JOIN (
            SELECT bearing_id,
                   COUNT(DISTINCT sample_index) as data_points,
                   MIN(timestamp) as start_time,
                   MAX(timestamp) as end_time,
                   MAX(sample_index) as max_sample
            FROM vibration_data
            WHERE bearing_id = (SELECT id FROM bearing_info WHERE bearing_no = ?)
        ) vd_stats ON vd_stats.bearing_id = bi.id
        WHERE bi.bearing_no = ?
    ''', (bearing_no, bearing_no))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Bearing not found'}), 404

    bearing_id = row['id']

    # Consolidated single-scan query for early, late, and overall stats
    max_sample = row['max_sample']
    cursor.execute('''
        SELECT
            SUM(CASE WHEN sample_index <= 3 THEN h_sq ELSE 0 END) as early_h_sq_sum,
            SUM(CASE WHEN sample_index <= 3 THEN v_sq ELSE 0 END) as early_v_sq_sum,
            SUM(CASE WHEN sample_index <= 3 THEN 1 ELSE 0 END) as early_row_cnt,
            SUM(CASE WHEN sample_index >= ? THEN h_sq ELSE 0 END) as late_h_sq_sum,
            SUM(CASE WHEN sample_index >= ? THEN v_sq ELSE 0 END) as late_v_sq_sum,
            SUM(CASE WHEN sample_index >= ? THEN 1 ELSE 0 END) as late_row_cnt,
            SUM(h_sq) as overall_h_sq_sum,
            SUM(v_sq) as overall_v_sq_sum,
            SUM(cnt) as total_cnt,
            MAX(max_abs_h) as overall_h_peak,
            MAX(max_abs_v) as overall_v_peak
        FROM (
            SELECT sample_index,
                   SUM(horizontal_vibration * horizontal_vibration) as h_sq,
                   SUM(vertical_vibration * vertical_vibration) as v_sq,
                   MAX(ABS(horizontal_vibration)) as max_abs_h,
                   MAX(ABS(vertical_vibration)) as max_abs_v,
                   COUNT(*) as cnt
            FROM vibration_data
            WHERE bearing_id = ?
            GROUP BY sample_index
        )
    ''', (max_sample - 3 if max_sample else 0, max_sample - 3 if max_sample else 0,
          max_sample - 3 if max_sample else 0, bearing_id))
    stats = cursor.fetchone()

    early_h = math.sqrt(stats['early_h_sq_sum'] / stats['early_row_cnt']) if stats['early_row_cnt'] > 0 else 0
    early_v = math.sqrt(stats['early_v_sq_sum'] / stats['early_row_cnt']) if stats['early_row_cnt'] > 0 else 0
    late_h = math.sqrt(stats['late_h_sq_sum'] / stats['late_row_cnt']) if stats['late_row_cnt'] > 0 else early_h or 1
    late_v = math.sqrt(stats['late_v_sq_sum'] / stats['late_row_cnt']) if stats['late_row_cnt'] > 0 else early_v or 1
    overall_h_rms = math.sqrt(stats['overall_h_sq_sum'] / stats['total_cnt']) if stats['total_cnt'] > 0 else 0
    overall_v_rms = math.sqrt(stats['overall_v_sq_sum'] / stats['total_cnt']) if stats['total_cnt'] > 0 else 0

    # Degradation rate
    h_degradation = ((late_h - early_h) / early_h * 100) if early_h > 0 else 0
    v_degradation = ((late_v - early_v) / early_v * 100) if early_v > 0 else 0

    # Overall health score
    h_dev = abs(late_h - early_h) / early_h if early_h > 0 else 0
    v_dev = abs(late_v - early_v) / early_v if early_v > 0 else 0
    health_score = round(100 * math.exp(-max(h_dev, v_dev) * 3), 1)
    health_score = max(0, min(100, health_score))

    # Fault frequency characteristic based on bearing kinematics
    # For a typical ball bearing:
    # BPFO ≈ (N/2) * (1 - (d/D)*cos(α)) * fr
    # BPFI ≈ (N/2) * (1 + (d/D)*cos(α)) * fr
    # BSF ≈ (D/(2d)) * (1 - ((d/D)*cos(α))²) * fr
    # FTF ≈ (1/2) * (1 - (d/D)*cos(α)) * fr
    rotating_freq = row['rotating_speed_rpm'] / 60.0  # Hz

    # Estimated characteristic frequencies (typical ball bearing dimensions)
    N = 8   # number of rolling elements
    d = 8   # ball diameter mm (estimated)
    D = 40  # pitch diameter mm (estimated)
    alpha = 0  # contact angle

    bpfo = round(N / 2 * (1 - d / D * math.cos(alpha)) * rotating_freq, 2)
    bpfi = round(N / 2 * (1 + d / D * math.cos(alpha)) * rotating_freq, 2)
    bsf = round(D / (2 * d) * (1 - (d / D * math.cos(alpha))**2) * rotating_freq, 2)
    ftf = round(0.5 * (1 - d / D * math.cos(alpha)) * rotating_freq, 2)

    conn.close()

    return jsonify({
        'bearing_no': bearing_no,
        'condition_name': row['condition_name'],
        'radial_force_kN': row['radial_force_kN'],
        'rotating_speed_rpm': row['rotating_speed_rpm'],
        'sampling_frequency_hz': row['sampling_frequency_hz'],
        'fault_element': row['fault_element'],
        'fault_type': row['fault_type'],
        'total_samples': row['total_samples'],
        'start_time': row['start_time'],
        'end_time': row['end_time'],
        'early_h_rms': round(early_h, 6),
        'early_v_rms': round(early_v, 6),
        'late_h_rms': round(late_h, 6),
        'late_v_rms': round(late_v, 6),
        'overall_h_rms': round(overall_h_rms, 6),
        'overall_v_rms': round(overall_v_rms, 6),
        'overall_h_peak': round(stats['overall_h_peak'] or 0, 6),
        'overall_v_peak': round(stats['overall_v_peak'] or 0, 6),
        'h_degradation_pct': round(h_degradation, 2),
        'v_degradation_pct': round(v_degradation, 2),
        'health_score': health_score,
        'characteristic_frequencies': {
            'rotating_freq_hz': round(rotating_freq, 2),
            'bpfo_hz': bpfo,
            'bpfi_hz': bpfi,
            'bsf_hz': bsf,
            'ftf_hz': ftf
        }
    })


# ============================================================
# Analytics API - FFT Spectrum Data (simulated from time data)
# ============================================================
@app.route('/api/bearing/<bearing_no>/spectrum', methods=['GET'])
def get_spectrum(bearing_no):
    """Get vibration spectrum data for a bearing sample."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM bearing_info WHERE bearing_no = ?', (bearing_no,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Bearing not found'}), 404
    bearing_id = row['id']

    sample_index = request.args.get('sample_index', 1)

    # Get vibration data for this sample
    cursor.execute('''
        SELECT horizontal_vibration, vertical_vibration
        FROM vibration_data
        WHERE bearing_id = ? AND sample_index = ?
        ORDER BY id ASC
        LIMIT 8192
    ''', (bearing_id, int(sample_index)))

    h_data = []
    v_data = []
    for r in cursor.fetchall():
        h_data.append(r['horizontal_vibration'])
        v_data.append(r['vertical_vibration'])

    conn.close()

    if len(h_data) < 4:
        return jsonify({'error': 'Not enough data for spectrum analysis', 'bearing_no': bearing_no})

    # Compute FFT (using DFT for simplicity - in production use numpy FFT)
    # We'll compute a simple magnitude spectrum
    def compute_spectrum(data, sample_rate):
        n = len(data)
        # Apply Hann window
        windowed = [data[i] * (0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1))) for i in range(n)]

        # DFT
        spectrum = []
        max_freq = min(sample_rate // 2, 2000)  # Up to 2000 Hz for bearing analysis
        for k in range(1, n // 2):
            freq = k * sample_rate / n
            if freq > max_freq:
                break
            real = sum(windowed[i] * math.cos(2 * math.pi * k * i / n) for i in range(n))
            imag = sum(windowed[i] * math.sin(2 * math.pi * k * i / n) for i in range(n))
            mag = math.sqrt(real * real + imag * imag) / n * 2
            spectrum.append({'frequency': round(freq, 2), 'magnitude': round(mag, 6)})

        return spectrum

    # Get sampling frequency
    cursor2 = get_db_connection().cursor()
    cursor2.execute('''
        SELECT oc.sampling_frequency_hz
        FROM bearing_info bi
        JOIN operating_condition oc ON bi.condition_id = oc.id
        WHERE bi.id = ?
    ''', (bearing_id,))
    freq_row = cursor2.fetchone()
    sample_rate = freq_row['sampling_frequency_hz'] if freq_row else 25600
    cursor2.close()

    h_spectrum = compute_spectrum(h_data, sample_rate)
    v_spectrum = compute_spectrum(v_data, sample_rate)

    return jsonify({
        'bearing_no': bearing_no,
        'sample_index': int(sample_index),
        'sample_rate': sample_rate,
        'data_points': len(h_data),
        'horizontal_spectrum': h_spectrum,
        'vertical_spectrum': v_spectrum
    })


# ============================================================
# Other APIs
# ============================================================
@app.route('/api/operating_conditions', methods=['GET'])
def get_operating_conditions():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM operating_condition')

    conditions = []
    for row in cursor.fetchall():
        conditions.append({
            'id': row['id'],
            'condition_name': row['condition_name'],
            'radial_force_kN': row['radial_force_kN'],
            'rotating_speed_rpm': row['rotating_speed_rpm'],
            'sampling_frequency_hz': row['sampling_frequency_hz'],
            'sampling_points': row['sampling_points'],
            'sampling_period_min': row['sampling_period_min'],
            'description': row['description']
        })

    conn.close()
    return jsonify({'conditions': conditions})


@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM bearing_info')
        count = cursor.fetchone()[0]
        conn.close()
        return jsonify({'status': 'healthy', 'bearing_count': count})
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM bearing_info')
    bearing_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM vibration_data')
    total_points = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT condition_name) FROM operating_condition')
    condition_count = cursor.fetchone()[0]

    # Additional stats
    cursor.execute("SELECT COUNT(*) FROM bearing_info WHERE bearing_no LIKE 'Bearing%'")
    xjtu_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bearing_info WHERE bearing_no LIKE 'Gearbox%'")
    gearbox_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bearing_info WHERE bearing_no LIKE 'Bearing_%'")
    test_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(DISTINCT fault_type) FROM bearing_info WHERE fault_type IS NOT NULL AND fault_type != ""')
    fault_types = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'bearing_count': bearing_count,
        'total_points': total_points,
        'condition_count': condition_count,
        'xjtu_count': xjtu_count,
        'gearbox_count': gearbox_count,
        'test_count': test_count,
        'fault_types': fault_types
    })


@app.route('/api/bearing/<bearing_no>/rms_trend', methods=['GET'])
def get_rms_trend(bearing_no):
    """Get RMS trend over time for both channels."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM bearing_info WHERE bearing_no = ?', (bearing_no,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Bearing not found'}), 404
    bearing_id = row['id']

    limit = int(request.args.get('limit', 500))

    cursor.execute('''
        SELECT sample_index,
               MIN(timestamp) as timestamp,
               SQRT(AVG(horizontal_vibration * horizontal_vibration)) as h_rms,
               SQRT(AVG(vertical_vibration * vertical_vibration)) as v_rms
        FROM vibration_data
        WHERE bearing_id = ?
        GROUP BY sample_index
        ORDER BY sample_index ASC
        LIMIT ?
    ''', (bearing_id, limit))

    trend = []
    for r in cursor.fetchall():
        trend.append({
            'sample_index': r['sample_index'],
            'timestamp': r['timestamp'],
            'h_rms': round(r['h_rms'] or 0, 6),
            'v_rms': round(r['v_rms'] or 0, 6)
        })

    conn.close()
    return jsonify({'trend': trend, 'bearing_no': bearing_no})


# ============================================================
# Entry point
# ============================================================
if __name__ == '__main__':
    # Ensure template and static directories exist
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    os.makedirs(template_dir, exist_ok=True)
    os.makedirs(static_dir, exist_ok=True)

    print("=" * 60)
    print("  铁路轴承健康状态分析原型系统")
    print("  Railway Bearing Health Analysis Prototype System")
    print("=" * 60)
    print(f"  Database: {DB_PATH}")
    print(f"  Templates: {template_dir}")
    print(f"  Static: {static_dir}")
    print(f"  URL: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)

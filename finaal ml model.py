"""
EMPLOYEE BEHAVIOR ANALYTICS SYSTEM - PRODUCTION VERSION (FIXED)
==============================================================
Fixed version with proper error handling for missing columns
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_score, recall_score, f1_score
import joblib
import time
import os
import json
from collections import deque
from datetime import datetime
import warnings
import subprocess
import zipfile
import platform
import shutil
import mysql.connector
from mysql.connector import Error
warnings.filterwarnings('ignore')

# Try to import watchdog for file monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("ℹ️ Note: Install 'watchdog' for file monitoring: pip install watchdog")

# Try to import openpyxl for Excel support
try:
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
    print("ℹ️ Note: Install 'openpyxl' for Excel export: pip install openpyxl")

# =====================================================
# MYSQL DATABASE CONNECTION
# =====================================================

class MySQLDatabase:
    """MySQL database connection handler for persistent storage"""
    
    def __init__(self, host='localhost', database='employee_monitoring4', 
                 user='root', password='asma'):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
        self.cursor = None
        
    def connect(self):
        """Establish MySQL connection"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                print(f"✅ Successfully connected to MySQL database: {self.database}")
                return True
        except Error as e:
            print(f"❌ MySQL Connection Error: {e}")
            return False
    
    def disconnect(self):
        """Close MySQL connection"""
        if self.connection and self.connection.is_connected():
            self.cursor.close()
            self.connection.close()
            print("✅ MySQL connection closed")
    
    def create_tables_if_not_exist(self):
        """Create required tables if they don't exist"""
        try:
            # Create employee_reports table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_reports (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    employee_id VARCHAR(50),
                    timestamp DATETIME,
                    report_type VARCHAR(20),
                    productive_time_min INT,
                    unproductive_time_min INT,
                    idle_time_min INT,
                    app_switches INT,
                    focus_score DECIMAL(3,2),
                    task_completion_rate DECIMAL(3,2),
                    productive_ratio DECIMAL(3,2),
                    productivity_prediction VARCHAR(50),
                    productivity_confidence DECIMAL(5,2),
                    productivity_score DECIMAL(5,2),
                    anomaly_detected BOOLEAN,
                    anomaly_score DECIMAL(5,2),
                    file_activity_count INT DEFAULT 0,
                    file_modification_count INT DEFAULT 0,
                    productivity_risk_score INT DEFAULT 0,
                    productivity_risk_level VARCHAR(20) DEFAULT 'LOW',
                    risk_factors TEXT
                )
            """)
            
            # Create file_activities table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_activities (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    employee_id VARCHAR(50),
                    timestamp DATETIME,
                    activity_type VARCHAR(20),
                    file_name VARCHAR(255),
                    file_path TEXT,
                    file_size INT,
                    file_extension VARCHAR(20),
                    activity_duration_seconds INT DEFAULT 0
                )
            """)
            
            # Create employee_sessions table
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_sessions (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    employee_id VARCHAR(50),
                    session_start DATETIME,
                    session_end DATETIME,
                    is_active BOOLEAN DEFAULT 1,
                    last_activity DATETIME
                )
            """)
            
            self.connection.commit()
            print("✅ Tables created/verified successfully")
            return True
        except Error as e:
            print(f"❌ Error creating tables: {e}")
            return False
    
    def insert_employee_report(self, employee_id, report_data):
        """Insert employee report into database"""
        try:
            # Ensure table exists
            self.create_tables_if_not_exist()
            
            query = """
                INSERT INTO employee_reports (
                    employee_id, timestamp, report_type,
                    productive_time_min, unproductive_time_min, idle_time_min,
                    app_switches, focus_score, task_completion_rate,
                    productive_ratio, productivity_prediction,
                    productivity_confidence, productivity_score,
                    anomaly_detected, anomaly_score,
                    file_activity_count, file_modification_count,
                    productivity_risk_score, productivity_risk_level,
                    risk_factors
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                employee_id,
                report_data.get('timestamp'),
                report_data.get('report_type', 'regular'),
                report_data.get('productive_time_min', 0),
                report_data.get('unproductive_time_min', 0),
                report_data.get('idle_time_min', 0),
                report_data.get('app_switches', 0),
                report_data.get('focus_score', 0.0),
                report_data.get('task_completion_rate', 0.0),
                report_data.get('productive_ratio', 0.0),
                report_data.get('productivity_prediction', 'Unknown'),
                report_data.get('productivity_confidence', 0.0),
                report_data.get('productivity_score', 0.0),
                1 if report_data.get('anomaly_detected', False) else 0,
                report_data.get('anomaly_score', 0.0),
                report_data.get('file_activity_count', 0),
                report_data.get('file_modification_count', 0),
                report_data.get('productivity_risk_score', 0),
                report_data.get('productivity_risk_level', 'LOW'),
                report_data.get('risk_factors', '')
            )
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return True
        except Error as e:
            print(f"❌ Error inserting report: {e}")
            return False
    
    def insert_file_activity(self, employee_id, activity_data):
        """Insert file activity record into database"""
        try:
            # Ensure table exists
            self.create_tables_if_not_exist()
            
            query = """
                INSERT INTO file_activities (
                    employee_id, timestamp, activity_type,
                    file_name, file_path, file_size, file_extension,
                    activity_duration_seconds
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                employee_id,
                activity_data.get('timestamp'),
                activity_data.get('activity_type'),
                activity_data.get('file_name', ''),
                activity_data.get('file_path', ''),
                activity_data.get('file_size', 0),
                activity_data.get('file_extension', ''),
                activity_data.get('activity_duration', 0)
            )
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return True
        except Error as e:
            # Don't print error for missing tables - they'll be created on next try
            if "doesn't exist" not in str(e):
                print(f"❌ Error inserting file activity: {e}")
            return False
    
    def update_employee_session(self, employee_id, is_active=True):
        """Update or create employee session"""
        try:
            self.create_tables_if_not_exist()
            
            if is_active:
                # Check if session exists
                self.cursor.execute(
                    "SELECT id FROM employee_sessions WHERE employee_id = %s",
                    (employee_id,)
                )
                result = self.cursor.fetchone()
                
                if result:
                    # Update existing session
                    self.cursor.execute(
                        """UPDATE employee_sessions 
                           SET session_start = %s, is_active = 1, last_activity = %s 
                           WHERE employee_id = %s""",
                        (datetime.now(), datetime.now(), employee_id)
                    )
                else:
                    # Create new session
                    self.cursor.execute(
                        """INSERT INTO employee_sessions 
                           (employee_id, session_start, is_active, last_activity) 
                           VALUES (%s, %s, 1, %s)""",
                        (employee_id, datetime.now(), datetime.now())
                    )
            else:
                # End session
                self.cursor.execute(
                    """UPDATE employee_sessions 
                       SET session_end = %s, is_active = 0 
                       WHERE employee_id = %s AND is_active = 1""",
                    (datetime.now(), employee_id)
                )
            
            self.connection.commit()
            return True
        except Error as e:
            print(f"❌ Error updating session: {e}")
            return False
    
    def get_employee_history(self, employee_id, limit=100):
        """Get employee history from database"""
        try:
            self.cursor.execute(
                """SELECT * FROM employee_reports 
                   WHERE employee_id = %s 
                   ORDER BY timestamp DESC 
                   LIMIT %s""",
                (employee_id, limit)
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"❌ Error fetching history: {e}")
            return []
    
    def get_file_activity_history(self, employee_id, limit=100):
        """Get file activity history from database"""
        try:
            self.cursor.execute(
                """SELECT * FROM file_activities 
                   WHERE employee_id = %s 
                   ORDER BY timestamp DESC 
                   LIMIT %s""",
                (employee_id, limit)
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"❌ Error fetching file activity: {e}")
            return []
    
    def get_active_employees(self):
        """Get list of active employees"""
        try:
            self.cursor.execute(
                "SELECT employee_id FROM employee_sessions WHERE is_active = 1"
            )
            return [row['employee_id'] for row in self.cursor.fetchall()]
        except Error as e:
            print(f"❌ Error fetching active employees: {e}")
            return []
    
    def get_all_reports(self, limit=1000):
        """Get all reports from database"""
        try:
            self.cursor.execute(
                """SELECT * FROM employee_reports 
                   ORDER BY timestamp DESC 
                   LIMIT %s""",
                (limit,)
            )
            return self.cursor.fetchall()
        except Error as e:
            print(f"❌ Error fetching reports: {e}")
            return []

# =====================================================
# FILE ACTIVITY TRACKER - PRODUCTION GRADE
# =====================================================

class FileActivityTracker(FileSystemEventHandler):
    """Tracks legitimate file activity for productivity analysis"""
    
    def __init__(self, employee_id, callback_function, db_connection):
        self.employee_id = employee_id
        self.callback = callback_function
        self.db = db_connection
        self.activity_count = 0
        self.modification_count = 0
        self.last_reset = datetime.now()
        self.active_sessions = {}
        self.work_extensions = {'.py', '.java', '.cpp', '.js', '.html', '.css', 
                                '.json', '.xml', '.txt', '.md', '.xlsx', '.docx',
                                '.pptx', '.pdf', '.sql', '.csv', '.jpg', '.png'}
        
    def on_created(self, event):
        """Track file creation events"""
        if not event.is_directory:
            self.activity_count += 1
            self._log_activity('CREATED', event.src_path)
    
    def on_modified(self, event):
        """Track file modification events"""
        if not event.is_directory:
            self.modification_count += 1
            self._log_activity('MODIFIED', event.src_path)
    
    def on_deleted(self, event):
        """Track file deletion events"""
        if not event.is_directory:
            self.activity_count += 1
            self._log_activity('DELETED', event.src_path)
    
    def on_moved(self, event):
        """Track file move events"""
        if not event.is_directory:
            self.activity_count += 1
            self._log_activity('MOVED', event.src_path)
    
    def _log_activity(self, activity_type, file_path):
        """Log file activity to database and callback"""
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1]
        file_size = 0
        
        try:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
        except:
            pass
        
        activity_data = {
            'employee_id': self.employee_id,
            'timestamp': datetime.now().isoformat(),
            'activity_type': activity_type,
            'file_name': file_name,
            'file_path': file_path,
            'file_size': file_size,
            'file_extension': file_ext,
            'activity_duration': 0
        }
        
        # Callback for real-time updates
        self.callback('FILE_ACTIVITY', activity_data)
        
        # Store in database
        if self.db:
            self.db.insert_file_activity(self.employee_id, activity_data)
    
    def get_activity_stats(self):
        """Get current activity statistics"""
        now = datetime.now()
        if (now - self.last_reset).seconds > 3600:  # Reset hourly
            self.activity_count = 0
            self.modification_count = 0
            self.last_reset = now
        
        return {
            'total_activities': self.activity_count,
            'modifications': self.modification_count,
            'activity_rate': self.activity_count / max(1, (now - self.last_reset).seconds / 3600)
        }
    
    def reset_stats(self):
        """Reset activity counters"""
        self.activity_count = 0
        self.modification_count = 0
        self.last_reset = datetime.now()


class FileActivityMonitor:
    """Background file activity monitor - production grade"""
    
    def __init__(self, employee_id, callback, db_connection=None):
        self.employee_id = employee_id
        self.callback = callback
        self.db = db_connection
        self.observer = None
        self.is_monitoring = False
        self.tracker = None
        
    def start_monitoring(self, paths_to_monitor=None):
        """Start monitoring file activity"""
        if not WATCHDOG_AVAILABLE:
            print(f"⚠️ Watchdog not available for file monitoring")
            return False
        
        if paths_to_monitor is None:
            paths_to_monitor = [
                os.path.expanduser("~\\Desktop"),
                os.path.expanduser("~\\Documents"),
                os.path.expanduser("~\\Downloads"),
                os.getcwd()
            ]
        
        # Filter valid paths
        self.monitored_paths = [p for p in paths_to_monitor if os.path.exists(p)]
        
        if not self.monitored_paths:
            print(f"⚠️ No valid paths to monitor for Employee {self.employee_id}")
            return False
        
        self.observer = Observer()
        self.tracker = FileActivityTracker(self.employee_id, self.callback, self.db)
        
        for path in self.monitored_paths:
            self.observer.schedule(self.tracker, path, recursive=True)
            print(f"📁 Monitoring: {path}")
        
        self.observer.start()
        self.is_monitoring = True
        print(f"✅ File activity monitoring started for Employee {self.employee_id}")
        return True
    
    def stop_monitoring(self):
        """Stop monitoring file activity"""
        if self.observer and self.is_monitoring:
            self.observer.stop()
            self.observer.join()
            self.is_monitoring = False
            print(f"✅ File activity monitoring stopped for Employee {self.employee_id}")
    
    def get_activity_stats(self):
        """Get current activity statistics"""
        if self.tracker:
            return self.tracker.get_activity_stats()
        return {'total_activities': 0, 'modifications': 0, 'activity_rate': 0}

# =====================================================
# EMPLOYEE MONITORING AGENT - PRODUCTION GRADE
# =====================================================

class EmployeeMonitoringAgent:
    """Production-grade employee monitoring agent"""
    
    def __init__(self, employee_id, manager_config, db_connection=None):
        self.employee_id = str(employee_id)
        self.manager_config = manager_config
        self.model = None
        self.anomaly_model = None
        self.is_running = False
        self.data_buffer = deque(maxlen=100)
        self.performance_history = deque(maxlen=100)
        self.start_time = datetime.now()
        
        self.db = db_connection
        
        # File activity monitor
        self.file_monitor = None
        self.file_activity_log = deque(maxlen=500)
        self.daily_activity_count = 0
        self.last_activity_reset = datetime.now()
        
        # Initialize components
        self.load_models()
        self.init_file_monitoring()
        
        # Update session in database
        if self.db:
            self.db.update_employee_session(employee_id, is_active=True)
        
        # Initialize metrics
        self.metrics = self._initialize_metrics()
    
    def _initialize_metrics(self):
        """Initialize employee metrics"""
        return {
            'productive_time': 0,
            'unproductive_time': 0,
            'idle_time': 0,
            'app_switches': 0,
            'focus_score': 0.0,
            'task_completion_rate': 0.0,
            'productive_ratio': 0.0,
            'file_activities': 0,
            'file_modifications': 0,
            'work_efficiency': 0.0
        }
    
    def init_file_monitoring(self):
        """Initialize file activity monitoring"""
        if WATCHDOG_AVAILABLE:
            self.file_monitor = FileActivityMonitor(
                self.employee_id, 
                self.handle_file_activity, 
                self.db
            )
            print(f"✅ File monitoring initialized for {self.employee_id}")
    
    def start_file_monitoring(self):
        """Start file activity monitoring"""
        if self.file_monitor:
            return self.file_monitor.start_monitoring()
        return False
    
    def stop_file_monitoring(self):
        """Stop file activity monitoring"""
        if self.file_monitor:
            self.file_monitor.stop_monitoring()
    
    def handle_file_activity(self, event_type, activity_data):
        """Handle file activity events"""
        self.file_activity_log.append(activity_data)
        
        # Track daily activity
        now = datetime.now()
        if (now - self.last_activity_reset).days >= 1:
            self.daily_activity_count = 0
            self.last_activity_reset = now
        
        self.daily_activity_count += 1
        
        # Log file activity (only show occasional messages to reduce clutter)
        if self.daily_activity_count % 10 == 0:
            print(f"\n📄 File activity logged: {self.daily_activity_count} total")
        
        # Update metrics
        self.metrics['file_activities'] = self.daily_activity_count
        
        if event_type == 'MODIFIED':
            self.metrics['file_modifications'] += 1
        
        # Save to CSV for analysis
        self._save_file_activity(activity_data)
    
    def _save_file_activity(self, activity_data):
        """Save file activity to CSV"""
        manager_folder = self.manager_config.get('shared_folder', './manager_reports')
        os.makedirs(manager_folder, exist_ok=True)
        
        file_activity_csv = os.path.join(manager_folder, f"file_activities.csv")
        
        new_activity = {
            'timestamp': activity_data.get('timestamp'),
            'employee_id': self.employee_id,
            'activity_type': activity_data.get('activity_type'),
            'file_name': activity_data.get('file_name', ''),
            'file_path': activity_data.get('file_path', ''),
            'file_size': activity_data.get('file_size', 0),
            'file_extension': activity_data.get('file_extension', '')
        }
        
        new_df = pd.DataFrame([new_activity])
        if os.path.exists(file_activity_csv):
            existing_df = pd.read_csv(file_activity_csv)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            updated_df = new_df
        
        updated_df.to_csv(file_activity_csv, index=False)
    
    def load_models(self):
        """Load trained models or train new ones"""
        try:
            if os.path.exists('productivity_model_enhanced.pkl') and os.path.exists('anomaly_model_enhanced.pkl'):
                self.model = joblib.load('productivity_model_enhanced.pkl')
                self.anomaly_model = joblib.load('anomaly_model_enhanced.pkl')
                print(f"✅ Models loaded successfully")
            else:
                print(f"ℹ️ Models not found. Training new models...")
                self.train_demo_models()
        except Exception as e:
            print(f"⚠️ Error loading models: {e}")
            self.train_demo_models()
    
    def train_demo_models(self):
        """Train models with proper validation"""
        print("🔄 Training models with proper validation...")
        np.random.seed(42)
        rows = 5000
        
        data = {
            "productive_app_usage": np.random.gamma(2, 30, rows),
            "unproductive_app_usage": np.random.gamma(1.5, 20, rows),
            "idle_time": np.random.exponential(15, rows),
            "app_switch_count": np.random.poisson(8, rows),
            "focus_score": np.random.beta(8, 3, rows),
            "task_completion_rate": np.random.beta(7, 3, rows),
            "file_activity_count": np.random.poisson(15, rows),
            "file_modification_count": np.random.poisson(10, rows)
        }
        
        df = pd.DataFrame(data)
        
        # Cap values to realistic ranges
        df['productive_app_usage'] = np.clip(df['productive_app_usage'], 10, 300)
        df['unproductive_app_usage'] = np.clip(df['unproductive_app_usage'], 0, 200)
        df['idle_time'] = np.clip(df['idle_time'], 0, 120)
        df['app_switch_count'] = np.clip(df['app_switch_count'], 1, 30)
        df['file_activity_count'] = np.clip(df['file_activity_count'], 0, 100)
        df['file_modification_count'] = np.clip(df['file_modification_count'], 0, 80)
        
        df["productive_ratio"] = df["productive_app_usage"] / (df["productive_app_usage"] + df["unproductive_app_usage"] + 1)
        df["productivity_label"] = np.where(df["productive_ratio"] > 0.55, 1, 0)
        
        features = ["productive_app_usage", "unproductive_app_usage", "idle_time", 
                   "app_switch_count", "focus_score", "task_completion_rate", 
                   "productive_ratio", "file_activity_count", "file_modification_count"]
        
        X = df[features]
        y = df["productivity_label"]
        
        # Split for validation
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)
        
        self.anomaly_model = IsolationForest(contamination=0.05, random_state=42)
        self.anomaly_model.fit(X_train)
        
        # Calculate accuracy
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        joblib.dump(self.model, 'productivity_model_enhanced.pkl')
        joblib.dump(self.anomaly_model, 'anomaly_model_enhanced.pkl')
        print(f"✅ Models trained and saved (Test Accuracy: {accuracy:.2%})")
    
    def collect_employee_metrics(self):
        """Collect comprehensive employee metrics"""
        # Get file activity stats
        file_stats = {'total_activities': 0, 'modifications': 0}
        if self.file_monitor:
            file_stats = self.file_monitor.get_activity_stats()
        
        # Generate synthetic metrics for demo
        # In production, this would come from actual data sources
        productive_time = np.random.randint(20, 250)
        unproductive_time = np.random.randint(0, 180)
        idle_time = np.random.randint(0, 120)
        app_switches = np.random.randint(1, 20)
        
        # Calculate focus score
        if productive_time > unproductive_time * 1.5:
            focus_score = np.random.uniform(0.7, 1.0)
            task_completion = np.random.uniform(0.7, 1.0)
        elif productive_time < unproductive_time * 0.5:
            focus_score = np.random.uniform(0.3, 0.6)
            task_completion = np.random.uniform(0.4, 0.7)
        else:
            focus_score = np.random.uniform(0.5, 0.8)
            task_completion = np.random.uniform(0.5, 0.8)
        
        productive_ratio = productive_time / (productive_time + unproductive_time + 1)
        
        # Work efficiency based on file activity
        file_efficiency = min(1.0, file_stats.get('modifications', 0) / 50.0)
        work_efficiency = (productive_ratio * 0.7 + file_efficiency * 0.3)
        
        metrics = {
            'productive_time': productive_time,
            'unproductive_time': unproductive_time,
            'idle_time': idle_time,
            'app_switches': app_switches,
            'focus_score': focus_score,
            'task_completion_rate': task_completion,
            'productive_ratio': productive_ratio,
            'work_efficiency': work_efficiency,
            'file_activities': file_stats.get('total_activities', 0),
            'file_modifications': file_stats.get('modifications', 0),
            'cpu_usage': np.random.randint(10, 90),
            'memory_usage': np.random.randint(20, 80),
            'session_duration': (datetime.now() - self.start_time).seconds / 60
        }
        
        self.metrics = metrics
        return metrics
    
    def calculate_productivity_risk(self, metrics, anomaly_detected):
        """Calculate productivity-based risk score"""
        risk_score = 0
        risk_factors = []
        
        # Low productivity
        if metrics['productive_ratio'] < 0.35:
            risk_score += 35
            risk_factors.append("Low productivity ratio")
        elif metrics['productive_ratio'] < 0.50:
            risk_score += 15
            risk_factors.append("Below average productivity")
        
        # Low focus
        if metrics['focus_score'] < 0.4:
            risk_score += 20
            risk_factors.append("Low focus score")
        elif metrics['focus_score'] < 0.6:
            risk_score += 10
            risk_factors.append("Below average focus")
        
        # High idle time
        if metrics['idle_time'] > 90:
            risk_score += 20
            risk_factors.append("High idle time")
        elif metrics['idle_time'] > 60:
            risk_score += 10
            risk_factors.append("Above average idle time")
        
        # Task completion issues
        if metrics['task_completion_rate'] < 0.4:
            risk_score += 15
            risk_factors.append("Low task completion")
        
        # Low file activity (lack of work output)
        if metrics.get('file_modifications', 0) < 2:
            risk_score += 15
            risk_factors.append("Low file modification activity")
        
        # Anomaly detection
        if anomaly_detected:
            risk_score += 20
            risk_factors.append("Unusual work pattern detected")
        
        # Work efficiency
        if metrics.get('work_efficiency', 0.5) < 0.3:
            risk_score += 15
            risk_factors.append("Low work efficiency")
        
        # Cap risk score
        risk_score = min(100, risk_score)
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "MEDIUM"
        elif risk_score >= 30:
            risk_level = "LOW"
        else:
            risk_level = "VERY_LOW"
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors[:5]  # Top 5 risk factors
        }
    
    def analyze_behavior(self, metrics):
        """Perform comprehensive behavior analysis"""
        # Prepare features for model
        features = pd.DataFrame([[
            metrics['productive_time'],
            metrics['unproductive_time'],
            metrics['idle_time'],
            metrics['app_switches'],
            metrics['focus_score'],
            metrics['task_completion_rate'],
            metrics['productive_ratio'],
            metrics.get('file_activities', 0),
            metrics.get('file_modifications', 0)
        ]], columns=['productive_app_usage', 'unproductive_app_usage', 'idle_time',
                    'app_switch_count', 'focus_score', 'task_completion_rate',
                    'productive_ratio', 'file_activity_count', 'file_modification_count'])
        
        # Productivity prediction
        productivity_pred = self.model.predict(features)[0]
        productivity_proba = self.model.predict_proba(features)[0][1]
        
        # Anomaly detection
        anomaly_pred = self.anomaly_model.predict(features)[0]
        anomaly_score = self.anomaly_model.decision_function(features)[0]
        anomaly_detected = bool(anomaly_pred == -1)
        
        # Productivity score
        productivity_score = metrics['productive_ratio']
        
        # Calculate productivity risk
        risk_analysis = self.calculate_productivity_risk(metrics, anomaly_detected)
        
        return {
            'productivity_prediction': 'Productive' if productivity_pred == 1 else 'Needs Improvement',
            'productivity_confidence': float(productivity_proba),
            'productivity_score': float(round(productivity_score, 3)),
            'anomaly_detected': anomaly_detected,
            'anomaly_score': float(round(anomaly_score, 3)),
            'productivity_risk_score': risk_analysis['risk_score'],
            'productivity_risk_level': risk_analysis['risk_level'],
            'risk_factors': risk_analysis['risk_factors'],
            'work_efficiency': metrics.get('work_efficiency', 0.0),
            'metrics': metrics
        }
    
    def send_report_to_manager(self, analysis, report_type='regular'):
        """Send comprehensive report to manager"""
        current_time = datetime.now().isoformat()
        
        # Save to CSV
        self._export_to_csv(analysis, report_type, current_time)
        
        # Save to MySQL (skip if db is None)
        if self.db:
            report_data = {
                'timestamp': current_time,
                'report_type': report_type,
                'productive_time_min': analysis['metrics']['productive_time'],
                'unproductive_time_min': analysis['metrics']['unproductive_time'],
                'idle_time_min': analysis['metrics']['idle_time'],
                'app_switches': analysis['metrics']['app_switches'],
                'focus_score': analysis['metrics']['focus_score'],
                'task_completion_rate': analysis['metrics']['task_completion_rate'],
                'productive_ratio': analysis['metrics']['productive_ratio'],
                'productivity_prediction': analysis['productivity_prediction'],
                'productivity_confidence': analysis['productivity_confidence'],
                'productivity_score': analysis['productivity_score'],
                'anomaly_detected': analysis['anomaly_detected'],
                'anomaly_score': analysis['anomaly_score'],
                'file_activity_count': analysis['metrics'].get('file_activities', 0),
                'file_modification_count': analysis['metrics'].get('file_modifications', 0),
                'productivity_risk_score': analysis['productivity_risk_score'],
                'productivity_risk_level': analysis['productivity_risk_level'],
                'risk_factors': ', '.join(analysis['risk_factors'])
            }
            self.db.insert_employee_report(self.employee_id, report_data)
        
        # Save to JSON
        report = {
            'report_type': report_type,
            'timestamp': current_time,
            'employee_id': self.employee_id,
            'analysis': analysis
        }
        
        manager_folder = self.manager_config.get('shared_folder', './manager_reports')
        os.makedirs(manager_folder, exist_ok=True)
        
        report_file = os.path.join(manager_folder, f"employee_{self.employee_id}_reports.json")
        
        reports = []
        if os.path.exists(report_file):
            try:
                with open(report_file, 'r') as f:
                    reports = json.load(f)
            except:
                reports = []
        
        reports.append(report)
        if len(reports) > 100:
            reports = reports[-100:]
        
        with open(report_file, 'w') as f:
            json.dump(reports, f, indent=2)
        
        self._print_report(analysis, report_type)
        return True
    
    def _export_to_csv(self, analysis, report_type, timestamp):
        """Export analysis to CSV"""
        manager_folder = self.manager_config.get('shared_folder', './manager_reports')
        os.makedirs(manager_folder, exist_ok=True)
        
        csv_file = os.path.join(manager_folder, f"all_employee_reports.csv")
        
        new_row = {
            'timestamp': timestamp,
            'employee_id': self.employee_id,
            'report_type': report_type,
            'productive_time_min': analysis['metrics']['productive_time'],
            'unproductive_time_min': analysis['metrics']['unproductive_time'],
            'idle_time_min': analysis['metrics']['idle_time'],
            'app_switches': analysis['metrics']['app_switches'],
            'focus_score': analysis['metrics']['focus_score'],
            'task_completion_rate': analysis['metrics']['task_completion_rate'],
            'productive_ratio': analysis['metrics']['productive_ratio'],
            'productivity_prediction': analysis['productivity_prediction'],
            'productivity_confidence': analysis['productivity_confidence'],
            'productivity_score': analysis['productivity_score'],
            'anomaly_detected': analysis['anomaly_detected'],
            'anomaly_score': analysis['anomaly_score'],
            'file_activities': analysis['metrics'].get('file_activities', 0),
            'file_modifications': analysis['metrics'].get('file_modifications', 0),
            'work_efficiency': analysis.get('work_efficiency', 0.0),
            'risk_score': analysis['productivity_risk_score'],
            'risk_level': analysis['productivity_risk_level'],
            'risk_factors': ', '.join(analysis['risk_factors'])
        }
        
        new_df = pd.DataFrame([new_row])
        
        if os.path.exists(csv_file):
            existing_df = pd.read_csv(csv_file)
            existing_df['employee_id'] = existing_df['employee_id'].astype(str)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            updated_df = new_df        
        updated_df.to_csv(csv_file, index=False)
    
    def _print_report(self, analysis, report_type):
        """Print formatted report"""
        if report_type == 'alert':
            print(f"\n{'='*50}")
            print(f"📊 Employee {self.employee_id} - Activity Report")
            print(f"{'='*50}")
            print(f"Productivity: {analysis['productivity_prediction']} ({analysis['productivity_score']:.1%})")
            print(f"Risk Level: {analysis['productivity_risk_level']} (Score: {analysis['productivity_risk_score']}/100)")
            if analysis['anomaly_detected']:
                print(f"⚠️ Unusual work pattern detected")
            if analysis['risk_factors']:
                print(f"Risk Factors: {', '.join(analysis['risk_factors'])}")
        else:
            print(f"\n   {self.employee_id}: {analysis['productivity_prediction']} ({analysis['productivity_score']:.1%}) | "
                  f"Risk: {analysis['productivity_risk_level']}")
            if analysis['anomaly_detected']:
                print(f"   ⚠️ Unusual work pattern detected")
            if analysis.get('work_efficiency', 0) > 0:
                print(f"   📊 Work Efficiency: {analysis.get('work_efficiency', 0):.1%}")
    
    def start_monitoring(self, interval_minutes=5):
        """Start monitoring employee"""
        self.is_running = True
        self.start_time = datetime.now()
        
        # Start file monitoring
        self.start_file_monitoring()
        
        print(f"\n✅ Started monitoring for Employee {self.employee_id}")
        print(f"📊 Analysis interval: Every {interval_minutes} minutes")
        print(f"📁 File activity monitoring: ACTIVE")
        print(f"💾 Reports saved to: MySQL database and ./manager_reports/")
        print(f"⚠️  Press Ctrl+C to stop monitoring\n")
        
        report_count = 0
        
        try:
            while self.is_running:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Analyzing employee activity...")
                
                # Collect metrics
                metrics = self.collect_employee_metrics()
                analysis = self.analyze_behavior(metrics)
                
                # Check if report should be sent
                if analysis['productivity_risk_level'] in ['CRITICAL', 'MEDIUM'] or analysis['anomaly_detected']:
                    self.send_report_to_manager(analysis, report_type='alert')
                else:
                    report_count += 1
                    if report_count % 3 == 0:
                        self.send_report_to_manager(analysis, report_type='regular')
                    else:
                        self._print_report(analysis, 'regular')
                
                self.data_buffer.append(analysis)
                self.performance_history.append({
                    'timestamp': datetime.now(),
                    'productivity_score': analysis['productivity_score'],
                    'risk_score': analysis['productivity_risk_score'],
                    'anomaly_detected': analysis['anomaly_detected']
                })
                
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print(f"\n⚠️ Stopping monitoring for Employee {self.employee_id}")
            self.is_running = False
            self.stop_file_monitoring()
            if self.db:
                self.db.update_employee_session(self.employee_id, is_active=False)
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_running = False
        self.stop_file_monitoring()
        if self.db:
            self.db.update_employee_session(self.employee_id, is_active=False)
        print(f"\n✅ Monitoring stopped for Employee {self.employee_id}")

# =====================================================
# MANAGER DASHBOARD - FIXED VERSION (Shows Employee 34)
# =====================================================

class ManagerDashboard:
    """Enhanced manager dashboard with comprehensive analytics"""
    
    def __init__(self, shared_folder='./manager_reports', db_connection=None):
        self.shared_folder = shared_folder
        self.db = db_connection
    
    def get_all_data(self):
        """Get all reports from MySQL AND CSV (combines both)"""
        all_data = pd.DataFrame()
        
        # Try to get from MySQL first
        if self.db:
            try:
                results = self.db.get_all_reports(1000)
                if results:
                    mysql_df = pd.DataFrame(results)
                    mysql_df['employee_id'] = mysql_df['employee_id'].astype(str)
                    all_data = mysql_df
                    print(f"✅ Loaded {len(all_data)} records from MySQL")
            except Exception as e:
                print(f"⚠️ Error loading from MySQL: {e}")
        
        # ALSO load from CSV (to include employee 34 data that might not be in MySQL)
        csv_file = os.path.join(self.shared_folder, 'all_employee_reports.csv')
        if os.path.exists(csv_file):
            try:
                csv_df = pd.read_csv(csv_file)
                csv_df['employee_id'] = csv_df['employee_id'].astype(str)
                
                # If we already have MySQL data, combine them
                if not all_data.empty:
                    # Combine MySQL and CSV data
                    all_data = pd.concat([all_data, csv_df], ignore_index=True)
                    # Remove duplicates based on timestamp and employee_id
                    all_data = all_data.drop_duplicates(subset=['timestamp', 'employee_id'], keep='last')
                    print(f"✅ Combined MySQL + CSV = {len(all_data)} records")
                else:
                    all_data = csv_df
                    print(f"✅ Loaded {len(all_data)} records from CSV (including employee 34)")
            except Exception as e:
                print(f"⚠️ Error loading from CSV: {e}")
        
        return all_data
    
    def get_file_activities(self):
        """Get file activities from CSV"""
        file_activity_file = os.path.join(self.shared_folder, 'file_activities.csv')
        if os.path.exists(file_activity_file):
            df = pd.read_csv(file_activity_file)
            df['employee_id'] = df['employee_id'].astype(str)
            return df
        return pd.DataFrame()
    
    def get_employee_history(self, employee_id):
        """Get history for a specific employee from combined data"""
        all_data = self.get_all_data()
        if all_data.empty:
            return pd.DataFrame()
        
        # Filter by employee_id
        emp_history = all_data[all_data['employee_id'].astype(str) == str(employee_id)]
        return emp_history.sort_values('timestamp', ascending=False)
    
    def export_comprehensive_csv_report(self):
        """Export all reports to CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_folder = f"export_{timestamp}"
        os.makedirs(export_folder, exist_ok=True)
        
        all_data = self.get_all_data()
        file_activities = self.get_file_activities()
        
        # Export all reports
        if not all_data.empty:
            all_data.to_csv(os.path.join(export_folder, '1_all_reports.csv'), index=False)
            print(f"✅ 1_all_reports.csv - All reports ({len(all_data)} records)")
            
            # Show which employees are in the data
            employees = all_data['employee_id'].unique()
            print(f"   📋 Employees in report: {', '.join(employees)}")
        
        # Export summary (with safe column handling)
        if not all_data.empty:
            summary = self.get_employee_summary(all_data)
            if not summary.empty:
                summary.to_csv(os.path.join(export_folder, '2_employee_summary.csv'), index=False)
                print(f"✅ 2_employee_summary.csv - Employee summary")
        
        # Export risk analysis
        if not all_data.empty:
            risk_report = self.get_risk_report(all_data)
            if not risk_report.empty:
                risk_report.to_csv(os.path.join(export_folder, '3_risk_analysis.csv'), index=False)
                print(f"✅ 3_risk_analysis.csv - Risk analysis")
        
        # Export file activities
        if not file_activities.empty:
            file_activities.to_csv(os.path.join(export_folder, '4_file_activities.csv'), index=False)
            print(f"✅ 4_file_activities.csv - File activities ({len(file_activities)} records)")
        
        # Export anomalies (with safe column handling)
        if not all_data.empty and 'anomaly_detected' in all_data.columns:
            anomalies = all_data[all_data['anomaly_detected'] == True]
            if not anomalies.empty:
                anomalies.to_csv(os.path.join(export_folder, '5_anomalies.csv'), index=False)
                print(f"✅ 5_anomalies.csv - Anomalies ({len(anomalies)} records)")
        
        print(f"\n✅ All CSV reports exported to folder: {export_folder}/")
        print(f"📁 Full path: {os.path.abspath(export_folder)}")
        return export_folder
    
    def get_employee_summary(self, all_data):
        """Get employee summary with safe column handling"""
        if all_data.empty:
            return pd.DataFrame()
        
        # Define aggregation safely - only use columns that exist
        agg_dict = {
            'productivity_score': ['mean', 'min', 'max', 'count'],
            'anomaly_detected': 'sum'
        }
        
        # Add risk_score if it exists
        if 'risk_score' in all_data.columns:
            agg_dict['risk_score'] = 'mean'
        
        # Add file_activities if it exists
        if 'file_activities' in all_data.columns:
            agg_dict['file_activities'] = 'mean'
        
        summary = all_data.groupby('employee_id').agg(agg_dict).round(2)
        
        # Build column names safely
        columns = ['Avg_Productivity', 'Min_Productivity', 'Max_Productivity', 'Report_Count', 'Anomalies']
        if 'risk_score' in all_data.columns:
            columns.append('Avg_Risk')
        if 'file_activities' in all_data.columns:
            columns.append('Avg_File_Activity')
        
        summary.columns = columns
        summary = summary.reset_index()
        
        # Add rating
        summary['Rating'] = summary['Avg_Productivity'].apply(
            lambda x: 'Excellent' if x >= 0.7 else 'Good' if x >= 0.5 else 
            'Average' if x >= 0.3 else 'Needs Improvement'
        )
        
        return summary
    
    def get_risk_report(self, all_data):
        """Get risk analysis report"""
        if all_data.empty:
            return pd.DataFrame()
        
        risk_report = all_data.groupby('employee_id').agg({
            'risk_level': lambda x: x.mode()[0] if len(x) > 0 else 'LOW',
            'risk_score': 'mean',
            'anomaly_detected': 'sum'
        }).reset_index()
        
        risk_report.columns = ['employee_id', 'Primary_Risk_Level', 'Avg_Risk_Score', 'Total_Anomalies']
        
        return risk_report
    
    def display_dashboard(self):
        """Display the manager dashboard"""
        print("\n" + "="*60)
        print("👔 MANAGER DASHBOARD - TEAM PERFORMANCE")
        print("="*60)
        
        all_data = self.get_all_data()
        
        if all_data.empty:
            print("[!] No reports available. Run employee monitoring first!")
            print("   💡 Go to option 1 to start monitoring employees")
            return
        
        # Ensure required columns exist
        if 'anomaly_detected' not in all_data.columns:
            all_data['anomaly_detected'] = False
        if 'risk_score' not in all_data.columns:
            all_data['risk_score'] = 0
        if 'risk_level' not in all_data.columns:
            all_data['risk_level'] = 'LOW'
        if 'file_activities' not in all_data.columns:
            all_data['file_activities'] = 0
        
        latest_reports = all_data.sort_values('timestamp').groupby('employee_id').last().reset_index()
        
        print(f"\n📊 Team Summary:")
        print(f"   Total Employees: {len(latest_reports)}")
        print(f"   Total Reports: {len(all_data)}")
        print(f"   Average Productivity: {latest_reports['productivity_score'].mean():.1%}")
        high_risk = len(latest_reports[latest_reports['risk_level'].isin(['CRITICAL', 'MEDIUM'])])
        print(f"   High/Medium Risk Employees: {high_risk}")
        print(f"   Total Anomalies Detected: {latest_reports['anomaly_detected'].sum()}")
        
        # Get active employees from MySQL
        if self.db:
            active_employees = self.db.get_active_employees()
            if active_employees:
                print(f"   🟢 Currently Active: {len(active_employees)} employees")
                print(f"   Active IDs: {', '.join(active_employees)}")
        
        print(f"\n📈 Employee Status:")
        print("-" * 90)
        print(f"{'ID':<12} {'Productivity':<15} {'Risk':<12} {'Status':<12} {'Activity':<12}")
        print("-" * 90)
        
        for _, emp in latest_reports.iterrows():
            icon = "🔴" if emp['risk_level'] in ['CRITICAL'] else "🟡" if emp['risk_level'] == 'MEDIUM' else "🟢"
            anomaly_mark = "⚠️" if emp['anomaly_detected'] else "✅"
            
            # Check if employee is currently active
            active_mark = "🟢" if self.db and emp['employee_id'] in self.db.get_active_employees() else "⚫"
            
            file_act = emp.get('file_activities', 0)
            file_act_display = f"{file_act:.0f}" if isinstance(file_act, (int, float)) else "0"
            
            print(f"{icon} {emp['employee_id']:<10} {emp['productivity_score']:.1%}      "
                  f"{emp['risk_level']:<8} {anomaly_mark} {active_mark}     "
                  f"{file_act_display}")
        
        # High risk employees
        high_risk_emps = latest_reports[latest_reports['risk_level'].isin(['CRITICAL', 'MEDIUM'])]
        if not high_risk_emps.empty:
            print("\n" + "="*60)
            print("⚠️ PRODUCTIVITY RISK ALERTS")
            print("="*60)
            for _, emp in high_risk_emps.iterrows():
                print(f"⚠️ Employee {emp['employee_id']} - {emp['risk_level']} Risk")
                print(f"   Productivity: {emp['productivity_score']:.1%}")
                print(f"   Risk Score: {emp['risk_score']}/100")
                if emp.get('risk_factors'):
                    print(f"   Factors: {emp.get('risk_factors', '')}")
                print()
    
    def generate_productivity_insights(self):
        """Generate productivity insights"""
        all_data = self.get_all_data()
        if all_data.empty:
            return
        
        print("\n" + "="*60)
        print("📊 PRODUCTIVITY INSIGHTS")
        print("="*60)
        
        # Overall stats
        avg_productivity = all_data['productivity_score'].mean()
        print(f"\n📈 Overall Team Productivity: {avg_productivity:.1%}")
        
        # Trend analysis
        recent_data = all_data.sort_values('timestamp').tail(20)
        if len(recent_data) > 10:
            trend = recent_data['productivity_score'].rolling(5).mean()
            if len(trend) > 1:
                trend_direction = "Upward" if trend.iloc[-1] > trend.iloc[0] else "Downward"
                print(f"📈 Trend: {trend_direction} (Last 5 periods)")
        
        # Risk distribution
        if 'risk_level' in all_data.columns:
            risk_dist = all_data['risk_level'].value_counts()
            print(f"\n📊 Risk Distribution:")
            for level in ['VERY_LOW', 'LOW', 'MEDIUM', 'CRITICAL']:
                count = risk_dist.get(level, 0)
                pct = (count / len(all_data)) * 100
                print(f"   {level}: {count} ({pct:.1f}%)")
        
        # File activity insights
        if 'file_activities' in all_data.columns:
            avg_file_activity = all_data['file_activities'].mean()
            print(f"\n📁 Average File Activity: {avg_file_activity:.1f} per period")
        
        print("-" * 60)

# =====================================================
# MODEL TRAINING FUNCTIONS
# =====================================================

def train_and_validate_model():
    """Train model with proper train/test split and show real accuracy"""
    print("\n" + "="*60)
    print("📊 MODEL TRAINING & VALIDATION")
    print("="*60)
    
    np.random.seed(42)
    
    # Generate comprehensive training data
    n_samples = 5000
    
    data = {
        "productive_app_usage": np.random.gamma(2, 30, n_samples),
        "unproductive_app_usage": np.random.gamma(1.5, 20, n_samples),
        "idle_time": np.random.exponential(15, n_samples),
        "app_switch_count": np.random.poisson(8, n_samples),
        "focus_score": np.random.beta(8, 3, n_samples),
        "task_completion_rate": np.random.beta(7, 3, n_samples),
        "file_activity_count": np.random.poisson(15, n_samples),
        "file_modification_count": np.random.poisson(10, n_samples)
    }
    
    df = pd.DataFrame(data)
    
    # Cap values to realistic ranges
    df['productive_app_usage'] = np.clip(df['productive_app_usage'], 10, 300)
    df['unproductive_app_usage'] = np.clip(df['unproductive_app_usage'], 0, 200)
    df['idle_time'] = np.clip(df['idle_time'], 0, 120)
    df['app_switch_count'] = np.clip(df['app_switch_count'], 1, 30)
    df['file_activity_count'] = np.clip(df['file_activity_count'], 0, 100)
    df['file_modification_count'] = np.clip(df['file_modification_count'], 0, 80)
    
    df["productive_ratio"] = df["productive_app_usage"] / (df["productive_app_usage"] + df["unproductive_app_usage"] + 1)
    df["productivity_label"] = (
        (df["productive_ratio"] > 0.55) & 
        (df["focus_score"] > 0.6) & 
        (df["task_completion_rate"] > 0.65)
    ).astype(int)
    
    # Add some noise
    noise_idx = np.random.choice(df.index, size=int(0.05 * len(df)), replace=False)
    df.loc[noise_idx, "productivity_label"] = 1 - df.loc[noise_idx, "productivity_label"]
    
    features = ["productive_app_usage", "unproductive_app_usage", "idle_time", 
                "app_switch_count", "focus_score", "task_completion_rate", 
                "productive_ratio", "file_activity_count", "file_modification_count"]
    
    X = df[features]
    y = df["productivity_label"]
    
    # Split data
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.176, random_state=42, stratify=y_temp)
    
    print(f"\n📊 Dataset Split:")
    print(f"   Training samples: {len(X_train)} (70%)")
    print(f"   Validation samples: {len(X_val)} (15%)")
    print(f"   Test samples: {len(X_test)} (15%)")
    print(f"   Class balance: {y.sum()/len(y):.1%} productive, {(1-y.sum()/len(y)):.1%} needs improvement")
    
    # Train Random Forest
    print("\n🔄 Training Random Forest model...")
    rf_model = RandomForestClassifier(
        n_estimators=200, 
        max_depth=10,
        min_samples_split=20,
        min_samples_leaf=10,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    
    # Train Isolation Forest for anomaly detection
    print("🔄 Training Anomaly Detection model...")
    iso_forest = IsolationForest(contamination=0.05, random_state=42)
    iso_forest.fit(X_train)
    
    # Evaluate
    print("\n" + "="*60)
    print("📈 MODEL PERFORMANCE METRICS")
    print("="*60)
    
    y_train_pred = rf_model.predict(X_train)
    train_acc = accuracy_score(y_train, y_train_pred)
    
    y_val_pred = rf_model.predict(X_val)
    val_acc = accuracy_score(y_val, y_val_pred)
    
    y_test_pred = rf_model.predict(X_test)
    test_acc = accuracy_score(y_test, y_test_pred)
    
    print(f"\n🎯 Accuracy Scores:")
    print(f"   Training Accuracy: {train_acc:.2%}")
    print(f"   Validation Accuracy: {val_acc:.2%}")
    print(f"   Test Accuracy (Unseen Data): {test_acc:.2%} ⭐")
    
    precision = precision_score(y_test, y_test_pred)
    recall = recall_score(y_test, y_test_pred)
    f1 = f1_score(y_test, y_test_pred)
    
    print(f"\n📊 Additional Metrics (Test Data):")
    print(f"   Precision: {precision:.2%}")
    print(f"   Recall: {recall:.2%}")
    print(f"   F1-Score: {f1:.2%}")
    
    overfit_gap = train_acc - test_acc
    if overfit_gap > 0.1:
        print(f"\n⚠️  Possible overfitting detected! (Gap: {overfit_gap:.1%})")
    else:
        print(f"\n✅ Model generalizes well! (Train-Test gap: {overfit_gap:.1%})")
    
    print("\n📋 Detailed Classification Report (Test Data):")
    print("-" * 40)
    print(classification_report(y_test, y_test_pred, 
                                target_names=['Needs Improvement', 'Productive']))
    
    # Feature importance
    print("\n🔍 Top 5 Most Important Features:")
    feature_importance = pd.DataFrame({
        'feature': features,
        'importance': rf_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    for i, row in feature_importance.head().iterrows():
        print(f"   {i+1}. {row['feature']}: {row['importance']:.3f}")
    
    # Save models
    joblib.dump(rf_model, 'productivity_model_enhanced.pkl')
    joblib.dump(iso_forest, 'anomaly_model_enhanced.pkl')
    
    # Save training results
    results = {
        'training_accuracy': float(train_acc),
        'validation_accuracy': float(val_acc),
        'test_accuracy': float(test_acc),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'overfitting_gap': float(overfit_gap),
        'feature_importance': feature_importance.to_dict(),
        'test_date': datetime.now().isoformat(),
        'samples_used': len(X_train) + len(X_val) + len(X_test)
    }
    
    with open('model_training_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Models saved successfully!")
    print(f"📁 Training results saved to: model_training_results.json")
    
    return test_acc

def view_model_results():
    """View previously saved model training results"""
    print("\n" + "="*60)
    print("📊 VIEW MODEL TRAINING RESULTS")
    print("="*60)
    
    if os.path.exists('model_training_results.json'):
        with open('model_training_results.json', 'r') as f:
            results = json.load(f)
        
        print(f"\n📈 Last Training Results ({results['test_date']}):")
        print(f"   Training Accuracy: {results['training_accuracy']:.2%}")
        print(f"   Validation Accuracy: {results['validation_accuracy']:.2%}")
        print(f"   Test Accuracy: {results['test_accuracy']:.2%}")
        print(f"   Precision: {results['precision']:.2%}")
        print(f"   Recall: {results['recall']:.2%}")
        print(f"   F1-Score: {results['f1_score']:.2%}")
        print(f"   Overfitting Gap: {results['overfitting_gap']:.2%}")
        print(f"   Samples Used: {results['samples_used']}")
        
        print(f"\n🔍 Feature Importance:")
        for feature, importance in results['feature_importance']['importance'].items():
            print(f"   {feature}: {float(importance):.3f}")
    else:
        print("\n❌ No training results found. Please train a model first")

# =====================================================
# MAIN FUNCTIONS
# =====================================================

def setup_mysql_connection():
    """Setup MySQL connection"""
    print("\n" + "="*60)
    print("🐬 MYSQL DATABASE SETUP")
    print("="*60)
    
    print("\nPlease enter your MySQL credentials:")
    host = input("Host (default: localhost): ").strip() or "localhost"
    user = input("Username (default: root): ").strip() or "root"
    password = input("Password: ").strip()
    database = input("Database name (default: employee_monitoring): ").strip() or "employee_monitoring"
    
    db = MySQLDatabase(host=host, database=database, user=user, password=password)
    
    if db.connect():
        # Create tables if they don't exist
        db.create_tables_if_not_exist()
        print("\n✅ MySQL connection established and tables verified!")
        return db
    else:
        print("\n❌ Failed to connect to MySQL. Continuing without database...")
        return None

def run_employee_mode(db_connection=None):
    """Run as employee agent"""
    print("\n" + "="*60)
    print("🖥️  EMPLOYEE MONITORING AGENT")
    print("="*60)
    
    employee_id = input("Enter your Employee ID: ").strip()
    if not employee_id:
        employee_id = f"EMP{np.random.randint(100, 999)}"
        print(f"Using auto-generated ID: {employee_id}")
    
    interval = input("Monitoring interval in minutes (default 5, 0 for single analysis): ").strip()
    interval = int(interval) if interval else 5
    
    config = {'shared_folder': './manager_reports'}
    agent = EmployeeMonitoringAgent(employee_id, config, db_connection)
    
    if interval == 0:
        print("\n🔄 Running single analysis...")
        metrics = agent.collect_employee_metrics()
        analysis = agent.analyze_behavior(metrics)
        agent.send_report_to_manager(analysis, 'regular')
        print(f"\n✅ Analysis complete for {employee_id}")
        if db_connection:
            db_connection.update_employee_session(employee_id, is_active=False)
    else:
        print(f"\n⚠️ Monitoring started for {interval} minute intervals")
        print("📁 File activity monitoring: ACTIVE")
        print("📊 Productivity risk analysis: ENABLED")
        print("💡 Press Ctrl+C to stop and return to menu\n")
        agent.start_monitoring(interval_minutes=interval)
    
    print("\n✅ Returning to main menu...")
    time.sleep(2)

def run_manager_mode(db_connection=None):
    """Run as manager"""
    print("\n" + "="*60)
    print("👔 MANAGER DASHBOARD")
    print("="*60)
    
    dashboard = ManagerDashboard(db_connection=db_connection)
    
    while True:
        dashboard.display_dashboard()
        
        print("\n📋 OPTIONS:")
        print("   1. Refresh Dashboard")
        print("   2. Export CSV Reports")
        print("   3. View Employee History")
        print("   4. View File Activities")
        print("   5. Generate Productivity Insights")
        print("   6. Return to Main Menu")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            continue
        elif choice == '2':
            dashboard.export_comprehensive_csv_report()
            input("\nPress Enter to continue...")
        elif choice == '3':
            emp_id = input("Enter Employee ID: ").strip()
            emp_id = str(emp_id)
            
            # Get history from combined data
            history = dashboard.get_employee_history(emp_id)
            if not history.empty:
                print(f"\n📊 Employee {emp_id} Details:")
                print(f"Total Reports: {len(history)}")
                print(history[['timestamp', 'productivity_prediction', 'productivity_score', 
                              'risk_level', 'anomaly_detected']].head(10).to_string())
                
                # Show statistics
                print(f"\n📊 Statistics for {emp_id}:")
                print(f"   Average Productivity: {history['productivity_score'].mean():.1%}")
                print(f"   Best Productivity: {history['productivity_score'].max():.1%}")
                print(f"   Worst Productivity: {history['productivity_score'].min():.1%}")
                print(f"   Anomalies Detected: {history['anomaly_detected'].sum()}")
            else:
                print(f"❌ No data found for Employee {emp_id}")
                print(f"   💡 Run option 1 to start monitoring this employee")
            input("\nPress Enter to continue...")
        elif choice == '4':
            file_activities = dashboard.get_file_activities()
            if not file_activities.empty:
                print("\n📁 FILE ACTIVITIES:")
                print(f"Total Activities: {len(file_activities)}")
                print(file_activities[['timestamp', 'employee_id', 'activity_type', 
                                      'file_name']].head(20).to_string())
            else:
                print("❌ No file activities found")
                print("   💡 File monitoring is active when employees are being monitored")
            input("\nPress Enter to continue...")
        elif choice == '5':
            dashboard.generate_productivity_insights()
            input("\nPress Enter to continue...")
        elif choice == '6':
            print("\n✅ Returning to main menu...")
            break
        else:
            print("❌ Invalid option")

def run_demo(db_connection=None):
    """Run complete demo"""
    print("\n" + "="*60)
    print("🎯 EMPLOYEE MONITORING SYSTEM - DEMO MODE")
    print("="*60)
    
    os.makedirs('./manager_reports', exist_ok=True)
    
    employees = ['EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005']
    
    print("\n🔄 Starting demo analysis for 5 employees...")
    print("📁 File activity tracking: ACTIVE")
    print("📊 Productivity risk analysis: ENABLED\n")
    
    agents = []
    for emp_id in employees:
        config = {'shared_folder': './manager_reports'}
        agent = EmployeeMonitoringAgent(emp_id, config, db_connection)
        agents.append(agent)
    
    for cycle in range(5):
        print(f"Cycle {cycle + 1}/5", end=" ", flush=True)
        
        for agent in agents:
            # Simulate file activity (reduced frequency to avoid clutter)
            if np.random.random() < 0.2:
                activity_types = ['MODIFIED', 'CREATED', 'DELETED']
                activity_type = np.random.choice(activity_types)
                agent.handle_file_activity(activity_type, {
                    'employee_id': agent.employee_id,
                    'file_name': f"project_file_{cycle}.txt",
                    'file_path': f"C:\\work\\project_file_{cycle}.txt",
                    'file_size': np.random.randint(100, 10000),
                    'file_extension': '.txt',
                    'timestamp': datetime.now().isoformat()
                })
            
            metrics = agent.collect_employee_metrics()
            analysis = agent.analyze_behavior(metrics)
            
            if analysis['productivity_risk_level'] in ['CRITICAL', 'MEDIUM'] or analysis['anomaly_detected']:
                agent.send_report_to_manager(analysis, 'alert')
            else:
                agent.send_report_to_manager(analysis, 'regular')
        
        print("✓", end=" ", flush=True)
        time.sleep(0.5)
    
    print("\n\n✅ Demo complete!")
    
    dashboard = ManagerDashboard(db_connection=db_connection)
    dashboard.display_dashboard()
    dashboard.generate_productivity_insights()
    
    print("\n📊 Exporting reports...")
    dashboard.export_comprehensive_csv_report()
    
    print("\n✅ Demo finished! Returning to main menu...")
    time.sleep(3)

def run_documentation():
    """Generate documentation and reports"""
    print("\n" + "="*60)
    print("📄 DOCUMENTATION & REPORT GENERATION")
    print("="*60)
    
    dashboard = ManagerDashboard()
    
    print("\n🔄 Generating comprehensive documentation...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_folder = f"documentation_{timestamp}"
    os.makedirs(doc_folder, exist_ok=True)
    
    all_data = dashboard.get_all_data()
    
    # Generate summary report
    summary_text = f"""
    ============================================
    EMPLOYEE MONITORING SYSTEM REPORT
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    ============================================
    
    SYSTEM OVERVIEW
    --------------
    Total Employees Monitored: {len(all_data['employee_id'].unique()) if not all_data.empty else 0}
    Total Reports Generated: {len(all_data) if not all_data.empty else 0}
    
    PERFORMANCE SUMMARY
    ------------------
    Average Productivity Score: {all_data['productivity_score'].mean():.1%} if not all_data.empty else 'N/A'
    Total Anomalies: {all_data['anomaly_detected'].sum() if not all_data.empty else 0}
    High Risk Employees: {len(all_data[all_data['risk_level'].isin(['CRITICAL', 'MEDIUM'])]) if not all_data.empty else 0}
    
    FILES GENERATED
    --------------
    - CSV Reports in export_* folders
    - File activities in file_activities.csv
    - Individual employee reports in JSON format
    - Model training results
    """
    
    with open(os.path.join(doc_folder, "system_report.txt"), 'w') as f:
        f.write(summary_text)
    
    print(f"✅ System report saved to {doc_folder}/system_report.txt")
    
    # Export all CSV reports
    dashboard.export_comprehensive_csv_report()
    
    # Copy model results if available
    if os.path.exists('model_training_results.json'):
        shutil.copy('model_training_results.json', doc_folder)
        print(f"✅ Model training results copied")
    
    print(f"\n✅ Documentation generated in folder: {doc_folder}/")
    print("\n✅ Documentation generation complete!")
    time.sleep(3)

# =====================================================
# MAIN PROGRAM
# =====================================================

def main():
    """Main program loop"""
    db_connection = None
    
    # Check for MySQL connection on startup
    print("\n" + "="*60)
    print("🐬 CHECKING MYSQL CONNECTION")
    print("="*60)
    
    try:
        test_db = MySQLDatabase()
        if test_db.connect():
            test_db.disconnect()
            print("✅ MySQL is available. You can set up connection in the menu.")
        else:
            print("ℹ️  MySQL not available. Data will be saved to CSV files only.")
    except:
        print("ℹ️  MySQL not available. Data will be saved to CSV files only.")
    
    while True:
        print("\n" + "="*60)
        print("🎯 EMPLOYEE BEHAVIOR ANALYTICS SYSTEM")
        print("="*60)
        
        if db_connection:
            print(f"✅ MySQL Connected: {db_connection.database}")
        else:
            print("ℹ️  MySQL: Not Connected (CSV mode only)")
        
        if not WATCHDOG_AVAILABLE:
            print("\n💡 Tip: For file monitoring, run: pip install watchdog")
        
        print("\n📋 MAIN MENU:")
        print("   1. Employee Agent (Start Monitoring)")
        print("   2. Manager Dashboard (View Reports)")
        print("   3. Quick Demo (Generate Sample Data)")
        print("   4. Generate Documentation 📥")
        print("   5. 🧪 Train & Validate Model")
        print("   6. 📈 View Saved Model Results")
        print("   7. 🔗 Setup MySQL Connection")
        print("   8. Exit Program")
        
        mode = input("\n👉 Select option (1-8): ").strip()
        
        if mode == '1':
            run_employee_mode(db_connection)
        elif mode == '2':
            run_manager_mode(db_connection)
        elif mode == '3':
            run_demo(db_connection)
        elif mode == '4':
            run_documentation()
        elif mode == '5':
            accuracy = train_and_validate_model()
            print(f"\n🎉 Model Training Complete! Test Accuracy: {accuracy:.2%}")
            input("\nPress Enter to continue...")
        elif mode == '6':
            view_model_results()
            input("\nPress Enter to continue...")
        elif mode == '7':
            db_connection = setup_mysql_connection()
            if db_connection:
                print("\n✅ MySQL connection established! Data will be stored in database.")
            else:
                print("\n⚠️ Continuing with CSV mode only.")
            input("\nPress Enter to continue...")
        elif mode == '8':
            if db_connection:
                db_connection.disconnect()
            print("\n👋 Thank you for using Employee Behavior Analytics System!")
            print("Exiting program...")
            break
        else:
            print("\n❌ Invalid option! Please select 1-8")
            time.sleep(1)

# =====================================================
# PROGRAM ENTRY POINT
# =====================================================

if __name__ == "__main__":
    main()
    print("\n✅ Program terminated successfully!")
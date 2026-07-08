"""
EMPLOYEE BEHAVIOR ANALYTICS SYSTEM WITH MYSQL INTEGRATION
==========================================================
Complete system for monitoring employee behavior with persistent MySQL storage
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_score, recall_score, f1_score
import joblib
import time
import os
import json
from collections import deque
from datetime import datetime
import hashlib
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
    print("ℹ️  Note: Install 'openpyxl' for Excel export: pip install openpyxl")

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
    
    def insert_employee_report(self, employee_id, report_data):
        """Insert employee report into database"""
        try:
            query = """
                INSERT INTO employee_reports (
                    employee_id, timestamp, report_type, productive_time_min,
                    unproductive_time_min, idle_time_min, app_switches, deleted_files,
                    focus_score, task_completion_rate, productive_ratio,
                    productivity_prediction, productivity_confidence, productivity_score,
                    anomaly_detected, anomaly_score, risk_level, risk_score,
                    risk_factors, suspicious_files
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
                report_data.get('deleted_files', 0),
                report_data.get('focus_score', 0.0),
                report_data.get('task_completion_rate', 0.0),
                report_data.get('productive_ratio', 0.0),
                report_data.get('productivity_prediction', 'Unknown'),
                report_data.get('productivity_confidence', 0.0),
                report_data.get('productivity_score', 0.0),
                1 if report_data.get('anomaly_detected', False) else 0,
                report_data.get('anomaly_score', 0.0),
                report_data.get('risk_level', 'LOW'),
                report_data.get('risk_score', 0),
                report_data.get('risk_factors', ''),
                report_data.get('suspicious_files', 0)
            )
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return True
        except Error as e:
            print(f"❌ Error inserting report: {e}")
            return False
    
    def insert_file_event(self, employee_id, event_data):
        """Insert file event into database"""
        try:
            query = """
                INSERT INTO file_events (
                    employee_id, timestamp, event_type, file_name,
                    file_path, file_size, file_type, severity
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                employee_id,
                event_data.get('timestamp'),
                event_data.get('event_type'),
                event_data.get('file_name', ''),
                event_data.get('file_path', ''),
                event_data.get('file_size', 0),
                event_data.get('file_type', ''),
                event_data.get('severity', 'INFO')
            )
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return True
        except Error as e:
            print(f"❌ Error inserting file event: {e}")
            return False
    
    def insert_security_alert(self, employee_id, alert_data):
        """Insert security alert into database"""
        try:
            query = """
                INSERT INTO security_alerts (
                    employee_id, timestamp, alert_type, severity,
                    file_name, file_path, details, resolved
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                employee_id,
                alert_data.get('timestamp'),
                alert_data.get('alert_type'),
                alert_data.get('severity', 'MEDIUM'),
                alert_data.get('file_name', ''),
                alert_data.get('file_path', ''),
                alert_data.get('message', alert_data.get('reason', '')),
                0
            )
            
            self.cursor.execute(query, values)
            self.connection.commit()
            return True
        except Error as e:
            print(f"❌ Error inserting security alert: {e}")
            return False
    
    def update_employee_session(self, employee_id, is_active=True):
        """Update or create employee session"""
        try:
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
# FILE DETECTION SYSTEM
# =====================================================

class FileDetectionHandler(FileSystemEventHandler):
    """Detects file system events in real-time"""
    
    def __init__(self, employee_id, callback_function, db_connection):
        self.employee_id = employee_id
        self.callback = callback_function
        self.db = db_connection
        self.suspicious_extensions = {'.exe', '.bat', '.ps1', '.vbs', '.js', '.py', '.scr', '.com', '.dll'}
        self.file_hashes = {}
        self.deletion_count = 0
        self.last_reset = datetime.now()
        
    def on_created(self, event):
        if not event.is_directory:
            file_info = self.get_file_info(event.src_path)
            event_data = {
                'employee_id': self.employee_id,
                'file_path': event.src_path,
                'file_name': os.path.basename(event.src_path),
                'file_size': file_info['size'],
                'file_type': file_info['extension'],
                'timestamp': datetime.now().isoformat(),
                'event_type': 'FILE_CREATED'
            }
            
            self.callback('FILE_CREATED', event_data)
            if self.db:
                self.db.insert_file_event(self.employee_id, event_data)
            
            if file_info['extension'].lower() in self.suspicious_extensions:
                alert_data = {
                    'employee_id': self.employee_id,
                    'file_path': event.src_path,
                    'file_name': os.path.basename(event.src_path),
                    'reason': f"Suspicious file type: {file_info['extension']}",
                    'severity': 'HIGH',
                    'timestamp': datetime.now().isoformat(),
                    'alert_type': 'SUSPICIOUS_FILE'
                }
                self.callback('SUSPICIOUS_FILE', alert_data)
                if self.db:
                    self.db.insert_security_alert(self.employee_id, alert_data)
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.deletion_count += 1
            
            now = datetime.now()
            if (now - self.last_reset).seconds > 60:
                self.deletion_count = 0
                self.last_reset = now
            
            event_data = {
                'employee_id': self.employee_id,
                'file_path': event.src_path,
                'file_name': os.path.basename(event.src_path),
                'timestamp': datetime.now().isoformat(),
                'event_type': 'FILE_DELETED'
            }
            
            self.callback('FILE_DELETED', event_data)
            if self.db:
                self.db.insert_file_event(self.employee_id, event_data)
            
            if self.deletion_count > 10:
                alert_data = {
                    'employee_id': self.employee_id,
                    'deletion_count': self.deletion_count,
                    'severity': 'CRITICAL',
                    'message': f'Mass file deletion detected: {self.deletion_count} files in last minute',
                    'timestamp': datetime.now().isoformat(),
                    'alert_type': 'MASS_DELETION'
                }
                self.callback('MASS_DELETION', alert_data)
                if self.db:
                    self.db.insert_security_alert(self.employee_id, alert_data)
    
    def on_modified(self, event):
        if not event.is_directory:
            current_hash = self.get_file_hash(event.src_path)
            if event.src_path in self.file_hashes:
                if current_hash and current_hash != self.file_hashes[event.src_path]:
                    event_data = {
                        'employee_id': self.employee_id,
                        'file_path': event.src_path,
                        'file_name': os.path.basename(event.src_path),
                        'hash_changed': True,
                        'timestamp': datetime.now().isoformat(),
                        'event_type': 'FILE_MODIFIED'
                    }
                    self.callback('FILE_MODIFIED', event_data)
                    if self.db:
                        self.db.insert_file_event(self.employee_id, event_data)
            
            if current_hash:
                self.file_hashes[event.src_path] = current_hash
    
    def get_file_info(self, file_path):
        try:
            stat = os.stat(file_path)
            return {
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'extension': os.path.splitext(file_path)[1]
            }
        except:
            return {'size': 0, 'extension': 'unknown'}
    
    def get_file_hash(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None


class FileMonitor:
    """Background file system monitor"""
    
    def __init__(self, employee_id, callback, db_connection=None):
        self.employee_id = employee_id
        self.callback = callback
        self.db = db_connection
        self.observer = None
        self.is_monitoring = False
        
    def start_monitoring(self, paths_to_monitor=None):
        if not WATCHDOG_AVAILABLE:
            print(f"[!] Watchdog not available for file monitoring")
            return False
        
        if paths_to_monitor is None:
            paths_to_monitor = [
                os.path.expanduser("~\\Desktop"),
                os.path.expanduser("~\\Documents"),
                os.path.expanduser("~\\Downloads"),
            ]
        
        self.monitored_paths = [p for p in paths_to_monitor if os.path.exists(p)]
        
        if not self.monitored_paths:
            print(f"[!] No valid paths to monitor for Employee {self.employee_id}")
            return False
        
        self.observer = Observer()
        event_handler = FileDetectionHandler(self.employee_id, self.callback, self.db)
        
        for path in self.monitored_paths:
            self.observer.schedule(event_handler, path, recursive=True)
            print(f"[✓] Monitoring: {path}")
        
        self.observer.start()
        self.is_monitoring = True
        print(f"[✓] File monitoring started for Employee {self.employee_id}")
        return True
    
    def stop_monitoring(self):
        if self.observer and self.is_monitoring:
            self.observer.stop()
            self.observer.join()
            self.is_monitoring = False
            print(f"[✓] File monitoring stopped for Employee {self.employee_id}")

# =====================================================
# EMPLOYEE MONITORING AGENT
# =====================================================

class SimpleEmployeeMonitoringAgent:
    """Employee monitoring agent with MySQL storage"""
    
    def __init__(self, employee_id, manager_config, db_connection=None):
        self.employee_id = str(employee_id)
        self.manager_config = manager_config
        self.model = None
        self.anomaly_model = None
        self.is_running = False
        self.data_buffer = deque(maxlen=100)
        
        self.db = db_connection
        
        self.file_monitor = None
        self.file_events = deque(maxlen=100)
        self.suspicious_file_count = 0
        
        self.load_models()
        self.init_file_monitoring()
        
        # Update session in database
        if self.db:
            self.db.update_employee_session(employee_id, is_active=True)
        
    def init_file_monitoring(self):
        if WATCHDOG_AVAILABLE:
            self.file_monitor = FileMonitor(self.employee_id, self.handle_file_event, self.db)
            print(f"[✓] File monitoring initialized for {self.employee_id}")
    
    def start_file_monitoring(self):
        if self.file_monitor:
            return self.file_monitor.start_monitoring()
        return False
    
    def stop_file_monitoring(self):
        if self.file_monitor:
            self.file_monitor.stop_monitoring()
    
    def handle_file_event(self, event_type, event_data):
        self.file_events.append(event_data)
        print(f"\n[FILE] {event_type}: {event_data.get('file_name', 'Unknown')}")
        
        if event_type == 'SUSPICIOUS_FILE':
            self.suspicious_file_count += 1
            self.send_security_alert(event_type, event_data)
        elif event_type == 'MASS_DELETION':
            self.send_security_alert(event_type, event_data)
        
        self.save_file_event_to_csv(event_type, event_data)
    
    def send_security_alert(self, alert_type, alert_data):
        current_time = datetime.now().isoformat()
        
        # Save to CSV
        security_file = os.path.join(self.manager_config.get('shared_folder', './manager_reports'), 
                                      f"security_alerts.csv")
        
        new_alert = {
            'timestamp': current_time,
            'employee_id': self.employee_id,
            'alert_type': alert_type,
            'severity': alert_data.get('severity', 'MEDIUM'),
            'file_name': alert_data.get('file_name', ''),
            'file_path': alert_data.get('file_path', ''),
            'details': alert_data.get('message', alert_data.get('reason', '')),
            'resolved': False
        }
        
        new_df = pd.DataFrame([new_alert])
        if os.path.exists(security_file):
            existing_df = pd.read_csv(security_file)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            updated_df = new_df
        
        updated_df.to_csv(security_file, index=False)
        
        print(f"\n{'='*50}")
        print(f"🔐 SECURITY ALERT - {alert_type}")
        print(f"{'='*50}")
        print(f"Employee: {self.employee_id}")
        print(f"Severity: {alert_data.get('severity', 'MEDIUM')}")
        print(f"File: {alert_data.get('file_name', 'Unknown')}")
    
    def save_file_event_to_csv(self, event_type, event_data):
        manager_folder = self.manager_config.get('shared_folder', './manager_reports')
        os.makedirs(manager_folder, exist_ok=True)
        
        file_events_csv = os.path.join(manager_folder, f"file_events.csv")
        
        new_event = {
            'timestamp': event_data.get('timestamp', datetime.now().isoformat()),
            'employee_id': self.employee_id,
            'event_type': event_type,
            'file_name': event_data.get('file_name', ''),
            'file_path': event_data.get('file_path', ''),
            'file_size': event_data.get('file_size', 0),
            'file_type': event_data.get('file_type', ''),
            'severity': event_data.get('severity', 'INFO')
        }
        
        new_df = pd.DataFrame([new_event])
        if os.path.exists(file_events_csv):
            existing_df = pd.read_csv(file_events_csv)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            updated_df = new_df
        
        updated_df.to_csv(file_events_csv, index=False)
    
    def load_models(self):
        try:
            if os.path.exists('productivity_model_enhanced.pkl') and os.path.exists('anomaly_model_enhanced.pkl'):
                self.model = joblib.load('productivity_model_enhanced.pkl')
                self.anomaly_model = joblib.load('anomaly_model_enhanced.pkl')
                print(f"[✓] Models loaded successfully")
            else:
                print(f"[!] Models not found. Training new models...")
                self.train_demo_models()
        except Exception as e:
            print(f"[!] Error loading models: {e}")
            self.train_demo_models()
            
    def train_demo_models(self):
        print("[*] Training models with proper validation...")
        np.random.seed(42)
        rows = 5000
        
        data = {
            "productive_app_usage": np.random.gamma(2, 30, rows),
            "unproductive_app_usage": np.random.gamma(1.5, 20, rows),
            "idle_time": np.random.exponential(15, rows),
            "app_switch_count": np.random.poisson(8, rows),
            "deleted_files": np.random.poisson(2, rows),
            "focus_score": np.random.beta(8, 3, rows),
            "task_completion_rate": np.random.beta(7, 3, rows)
        }
        
        df = pd.DataFrame(data)
        
        # Cap values
        df['productive_app_usage'] = np.clip(df['productive_app_usage'], 10, 300)
        df['unproductive_app_usage'] = np.clip(df['unproductive_app_usage'], 0, 200)
        df['idle_time'] = np.clip(df['idle_time'], 0, 120)
        df['app_switch_count'] = np.clip(df['app_switch_count'], 1, 30)
        df['deleted_files'] = np.clip(df['deleted_files'], 0, 15)
        
        df["productive_ratio"] = df["productive_app_usage"] / (df["productive_app_usage"] + df["unproductive_app_usage"] + 1)
        df["productivity_label"] = np.where(df["productive_ratio"] > 0.55, 1, 0)
        
        features = ["productive_app_usage", "unproductive_app_usage", "idle_time", 
                   "app_switch_count", "deleted_files", "focus_score", 
                   "task_completion_rate", "productive_ratio"]
        
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
        print(f"[✓] Models trained and saved (Test Accuracy: {accuracy:.2%})")
        
    def simulate_metrics(self):
        productive_time = np.random.randint(20, 250)
        unproductive_time = np.random.randint(0, 180)
        idle_time = np.random.randint(0, 120)
        app_switches = np.random.randint(1, 20)
        deleted_files = np.random.randint(0, 10) + self.suspicious_file_count
        
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
        
        metrics = {
            'productive_time': productive_time,
            'unproductive_time': unproductive_time,
            'idle_time': idle_time,
            'app_switches': app_switches,
            'deleted_files': deleted_files,
            'focus_score': focus_score,
            'task_completion_rate': task_completion,
            'productive_ratio': productive_ratio,
            'cpu_usage': np.random.randint(10, 90),
            'memory_usage': np.random.randint(20, 80)
        }
        
        return metrics
    
    def analyze_behavior(self, metrics):
        features = pd.DataFrame([[
            metrics['productive_time'],
            metrics['unproductive_time'],
            metrics['idle_time'],
            metrics['app_switches'],
            metrics['deleted_files'],
            metrics['focus_score'],
            metrics['task_completion_rate'],
            metrics['productive_ratio']
        ]], columns=['productive_app_usage', 'unproductive_app_usage', 'idle_time',
                    'app_switch_count', 'deleted_files', 'focus_score',
                    'task_completion_rate', 'productive_ratio'])
        
        productivity_pred = self.model.predict(features)[0]
        productivity_proba = self.model.predict_proba(features)[0][1]
        
        anomaly_pred = self.anomaly_model.predict(features)[0]
        anomaly_score = self.anomaly_model.decision_function(features)[0]
        
        productivity_score = metrics['productive_ratio']
        
        risk_score = 0
        risk_factors = []
        
        if metrics['deleted_files'] > 5:
            risk_score += 30
            risk_factors.append("excessive file deletions")
        if metrics['idle_time'] > 60:
            risk_score += 25
            risk_factors.append("high idle time")
        if metrics['app_switches'] > 15:
            risk_score += 20
            risk_factors.append("frequent app switching")
        if productivity_score < 0.4:
            risk_score += 30
            risk_factors.append("low productivity")
        if metrics['focus_score'] < 0.5:
            risk_score += 15
            risk_factors.append("low focus score")
        
        if self.suspicious_file_count > 0:
            risk_score += self.suspicious_file_count * 10
            risk_factors.append(f"{self.suspicious_file_count} suspicious file(s) detected")
            
        if risk_score >= 70:
            risk_level = "CRITICAL"
        elif risk_score >= 50:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            'productivity_prediction': 'Productive' if productivity_pred == 1 else 'Unproductive',
            'productivity_confidence': float(productivity_proba),
            'productivity_score': float(round(productivity_score, 3)),
            'anomaly_detected': bool(anomaly_pred == -1),
            'anomaly_score': float(round(anomaly_score, 3)),
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'metrics': metrics,
            'suspicious_files': self.suspicious_file_count
        }
    
    def send_report_to_manager(self, analysis, report_type='regular'):
        current_time = datetime.now().isoformat()
        
        # Save to CSV
        self.export_to_csv(analysis, report_type, current_time)
        
        # Save to MySQL
        if self.db:
            report_data = {
                'timestamp': current_time,
                'report_type': report_type,
                'productive_time_min': analysis['metrics']['productive_time'],
                'unproductive_time_min': analysis['metrics']['unproductive_time'],
                'idle_time_min': analysis['metrics']['idle_time'],
                'app_switches': analysis['metrics']['app_switches'],
                'deleted_files': analysis['metrics']['deleted_files'],
                'focus_score': analysis['metrics']['focus_score'],
                'task_completion_rate': analysis['metrics']['task_completion_rate'],
                'productive_ratio': analysis['metrics']['productive_ratio'],
                'productivity_prediction': analysis['productivity_prediction'],
                'productivity_confidence': analysis['productivity_confidence'],
                'productivity_score': analysis['productivity_score'],
                'anomaly_detected': analysis['anomaly_detected'],
                'anomaly_score': analysis['anomaly_score'],
                'risk_level': analysis['risk_level'],
                'risk_score': analysis['risk_score'],
                'risk_factors': ', '.join(analysis['risk_factors']),
                'suspicious_files': analysis.get('suspicious_files', 0)
            }
            self.db.insert_employee_report(self.employee_id, report_data)
        
        # Save to JSON
        report = {
            'report_type': report_type,
            'timestamp': current_time,
            'employee_id': self.employee_id,
            'analysis': {
                'productivity_prediction': analysis['productivity_prediction'],
                'productivity_confidence': analysis['productivity_confidence'],
                'productivity_score': analysis['productivity_score'],
                'anomaly_detected': analysis['anomaly_detected'],
                'anomaly_score': analysis['anomaly_score'],
                'risk_level': analysis['risk_level'],
                'risk_score': analysis['risk_score'],
                'risk_factors': analysis['risk_factors'],
                'metrics': analysis['metrics'],
                'suspicious_files': analysis.get('suspicious_files', 0)
            }
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
        
        self.print_report(analysis, report_type)
        return True
    
    def export_to_csv(self, analysis, report_type, timestamp):
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
            'deleted_files': analysis['metrics']['deleted_files'],
            'focus_score': analysis['metrics']['focus_score'],
            'task_completion_rate': analysis['metrics']['task_completion_rate'],
            'productive_ratio': analysis['metrics']['productive_ratio'],
            'productivity_prediction': analysis['productivity_prediction'],
            'productivity_confidence': analysis['productivity_confidence'],
            'productivity_score': analysis['productivity_score'],
            'anomaly_detected': analysis['anomaly_detected'],
            'anomaly_score': analysis['anomaly_score'],
            'risk_level': analysis['risk_level'],
            'risk_score': analysis['risk_score'],
            'risk_factors': ', '.join(analysis['risk_factors']),
            'suspicious_files': analysis.get('suspicious_files', 0)
        }
        
        new_df = pd.DataFrame([new_row])
        
        if os.path.exists(csv_file):
            existing_df = pd.read_csv(csv_file)
            existing_df['employee_id'] = existing_df['employee_id'].astype(str)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            updated_df = new_df
        
        updated_df.to_csv(csv_file, index=False)
    
    def print_report(self, analysis, report_type):
        if report_type == 'alert':
            print(f"\n{'='*50}")
            print(f"🚨 ALERT - Employee {self.employee_id}")
            print(f"{'='*50}")
            if analysis.get('suspicious_files', 0) > 0:
                print(f"⚠️ Suspicious Files Detected: {analysis.get('suspicious_files', 0)}")
        else:
            print(f"\n   {self.employee_id}: {analysis['productivity_prediction']} ({analysis['productivity_score']:.1%}) | Risk: {analysis['risk_level']}")
            if analysis.get('suspicious_files', 0) > 0:
                print(f"   ⚠️ Suspicious Files: {analysis.get('suspicious_files', 0)}")
    
    def start_monitoring(self, interval_minutes=5):
        self.is_running = True
        self.start_file_monitoring()
        
        print(f"\n[✓] Started monitoring for Employee {self.employee_id}")
        print(f"[*] Analysis interval: Every {interval_minutes} minutes")
        print(f"[*] File monitoring: ACTIVE")
        print(f"[*] Reports saved to: MySQL database and ./manager_reports/")
        print(f"[*] Press Ctrl+C to stop monitoring\n")
        
        report_count = 0
        
        try:
            while self.is_running:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Analyzing...")
                metrics = self.simulate_metrics()
                analysis = self.analyze_behavior(metrics)
                
                if analysis['risk_level'] in ['HIGH', 'CRITICAL'] or analysis['anomaly_detected']:
                    self.send_report_to_manager(analysis, report_type='alert')
                else:
                    report_count += 1
                    if report_count % 3 == 0:
                        self.send_report_to_manager(analysis, report_type='regular')
                    else:
                        print(f"   {self.employee_id}: {analysis['productivity_prediction']} ({analysis['productivity_score']:.1%})")
                
                self.data_buffer.append(analysis)
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print(f"\n[!] Stopping monitoring for Employee {self.employee_id}")
            self.is_running = False
            self.stop_file_monitoring()
            if self.db:
                self.db.update_employee_session(self.employee_id, is_active=False)
    
    def stop_monitoring(self):
        self.is_running = False
        self.stop_file_monitoring()
        if self.db:
            self.db.update_employee_session(self.employee_id, is_active=False)
        print(f"\n[✓] Monitoring stopped for Employee {self.employee_id}")

# =====================================================
# MANAGER DASHBOARD WITH EXPORT
# =====================================================

class ManagerDashboard:
    """Manager dashboard with MySQL integration and export"""
    
    def __init__(self, shared_folder='./manager_reports', db_connection=None):
        self.shared_folder = shared_folder
        self.db = db_connection
        
    def get_all_data(self):
        """Get all reports from MySQL or CSV"""
        if self.db:
            try:
                results = self.db.get_all_reports(1000)
                if results:
                    df = pd.DataFrame(results)
                    df['employee_id'] = df['employee_id'].astype(str)
                    return df
            except:
                pass
        
        # Fallback to CSV
        csv_file = os.path.join(self.shared_folder, 'all_employee_reports.csv')
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df['employee_id'] = df['employee_id'].astype(str)
            return df
        return pd.DataFrame()
    
    def get_security_alerts(self):
        """Get security alerts from MySQL or CSV"""
        if self.db:
            try:
                self.db.cursor.execute("SELECT * FROM security_alerts ORDER BY timestamp DESC LIMIT 100")
                results = self.db.cursor.fetchall()
                if results:
                    df = pd.DataFrame(results)
                    df['employee_id'] = df['employee_id'].astype(str)
                    return df
            except:
                pass
        
        # Fallback to CSV
        security_file = os.path.join(self.shared_folder, 'security_alerts.csv')
        if os.path.exists(security_file):
            df = pd.read_csv(security_file)
            df['employee_id'] = df['employee_id'].astype(str)
            return df
        return pd.DataFrame()
    
    def get_file_events(self):
        """Get file events from MySQL or CSV"""
        if self.db:
            try:
                self.db.cursor.execute("SELECT * FROM file_events ORDER BY timestamp DESC LIMIT 100")
                results = self.db.cursor.fetchall()
                if results:
                    df = pd.DataFrame(results)
                    df['employee_id'] = df['employee_id'].astype(str)
                    return df
            except:
                pass
        
        # Fallback to CSV
        file_events_file = os.path.join(self.shared_folder, 'file_events.csv')
        if os.path.exists(file_events_file):
            df = pd.read_csv(file_events_file)
            df['employee_id'] = df['employee_id'].astype(str)
            return df
        return pd.DataFrame()
    
    def export_comprehensive_csv_report(self):
        """Export all reports to CSV with download"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_folder = f"export_{timestamp}"
        os.makedirs(export_folder, exist_ok=True)
        
        all_data = self.get_all_data()
        security_alerts = self.get_security_alerts()
        file_events = self.get_file_events()
        
        # Export all reports
        if not all_data.empty:
            all_data.to_csv(os.path.join(export_folder, '1_all_reports.csv'), index=False)
            print(f"✅ 1_all_reports.csv - All reports")
        
        # Export summary
        if not all_data.empty:
            summary = self.get_employee_summary(all_data)
            if not summary.empty:
                summary.to_csv(os.path.join(export_folder, '2_employee_summary.csv'), index=False)
                print(f"✅ 2_employee_summary.csv - Employee summary")
        
        # Export security alerts
        if not security_alerts.empty:
            security_alerts.to_csv(os.path.join(export_folder, '3_security_alerts.csv'), index=False)
            print(f"✅ 3_security_alerts.csv - Security alerts")
        
        # Export file events
        if not file_events.empty:
            file_events.to_csv(os.path.join(export_folder, '4_file_events.csv'), index=False)
            print(f"✅ 4_file_events.csv - File events")
        
        # Export risk analysis
        if not all_data.empty:
            risk_report = self.get_risk_report(all_data)
            if not risk_report.empty:
                risk_report.to_csv(os.path.join(export_folder, '5_risk_analysis.csv'), index=False)
                print(f"✅ 5_risk_analysis.csv - Risk analysis")
        
        # Export anomalies
        if not all_data.empty and 'anomaly_detected' in all_data.columns:
            anomalies = all_data[all_data['anomaly_detected'] == True]
            if not anomalies.empty:
                anomalies.to_csv(os.path.join(export_folder, '6_anomalies.csv'), index=False)
                print(f"✅ 6_anomalies.csv - Anomalies")
        
        print(f"\n✅ All CSV reports exported to folder: {export_folder}/")
        
        # Create zip for download
        self.create_download_zip(export_folder, timestamp)
        
        return export_folder
    
    def get_employee_summary(self, all_data):
        """Get employee summary"""
        if all_data.empty:
            return pd.DataFrame()
        
        summary = all_data.groupby('employee_id').agg({
            'productivity_score': ['mean', 'min', 'max', 'count'],
            'risk_score': 'mean',
            'anomaly_detected': 'sum'
        }).round(2)
        
        summary.columns = ['Avg_Productivity', 'Min_Productivity', 'Max_Productivity', 
                          'Report_Count', 'Avg_Risk', 'Anomalies']
        summary = summary.reset_index()
        
        # Add rating
        summary['Rating'] = summary['Avg_Productivity'].apply(
            lambda x: 'Excellent' if x >= 0.7 else 'Good' if x >= 0.5 else 'Average' if x >= 0.3 else 'Poor'
        )
        
        return summary
    
    def get_risk_report(self, all_data):
        """Get risk analysis report"""
        if all_data.empty:
            return pd.DataFrame()
        
        risk_report = all_data.groupby('employee_id').agg({
            'risk_level': lambda x: x.mode()[0] if len(x) > 0 else 'LOW',
            'risk_score': 'mean',
            'suspicious_files': 'sum'
        }).reset_index()
        
        risk_report.columns = ['employee_id', 'Primary_Risk', 'Avg_Risk_Score', 'Total_Suspicious_Files']
        
        return risk_report
    
    def create_download_zip(self, export_folder, timestamp):
        """Create zip file for download"""
        zip_filename = f"employee_reports_{timestamp}.zip"
        
        print(f"\n📦 Creating zip file: {zip_filename}")
        
        try:
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(export_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(export_folder))
                        zipf.write(file_path, arcname)
                
                # Add manager_reports folder if exists
                if os.path.exists(self.shared_folder):
                    for file in os.listdir(self.shared_folder):
                        if file.endswith('.csv'):
                            file_path = os.path.join(self.shared_folder, file)
                            zipf.write(file_path, f"manager_reports/{file}")
            
            zip_path = os.path.abspath(zip_filename)
            print(f"✅ Zip file created: {zip_path}")
            
            # Open folder
            try:
                if platform.system() == 'Windows':
                    os.startfile(os.path.dirname(zip_path))
                elif platform.system() == 'Darwin':
                    subprocess.run(['open', os.path.dirname(zip_path)])
                else:
                    subprocess.run(['xdg-open', os.path.dirname(zip_path)])
                print(f"📂 Folder opened with zip file")
            except:
                print(f"📁 Zip file location: {zip_path}")
                
        except Exception as e:
            print(f"⚠️ Error creating zip: {e}")
    
    def display_dashboard(self):
        """Display the manager dashboard"""
        print("\n" + "="*60)
        print("👔 MANAGER DASHBOARD - TEAM PERFORMANCE")
        print("="*60)
        
        all_data = self.get_all_data()
        security_alerts = self.get_security_alerts()
        
        if all_data.empty:
            print("[!] No reports available. Waiting for employee agents...")
            return
        
        # Ensure required columns exist
        if 'suspicious_files' not in all_data.columns:
            all_data['suspicious_files'] = 0
        if 'anomaly_detected' not in all_data.columns:
            all_data['anomaly_detected'] = False
        
        latest_reports = all_data.sort_values('timestamp').groupby('employee_id').last().reset_index()
        
        print(f"\n📊 Team Summary:")
        print(f"   Total Employees: {len(latest_reports)}")
        print(f"   Average Productivity: {latest_reports['productivity_score'].mean():.1%}")
        high_risk = len(latest_reports[latest_reports['risk_level'].isin(['HIGH', 'CRITICAL'])])
        print(f"   High Risk Employees: {high_risk}")
        print(f"   Total Anomalies Detected: {latest_reports['anomaly_detected'].sum()}")
        
        if not security_alerts.empty:
            critical_security = len(security_alerts[security_alerts['severity'] == 'CRITICAL'])
            print(f"   🔐 Security Alerts: {len(security_alerts)} (Critical: {critical_security})")
        
        # Get active employees from MySQL
        if self.db:
            active_employees = self.db.get_active_employees()
            if active_employees:
                print(f"   🟢 Currently Active: {len(active_employees)} employees")
                print(f"   Active IDs: {', '.join(active_employees)}")
        
        print(f"\n📈 Employee Status:")
        print("-" * 80)
        
        for _, emp in latest_reports.iterrows():
            icon = "🔴" if emp['risk_level'] in ['HIGH', 'CRITICAL'] else "🟡" if emp['risk_level'] == 'MEDIUM' else "🟢"
            anomaly_mark = "⚠️" if emp['anomaly_detected'] else "✅"
            security_mark = "🔐" if emp.get('suspicious_files', 0) > 0 else ""
            
            # Check if employee is currently active
            active_mark = "🟢" if self.db and emp['employee_id'] in self.db.get_active_employees() else "⚫"
            
            print(f"{icon} {emp['employee_id']}: {emp['productivity_prediction']} ({emp['productivity_score']:.1%}) | "
                  f"Risk: {emp['risk_level']} | {anomaly_mark} {security_mark} {active_mark}")
        
        critical = latest_reports[latest_reports['risk_level'].isin(['HIGH', 'CRITICAL'])]
        if not critical.empty:
            print("\n" + "="*60)
            print("🚨 CRITICAL ALERTS")
            print("="*60)
            for _, emp in critical.iterrows():
                print(f"⚠️ Employee {emp['employee_id']} - {emp['risk_level']} RISK")
                print(f"   Productivity: {emp['productivity_score']:.1%}")
                print(f"   Risk Score: {emp['risk_score']}/100")
                if emp.get('suspicious_files', 0) > 0:
                    print(f"   🔐 Suspicious Files: {emp.get('suspicious_files', 0)}")
                print()

# =====================================================
# MODEL TRAINING FUNCTIONS
# =====================================================

def train_and_validate_model():
    """Train model with proper train/test split and show real accuracy"""
    print("\n" + "="*60)
    print("📊 MODEL TRAINING & VALIDATION")
    print("="*60)
    
    np.random.seed(42)
    
    # Generate more realistic training data
    n_samples = 5000
    
    # Create realistic patterns
    data = {
        "productive_app_usage": np.random.gamma(2, 30, n_samples),
        "unproductive_app_usage": np.random.gamma(1.5, 20, n_samples),
        "idle_time": np.random.exponential(15, n_samples),
        "app_switch_count": np.random.poisson(8, n_samples),
        "deleted_files": np.random.poisson(2, n_samples),
        "focus_score": np.random.beta(8, 3, n_samples),
        "task_completion_rate": np.random.beta(7, 3, n_samples)
    }
    
    df = pd.DataFrame(data)
    
    # Cap values to realistic ranges
    df['productive_app_usage'] = np.clip(df['productive_app_usage'], 10, 300)
    df['unproductive_app_usage'] = np.clip(df['unproductive_app_usage'], 0, 200)
    df['idle_time'] = np.clip(df['idle_time'], 0, 120)
    df['app_switch_count'] = np.clip(df['app_switch_count'], 1, 30)
    df['deleted_files'] = np.clip(df['deleted_files'], 0, 15)
    
    # Calculate productive ratio
    df["productive_ratio"] = df["productive_app_usage"] / (df["productive_app_usage"] + df["unproductive_app_usage"] + 1)
    
    # Create realistic productivity labels based on multiple factors
    df["productivity_label"] = (
        (df["productive_ratio"] > 0.55) & 
        (df["focus_score"] > 0.6) & 
        (df["task_completion_rate"] > 0.65)
    ).astype(int)
    
    # Add some noise (mislabeled samples)
    noise_idx = np.random.choice(df.index, size=int(0.05 * len(df)), replace=False)
    df.loc[noise_idx, "productivity_label"] = 1 - df.loc[noise_idx, "productivity_label"]
    
    features = ["productive_app_usage", "unproductive_app_usage", "idle_time", 
                "app_switch_count", "deleted_files", "focus_score", 
                "task_completion_rate", "productive_ratio"]
    
    X = df[features]
    y = df["productivity_label"]
    
    # SPLIT INTO TRAIN (70%), VALIDATION (15%), TEST (15%)
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.176, random_state=42, stratify=y_temp)
    
    print(f"\n📊 Dataset Split:")
    print(f"   Training samples: {len(X_train)} (70%)")
    print(f"   Validation samples: {len(X_val)} (15%)")
    print(f"   Test samples: {len(X_test)} (15%)")
    print(f"   Class balance: {y.sum()/len(y):.1%} productive, {(1-y.sum()/len(y)):.1%} unproductive")
    
    # Train Random Forest
    print("\n[*] Training Random Forest model...")
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
    print("[*] Training Anomaly Detection model...")
    iso_forest = IsolationForest(contamination=0.05, random_state=42)
    iso_forest.fit(X_train)
    
    # Evaluate on ALL sets
    print("\n" + "="*60)
    print("📈 MODEL PERFORMANCE METRICS")
    print("="*60)
    
    # Training accuracy
    y_train_pred = rf_model.predict(X_train)
    train_acc = accuracy_score(y_train, y_train_pred)
    
    # Validation accuracy
    y_val_pred = rf_model.predict(X_val)
    val_acc = accuracy_score(y_val, y_val_pred)
    
    # Test accuracy (TRUE unseen data)
    y_test_pred = rf_model.predict(X_test)
    test_acc = accuracy_score(y_test, y_test_pred)
    
    print(f"\n🎯 Accuracy Scores:")
    print(f"   Training Accuracy: {train_acc:.2%}")
    print(f"   Validation Accuracy: {val_acc:.2%}")
    print(f"   Test Accuracy (Unseen Data): {test_acc:.2%} ⭐")
    
    # Calculate additional metrics
    precision = precision_score(y_test, y_test_pred)
    recall = recall_score(y_test, y_test_pred)
    f1 = f1_score(y_test, y_test_pred)
    
    print(f"\n📊 Additional Metrics (Test Data):")
    print(f"   Precision: {precision:.2%}")
    print(f"   Recall: {recall:.2%}")
    print(f"   F1-Score: {f1:.2%}")
    
    # Check for overfitting
    overfit_gap = train_acc - test_acc
    if overfit_gap > 0.1:
        print(f"\n⚠️  WARNING: Possible overfitting detected! (Gap: {overfit_gap:.1%})")
        print("   Consider: more data, regularization, or simpler model")
    else:
        print(f"\n✅ Model generalizes well! (Train-Test gap: {overfit_gap:.1%})")
    
    # Detailed classification report for test data
    print("\n📋 Detailed Classification Report (Test Data):")
    print("-" * 40)
    print(classification_report(y_test, y_test_pred, 
                                target_names=['Unproductive', 'Productive']))
    
    # Confusion Matrix
    cm = confusion_matrix(y_test, y_test_pred)
    print("\n📊 Confusion Matrix:")
    print(f"   True Negatives: {cm[0,0]} | False Positives: {cm[0,1]}")
    print(f"   False Negatives: {cm[1,0]} | True Positives: {cm[1,1]}")
    
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
        'samples_used': len(X_train) + len(X_val) + len(X_test),
        'confusion_matrix': cm.tolist()
    }
    
    with open('model_training_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Models saved successfully!")
    print(f"📁 Training results saved to: model_training_results.json")
    
    return test_acc

def test_on_real_data():
    """Test model on user-provided CSV data"""
    print("\n" + "="*60)
    print("🧪 TEST MODEL ON YOUR OWN DATA")
    print("="*60)
    
    # Load the trained model
    try:
        model = joblib.load('productivity_model_enhanced.pkl')
        anomaly_model = joblib.load('anomaly_model_enhanced.pkl')
        print("✅ Models loaded successfully")
    except Exception as e:
        print(f"❌ No trained model found. Please train first (Option 5)")
        print(f"   Error: {e}")
        return
    
    csv_path = input("\n📁 Enter path to your CSV file: ").strip()
    
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return
    
    try:
        test_data = pd.read_csv(csv_path)
        print(f"✅ Loaded {len(test_data)} records")
        
        # Required columns
        required_cols = ["productive_app_usage", "unproductive_app_usage", "idle_time",
                        "app_switch_count", "deleted_files", "focus_score",
                        "task_completion_rate"]
        
        missing_cols = [col for col in required_cols if col not in test_data.columns]
        if missing_cols:
            print(f"❌ Missing columns: {missing_cols}")
            print("Required columns:", required_cols)
            return
        
        # Calculate productive ratio
        test_data["productive_ratio"] = test_data["productive_app_usage"] / (
            test_data["productive_app_usage"] + test_data["unproductive_app_usage"] + 1
        )
        
        features = required_cols + ["productive_ratio"]
        X_test = test_data[features]
        
        # Make predictions
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)[:, 1]
        anomalies = anomaly_model.predict(X_test)
        
        # Add results to dataframe
        test_data['productivity_prediction'] = ['Productive' if p == 1 else 'Unproductive' for p in predictions]
        test_data['productivity_confidence'] = probabilities
        test_data['anomaly'] = ['⚠️ Anomaly' if a == -1 else '✅ Normal' for a in anomalies]
        
        print(f"\n📊 Prediction Summary:")
        print(f"   Productive: {(predictions == 1).sum()} employees ({(predictions == 1).mean():.1%})")
        print(f"   Unproductive: {(predictions == 0).sum()} employees ({(predictions == 0).mean():.1%})")
        print(f"   Anomalies Detected: {(anomalies == -1).sum()}")
        
        # Calculate metrics if ground truth exists
        if 'productivity_label' in test_data.columns:
            accuracy = accuracy_score(test_data['productivity_label'], predictions)
            precision = precision_score(test_data['productivity_label'], predictions)
            recall = recall_score(test_data['productivity_label'], predictions)
            f1 = f1_score(test_data['productivity_label'], predictions)
            
            print(f"\n📊 Model Performance on Your Data:")
            print(f"   ✅ Accuracy: {accuracy:.2%}")
            print(f"   ✅ Precision: {precision:.2%}")
            print(f"   ✅ Recall: {recall:.2%}")
            print(f"   ✅ F1-Score: {f1:.2%}")
            
            print(f"\n📋 Classification Report:")
            print(classification_report(test_data['productivity_label'], predictions, 
                                      target_names=['Unproductive', 'Productive']))
        else:
            print(f"\n💡 Tip: Add a 'productivity_label' column (0/1) to see accuracy metrics")
        
        # Save results
        output_path = csv_path.replace('.csv', '_predictions.csv')
        test_data.to_csv(output_path, index=False)
        print(f"\n✅ Results saved to: {output_path}")
        
        # Show sample predictions
        print(f"\n📋 Sample Predictions (first 10 rows):")
        display_cols = ['productive_app_usage', 'unproductive_app_usage', 
                       'productivity_prediction', 'productivity_confidence', 'anomaly']
        print(test_data[display_cols].head(10).to_string())
        
    except Exception as e:
        print(f"❌ Error processing file: {e}")

def compare_models():
    """Compare different models to find the best one"""
    print("\n" + "="*60)
    print("🤖 MODEL COMPARISON & SELECTION")
    print("="*60)
    
    np.random.seed(42)
    
    # Generate data
    n_samples = 3000
    data = {
        "productive_app_usage": np.random.gamma(2, 30, n_samples),
        "unproductive_app_usage": np.random.gamma(1.5, 20, n_samples),
        "idle_time": np.random.exponential(15, n_samples),
        "app_switch_count": np.random.poisson(8, n_samples),
        "deleted_files": np.random.poisson(2, n_samples),
        "focus_score": np.random.beta(8, 3, n_samples),
        "task_completion_rate": np.random.beta(7, 3, n_samples)
    }
    
    df = pd.DataFrame(data)
    df["productive_ratio"] = df["productive_app_usage"] / (df["productive_app_usage"] + df["unproductive_app_usage"] + 1)
    df["productivity_label"] = ((df["productive_ratio"] > 0.55) & (df["focus_score"] > 0.6)).astype(int)
    
    features = ["productive_app_usage", "unproductive_app_usage", "idle_time", 
                "app_switch_count", "deleted_files", "focus_score", 
                "task_completion_rate", "productive_ratio"]
    
    X = df[features]
    y = df["productivity_label"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    models = {
        'Random Forest': RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
        'Gradient Boosting': GradientBoostingClassifier(n_estimators=100, random_state=42),
        'Logistic Regression': LogisticRegression(random_state=42, max_iter=1000),
        'K-Neighbors': KNeighborsClassifier(n_neighbors=5)
    }
    
    results = []
    
    print("\n[*] Training and comparing models...\n")
    
    for name, model in models.items():
        # Train
        start_time = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - start_time
        
        # Predict
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        
        # Cross-validation score
        cv_scores = cross_val_score(model, X_train, y_train, cv=5)
        
        results.append({
            'Model': name,
            'Accuracy': f"{accuracy:.2%}",
            'Precision': f"{precision:.2%}",
            'Recall': f"{recall:.2%}",
            'F1-Score': f"{f1:.2%}",
            'CV_Mean': f"{cv_scores.mean():.2%}",
            'CV_Std': f"{cv_scores.std():.2%}",
            'Train_Time': f"{train_time:.2f}s",
            'Status': '✅' if accuracy > 0.7 else '⚠️' if accuracy > 0.6 else '❌'
        })
        
        print(f"{results[-1]['Status']} {name}: {accuracy:.2%} (CV: {cv_scores.mean():.2%} ± {cv_scores.std():.2%})")
    
    results_df = pd.DataFrame(results)
    
    print(f"\n{'='*60}")
    print("📊 COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(results_df.to_string(index=False))
    
    best_model = results_df.loc[results_df['Accuracy'].idxmax()]
    print(f"\n🏆 Best Model: {best_model['Model']} with {best_model['Accuracy']} accuracy")
    
    # Save comparison
    results_df.to_csv('model_comparison.csv', index=False)
    print(f"\n✅ Model comparison saved to: model_comparison.csv")
    
    return results_df

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
        print("\n❌ No training results found. Please train a model first (Option 5)")

# =====================================================
# DOCUMENTATION GENERATION
# =====================================================

def run_doc_generation(db_connection=None):
    """Generate documentation and reports with auto-download to PC"""
    print("\n" + "="*60)
    print("📄 DOCUMENTATION & REPORT GENERATION")
    print("="*60)
    
    dashboard = ManagerDashboard(db_connection=db_connection)
    
    print("\n[*] Generating comprehensive documentation...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_folder = f"documentation_{timestamp}"
    os.makedirs(doc_folder, exist_ok=True)
    
    all_data = dashboard.get_all_data()
    security_alerts = dashboard.get_security_alerts()
    file_events = dashboard.get_file_events()
    
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
    Security Alerts: {len(security_alerts) if not security_alerts.empty else 0}
    File Events: {len(file_events) if not file_events.empty else 0}
    
    PERFORMANCE SUMMARY
    ------------------
    Average Productivity Score: {all_data['productivity_score'].mean():.1%} if not all_data.empty else 'N/A'
    High Risk Employees: {len(all_data[all_data['risk_level'].isin(['HIGH', 'CRITICAL'])]) if not all_data.empty else 0}
    Total Anomalies: {all_data['anomaly_detected'].sum() if not all_data.empty else 0}
    """
    
    if not all_data.empty and 'suspicious_files' in all_data.columns:
        summary_text += f"Total Suspicious Files: {all_data['suspicious_files'].sum()}\n"
    
    summary_text += """
    FILES GENERATED
    --------------
    - CSV Reports in export_* folders
    - Security alerts in security_alerts.csv
    - File events in file_events.csv
    - Individual employee reports
    """
    
    with open(os.path.join(doc_folder, "system_report.txt"), 'w') as f:
        f.write(summary_text)
    
    print(f"✅ System report saved to {doc_folder}/system_report.txt")
    
    # Export all CSV reports
    dashboard.export_comprehensive_csv_report()
    
    # Also save model results if available
    if os.path.exists('model_training_results.json'):
        shutil.copy('model_training_results.json', doc_folder)
        print(f"✅ Model training results copied")
    
    if os.path.exists('model_comparison.csv'):
        shutil.copy('model_comparison.csv', doc_folder)
        print(f"✅ Model comparison results copied")
    
    print(f"\n✅ Documentation generated in folder: {doc_folder}/")
    
    # Create zip for download
    print("\n" + "="*60)
    print("📥 PREPARING REPORTS FOR DOWNLOAD")
    print("="*60)
    
    try:
        zip_filename = f"employee_monitoring_reports_{timestamp}.zip"
        print(f"\n📦 Creating zip file: {zip_filename}")
        
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add doc folder
            for root, dirs, files in os.walk(doc_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(doc_folder))
                    zipf.write(file_path, arcname)
            
            # Add export folders
            export_folders = [f for f in os.listdir('.') if f.startswith('export_') and os.path.isdir(f)]
            for folder in export_folders:
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.dirname(folder))
                        zipf.write(file_path, arcname)
            
            # Add manager reports
            if os.path.exists('./manager_reports'):
                for file in os.listdir('./manager_reports'):
                    if file.endswith('.csv'):
                        file_path = os.path.join('./manager_reports', file)
                        zipf.write(file_path, f"manager_reports/{file}")
            
            # Add JSON files
            json_files = [f for f in os.listdir('.') if f.endswith('.json')]
            for json_file in json_files:
                zipf.write(json_file)
        
        zip_path = os.path.abspath(zip_filename)
        print(f"✅ Zip file created: {zip_path}")
        
        # Open folder
        try:
            if platform.system() == 'Windows':
                os.startfile(os.path.dirname(zip_path))
            elif platform.system() == 'Darwin':
                subprocess.run(['open', os.path.dirname(zip_path)])
            else:
                subprocess.run(['xdg-open', os.path.dirname(zip_path)])
            print(f"\n📂 Folder opened with your reports!")
        except:
            print(f"\n📁 Reports location: {os.path.dirname(zip_path)}")
            
    except Exception as e:
        print(f"\n⚠️ Could not create zip file: {e}")
        print(f"📁 Reports are available in: {doc_folder}/")
    
    print("\n[✓] Documentation generation complete!")
    time.sleep(3)

# =====================================================
# MAIN FUNCTIONS
# =====================================================

def setup_mysql_connection():
    """Setup MySQL connection with user input"""
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
        print("\n✅ MySQL connection established!")
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
    agent = SimpleEmployeeMonitoringAgent(employee_id, config, db_connection)
    
    if interval == 0:
        print("\n[*] Running single analysis...")
        metrics = agent.simulate_metrics()
        analysis = agent.analyze_behavior(metrics)
        agent.send_report_to_manager(analysis, 'regular')
        print(f"\n✅ Analysis complete for {employee_id}")
        if db_connection:
            db_connection.update_employee_session(employee_id, is_active=False)
    else:
        print(f"\n⚠️  Monitoring started for {interval} minute intervals")
        print("🔐 File detection is ACTIVE")
        print("💡 Press Ctrl+C to stop and return to menu\n")
        agent.start_monitoring(interval_minutes=interval)
    
    print("\n[✓] Returning to main menu...")
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
        print("   3. View Employee Details")
        print("   4. View Security Alerts")
        print("   5. Return to Main Menu")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            continue
        elif choice == '2':
            dashboard.export_comprehensive_csv_report()
            input("\nPress Enter to continue...")
        elif choice == '3':
            emp_id = input("Enter Employee ID: ").strip()
            emp_id = str(emp_id)
            
            if db_connection:
                history = db_connection.get_employee_history(emp_id)
                if history:
                    df = pd.DataFrame(history)
                    print(f"\n📊 Employee {emp_id} Details:")
                    print(f"Total Reports: {len(df)}")
                    print(df[['timestamp', 'productivity_prediction', 'productivity_score', 
                             'risk_level', 'anomaly_detected']].to_string())
                else:
                    print(f"❌ No data found for Employee {emp_id}")
            else:
                print("❌ MySQL connection not available")
            input("\nPress Enter to continue...")
        elif choice == '4':
            security_alerts = dashboard.get_security_alerts()
            if not security_alerts.empty:
                print("\n🔐 SECURITY ALERTS:")
                print(security_alerts[['timestamp', 'employee_id', 'alert_type', 
                                      'severity', 'details']].to_string())
            else:
                print("❌ No security alerts found")
            input("\nPress Enter to continue...")
        elif choice == '5':
            print("\n[✓] Returning to main menu...")
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
    
    print("\n[*] Starting demo analysis for 5 employees...\n")
    
    agents = []
    for emp_id in employees:
        config = {'shared_folder': './manager_reports'}
        agent = SimpleEmployeeMonitoringAgent(emp_id, config, db_connection)
        agents.append(agent)
    
    for cycle in range(5):
        print(f"Cycle {cycle + 1}/5", end=" ", flush=True)
        
        for agent in agents:
            if np.random.random() < 0.2:
                event_type = np.random.choice(['FILE_CREATED', 'FILE_DELETED', 'SUSPICIOUS_FILE'])
                agent.handle_file_event(event_type, {
                    'employee_id': agent.employee_id,
                    'file_name': f"demo_file_{cycle}.txt",
                    'file_path': f"C:\\Users\\demo_file_{cycle}.txt",
                    'severity': 'HIGH' if event_type == 'SUSPICIOUS_FILE' else 'MEDIUM',
                    'timestamp': datetime.now().isoformat()
                })
            
            metrics = agent.simulate_metrics()
            analysis = agent.analyze_behavior(metrics)
            
            if analysis['risk_level'] in ['HIGH', 'CRITICAL'] or analysis['anomaly_detected']:
                agent.send_report_to_manager(analysis, 'alert')
            else:
                agent.send_report_to_manager(analysis, 'regular')
        
        print("✓", end=" ", flush=True)
        time.sleep(0.5)
    
    print("\n\n[✓] Demo complete!")
    
    dashboard = ManagerDashboard(db_connection=db_connection)
    dashboard.display_dashboard()
    
    print("\n📊 Exporting reports...")
    dashboard.export_comprehensive_csv_report()
    
    print("\n[✓] Demo finished! Returning to main menu...")
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
        print("   4. Generate Documentation 📥 (Auto-Download)")
        print("   5. 🧪 Train & Validate Model (Test on Unseen Data)")
        print("   6. 📊 Test Model on Your Own CSV Data")
        print("   7. 🤖 Compare Different Models")
        print("   8. 📈 View Saved Model Results")
        print("   9. 🔗 Setup MySQL Connection")
        print("   10. Exit Program")
        
        mode = input("\n👉 Select option (1-10): ").strip()
        
        if mode == '1':
            run_employee_mode(db_connection)
        elif mode == '2':
            run_manager_mode(db_connection)
        elif mode == '3':
            run_demo(db_connection)
        elif mode == '4':
            run_doc_generation(db_connection)
        elif mode == '5':
            accuracy = train_and_validate_model()
            print(f"\n🎉 Model Training Complete! Test Accuracy: {accuracy:.2%}")
            input("\nPress Enter to continue...")
        elif mode == '6':
            test_on_real_data()
            input("\nPress Enter to continue...")
        elif mode == '7':
            compare_models()
            input("\nPress Enter to continue...")
        elif mode == '8':
            view_model_results()
            input("\nPress Enter to continue...")
        elif mode == '9':
            db_connection = setup_mysql_connection()
            if db_connection:
                print("\n✅ MySQL connection established! Data will be stored in database.")
            else:
                print("\n⚠️ Continuing with CSV mode only.")
            input("\nPress Enter to continue...")
        elif mode == '10':
            if db_connection:
                db_connection.disconnect()
            print("\n👋 Thank you for using Employee Behavior Analytics System!")
            print("Exiting program...")
            break
        else:
            print("\n❌ Invalid option! Please select 1-10")
            time.sleep(1)

# =====================================================
# PROGRAM ENTRY POINT
# =====================================================

if __name__ == "__main__":
    main()
    print("\n✅ Program terminated successfully!")
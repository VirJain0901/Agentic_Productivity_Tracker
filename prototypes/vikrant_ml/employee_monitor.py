# ONE FILE - Contains ALL code
# =====================================================
# EMPLOYEE MONITORING SYSTEM - COMPLETE DJANGO + MYSQL + MONITORING
# ALL IN ONE FILE
# =====================================================

import os
import sys
import django
from pathlib import Path

from django.urls import path

# =====================================================
# DJANGO SETTINGS WITH MYSQL
# =====================================================

# Set up Django settings
BASE_DIR = Path(__file__).resolve().parent

# Django settings
SECRET_KEY = 'django-insecure-your-secret-key-here-change-in-production'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'employee_apps',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'urls'  # Use dedicated url config module

# Static files (required by django.contrib.staticfiles)
STATIC_URL = '/static/'

TEMPLATES = [

    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]
WSGI_APPLICATION = __name__ + '.application'

# =====================================================
# MYSQL DATABASE CONFIGURATION
# =====================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'employee_tracker'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'asma'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        }
    }
}

# =====================================================
# DJANGO URLS
# =====================================================
# (moved to urls.py)

# =====================================================
# MONITORING CODE - YOUR COMPLETE CODE
# =====================================================


import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, precision_score, recall_score, f1_score
import joblib
import time
import json
from collections import deque
from datetime import datetime
import hashlib
import threading
import warnings
import subprocess
import zipfile
import webbrowser
import platform
import shutil
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
# FILE DETECTION SYSTEM
# =====================================================

class FileDetectionHandler(FileSystemEventHandler):
    """Detects file system events in real-time"""
    
    def __init__(self, employee_id, callback_function):
        self.employee_id = employee_id
        self.callback = callback_function
        self.suspicious_extensions = {'.exe', '.bat', '.ps1', '.vbs', '.js', '.py', '.scr', '.com', '.dll'}
        self.file_hashes = {}
        self.deletion_count = 0
        self.last_reset = datetime.now()
        
    def on_created(self, event):
        if not event.is_directory:
            file_info = self.get_file_info(event.src_path)
            self.callback('FILE_CREATED', {
                'employee_id': self.employee_id,
                'file_path': event.src_path,
                'file_name': os.path.basename(event.src_path),
                'file_size': file_info['size'],
                'file_type': file_info['extension'],
                'timestamp': datetime.now().isoformat()
            })
            
            if file_info['extension'].lower() in self.suspicious_extensions:
                self.callback('SUSPICIOUS_FILE', {
                    'employee_id': self.employee_id,
                    'file_path': event.src_path,
                    'file_name': os.path.basename(event.src_path),
                    'reason': f"Suspicious file type: {file_info['extension']}",
                    'severity': 'HIGH',
                    'timestamp': datetime.now().isoformat()
                })
    
    def on_deleted(self, event):
        if not event.is_directory:
            self.deletion_count += 1
            
            now = datetime.now()
            if (now - self.last_reset).seconds > 60:
                self.deletion_count = 0
                self.last_reset = now
            
            if self.deletion_count > 10:
                self.callback('MASS_DELETION', {
                    'employee_id': self.employee_id,
                    'deletion_count': self.deletion_count,
                    'severity': 'CRITICAL',
                    'message': f'Mass file deletion detected: {self.deletion_count} files in last minute',
                    'timestamp': datetime.now().isoformat()
                })
            
            self.callback('FILE_DELETED', {
                'employee_id': self.employee_id,
                'file_path': event.src_path,
                'file_name': os.path.basename(event.src_path),
                'timestamp': datetime.now().isoformat()
            })
    
    def on_modified(self, event):
        if not event.is_directory:
            current_hash = self.get_file_hash(event.src_path)
            if event.src_path in self.file_hashes:
                if current_hash and current_hash != self.file_hashes[event.src_path]:
                    self.callback('FILE_MODIFIED', {
                        'employee_id': self.employee_id,
                        'file_path': event.src_path,
                        'file_name': os.path.basename(event.src_path),
                        'hash_changed': True,
                        'timestamp': datetime.now().isoformat()
                    })
            
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
    
    def __init__(self, employee_id, callback):
        self.employee_id = employee_id
        self.callback = callback
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
        event_handler = FileDetectionHandler(self.employee_id, self.callback)
        
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
# EMPLOYEE BEHAVIOR ANALYTICS WITH CSV EXPORT
# =====================================================

class SimpleEmployeeMonitoringAgent:
    """Employee monitoring agent with CSV export"""
    
    def __init__(self, employee_id, manager_config):
        self.employee_id = str(employee_id)
        self.manager_config = manager_config
        self.model = None
        self.anomaly_model = None
        self.is_running = False
        self.data_buffer = deque(maxlen=100)
        
        self.file_monitor = None
        self.file_events = deque(maxlen=100)
        self.suspicious_file_count = 0
        
        self.load_models()
        self.init_file_monitoring()
        
    def init_file_monitoring(self):
        if WATCHDOG_AVAILABLE:
            self.file_monitor = FileMonitor(self.employee_id, self.handle_file_event)
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
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)
        
        self.anomaly_model = IsolationForest(contamination=0.05, random_state=42)
        self.anomaly_model.fit(X_train)
        
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
        self.export_to_csv(analysis, report_type, current_time)
        
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
        print(f"[*] Reports saved to: ./manager_reports/")
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
    
    def stop_monitoring(self):
        self.is_running = False
        self.stop_file_monitoring()
        print(f"\n[✓] Monitoring stopped for Employee {self.employee_id}")


class ManagerDashboard:
    """Manager dashboard with advanced CSV export"""
    
    def __init__(self, shared_folder='./manager_reports'):
        self.shared_folder = shared_folder
        
    def export_comprehensive_csv_report(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_folder = f"export_{timestamp}"
        os.makedirs(export_folder, exist_ok=True)
        
        all_data = self.get_all_data()
        
        if not all_data.empty:
            if 'suspicious_files' not in all_data.columns:
                all_data['suspicious_files'] = 0
            if 'anomaly_detected' not in all_data.columns:
                all_data['anomaly_detected'] = False
            if 'risk_level' not in all_data.columns:
                all_data['risk_level'] = 'LOW'
            all_data['employee_id'] = all_data['employee_id'].astype(str)
        
        if not all_data.empty:
            all_data.to_csv(os.path.join(export_folder, '1_all_reports.csv'), index=False)
            print(f"✅ 1_all_reports.csv - Raw data")
        
        summary = self.get_employee_summary(all_data)
        if not summary.empty:
            summary.to_csv(os.path.join(export_folder, '2_employee_summary.csv'), index=False)
            print(f"✅ 2_employee_summary.csv - Employee averages")
        
        risk_report = self.get_risk_report(all_data)
        if not risk_report.empty:
            risk_report.to_csv(os.path.join(export_folder, '3_risk_analysis.csv'), index=False)
            print(f"✅ 3_risk_analysis.csv - Risk assessment")
        
        trends = self.get_productivity_trends(all_data)
        if not trends.empty:
            trends.to_csv(os.path.join(export_folder, '4_productivity_trends.csv'), index=False)
            print(f"✅ 4_productivity_trends.csv - Daily trends")
        
        anomalies = self.get_anomaly_report(all_data)
        if not anomalies.empty:
            anomalies.to_csv(os.path.join(export_folder, '5_anomalies.csv'), index=False)
            print(f"✅ 5_anomalies.csv - Detected anomalies")
        
        alerts = self.get_alerts_summary(all_data)
        if not alerts.empty:
            alerts.to_csv(os.path.join(export_folder, '6_alerts.csv'), index=False)
            print(f"✅ 6_alerts.csv - Critical alerts")
        
        security_alerts = self.get_security_alerts()
        if not security_alerts.empty:
            security_alerts.to_csv(os.path.join(export_folder, '7_security_alerts.csv'), index=False)
            print(f"✅ 7_security_alerts.csv - Security incidents")
        
        file_events = self.get_file_events()
        if not file_events.empty:
            file_events.to_csv(os.path.join(export_folder, '8_file_events.csv'), index=False)
            print(f"✅ 8_file_events.csv - All file activities")
        
        print(f"\n✅ All CSV reports exported to folder: {export_folder}/")
        self.export_individual_csv_reports(all_data, timestamp)
        
        return export_folder
    
    def get_all_data(self):
        if not os.path.exists(self.shared_folder):
            return pd.DataFrame()
        
        csv_file = os.path.join(self.shared_folder, 'all_employee_reports.csv')
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            df['employee_id'] = df['employee_id'].astype(str)
            return df
        return pd.DataFrame()
    
    def get_security_alerts(self):
        security_file = os.path.join(self.shared_folder, 'security_alerts.csv')
        if os.path.exists(security_file):
            df = pd.read_csv(security_file)
            df['employee_id'] = df['employee_id'].astype(str)
            return df
        return pd.DataFrame()
    
    def get_file_events(self):
        file_events_file = os.path.join(self.shared_folder, 'file_events.csv')
        if os.path.exists(file_events_file):
            df = pd.read_csv(file_events_file)
            df['employee_id'] = df['employee_id'].astype(str)
            return df
        return pd.DataFrame()
    
    def get_employee_summary(self, all_data):
        if all_data.empty:
            return pd.DataFrame()
        
        agg_dict = {
            'productivity_score': ['mean', 'min', 'max', 'std'],
            'risk_score': 'mean',
            'anomaly_detected': 'sum',
            'productive_time_min': 'mean',
            'unproductive_time_min': 'mean',
            'idle_time_min': 'mean',
            'app_switches': 'mean',
            'deleted_files': 'mean'
        }
        
        if 'suspicious_files' in all_data.columns:
            agg_dict['suspicious_files'] = 'sum'
        
        summary = all_data.groupby('employee_id').agg(agg_dict).round(2)
        
        col_names = ['Avg_Productivity', 'Min_Productivity', 'Max_Productivity', 
                    'Productivity_Std', 'Avg_Risk_Score', 'Total_Anomalies',
                    'Avg_Productive_Time', 'Avg_Unproductive_Time', 'Avg_Idle_Time',
                    'Avg_App_Switches', 'Avg_Deleted_Files']
        
        if 'suspicious_files' in all_data.columns:
            col_names.append('Total_Suspicious_Files')
        
        summary.columns = col_names
        summary = summary.reset_index()
        
        summary['Performance_Rating'] = summary['Avg_Productivity'].apply(
            lambda x: 'Excellent' if x > 0.7 else ('Good' if x > 0.5 else ('Average' if x > 0.3 else 'Poor'))
        )
        
        if 'Total_Suspicious_Files' in summary.columns:
            summary['Recommendation'] = summary.apply(
                lambda x: 'Immediate intervention needed' if x['Avg_Productivity'] < 0.3 or x['Total_Suspicious_Files'] > 5
                else 'Monitor closely' if x['Avg_Productivity'] < 0.5 or x['Total_Suspicious_Files'] > 2
                else 'Regular check-in' if x['Avg_Productivity'] < 0.7
                else 'Recognition & rewards',
                axis=1
            )
        else:
            summary['Recommendation'] = summary['Avg_Productivity'].apply(
                lambda x: 'Immediate intervention needed' if x < 0.3
                else 'Monitor closely' if x < 0.5
                else 'Regular check-in' if x < 0.7
                else 'Recognition & rewards'
            )
        
        return summary
    
    def get_risk_report(self, all_data):
        if all_data.empty:
            return pd.DataFrame()
        
        agg_dict = {
            'risk_level': lambda x: x.mode()[0] if len(x) > 0 else 'LOW',
            'risk_score': 'mean',
            'risk_factors': lambda x: ', '.join(set(', '.join(x.astype(str)).split(', ')))[:200]
        }
        
        if 'suspicious_files' in all_data.columns:
            agg_dict['suspicious_files'] = 'sum'
        
        risk_report = all_data.groupby('employee_id').agg(agg_dict).reset_index()
        
        col_names = ['employee_id', 'Primary_Risk_Level', 'Average_Risk_Score', 'Common_Risk_Factors']
        if 'suspicious_files' in all_data.columns:
            col_names.append('Total_Suspicious_Files')
            risk_report.columns = col_names
        else:
            risk_report.columns = col_names
        
        risk_report['Risk_Category'] = risk_report['Average_Risk_Score'].apply(
            lambda x: 'Critical' if x >= 70 else ('High' if x >= 50 else ('Medium' if x >= 30 else 'Low'))
        )
        
        if 'Total_Suspicious_Files' in risk_report.columns:
            risk_report['Urgency'] = risk_report.apply(
                lambda x: 'Immediate' if x['Risk_Category'] in ['Critical', 'High'] or x['Total_Suspicious_Files'] > 5
                else 'Normal' if x['Risk_Category'] == 'Medium'
                else 'Low',
                axis=1
            )
        else:
            risk_report['Urgency'] = risk_report['Risk_Category'].apply(
                lambda x: 'Immediate' if x in ['Critical', 'High']
                else 'Normal' if x == 'Medium'
                else 'Low'
            )
        
        return risk_report
    
    def get_productivity_trends(self, all_data):
        if all_data.empty:
            return pd.DataFrame()
        
        all_data['timestamp'] = pd.to_datetime(all_data['timestamp'])
        all_data['date'] = all_data['timestamp'].dt.date
        
        agg_dict = {
            'productivity_score': 'mean',
            'productive_time_min': 'sum',
            'unproductive_time_min': 'sum',
            'risk_score': 'mean'
        }
        
        if 'suspicious_files' in all_data.columns:
            agg_dict['suspicious_files'] = 'sum'
        
        trends = all_data.groupby(['employee_id', 'date']).agg(agg_dict).reset_index()
        
        return trends
    
    def get_anomaly_report(self, all_data):
        if all_data.empty:
            return pd.DataFrame()
        
        anomalies = all_data[all_data['anomaly_detected'] == True].copy()
        
        if not anomalies.empty:
            cols = ['timestamp', 'employee_id', 'anomaly_score', 
                   'productivity_score', 'risk_level', 'risk_factors']
            
            if 'suspicious_files' in anomalies.columns:
                cols.append('suspicious_files')
            
            anomalies = anomalies[cols]
            anomalies = anomalies.sort_values('anomaly_score', ascending=True)
        
        return anomalies
    
    def get_alerts_summary(self, all_data):
        if all_data.empty:
            return pd.DataFrame()
        
        alert_condition = (all_data['risk_level'].isin(['HIGH', 'CRITICAL'])) | (all_data['anomaly_detected'] == True)
        
        if 'suspicious_files' in all_data.columns:
            alert_condition = alert_condition | (all_data['suspicious_files'] > 0)
        
        alerts = all_data[alert_condition].copy()
        
        if not alerts.empty:
            cols = ['timestamp', 'employee_id', 'risk_level', 
                   'risk_score', 'anomaly_detected', 'productivity_score']
            
            if 'suspicious_files' in alerts.columns:
                cols.append('suspicious_files')
            
            alerts = alerts[cols]
            alerts = alerts.sort_values('risk_score', ascending=False)
            
            alerts['alert_type'] = alerts.apply(
                lambda x: 'Critical Risk' if x['risk_level'] == 'CRITICAL'
                else 'High Risk' if x['risk_level'] == 'HIGH'
                else 'Anomaly' if x['anomaly_detected']
                else 'Suspicious Files' if x.get('suspicious_files', 0) > 0
                else 'Warning',
                axis=1
            )
        
        return alerts
    
    def export_individual_csv_reports(self, all_data, timestamp):
        if all_data.empty:
            print("[!] No data to export")
            return
        
        export_folder = f"detailed_reports_{timestamp}"
        os.makedirs(export_folder, exist_ok=True)
        
        all_data['date'] = pd.to_datetime(all_data['timestamp']).dt.date
        
        agg_dict = {
            'productivity_score': 'mean',
            'productive_time_min': 'sum',
            'risk_score': 'mean'
        }
        
        if 'suspicious_files' in all_data.columns:
            agg_dict['suspicious_files'] = 'sum'
        
        daily_report = all_data.groupby(['date', 'employee_id']).agg(agg_dict).reset_index()
        daily_report.to_csv(os.path.join(export_folder, f"daily_report.csv"), index=False)
        print(f"✅ daily_report.csv - Daily summaries")
        
        high_risk_cols = ['timestamp', 'employee_id', 'risk_level', 'risk_score', 'productivity_score']
        if 'suspicious_files' in all_data.columns:
            high_risk_cols.append('suspicious_files')
        
        high_risk = all_data[all_data['risk_level'].isin(['HIGH', 'CRITICAL'])][high_risk_cols].drop_duplicates(subset=['employee_id'])
        high_risk.to_csv(os.path.join(export_folder, f"high_risk_employees.csv"), index=False)
        print(f"✅ high_risk_employees.csv - High risk list")
        
        ranking_cols = ['productivity_score', 'productive_time_min']
        if 'suspicious_files' in all_data.columns:
            ranking_cols.append('suspicious_files')
        
        ranking = all_data.groupby('employee_id').agg({
            'productivity_score': 'mean',
            'productive_time_min': 'sum',
            **({'suspicious_files': 'sum'} if 'suspicious_files' in all_data.columns else {})
        }).reset_index()
        
        ranking = ranking.sort_values('productivity_score', ascending=False)
        ranking['rank'] = range(1, len(ranking) + 1)
        ranking.to_csv(os.path.join(export_folder, f"performance_ranking.csv"), index=False)
        print(f"✅ performance_ranking.csv - Ranked performance")
        
        for employee in all_data['employee_id'].unique():
            emp_data = all_data[all_data['employee_id'] == employee]
            emp_data.to_csv(os.path.join(export_folder, f"employee_{employee}_report.csv"), index=False)
        
        print(f"✅ Individual employee reports - {len(all_data['employee_id'].unique())} files")
        print(f"\n✅ All detailed reports saved to folder: {export_folder}/")
    
    def display_dashboard(self):
        print("\n" + "="*60)
        print("👔 MANAGER DASHBOARD - TEAM PERFORMANCE")
        print("="*60)
        
        all_data = self.get_all_data()
        security_alerts = self.get_security_alerts()
        
        if not all_data.empty:
            if 'suspicious_files' not in all_data.columns:
                all_data['suspicious_files'] = 0
            if 'anomaly_detected' not in all_data.columns:
                all_data['anomaly_detected'] = False
            all_data['employee_id'] = all_data['employee_id'].astype(str)
        
        if all_data.empty:
            print("[!] No reports available. Waiting for employee agents...")
            return
        
        latest_reports = all_data.sort_values('timestamp').groupby('employee_id').last().reset_index()
        
        print(f"\n📊 Team Summary:")
        print(f"   Total Employees: {len(latest_reports)}")
        print(f"   Average Productivity: {latest_reports['productivity_score'].mean():.1%}")
        print(f"   High Risk Employees: {len(latest_reports[latest_reports['risk_level'].isin(['HIGH', 'CRITICAL'])])}")
        print(f"   Total Anomalies Detected: {latest_reports['anomaly_detected'].sum()}")
        
        if not security_alerts.empty:
            critical_security = len(security_alerts[security_alerts['severity'] == 'CRITICAL'])
            print(f"   🔐 Security Alerts: {len(security_alerts)} (Critical: {critical_security})")
        
        print(f"\n📈 Employee Status:")
        print("-" * 80)
        
        for _, emp in latest_reports.iterrows():
            icon = "🔴" if emp['risk_level'] in ['HIGH', 'CRITICAL'] else "🟡" if emp['risk_level'] == 'MEDIUM' else "🟢"
            anomaly_mark = "⚠️" if emp['anomaly_detected'] else "✅"
            security_mark = "🔐" if emp.get('suspicious_files', 0) > 0 else ""
            
            print(f"{icon} {emp['employee_id']}: {emp['productivity_prediction']} ({emp['productivity_score']:.1%}) | "
                  f"Risk: {emp['risk_level']} | Anomaly: {anomaly_mark} {security_mark}")
        
        critical_condition = (latest_reports['risk_level'].isin(['HIGH', 'CRITICAL']))
        if 'suspicious_files' in latest_reports.columns:
            critical_condition = critical_condition | (latest_reports['suspicious_files'] > 5)
        
        critical = latest_reports[critical_condition]
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
# TRAINING & VALIDATION FUNCTIONS
# =====================================================

def train_and_validate_model():
    print("\n" + "="*60)
    print("📊 MODEL TRAINING & VALIDATION")
    print("="*60)
    
    np.random.seed(42)
    n_samples = 5000
    
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
    df['productive_app_usage'] = np.clip(df['productive_app_usage'], 10, 300)
    df['unproductive_app_usage'] = np.clip(df['unproductive_app_usage'], 0, 200)
    df['idle_time'] = np.clip(df['idle_time'], 0, 120)
    df['app_switch_count'] = np.clip(df['app_switch_count'], 1, 30)
    df['deleted_files'] = np.clip(df['deleted_files'], 0, 15)
    
    df["productive_ratio"] = df["productive_app_usage"] / (df["productive_app_usage"] + df["unproductive_app_usage"] + 1)
    df["productivity_label"] = ((df["productive_ratio"] > 0.55) & (df["focus_score"] > 0.6) & (df["task_completion_rate"] > 0.65)).astype(int)
    
    noise_idx = np.random.choice(df.index, size=int(0.05 * len(df)), replace=False)
    df.loc[noise_idx, "productivity_label"] = 1 - df.loc[noise_idx, "productivity_label"]
    
    features = ["productive_app_usage", "unproductive_app_usage", "idle_time", 
                "app_switch_count", "deleted_files", "focus_score", 
                "task_completion_rate", "productive_ratio"]
    
    X = df[features]
    y = df["productivity_label"]
    
    X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.15, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.176, random_state=42, stratify=y_temp)
    
    print(f"\n📊 Dataset Split:")
    print(f"   Training samples: {len(X_train)} (70%)")
    print(f"   Validation samples: {len(X_val)} (15%)")
    print(f"   Test samples: {len(X_test)} (15%)")
    
    print("\n[*] Training Random Forest model...")
    rf_model = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_split=20, min_samples_leaf=10, random_state=42, n_jobs=-1)
    rf_model.fit(X_train, y_train)
    
    print("[*] Training Anomaly Detection model...")
    iso_forest = IsolationForest(contamination=0.05, random_state=42)
    iso_forest.fit(X_train)
    
    y_train_pred = rf_model.predict(X_train)
    train_acc = accuracy_score(y_train, y_train_pred)
    
    y_val_pred = rf_model.predict(X_val)
    val_acc = accuracy_score(y_val, y_val_pred)
    
    y_test_pred = rf_model.predict(X_test)
    test_acc = accuracy_score(y_test, y_test_pred)
    
    print(f"\n🎯 Accuracy Scores:")
    print(f"   Training Accuracy: {train_acc:.2%}")
    print(f"   Validation Accuracy: {val_acc:.2%}")
    print(f"   Test Accuracy: {test_acc:.2%} ⭐")
    
    precision = precision_score(y_test, y_test_pred)
    recall = recall_score(y_test, y_test_pred)
    f1 = f1_score(y_test, y_test_pred)
    
    print(f"\n📊 Additional Metrics:")
    print(f"   Precision: {precision:.2%}")
    print(f"   Recall: {recall:.2%}")
    print(f"   F1-Score: {f1:.2%}")
    
    joblib.dump(rf_model, 'productivity_model_enhanced.pkl')
    joblib.dump(iso_forest, 'anomaly_model_enhanced.pkl')
    
    results = {
        'training_accuracy': float(train_acc),
        'validation_accuracy': float(val_acc),
        'test_accuracy': float(test_acc),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'test_date': datetime.now().isoformat()
    }
    
    with open('model_training_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Models saved successfully!")
    return test_acc


def test_on_real_data():
    print("\n" + "="*60)
    print("🧪 TEST MODEL ON YOUR OWN DATA")
    print("="*60)
    
    try:
        model = joblib.load('productivity_model_enhanced.pkl')
        anomaly_model = joblib.load('anomaly_model_enhanced.pkl')
        print("✅ Models loaded successfully")
    except Exception as e:
        print(f"❌ No trained model found. Please train first (Option 5)")
        return
    
    csv_path = input("\n📁 Enter path to your CSV file: ").strip()
    
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return
    
    try:
        test_data = pd.read_csv(csv_path)
        print(f"✅ Loaded {len(test_data)} records")
        
        required_cols = ["productive_app_usage", "unproductive_app_usage", "idle_time",
                        "app_switch_count", "deleted_files", "focus_score",
                        "task_completion_rate"]
        
        missing_cols = [col for col in required_cols if col not in test_data.columns]
        if missing_cols:
            print(f"❌ Missing columns: {missing_cols}")
            return
        
        test_data["productive_ratio"] = test_data["productive_app_usage"] / (
            test_data["productive_app_usage"] + test_data["unproductive_app_usage"] + 1
        )
        
        features = required_cols + ["productive_ratio"]
        X_test = test_data[features]
        
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)[:, 1]
        anomalies = anomaly_model.predict(X_test)
        
        test_data['productivity_prediction'] = ['Productive' if p == 1 else 'Unproductive' for p in predictions]
        test_data['productivity_confidence'] = probabilities
        test_data['anomaly'] = ['⚠️ Anomaly' if a == -1 else '✅ Normal' for a in anomalies]
        
        print(f"\n📊 Prediction Summary:")
        print(f"   Productive: {(predictions == 1).sum()} employees ({(predictions == 1).mean():.1%})")
        print(f"   Unproductive: {(predictions == 0).sum()} employees ({(predictions == 0).mean():.1%})")
        print(f"   Anomalies Detected: {(anomalies == -1).sum()}")
        
        if 'productivity_label' in test_data.columns:
            accuracy = accuracy_score(test_data['productivity_label'], predictions)
            precision = precision_score(test_data['productivity_label'], predictions)
            recall = recall_score(test_data['productivity_label'], predictions)
            f1 = f1_score(test_data['productivity_label'], predictions)
            
            print(f"\n📊 Model Performance:")
            print(f"   ✅ Accuracy: {accuracy:.2%}")
            print(f"   ✅ Precision: {precision:.2%}")
            print(f"   ✅ Recall: {recall:.2%}")
            print(f"   ✅ F1-Score: {f1:.2%}")
        
        output_path = csv_path.replace('.csv', '_predictions.csv')
        test_data.to_csv(output_path, index=False)
        print(f"\n✅ Results saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error processing file: {e}")


def compare_models():
    print("\n" + "="*60)
    print("🤖 MODEL COMPARISON & SELECTION")
    print("="*60)
    
    np.random.seed(42)
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
        start_time = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - start_time
        
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        
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
        
        print(f"{results[-1]['Status']} {name}: {accuracy:.2%}")
    
    results_df = pd.DataFrame(results)
    print(f"\n{'='*60}")
    print(results_df.to_string(index=False))
    
    best_model = results_df.loc[results_df['Accuracy'].idxmax()]
    print(f"\n🏆 Best Model: {best_model['Model']} with {best_model['Accuracy']}")
    
    results_df.to_csv('model_comparison.csv', index=False)
    return results_df


def view_model_results():
    print("\n" + "="*60)
    print("📊 VIEW MODEL TRAINING RESULTS")
    print("="*60)
    
    if os.path.exists('model_training_results.json'):
        with open('model_training_results.json', 'r') as f:
            results = json.load(f)
        
        print(f"\n📈 Training Results:")
        print(f"   Training Accuracy: {results.get('training_accuracy', 'N/A')}")
        print(f"   Validation Accuracy: {results.get('validation_accuracy', 'N/A')}")
        print(f"   Test Accuracy: {results.get('test_accuracy', 'N/A')}")
        print(f"   Precision: {results.get('precision', 'N/A')}")
        print(f"   Recall: {results.get('recall', 'N/A')}")
        print(f"   F1-Score: {results.get('f1_score', 'N/A')}")
        print(f"   Date: {results.get('test_date', 'N/A')}")
    else:
        print("\n❌ No training results found. Please train a model first (Option 5)")


# =====================================================
# MAIN PROGRAM FUNCTIONS
# =====================================================

def run_employee_mode():
    print("\n" + "="*60)
    print("🖥️  EMPLOYEE MONITORING AGENT")
    print("="*60)
    
    employee_id = input("Enter Employee ID: ").strip()
    if not employee_id:
        employee_id = f"EMP{np.random.randint(100, 999)}"
        print(f"Using auto-generated ID: {employee_id}")
    
    interval = input("Interval in minutes (default 5): ").strip()
    interval = int(interval) if interval else 5
    
    config = {'shared_folder': './manager_reports'}
    agent = SimpleEmployeeMonitoringAgent(employee_id, config)
    
    if interval == 0:
        print("\n[*] Running single analysis...")
        metrics = agent.simulate_metrics()
        analysis = agent.analyze_behavior(metrics)
        agent.send_report_to_manager(analysis, 'regular')
        print(f"\n✅ Analysis complete for {employee_id}")
    else:
        print(f"\n⚠️ Monitoring started for {interval} minute intervals")
        agent.start_monitoring(interval_minutes=interval)


def run_manager_mode():
    print("\n" + "="*60)
    print("👔 MANAGER DASHBOARD")
    print("="*60)
    
    dashboard = ManagerDashboard()
    
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
            all_data = dashboard.get_all_data()
            all_data['employee_id'] = all_data['employee_id'].astype(str)
            emp_data = all_data[all_data['employee_id'] == emp_id]
            if not emp_data.empty:
                print(f"\n📊 Employee {emp_id} Details:")
                print(emp_data.to_string())
            else:
                print(f"❌ No data found for Employee {emp_id}")
            input("\nPress Enter to continue...")
        elif choice == '4':
            security_alerts = dashboard.get_security_alerts()
            if not security_alerts.empty:
                print("\n🔐 SECURITY ALERTS:")
                print(security_alerts.to_string())
            else:
                print("❌ No security alerts found")
            input("\nPress Enter to continue...")
        elif choice == '5':
            print("\n[✓] Returning to main menu...")
            break
        else:
            print("❌ Invalid option")


def run_demo():
    print("\n" + "="*60)
    print("🎯 DEMO MODE")
    print("="*60)
    
    os.makedirs('./manager_reports', exist_ok=True)
    employees = ['EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005']
    
    print("\n[*] Starting demo for 5 employees...\n")
    
    agents = []
    for emp_id in employees:
        config = {'shared_folder': './manager_reports'}
        agent = SimpleEmployeeMonitoringAgent(emp_id, config)
        agents.append(agent)
    
    for cycle in range(5):
        print(f"Cycle {cycle + 1}/5", end=" ", flush=True)
        
        for agent in agents:
            metrics = agent.simulate_metrics()
            analysis = agent.analyze_behavior(metrics)
            agent.send_report_to_manager(analysis, 'regular')
        
        print("✓", end=" ", flush=True)
        time.sleep(0.5)
    
    print("\n\n[✓] Demo complete!")
    
    dashboard = ManagerDashboard()
    dashboard.display_dashboard()
    dashboard.export_comprehensive_csv_report()


def run_doc_generation():
    print("\n" + "="*60)
    print("📄 DOCUMENTATION GENERATION")
    print("="*60)
    
    dashboard = ManagerDashboard()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_folder = f"documentation_{timestamp}"
    os.makedirs(doc_folder, exist_ok=True)
    
    print("\n[*] Generating documentation...")
    dashboard.export_comprehensive_csv_report()
    
    print(f"\n✅ Documentation generated in: {doc_folder}/")
    time.sleep(2)


# =====================================================
# MAIN MENU
# =====================================================

def main():
    while True:
        print("\n" + "="*60)
        print("🎯 EMPLOYEE BEHAVIOR ANALYTICS SYSTEM")
        print("="*60)
        
        if not WATCHDOG_AVAILABLE:
            print("\n💡 Tip: pip install watchdog")
        
        print("\n📋 MAIN MENU:")
        print("   1. Employee Agent (Start Monitoring)")
        print("   2. Manager Dashboard (View Reports)")
        print("   3. Quick Demo (Generate Sample Data)")
        print("   4. Generate Documentation")
        print("   5. 🧪 Train & Validate Model")
        print("   6. 📊 Test Model on Your Own Data")
        print("   7. 🤖 Compare Models")
        print("   8. 📈 View Model Results")
        print("   9. Exit")
        
        mode = input("\n👉 Select option (1-9): ").strip()
        
        if mode == '1':
            run_employee_mode()
        elif mode == '2':
            run_manager_mode()
        elif mode == '3':
            run_demo()
        elif mode == '4':
            run_doc_generation()
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
            print("\n👋 Thank you for using Employee Behavior Analytics System!")
            break
        else:
            print("\n❌ Invalid option!")
            time.sleep(1)


# =====================================================
# DJANGO WSGI APPLICATION
# =====================================================

# This is required for Django to work
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()


# =====================================================
# ENTRY POINT
# =====================================================

if __name__ == "__main__":
    main()
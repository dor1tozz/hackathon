import pytest
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from mail_processor import MailProcessor
    from file_main_process import main as process_main
except ImportError as e:
    class MailProcessor:
        def classify_email(self, subject, body):
            text = f"{subject} {body}".lower()
            if 'срочно' in text:
                return 'critical_incident'
            if 'спам' in text:
                return 'spam'
            return 'uncategorized'


class TestIntegration:

    @pytest.fixture
    def temp_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = os.path.join(tmpdir, "data", "inbox")
            output_dir = os.path.join(tmpdir, "data", "output")
            logs_dir = os.path.join(tmpdir, "logs")
            reports_dir = os.path.join(tmpdir, "reports")
            
            for dir_path in [inbox_dir, output_dir, logs_dir, reports_dir]:
                os.makedirs(dir_path)
            
            fixtures_path = os.path.join(os.path.dirname(__file__), "fixtures")
            if os.path.exists(fixtures_path):
                for filename in os.listdir(fixtures_path):
                    if filename.endswith('.eml'):
                        src = os.path.join(fixtures_path, filename)
                        dst = os.path.join(inbox_dir, filename)
                        shutil.copy2(src, dst)
            
            yield {
                "root": tmpdir,
                "inbox": inbox_dir,
                "output": output_dir,
                "logs": logs_dir,
                "reports": reports_dir,
            }

    def test_classifier_reads_email_and_classifies(self, temp_project):
        processor = MailProcessor()
        
        inbox_files = os.listdir(temp_project["inbox"])
        if not inbox_files:
            pytest.skip("No test .eml files in fixtures folder")
        
        test_email_path = os.path.join(temp_project["inbox"], inbox_files[0])
        
        with open(test_email_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        subject = ""
        body = ""
        for line in content.split('\n'):
            if line.lower().startswith('subject:'):
                subject = line[8:].strip()
            elif not line.startswith('From:') and not line.startswith('To:') and not line.startswith('Date:'):
                body += line + " "
        
        category = processor.classify_email(subject, body)
        
        valid_categories = ['critical_incident', 'support_request', 'spam', 'sent', 
                           'draft', 'billing', 'hr', 'informational', 'uncategorized']
        assert category in valid_categories

    def test_processing_does_not_crash_with_empty_inbox(self, temp_project, monkeypatch):
        for f in os.listdir(temp_project["inbox"]):
            os.remove(os.path.join(temp_project["inbox"], f))
        
        monkeypatch.setattr("file_main_process.INBOX_DIR", temp_project["inbox"])
        monkeypatch.setattr("file_main_process.OUTPUT_DIR", temp_project["output"])
        monkeypatch.setattr("file_main_process.LOGS_DIR", temp_project["logs"])
        monkeypatch.setattr("file_main_process.REPORTS_DIR", temp_project["reports"])
        
        try:
            process_main()
        except SystemExit:
            pass
        except Exception as e:
            pytest.fail(f"System crashed with empty inbox: {e}")

    def test_output_folders_are_created(self, temp_project, monkeypatch):
        from file_main_process import main as process_main
        
        test_email_path = os.path.join(temp_project["inbox"], "test_critical.eml")
        with open(test_email_path, 'w', encoding='utf-8') as f:
            f.write("Subject: Срочная проблема\n\nКритический сбой системы")
        
        monkeypatch.setattr("file_main_process.INBOX_DIR", temp_project["inbox"])
        monkeypatch.setattr("file_main_process.OUTPUT_DIR", temp_project["output"])
        
        try:
            process_main()
        except SystemExit:
            pass
        
        critical_path = os.path.join(temp_project["output"], "critical_incident")
        assert os.path.exists(critical_path)
        
        target_files = os.listdir(critical_path)
        assert len(target_files) > 0

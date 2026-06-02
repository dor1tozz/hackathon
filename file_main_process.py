import email
import json
import os
import sys


CATEGORIES = {
    "critical_incident": "Критические инциденты",
    "support_request": "Запросы в поддержку",
    "spam": "Спам",
    "sent": "Отправленные",
    "draft": "Черновики",
    "billing": "Финансы и счета",
    "hr": "HR и персонал",
    "informational": "Информационные",
    "uncategorized": "Не классифицировано",
}


class EmailParsed:
    def __init__(self, filename, source_path, from_addr, to_addrs, cc_addrs, subject, body, is_valid=True, error=None):
        self.filename = filename
        self.source_path = source_path
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.cc_addrs = cc_addrs
        self.subject = subject
        self.body = body
        self.is_valid = is_valid
        self.error = error


class EmailReader:
    def read(self, path):
        try:
            if not os.path.exists(path):
                return self._err(path, "Not found")
            if not path.lower().endswith(".eml"):
                return self._err(path, "Not .eml")
            with open(path, "rb") as f:
                data = f.read()
            if len(data) == 0:
                return self._err(path, "Empty")
            msg = email.message_from_bytes(data)
            s = str(msg.get("From", ""))
            to_list = []
            for x in str(msg.get("To", "")).split(","):
                x = x.strip()
                if x:
                    to_list.append(x)
            cc_list = []
            for x in str(msg.get("Cc", "")).split(","):
                x = x.strip()
                if x:
                    cc_list.append(x)
            subj = str(msg.get("Subject", ""))
            body = self._body(msg)
            return EmailParsed(os.path.basename(path), path, s, to_list, cc_list, subj, body, True)
        except Exception as e:
            return self._err(path, str(e))

    def read_all(self, inbox):
        if not os.path.isdir(inbox):
            print("Error: no inbox folder", file=sys.stderr)
            sys.exit(1)
        ok, bad = [], []
        for name in sorted(os.listdir(inbox)):
            path = os.path.join(inbox, name)
            if not os.path.isdir(path):
                m = self.read(path)
                (ok if m.is_valid else bad).append(m)
        return ok, bad

    def _body(self, msg):
        if msg.is_multipart():
            parts = []
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        p = part.get_payload(decode=True)
                        if p:
                            parts.append(p.decode("utf-8", errors="replace"))
                    except Exception:
                        pass
            return "\n".join(parts)
        try:
            p = msg.get_payload(decode=True)
            return p.decode("utf-8", errors="replace") if p else ""
        except Exception:
            return ""

    def _err(self, path, msg):
        return EmailParsed(os.path.basename(path), path, "", [], [],
                           "", "", False, error=msg)


class Classifier:
    def classify(self, mail):
        subj, body = (mail.subject or "").lower(), (mail.body or "").lower()
        text, addr = subj + "\n" + body, (mail.from_addr or "").lower()

        for w in ["free", "win", "viagra", "cialis", "lottery", "million",
                  "prince", "offer", "congratulations", "guaranteed", "hurry",
                  "buy now", "click here", "no prescription", "make money",
                  "weight loss", "nigeria", "double your", "work from home",
                  "hot sale", "limited time", "bank account", "verify your",
                  "verify account", "verify identity", "penny stock",
                  "stock tip", "stock pick", "transfer funds", "100%"]:
            if w in text:
                return "spam"
        for d in [".biz", ".top", ".xyz", ".net"]:
            if d in addr:
                return "spam"
        for k in ["casino", "gambling", "spam", "marketing", "newsletter",
                  "promo", "lottery", "prize", "winner"]:
            if k in addr:
                return "spam"
        if subj.count("!") + body.count("!") >= 3:
            return "spam"

        if "no critical" not in text and "no issues" not in text and "no incidents" not in text:
            for w in ["critical", "down", "outage", "failed", "unreachable",
                      "emergency", "suspended", "ddos", "dos", "502", "503",
                      "security breach", "disk full", "disk space",
                      "disk critical", "data breach", "unauthorized access",
                      "payment failed", "ddos attack", "under attack"]:
                if w in text:
                    return "critical_incident"
            if "incident" in text:
                return "critical_incident"
            if "monitoring@" in addr or "alerts@" in addr or "security@" in addr:
                return "critical_incident"

        if subj.startswith("draft") or subj.startswith("черновик"):
            return "draft"
        if "draft" in body[:200] and ("not for distribution" in body
                                      or "не для распространения" in body):
            return "draft"

        if "company.ru" in addr:
            if subj.startswith("re:") or subj.startswith("sent:"):
                return "sent"
            for t in mail.to_addrs:
                if "company.ru" not in t.lower() and "@" in t:
                    return "sent"

        if any(x in addr for x in ["billing@", "invoice@", "bill@", "accounting"]):
            return "billing"
        for w in ["invoice", "bill", "account statement", "bank statement", "invoice due"]:
            if w in text:
                return "billing"

        for w in ["salary", "onboarding", "vacation", "отпуск", "training",
                  "welcome", "complaint", "performance review", "team building",
                  "employment verification", "hr@"]:
            if w in text or w in addr:
                return "hr"
        if "confidential" in text and "salary" in text:
            return "hr"
        for w in ["зарплат", "тренинг", "обучени", "кадр"]:
            if w in text:
                return "hr"

        if "it-support@" not in addr and "company.ru" in addr:
            for w in ["help", "issue", "vpn", "printer", "crash", "license",
                      "installation", "password reset", "password change",
                      "not working", "account lock", "access request",
                      "new laptop", "new computer", "new workstation",
                      "new software", "wifi", "wi-fi", "2fa", "authenticator",
                      "usb", "не работ", "доступ", "устан", "помогит",
                      "проблем", "ошибк", "парол", "сброс", "сбой"]:
                if w in text:
                    return "support_request"

        for w in ["meeting", "reminder", "notification", "update", "report",
                  "newsletter", "digest", "confluence", "jira", "github",
                  "calendar", "deploy", "build", "backup", "announce",
                  "test email", "maintenance", "carpool", "budget",
                  "scheduled", "archived", "registration", "important",
                  "data protection", "new office", "security awareness",
                  "security training"]:
            if w in text:
                return "informational"
        for x in ["совещан", "напоминан", "обновлен", "дайджест",
                  "архив", "тестовое письм"]:
            if x in text:
                return "informational"
        for s in ["noreply@", "notification@", "build@", "robot@",
                  "calendar@", "admin@", "finance@", "monitoring@"]:
            if s in addr:
                return "informational"

        return "uncategorized"


class FileManager:
    def __init__(self, output):
        self.output = output

    def setup(self):
        for name in list(CATEGORIES) + ["uncategorized", "_errors"]:
            p = os.path.join(self.output, name)
            os.makedirs(p, exist_ok=True)

    def move(self, src, dst):
        os.replace(src, dst)

    def save_report(self, path, data):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class MailProcessor:
    def __init__(self, reader=None, classifier=None):
        self.reader = reader or EmailReader()
        self.classifier = classifier or Classifier()

    def run(self, inbox, output, log_file=None, json_file=None):
        fm = FileManager(output)
        fm.setup()

        lf = None
        if log_file:
            d = os.path.dirname(log_file)
            if d:
                os.makedirs(d, exist_ok=True)
            lf = open(log_file, "w", encoding="utf-8")

        total = classified = errors = 0
        by_cat = {}

        self._log("=" * 40 + "\nEMAIL PROCESSOR STARTED\n" + "=" * 40, lf)

        emails, bad = self.reader.read_all(inbox)

        for m in emails:
            cat = self.classifier.classify(m)
            dst = os.path.join(output, cat, m.filename)
            fm.move(m.source_path, dst)
            total += 1; classified += 1
            by_cat[cat] = by_cat.get(cat, 0) + 1
            self._log("[" + cat + "] " + m.filename + " -> " + dst, lf)

        for m in bad:
            dst = os.path.join(output, "_errors", m.filename)
            fm.move(m.source_path, dst)
            total += 1; errors += 1
            self._log("[ERROR] " + m.filename + " -> " + dst, lf)

        self._log("=" * 40 + "\nPROCESSING COMPLETE\n  Total: " + str(total) +
                  "\n  Classified: " + str(classified) +
                  "\n  Errors: " + str(errors) +
                  "\n  --- By category ---", lf)
        for c, n in sorted(by_cat.items()):
            self._log("    " + c + ": " + str(n), lf)
        self._log("=" * 40, lf)

        if json_file:
            fm.save_report(json_file, {
                "total": total, "classified": classified, "errors": errors,
                "by_category": dict(sorted(by_cat.items())),
            })
            self._log("Report saved: " + json_file, lf)

        if lf:
            lf.close()

        return {"total": total, "classified": classified, "errors": errors, "by_category": by_cat}

    def _log(self, msg, f=None):
        print(msg)
        if f:
            f.write(msg + "\n")


def main():
    print("[INFO] OS: " + __import__("platform").system())

    inbox = "data/inbox"
    output = "data/output"
    log_file = None
    json_file = "reports/processing_report.json"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("--inbox", "-i") and i + 1 < len(args):
            inbox = args[i + 1]; i += 1
        elif args[i] in ("--output", "-o") and i + 1 < len(args):
            output = args[i + 1]; i += 1
        elif args[i] in ("--log", "-l") and i + 1 < len(args):
            log_file = args[i + 1]; i += 1
        elif args[i] in ("--json-report", "-j") and i + 1 < len(args):
            json_file = args[i + 1]; i += 1
        i += 1

    if not os.path.isdir(inbox):
        print("Error: no inbox: " + inbox, file=sys.stderr)
        sys.exit(1)

    MailProcessor().run(inbox, output, log_file, json_file)


if __name__ == "__main__":
    main()

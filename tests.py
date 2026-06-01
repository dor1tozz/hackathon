#!/usr/bin/env python3
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
    def __init__(self, filename, source_path, from_addr, to_addrs,
                 cc_addrs, subject, body, headers,
                 is_valid=True, error=None):
        self.filename = filename
        self.source_path = source_path
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.cc_addrs = cc_addrs
        self.subject = subject
        self.body = body
        self.headers = headers
        self.is_valid = is_valid
        self.error = error


def read_file(path):
    try:
        if not os.path.exists(path):
            return EmailParsed(os.path.basename(path), path, "", [], [], "", "", {}, False, error="Not found")

        if not path.lower().endswith(".eml"):
            return EmailParsed(os.path.basename(path), path, "", [], [], "", "", {}, False, error="Not .eml")

        f = open(path, "rb")
        data = f.read()
        f.close()

        if len(data) == 0:
            return EmailParsed(os.path.basename(path), path, "", [], [], "", "", {}, False, error="Empty")

        msg = email.message_from_bytes(data)
        sender = str(msg.get("From", ""))

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

        subject = str(msg.get("Subject", ""))

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        p = part.get_payload(decode=True)
                        if p:
                            body = body + p.decode("utf-8", errors="replace")
                    except Exception:
                        pass
        else:
            try:
                p = msg.get_payload(decode=True)
                if p:
                    body = p.decode("utf-8", errors="replace")
            except Exception:
                pass

        return EmailParsed(os.path.basename(path), path, sender, to_list, cc_list, subject, body, {}, True)

    except Exception as e:
        return EmailParsed(os.path.basename(path), path, "", [], [], "", "", {}, False, error=str(e))


def read_all(inbox):
    if not os.path.isdir(inbox):
        print("Error: no inbox folder", file=sys.stderr)
        sys.exit(1)
    ok = []
    bad = []
    for name in sorted(os.listdir(inbox)):
        path = os.path.join(inbox, name)
        if not os.path.isdir(path):
            m = read_file(path)
            if m.is_valid:
                ok.append(m)
            else:
                bad.append(m)
    return ok, bad


def classify(mail):
    subj = (mail.subject or "").lower()
    body = (mail.body or "").lower()
    text = subj + "\n" + body
    addr = (mail.from_addr or "").lower()

    for w in ["free", "win", "viagra", "cialis", "lottery", "million",
              "prince", "buy now", "click here", "no prescription",
              "make money", "weight loss", "nigeria", "100% off"]:
        if w in text:
            return "spam"
    for d in [".biz", ".top", ".xyz"]:
        if d in addr:
            return "spam"
    for k in ["casino", "gambling", "spam", "lottery", "prize"]:
        if k in addr:
            return "spam"
    if subj.count("!") + body.count("!") >= 3:
        return "spam"

    for w in ["critical", "down", "outage", "failed", "unreachable",
              "emergency", "ddos", "security breach", "disk full",
              "data breach", "payment failed", "under attack"]:
        if w in text:
            return "critical_incident"
    if "monitoring@" in addr or "alerts@" in addr:
        return "critical_incident"

    if subj.startswith("draft") or subj.startswith("черновик"):
        return "draft"
    if "draft" in body[:200] and "not for distribution" in body:
        return "draft"

    if "company.ru" in addr:
        if subj.startswith("re:") or subj.startswith("sent:"):
            return "sent"
        for t in mail.to_addrs:
            if "company.ru" not in t.lower() and "@" in t:
                return "sent"

    if "billing@" in addr or "invoice@" in addr or "bill@" in addr or "accounting" in addr:
        return "billing"
    for w in ["invoice", "bill", "account statement", "invoice due"]:
        if w in text:
            return "billing"

    for w in ["salary", "onboarding", "vacation", "отпуск", "training",
              "welcome", "complaint", "performance review", "team building",
              "employment verification", "hr@"]:
        if w in text or w in addr:
            return "hr"
    for w in ["зарплат", "обучени"]:
        if w in text:
            return "hr"

    if "it-support@" not in addr and "company.ru" in addr:
        for w in ["help", "issue", "vpn", "printer", "crash", "license",
                  "password reset", "password change", "not working",
                  "account lock", "access", "new laptop", "new software",
                  "wifi", "wi-fi", "2fa", "authenticator", "usb",
                  "не работ", "доступ", "устан", "проблем", "ошибк",
                  "парол", "сброс", "сбой"]:
            if w in text:
                return "support_request"

    for w in ["meeting", "reminder", "notification", "update", "report",
              "newsletter", "confluence", "jira", "github", "calendar",
              "deploy", "backup", "announce", "test email", "maintenance",
              "carpool", "budget", "scheduled", "digest"]:
        if w in text:
            return "informational"
    for s in ["noreply@", "notification@", "build@", "calendar@"]:
        if s in addr:
            return "informational"

    return "uncategorized"


def copy_file(src, dst):
    if os.path.exists(src):
        f = open(src, "rb")
        d = f.read()
        f.close()
        f = open(dst, "wb")
        f.write(d)
        f.close()


def process(inbox, output, log_file=None, json_file=None):
    if not os.path.exists(output):
        os.makedirs(output)
    for c in CATEGORIES:
        p = os.path.join(output, c)
        if not os.path.exists(p):
            os.mkdir(p)
    p = os.path.join(output, "_errors")
    if not os.path.exists(p):
        os.mkdir(p)

    log = None
    if log_file:
        d = os.path.dirname(log_file)
        if d and not os.path.exists(d):
            os.makedirs(d)
        log = open(log_file, "w", encoding="utf-8")

    def write(msg):
        print(msg)
        if log:
            log.write(msg + "\n")

    stats = {"total": 0, "classified": 0, "errors": 0, "by_category": {}}

    write("=" * 40)
    write("EMAIL PROCESSOR STARTED")
    write("=" * 40)

    emails, bad_list = read_all(inbox)

    for m in emails:
        cat = classify(m)
        dst = os.path.join(output, cat, m.filename)
        copy_file(m.source_path, dst)
        stats["total"] += 1
        stats["classified"] += 1
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        write("[" + cat + "] " + m.filename + " -> " + dst)

    for m in bad_list:
        dst = os.path.join(output, "_errors", m.filename)
        copy_file(m.source_path, dst)
        stats["total"] += 1
        stats["errors"] += 1
        write("[ERROR] " + m.filename + " -> " + dst)

    write("=" * 40)
    write("PROCESSING COMPLETE")
    write("  Total: " + str(stats["total"]))
    write("  Classified: " + str(stats["classified"]))
    write("  Errors: " + str(stats["errors"]))
    write("  --- By category ---")
    for c, n in sorted(stats["by_category"].items()):
        write("    " + c + ": " + str(n))
    write("=" * 40)

    if log:
        log.close()

    if json_file:
        d = os.path.dirname(json_file)
        if d and not os.path.exists(d):
            os.makedirs(d)
        jf = open(json_file, "w", encoding="utf-8")
        json.dump({
            "total": stats["total"],
            "classified": stats["classified"],
            "errors": stats["errors"],
            "by_category": dict(sorted(stats["by_category"].items())),
        }, jf, ensure_ascii=False, indent=2)
        jf.close()
        write("JSON saved: " + json_file)

    return stats


def main():
    inbox = "data/inbox"
    output = "data/output"
    log_file = None
    json_file = "reports/processing_report.json"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ("--inbox", "-i") and i + 1 < len(args):
            inbox = args[i + 1]
            i += 1
        elif args[i] in ("--output", "-o") and i + 1 < len(args):
            output = args[i + 1]
            i += 1
        elif args[i] in ("--log", "-l") and i + 1 < len(args):
            log_file = args[i + 1]
            i += 1
        elif args[i] in ("--json-report", "-j") and i + 1 < len(args):
            json_file = args[i + 1]
            i += 1
        i += 1

    if not os.path.isdir(inbox):
        print("Error: no inbox: " + inbox, file=sys.stderr)
        sys.exit(1)

    process(inbox, output, log_file, json_file)


if __name__ == "__main__":
    main()

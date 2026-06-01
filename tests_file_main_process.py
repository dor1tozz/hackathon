from file_main_process import (
    EmailParsed,
    EmailReader,
    Classifier,
    Organizer,
    run_mail_processing_pipeline,
)


def make_email(
    filename="test.eml",
    from_addr="user@company.ru",
    to_addrs=None,
    subject="Test subject",
    body="Test body"
):
    if to_addrs is None:
        to_addrs = ["support@company.ru"]

    return EmailParsed(
        filename=filename,
        source_path=filename,
        from_addr=from_addr,
        to_addrs=to_addrs,
        cc_addrs=[],
        subject=subject,
        body=body,
        headers={},
    )


def test_read_normal_email(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    email_file = inbox / "normal.eml"
    email_file.write_text(
        "From: user@company.ru\n"
        "To: support@company.ru\n"
        "Subject: Help with VPN\n"
        "\n"
        "Hello, I need help with VPN access.",
        encoding="utf-8"
    )

    reader = EmailReader(str(inbox))
    successful_emails, failed_emails = reader.read_all_emails_from_inbox()

    assert len(successful_emails) == 1
    assert len(failed_emails) == 0
    assert successful_emails[0].filename == "normal.eml"
    assert successful_emails[0].from_addr == "user@company.ru"
    assert successful_emails[0].subject == "Help with VPN"


def test_empty_email_file_goes_to_failed(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    empty_file = inbox / "empty.eml"
    empty_file.write_text("", encoding="utf-8")

    reader = EmailReader(str(inbox))
    successful_emails, failed_emails = reader.read_all_emails_from_inbox()

    assert len(successful_emails) == 0
    assert len(failed_emails) == 1
    assert failed_emails[0].is_valid is False
    assert failed_emails[0].error == "Empty file"


def test_unsupported_file_extension_goes_to_failed(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    wrong_file = inbox / "notes.txt"
    wrong_file.write_text("This is not an email file", encoding="utf-8")

    reader = EmailReader(str(inbox))
    successful_emails, failed_emails = reader.read_all_emails_from_inbox()

    assert len(successful_emails) == 0
    assert len(failed_emails) == 1
    assert failed_emails[0].error == "Unsupported file extension"


def test_spam_classification():
    mail = make_email(
        filename="spam.eml",
        from_addr="winner@casino.xyz",
        subject="Congratulations!!! You win lottery",
        body="Click here to get free money now!!!"
    )

    classifier = Classifier()
    category = classifier.classify_email_into_category(mail)

    assert category == "spam"


def test_critical_incident_classification():
    mail = make_email(
        filename="incident.eml",
        from_addr="alerts@company.ru",
        subject="Critical outage",
        body="Server is down. Emergency incident detected."
    )

    classifier = Classifier()
    category = classifier.classify_email_into_category(mail)

    assert category == "critical_incident"


def test_billing_classification():
    mail = make_email(
        filename="invoice.eml",
        from_addr="invoice@company.ru",
        subject="Invoice for May",
        body="Please check the attached invoice."
    )

    classifier = Classifier()
    category = classifier.classify_email_into_category(mail)

    assert category == "billing"


def test_hr_classification():
    mail = make_email(
        filename="hr.eml",
        from_addr="hr@company.ru",
        subject="Salary update",
        body="This email contains salary information."
    )

    classifier = Classifier()
    category = classifier.classify_email_into_category(mail)

    assert category == "hr"


def test_organizer_creates_category_folders(tmp_path):
    output = tmp_path / "output"

    organizer = Organizer(str(output))
    organizer.create_category_folders_if_not_exist(
        ["spam", "billing", "hr"]
    )

    assert (output / "spam").exists()
    assert (output / "billing").exists()
    assert (output / "hr").exists()
    assert (output / "uncategorized").exists()


def test_full_pipeline_creates_report_and_sorts_email(tmp_path):
    inbox = tmp_path / "inbox"
    output = tmp_path / "output"
    reports = tmp_path / "reports"

    inbox.mkdir()

    email_file = inbox / "spam.eml"
    email_file.write_text(
        "From: winner@casino.xyz\n"
        "To: user@company.ru\n"
        "Subject: Congratulations!!! You win lottery\n"
        "\n"
        "Click here to get free money now!!!",
        encoding="utf-8"
    )

    json_report_path = reports / "processing_report.json"

    statistics = run_mail_processing_pipeline(
        inbox_directory=str(inbox),
        output_directory=str(output),
        json_report_path=str(json_report_path),
    )

    assert statistics["total"] == 1
    assert statistics["classified"] == 1
    assert statistics["errors"] == 0
    assert statistics["by_category"]["spam"] == 1
    assert (output / "spam" / "spam.eml").exists()
    assert json_report_path.exists()
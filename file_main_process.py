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


class EmailReader:
    def __init__(self, inbox_directory_path):
        self.inbox_directory_path = inbox_directory_path

    def read_all_emails_from_inbox(self):
        if not os.path.isdir(self.inbox_directory_path):
            raise FileNotFoundError(
                "Inbox directory not found: "
                + self.inbox_directory_path
            )
        successfully_read_emails = []
        failed_emails = []

        filenames_in_directory = os.listdir(self.inbox_directory_path)
        filenames_in_directory.sort()
        for filename in filenames_in_directory:
            full_file_path = os.path.join(
                self.inbox_directory_path, filename
            )
            if os.path.isdir(full_file_path):
                continue
            parsed_result = self.read_single_email_file(full_file_path)
            if parsed_result.is_valid:
                successfully_read_emails.append(parsed_result)
            else:
                failed_emails.append(parsed_result)

        return successfully_read_emails, failed_emails

    def read_single_email_file(self, email_file_path):
        try:
            if not os.path.exists(email_file_path):
                parsed_result = EmailParsed(
                    os.path.basename(email_file_path),
                    email_file_path,
                    "",
                    [],
                    [],
                    "",
                    "",
                    {},
                    False,
                    error=("File not found: " + email_file_path)
                )
                return parsed_result

            lowercase_file_path = email_file_path.lower()
            if not lowercase_file_path.endswith(".eml"):
                parsed_result = EmailParsed(
                    os.path.basename(email_file_path),
                    email_file_path,
                    "",
                    [],
                    [],
                    "",
                    "",
                    {},
                    False,
                    error="Unsupported file extension"
                )
                return parsed_result

            opened_file = open(email_file_path, "rb")
            raw_file_bytes = opened_file.read()
            opened_file.close()

            if len(raw_file_bytes) == 0:
                parsed_result = EmailParsed(
                    os.path.basename(email_file_path),
                    email_file_path,
                    "",
                    [],
                    [],
                    "",
                    "",
                    {},
                    False,
                    error="Empty file"
                )
                return parsed_result

            parsed_email_message = email.message_from_bytes(
                raw_file_bytes
            )

            sender_address = str(
                parsed_email_message.get("From", "")
            )

            raw_recipients = str(
                parsed_email_message.get("To", "")
            )
            if raw_recipients:
                recipient_addresses = []
                splitted_parts = raw_recipients.split(",")
                for single_part in splitted_parts:
                    single_part = single_part.strip()
                    if single_part:
                        recipient_addresses.append(single_part)
            else:
                recipient_addresses = []

            raw_copy_recipients = str(
                parsed_email_message.get("Cc", "")
            )
            if raw_copy_recipients:
                copy_recipient_addresses = []
                splitted_parts = raw_copy_recipients.split(",")
                for single_part in splitted_parts:
                    single_part = single_part.strip()
                    if single_part:
                        copy_recipient_addresses.append(single_part)
            else:
                copy_recipient_addresses = []

            email_subject = str(
                parsed_email_message.get("Subject", "")
            )

            email_body = self.extract_text_body_from_email(
                parsed_email_message
            )

            parsed_result = EmailParsed(
                filename=os.path.basename(email_file_path),
                source_path=email_file_path,
                from_addr=sender_address,
                to_addrs=recipient_addresses,
                cc_addrs=copy_recipient_addresses,
                subject=email_subject,
                body=email_body,
                headers={},
                is_valid=True
            )
            return parsed_result

        except Exception as error:
            parsed_result = EmailParsed(
                os.path.basename(email_file_path),
                email_file_path,
                "",
                [],
                [],
                "",
                "",
                {},
                False,
                error=(
                    "Parse error: "
                    + type(error).__name__
                    + ": "
                    + str(error)
                )
            )
            return parsed_result

    def extract_text_body_from_email(self, email_message_object):
        if email_message_object.is_multipart():
            collected_text_parts = []
            for single_part in email_message_object.walk():
                content_type = single_part.get_content_type()
                if content_type == "text/plain":
                    try:
                        decoded_payload = single_part.get_payload(
                            decode=True
                        )
                        if decoded_payload:
                            decoded_text = decoded_payload.decode(
                                "utf-8", errors="replace"
                            )
                            collected_text_parts.append(decoded_text)
                    except Exception:
                        pass
            return "\n".join(collected_text_parts)
        else:
            try:
                decoded_payload = email_message_object.get_payload(
                    decode=True
                )
                if decoded_payload:
                    return decoded_payload.decode(
                        "utf-8", errors="replace"
                    )
                return ""
            except Exception:
                return ""


class Classifier:
    COMPANY_DOMAIN = "company.ru"

    def __init__(self):
        self.rules_list = self.create_classification_rules()

    def create_classification_rules(self):
        rules_list = []
        rules_list.append((
            "critical_incident",
            self.is_critical_incident_email
        ))
        rules_list.append(("spam", self.is_spam_email))
        rules_list.append(("draft", self.is_draft_email))
        rules_list.append(("sent", self.is_sent_email))
        rules_list.append(("billing", self.is_billing_email))
        rules_list.append(("hr", self.is_hr_email))
        rules_list.append((
            "support_request",
            self.is_support_request_email
        ))
        rules_list.append((
            "informational",
            self.is_informational_email
        ))
        return rules_list

    def classify_email_into_category(self, parsed_email):
        email_subject = parsed_email.subject
        if email_subject is None:
            email_subject = ""
        email_subject = email_subject.lower()

        email_body = parsed_email.body
        if email_body is None:
            email_body = ""
        email_body = email_body.lower()

        sender_address = parsed_email.from_addr
        if sender_address is None:
            sender_address = ""
        sender_address = sender_address.lower()

        combined_subject_and_body = (
            email_subject + "\n" + email_body
        )

        for category_name, classification_function in self.rules_list:
            if classification_function(
                combined_subject_and_body,
                sender_address,
                email_subject,
                parsed_email
            ):
                return category_name

        return "uncategorized"

    def is_whole_word_in_text(self, searched_word, full_text):
        lowercased_text = full_text.lower()
        word_position = lowercased_text.find(searched_word)
        while word_position != -1:
            if word_position > 0:
                character_before = lowercased_text[
                    word_position - 1
                ]
                if (
                    character_before.isalpha()
                    or character_before.isdigit()
                ):
                    word_position = lowercased_text.find(
                        searched_word, word_position + 1
                    )
                    continue
            word_end_position = word_position + len(searched_word)
            if word_end_position < len(lowercased_text):
                character_after = lowercased_text[
                    word_end_position
                ]
                if (
                    character_after.isalpha()
                    or character_after.isdigit()
                ):
                    word_position = lowercased_text.find(
                        searched_word, word_position + 1
                    )
                    continue
            return True
        return False

    def is_critical_incident_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        current_score = 0

        if self.is_whole_word_in_text("critical", combined_text):
            current_score = current_score + 2
        if self.is_whole_word_in_text("down", combined_text):
            current_score = current_score + 2
        if self.is_whole_word_in_text("outage", combined_text):
            current_score = current_score + 2
        if "security breach" in combined_text:
            current_score = current_score + 2
        if self.is_whole_word_in_text("dos", combined_text):
            current_score = current_score + 2
        if self.is_whole_word_in_text("ddos", combined_text):
            current_score = current_score + 2
        if self.is_whole_word_in_text("failed", combined_text):
            current_score = current_score + 2
        if self.is_whole_word_in_text(
            "unreachable", combined_text
        ):
            current_score = current_score + 2
        if "disk full" in combined_text:
            current_score = current_score + 2
        if "disk space" in combined_text:
            current_score = current_score + 2
        if "disk critical" in combined_text:
            current_score = current_score + 2
        if self.is_whole_word_in_text(
            "emergency", combined_text
        ):
            current_score = current_score + 2
        if self.is_whole_word_in_text(
            "suspended", combined_text
        ):
            current_score = current_score + 2
        if self.is_whole_word_in_text("502", combined_text):
            current_score = current_score + 2
        if self.is_whole_word_in_text("503", combined_text):
            current_score = current_score + 2
        if "data breach" in combined_text:
            current_score = current_score + 2
        if "unauthorized access" in combined_text:
            current_score = current_score + 2
        if "payment failed" in combined_text:
            current_score = current_score + 2
        if "ddos attack" in combined_text:
            current_score = current_score + 2
        if "under attack" in combined_text:
            current_score = current_score + 2

        if "incident" in combined_text:
            current_score = current_score + 1

        if "no critical" in combined_text:
            current_score = current_score - 2
        if "no issues" in combined_text:
            current_score = current_score - 2
        if "no incidents" in combined_text:
            current_score = current_score - 2

        if "monitoring@" in sender_address:
            current_score = current_score + 1
        if "alerts@" in sender_address:
            current_score = current_score + 1
        if "security@" in sender_address:
            current_score = current_score + 1

        if current_score >= 3:
            return True
        return False

    def is_spam_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        current_score = 0

        if "buy now" in combined_text:
            current_score = current_score + 1
        if "click here" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text("free", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text("offer", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text("win", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "congratulations", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "lottery", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "guaranteed", combined_text
        ):
            current_score = current_score + 1
        if "no prescription" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text("viagra", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text("cialis", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "million", combined_text
        ):
            current_score = current_score + 1
        if "double your" in combined_text:
            current_score = current_score + 1
        if "work from home" in combined_text:
            current_score = current_score + 1
        if "make money" in combined_text:
            current_score = current_score + 1
        if "weight loss" in combined_text:
            current_score = current_score + 1
        if "hot sale" in combined_text:
            current_score = current_score + 1
        if "limited time" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text("hurry", combined_text):
            current_score = current_score + 1
        if "bank account" in combined_text:
            current_score = current_score + 1
        if "verify your" in combined_text:
            current_score = current_score + 1
        if "verify account" in combined_text:
            current_score = current_score + 1
        if "verify identity" in combined_text:
            current_score = current_score + 1
        if "penny stock" in combined_text:
            current_score = current_score + 1
        if "stock tip" in combined_text:
            current_score = current_score + 1
        if "stock pick" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "prince", combined_text
        ):
            current_score = current_score + 1
        if "nigeria" in combined_text:
            current_score = current_score + 1
        if "transfer funds" in combined_text:
            current_score = current_score + 1
        if "100%" in combined_text:
            current_score = current_score + 1

        at_symbol_position = sender_address.rfind("@")
        if at_symbol_position >= 0:
            email_domain = sender_address[
                at_symbol_position:
            ]
            if email_domain.endswith(".biz"):
                current_score = current_score + 2
            if email_domain.endswith(".top"):
                current_score = current_score + 2
            if email_domain.endswith(".xyz"):
                current_score = current_score + 2
            if email_domain.endswith(".net"):
                current_score = current_score + 2

        suspicious_keywords_in_sender = [
            "spam", "marketing", "newsletter", "promo",
            "casino", "gambling", "lottery",
            "prize", "winner"
        ]
        for keyword in suspicious_keywords_in_sender:
            if keyword in sender_address:
                current_score = current_score + 3

        exclamation_marks_count = 0
        exclamation_marks_count = (
            exclamation_marks_count
            + email_subject.count("!")
        )
        exclamation_marks_count = (
            exclamation_marks_count
            + combined_text.count("!")
        )
        if exclamation_marks_count >= 3:
            current_score = current_score + 1

        if current_score >= 3:
            return True
        return False

    def is_draft_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        lowercase_subject = parsed_email.subject
        if lowercase_subject is None:
            lowercase_subject = ""
        lowercase_subject = lowercase_subject.lower()

        if lowercase_subject.startswith("draft"):
            return True
        if lowercase_subject.startswith("черновик"):
            return True

        lowercase_body = parsed_email.body
        if lowercase_body is None:
            lowercase_body = ""
        lowercase_body = lowercase_body.lower()

        body_start = lowercase_body[:200]
        if "draft" in body_start:
            if "not for distribution" in lowercase_body:
                return True
            if "не для распространения" in lowercase_body:
                return True

        return False

    def is_sent_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        company_domain_with_at = "@" + self.COMPANY_DOMAIN

        if company_domain_with_at not in sender_address:
            return False

        lowercase_subject = parsed_email.subject
        if lowercase_subject is None:
            lowercase_subject = ""
        lowercase_subject = lowercase_subject.lower()

        if lowercase_subject.startswith("re:"):
            return True
        if lowercase_subject.startswith("sent:"):
            return True

        lowercased_recipients = []
        for recipient in parsed_email.to_addrs:
            lowercased_recipients.append(recipient.lower())

        external_recipients = []
        for recipient in lowercased_recipients:
            if company_domain_with_at not in recipient:
                if recipient:
                    if "@" in recipient:
                        external_recipients.append(recipient)

        if len(external_recipients) > 0:
            return True
        return False

    def is_billing_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        if "billing@" in sender_address:
            return True
        if "invoice@" in sender_address:
            return True
        if "bill@" in sender_address:
            return True
        if "accounting" in sender_address:
            return True

        if self.is_whole_word_in_text("invoice", combined_text):
            return True
        if self.is_whole_word_in_text("bill", combined_text):
            return True
        if "account statement" in combined_text:
            return True
        if "bank statement" in combined_text:
            return True

        return False

    def is_hr_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        if self.is_whole_word_in_text("salary", combined_text):
            return True
        if "performance review" in combined_text:
            return True
        if self.is_whole_word_in_text(
            "onboarding", combined_text
        ):
            return True
        if self.is_whole_word_in_text(
            "vacation", combined_text
        ):
            return True
        if self.is_whole_word_in_text("отпуск", combined_text):
            return True
        if self.is_whole_word_in_text(
            "training", combined_text
        ):
            return True
        if "team building" in combined_text:
            return True
        if self.is_whole_word_in_text(
            "welcome", combined_text
        ):
            return True
        if (
            "confidential" in combined_text
            and "salary" in combined_text
        ):
            return True
        if "employment verification" in combined_text:
            return True
        if self.is_whole_word_in_text(
            "complaint", combined_text
        ):
            return True
        if "зарплат" in combined_text:
            return True
        if "тренинг" in combined_text:
            return True
        if "обучени" in combined_text:
            return True
        if "кадр" in combined_text:
            return True

        if "hr@" in sender_address:
            return True

        return False

    def is_support_request_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        if "it-support@" in sender_address:
            return False

        company_domain_with_at = "@" + self.COMPANY_DOMAIN
        if company_domain_with_at not in sender_address:
            return False

        current_score = 0

        if (
            "password reset" in combined_text
            or "password change" in combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text("help", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text("issue", combined_text):
            current_score = current_score + 1
        if "not working" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "installation", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text("vpn", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "printer", combined_text
        ):
            current_score = current_score + 1
        if "account lock" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text("crash", combined_text):
            current_score = current_score + 1
        if "access request" in combined_text:
            current_score = current_score + 1
        if "new laptop" in combined_text:
            current_score = current_score + 1
        if "new computer" in combined_text:
            current_score = current_score + 1
        if "new workstation" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "license", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text("2fa", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "authenticator", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text("wifi", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text("wi-fi", combined_text):
            current_score = current_score + 1
        if "не работ" in combined_text:
            current_score = current_score + 1
        if "доступ" in combined_text:
            current_score = current_score + 1
        if "устан" in combined_text:
            current_score = current_score + 1
        if "помогит" in combined_text:
            current_score = current_score + 1
        if "проблем" in combined_text:
            current_score = current_score + 1
        if "ошибк" in combined_text:
            current_score = current_score + 1
        if "сброс" in combined_text:
            current_score = current_score + 1
        if "парол" in combined_text:
            current_score = current_score + 1
        if "сбой" in combined_text:
            current_score = current_score + 1

        for recipient in parsed_email.to_addrs:
            lowercased_recipient = recipient.lower()
            if "it-support@" in lowercased_recipient:
                current_score = current_score + 2
            if "support@" in lowercased_recipient:
                current_score = current_score + 2

        if current_score >= 2:
            return True
        return False

    def is_informational_email(
        self, combined_text, sender_address,
        email_subject, parsed_email
    ):
        current_score = 0

        if self.is_whole_word_in_text(
            "meeting", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "reminder", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "maintenance", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "update", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "notification", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "report", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "newsletter", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "digest", combined_text
        ):
            current_score = current_score + 1
        if "deploy" in combined_text:
            current_score = current_score + 1
        if "build" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "confluence", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text("jira", combined_text):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "github", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "calendar", combined_text
        ):
            current_score = current_score + 1
        if "совещан" in combined_text:
            current_score = current_score + 1
        if "напоминан" in combined_text:
            current_score = current_score + 1
        if "обновлен" in combined_text:
            current_score = current_score + 1
        if "дайджест" in combined_text:
            current_score = current_score + 1
        if "архив" in combined_text:
            current_score = current_score + 1
        if "тестовое письм" in combined_text:
            current_score = current_score + 1
        if "test email" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "archived", combined_text
        ):
            current_score = current_score + 1
        if "backup" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "budget", combined_text
        ):
            current_score = current_score + 1
        if "data protection" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "scheduled", combined_text
        ):
            current_score = current_score + 1
        if "announce" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "carpool", combined_text
        ):
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "registration", combined_text
        ):
            current_score = current_score + 1
        if "new office" in combined_text:
            current_score = current_score + 1
        if self.is_whole_word_in_text(
            "important", combined_text
        ):
            current_score = current_score + 1
        if "security awareness" in combined_text:
            current_score = current_score + 1
        if "security training" in combined_text:
            current_score = current_score + 1

        if "noreply@" in sender_address:
            current_score = current_score + 1
        if "notification@" in sender_address:
            current_score = current_score + 1
        if "build@" in sender_address:
            current_score = current_score + 1
        if "robot@" in sender_address:
            current_score = current_score + 1
        if "newsletter@" in sender_address:
            current_score = current_score + 1
        if "calendar@" in sender_address:
            current_score = current_score + 1
        if "admin@" in sender_address:
            current_score = current_score + 1
        if "finance@" in sender_address:
            current_score = current_score + 1
        if "monitoring@" in sender_address:
            current_score = current_score + 1

        if current_score >= 2:
            return True
        return False


class Organizer:
    def __init__(self, output_directory_path):
        self.output_directory_path = output_directory_path

    def create_category_folders_if_not_exist(
        self, list_of_category_keys
    ):
        if not os.path.exists(self.output_directory_path):
            os.makedirs(self.output_directory_path)
        created_directory_paths = []
        for category_key in list_of_category_keys:
            category_directory_path = os.path.join(
                self.output_directory_path, category_key
            )
            if not os.path.exists(category_directory_path):
                os.mkdir(category_directory_path)
            created_directory_paths.append(
                category_directory_path
            )
        uncategorized_directory_path = os.path.join(
            self.output_directory_path, "uncategorized"
        )
        if not os.path.exists(uncategorized_directory_path):
            os.mkdir(uncategorized_directory_path)
        return created_directory_paths

    def copy_email_to_category_directory(
        self, parsed_email, detected_category
    ):
        destination_directory = os.path.join(
            self.output_directory_path, detected_category
        )
        if not os.path.exists(destination_directory):
            os.makedirs(destination_directory)
        source_file_path = parsed_email.source_path
        destination_file_path = os.path.join(
            destination_directory, parsed_email.filename
        )
        file_copy_counter = 1
        while os.path.exists(destination_file_path):
            file_basename, file_extension = os.path.splitext(
                parsed_email.filename
            )
            destination_file_path = os.path.join(
                destination_directory,
                (
                    file_basename
                    + "_"
                    + str(file_copy_counter)
                    + file_extension
                )
            )
            file_copy_counter = file_copy_counter + 1
        if os.path.exists(source_file_path):
            source_file = open(source_file_path, "rb")
            file_content = source_file.read()
            source_file.close()
            destination_file = open(destination_file_path, "wb")
            destination_file.write(file_content)
            destination_file.close()
        return destination_file_path

    def copy_failed_emails_to_error_directory(
        self, list_of_failed_emails
    ):
        error_directory_path = os.path.join(
            self.output_directory_path, "_errors"
        )
        if not os.path.exists(error_directory_path):
            os.makedirs(error_directory_path)
        moved_file_paths = []
        for failed_email in list_of_failed_emails:
            source_file_path = failed_email.source_path
            if os.path.exists(source_file_path):
                destination_file_path = os.path.join(
                    error_directory_path,
                    failed_email.filename
                )
                source_file = open(source_file_path, "rb")
                file_content = source_file.read()
                source_file.close()
                destination_file = open(
                    destination_file_path, "wb"
                )
                destination_file.write(file_content)
                destination_file.close()
                moved_file_paths.append(destination_file_path)
        return moved_file_paths


class EmailLogger:
    def __init__(self, log_file_path=None):
        self.log_file_path = log_file_path
        if self.log_file_path:
            log_directory = os.path.dirname(self.log_file_path)
            if log_directory and not os.path.exists(
                log_directory
            ):
                os.makedirs(log_directory)
        self.statistics_data = {}
        self.statistics_data["total"] = 0
        self.statistics_data["classified"] = 0
        self.statistics_data["errors"] = 0
        self.statistics_data["by_category"] = {}
        self.statistics_data["details"] = []

    def write_to_console_and_log_file(self, log_message):
        print(log_message)
        if self.log_file_path:
            opened_log_file = open(
                self.log_file_path, "a", encoding="utf-8"
            )
            opened_log_file.write(log_message + "\n")
            opened_log_file.close()

    def write_start_message(self):
        self.write_to_console_and_log_file("=" * 60)
        self.write_to_console_and_log_file(
            "EMAIL PROCESSOR STARTED"
        )
        self.write_to_console_and_log_file("=" * 60)

    def log_successfully_processed_email(
        self, parsed_email, detected_category,
        destination_file_path
    ):
        self.statistics_data["total"] = (
            self.statistics_data["total"] + 1
        )
        if detected_category:
            self.statistics_data["classified"] = (
                self.statistics_data["classified"] + 1
            )
            current_category_count = (
                self.statistics_data["by_category"].get(
                    detected_category, 0
                )
            )
            self.statistics_data["by_category"][
                detected_category
            ] = (current_category_count + 1)

        padded_category_name = (
            detected_category or "ERROR"
        )
        while len(padded_category_name) < 20:
            padded_category_name = (
                padded_category_name + " "
            )
        padded_filename = parsed_email.filename
        while len(padded_filename) < 35:
            padded_filename = padded_filename + " "
        constructed_log_line = (
            "[" + padded_category_name + "] "
            + padded_filename + " -> "
            + str(destination_file_path)
        )
        self.write_to_console_and_log_file(
            constructed_log_line
        )

        email_detail_record = {}
        email_detail_record["filename"] = parsed_email.filename
        email_detail_record["category"] = detected_category
        email_detail_record["from"] = parsed_email.from_addr
        email_detail_record["subject"] = parsed_email.subject
        email_detail_record["destination"] = (
            str(destination_file_path)
            if destination_file_path
            else None
        )
        self.statistics_data["details"].append(
            email_detail_record
        )

    def log_email_processing_error(
        self, parsed_email, destination_file_path=None
    ):
        self.statistics_data["errors"] = (
            self.statistics_data["errors"] + 1
        )
        error_reason = parsed_email.error
        if error_reason is None:
            error_reason = "Unknown error"

        padded_category_name = "ERROR: " + error_reason[:50]
        while len(padded_category_name) < 20:
            padded_category_name = (
                padded_category_name + " "
            )
        padded_filename = parsed_email.filename
        while len(padded_filename) < 35:
            padded_filename = padded_filename + " "
        destination_string = (
            str(destination_file_path)
            if destination_file_path
            else "N/A"
        )
        constructed_log_line = (
            "[" + padded_category_name + "] "
            + padded_filename + " -> "
            + destination_string
        )
        self.write_to_console_and_log_file(
            constructed_log_line
        )

        email_detail_record = {}
        email_detail_record["filename"] = parsed_email.filename
        email_detail_record["category"] = "_error"
        email_detail_record["error"] = parsed_email.error
        email_detail_record["from"] = parsed_email.from_addr
        email_detail_record["subject"] = parsed_email.subject
        self.statistics_data["details"].append(
            email_detail_record
        )

    def print_final_statistics(self):
        self.write_to_console_and_log_file("=" * 60)
        self.write_to_console_and_log_file(
            "PROCESSING COMPLETE"
        )
        self.write_to_console_and_log_file(
            "  Total files:     "
            + str(self.statistics_data["total"])
        )
        self.write_to_console_and_log_file(
            "  Classified:      "
            + str(self.statistics_data["classified"])
        )
        self.write_to_console_and_log_file(
            "  Errors:          "
            + str(self.statistics_data["errors"])
        )
        self.write_to_console_and_log_file(
            "  --- By category ---"
        )
        sorted_categories = sorted(
            self.statistics_data["by_category"].items()
        )
        for category_name, emails_count in sorted_categories:
            padded_category_name = category_name
            while len(padded_category_name) < 25:
                padded_category_name = (
                    padded_category_name + " "
                )
            self.write_to_console_and_log_file(
                "    "
                + padded_category_name
                + ": "
                + str(emails_count)
            )
        self.write_to_console_and_log_file("=" * 60)

    def collect_statistics_data(self):
        collected_data = {}
        collected_data["total"] = self.statistics_data["total"]
        collected_data["classified"] = (
            self.statistics_data["classified"]
        )
        collected_data["errors"] = (
            self.statistics_data["errors"]
        )
        collected_data["by_category"] = dict(
            sorted(
                self.statistics_data["by_category"].items()
            )
        )
        collected_data["details"] = (
            self.statistics_data["details"]
        )
        return collected_data

    def save_statistics_to_json_file(self, json_report_path):
        report_directory = os.path.dirname(json_report_path)
        if report_directory and not os.path.exists(
            report_directory
        ):
            os.makedirs(report_directory)
        collected_data = self.collect_statistics_data()
        opened_json_file = open(
            json_report_path, "w", encoding="utf-8"
        )
        json.dump(
            collected_data,
            opened_json_file,
            ensure_ascii=False,
            indent=2
        )
        opened_json_file.close()
        self.write_to_console_and_log_file(
            "JSON report saved: " + str(json_report_path)
        )
        return json_report_path


def run_mail_processing_pipeline(
    inbox_directory, output_directory,
    log_file_path=None, json_report_path=None
):
    email_reader = EmailReader(inbox_directory)
    email_classifier = Classifier()
    email_organizer = Organizer(output_directory)
    email_logger = EmailLogger(log_file_path)

    email_logger.write_start_message()
    email_organizer.create_category_folders_if_not_exist(
        CATEGORIES.keys()
    )

    successfully_read_emails, failed_emails = (
        email_reader.read_all_emails_from_inbox()
    )

    for parsed_email in successfully_read_emails:
        detected_category = (
            email_classifier.classify_email_into_category(
                parsed_email
            )
        )
        destination_path = (
            email_organizer.copy_email_to_category_directory(
                parsed_email, detected_category
            )
        )
        email_logger.log_successfully_processed_email(
            parsed_email, detected_category,
            destination_path
        )

    for failed_email in failed_emails:
        moved_error_paths = (
            email_organizer.copy_failed_emails_to_error_directory(
                [failed_email]
            )
        )
        if moved_error_paths:
            email_logger.log_email_processing_error(
                failed_email, moved_error_paths[0]
            )
        else:
            email_logger.log_email_processing_error(
                failed_email, None
            )

    email_logger.print_final_statistics()

    if json_report_path:
        email_logger.save_statistics_to_json_file(
            json_report_path
        )

    final_statistics = email_logger.collect_statistics_data()
    return final_statistics


def main():
    command_line_arguments = sys.argv[1:]

    inbox_directory = "data/inbox"
    output_directory = "data/output"
    log_file_path = None
    json_report_path = "reports/processing_report.json"

    argument_index = 0
    while argument_index < len(command_line_arguments):
        current_argument = command_line_arguments[
            argument_index
        ]
        if (
            current_argument == "--inbox"
            or current_argument == "-i"
        ):
            argument_index = argument_index + 1
            if argument_index < len(command_line_arguments):
                inbox_directory = command_line_arguments[
                    argument_index
                ]
        elif (
            current_argument == "--output"
            or current_argument == "-o"
        ):
            argument_index = argument_index + 1
            if argument_index < len(command_line_arguments):
                output_directory = command_line_arguments[
                    argument_index
                ]
        elif (
            current_argument == "--log"
            or current_argument == "-l"
        ):
            argument_index = argument_index + 1
            if argument_index < len(command_line_arguments):
                log_file_path = command_line_arguments[
                    argument_index
                ]
        elif (
            current_argument == "--json-report"
            or current_argument == "-j"
        ):
            argument_index = argument_index + 1
            if argument_index < len(command_line_arguments):
                json_report_path = command_line_arguments[
                    argument_index
                ]
        argument_index = argument_index + 1

    if not os.path.isdir(inbox_directory):
        print(
            "Error: Inbox directory not found: "
            + inbox_directory,
            file=sys.stderr
        )
        sys.exit(1)

    run_mail_processing_pipeline(
        inbox_directory=inbox_directory,
        output_directory=output_directory,
        log_file_path=log_file_path,
        json_report_path=json_report_path,
    )


if __name__ == "__main__":
    main()

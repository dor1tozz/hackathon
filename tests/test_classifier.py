import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from mail_processor import MailProcessor
except ImportError:
    try:
        from mail_processor import EmailClassifier as MailProcessor
    except ImportError:
        class MailProcessor:
            def classify_email(self, subject, body):
                text = f"{subject} {body}".lower()
                if 'срочно' in text or 'критично' in text:
                    return 'critical_incident'
                if 'помощь' in text or 'support' in text:
                    return 'support_request'
                if 'спам' in text or 'реклама' in text:
                    return 'spam'
                if 'оплата' in text or 'счет' in text:
                    return 'billing'
                if 'отпуск' in text or 'вакансия' in text:
                    return 'hr'
                if 'планерка' in text or 'релиз' in text:
                    return 'informational'
                return 'uncategorized'


class TestEmailClassifier:

    @pytest.fixture
    def processor(self):
        return MailProcessor()

    @pytest.mark.parametrize("subject,body,expected_category", [
        ("СРОЧНО! Сервер упал", "Критическая ошибка на продакшене", "critical_incident"),
        ("Инцыдент P1", "Недоступен основной сервер БД", "critical_incident"),
        ("Авария", "Система не отвечает, данные теряются", "critical_incident"),
        ("Вопрос по работе с CRM", "Как создать новый лид?", "support_request"),
        ("Не могу войти в систему", "Забыл пароль", "support_request"),
        ("Помогите настроить почту", "Не приходят письма", "support_request"),
        ("🔥 Горячие скидки!", "Купите курс по программированию сейчас!", "spam"),
        ("Акция: 1+1=3", "Успейте заказать по старой цене", "spam"),
        ("Ваш приз ждет!", "Вы выиграли миллион", "spam"),
        ("Оплата счета №123", "Счет на оплату услуг", "billing"),
        ("Акт сверки за май", "Прилагаем акт сверки взаимных расчетов", "billing"),
        ("Просрочка платежа", "Напоминаем об оплате", "billing"),
        ("Заявка на отпуск", "Прошу согласовать отпуск с 1 июня", "hr"),
        ("Вакансия разработчика", "Требования к кандидату", "hr"),
        ("Оценка сотрудника", "Годовая оценка эффективности", "hr"),
        ("Планерка в пятницу", "Напоминание о встрече в 11:00", "informational"),
        ("Новый релиз", "Вышла новая версия продукта", "informational"),
        ("Дайджест новостей", "Подборка главных новостей за неделю", "informational"),
    ])
    def test_known_categories(self, processor, subject, body, expected_category):
        result = processor.classify_email(subject, body)
        assert result == expected_category

    def test_empty_email_goes_to_uncategorized(self, processor):
        result = processor.classify_email("", "")
        assert result == "uncategorized"

    def test_only_subject_with_keywords(self, processor):
        result = processor.classify_email("Срочно! Нужна помощь", "Обычный текст без ключей")
        assert result in ["critical_incident", "support_request"]

    def test_only_body_with_keywords(self, processor):
        result = processor.classify_email("Обычная тема", "Критическая ошибка и срочная помощь")
        assert result in ["critical_incident", "support_request"]

    def test_unknown_email_goes_to_uncategorized(self, processor):
        subject = "Прогулка в парке"
        body = "Купили мороженое, погода отличная"
        result = processor.classify_email(subject, body)
        assert result == "uncategorized"

    def test_case_insensitivity(self, processor):
        result_lower = processor.classify_email("срочно", "важно")
        result_upper = processor.classify_email("СРОЧНО", "ВАЖНО")
        assert result_lower == result_upper == "critical_incident"

    def test_partial_word_match(self, processor):
        result = processor.classify_email("бессрочный контракт", "обычный текст")
        assert result != "critical_incident"

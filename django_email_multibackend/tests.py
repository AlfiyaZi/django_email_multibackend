try:
    import unittest2 as unittest
except ImportError:
    import unittest

from django_email_multibackend.backends import EmailMultiServerBackend, weighted_choice_by_val
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
from django_email_multibackend.conditions import MatchAll


class SendMailException(Exception):
    pass

class SentTransactionEmailException(SendMailException):
    pass

class SentCampaignException(SendMailException):
    pass

class FakeTransactionalMailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise SentTransactionEmailException()

class FakeCampaignMailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise SentCampaignException()

class FakeSendingBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return
        if not hasattr(email_messages, '__iter__'):
            email_messages = [email_messages]
        return len(email_messages)

class NoConnectionBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        return
        # Replicates django smtp.py behaviour

transactional_email = EmailMessage(
    'password reset', '', to=['tbarbugli@gmail.com']
)
transactional_email.extra_headers['X-MAIL-TYPE'] = 'transactional'

campaign_email = EmailMessage(
    'buy this', '', to=['tbarbugli@gmail.com']
)
campaign_email.extra_headers['X-MAIL-TYPE'] = 'non-transactional'

class TestMultiBackendEmail(unittest.TestCase):

    def test_init(self):
        EmailMultiServerBackend()

    def test_default_weights(self):
        instance = EmailMultiServerBackend()
        backends = dict.fromkeys(['b1', 'b2'])
        weights = instance.backends_weights(None, backends)
        self.assertListEqual(list(zip(*weights)[0]), backends.keys())

    def test_weights(self):
        instance = EmailMultiServerBackend()
        assert(instance.weights == settings.EMAIL_BACKENDS_WEIGHTS)

    def test_get_backend(self):
        instance = EmailMultiServerBackend()
        for i in range(10):
            assert instance.get_backend(campaign_email) in instance.servers.values()

    def test_send_message(self):
        instance = EmailMultiServerBackend()
        self.assertRaises(SendMailException, instance.send_messages, transactional_email)

    def test_send_messages(self):
        mails = [transactional_email, campaign_email]
        instance = EmailMultiServerBackend()
        self.assertRaises(SendMailException, instance.send_messages, mails)

    def test_backend_classes(self):
        instance = EmailMultiServerBackend()
        for backend_name, backend in instance.servers.items():
            assert isinstance(backend, (FakeTransactionalMailBackend, FakeCampaignMailBackend))

    def test_sent_count(self):
        test_backends = {
            'mailjet': {
                'backend': 'django_email_multibackend.tests.FakeSendingBackend',
                },
            }

        test_weights = (
            ('mailjet', 1),
        )
        instance = EmailMultiServerBackend(backends=test_backends, backend_weights=test_weights)
        messages = [EmailMessage(), EmailMessage()]
        self.assertEquals(2, instance.send_messages(messages))

    def test_empty_sent_count(self):
        test_backends = {
            'mailjet': {
                'backend': 'django_email_multibackend.tests.FakeSendingBackend',
                },
            }

        test_weights = (
            ('mailjet', 1),
        )
        instance = EmailMultiServerBackend(backends=test_backends, backend_weights=test_weights)
        messages = []
        self.assertEquals(0, instance.send_messages(messages))

    def test_connection_error_count(self):
        test_backends = {
            'mailjet': {
                'backend': 'django_email_multibackend.tests.NoConnectionBackend',
                },
            }

        test_weights = (
            ('mailjet', 1),
        )
        instance = EmailMultiServerBackend(backends=test_backends, backend_weights=test_weights)
        messages = [EmailMessage(), EmailMessage()]
        self.assertEquals(0, instance.send_messages(messages))

class TestWeightedChoice(unittest.TestCase):
    def test_low_limit(self):
        first = ('A', 5)
        second = ('B', 5)
        self.assertEquals('A', weighted_choice_by_val([first, second], 0.0))

    def test_high_limit(self):
        first = ('A', 5)
        second = ('B', 5)
        self.assertEquals('B', weighted_choice_by_val([first, second], 1.0))

    def test_boundary(self):
        first = ('A', 5)
        second = ('B', 5)
        self.assertEquals('B', weighted_choice_by_val([first, second], 0.5))




class TestConditions(unittest.TestCase):

    def test_send_non_email(self):
        self.assertRaises(TypeError, MatchAll(), None)

    def test_match_all_backends(self):
        instance = EmailMultiServerBackend()
        transactional_backends = instance.get_backends_for_email(transactional_email)
        assert transactional_backends == list(instance.weights)

    def test_filtered_backends(self):
        instance = EmailMultiServerBackend()
        transactional_backends = instance.get_backends_for_email(campaign_email)
        assert transactional_backends == [('mailchimp', 3)]

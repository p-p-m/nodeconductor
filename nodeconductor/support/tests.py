from __future__ import unicode_literals

import unittest

from rest_framework import status, test, settings
from django.core.urlresolvers import reverse

from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.support.serializers import CommentSerializer


class JiraTest(test.APITransactionTestCase):

    def setUp(self):
        self.user = structure_factories.UserFactory()

    def get_issues_url(cls, key=None):
        if key:
            return 'http://testserver' + reverse('issue-detail', kwargs={'pk': key})
        else:
            return 'http://testserver' + reverse('issue-list')

    def get_comments_url(cls, key):
        return 'http://testserver' + reverse('issue-comments-list', kwargs={'pk': key})

    def test_list_issues(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_issues_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 3)

    def test_search_issues(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_issues_url(), data={settings.api_settings.SEARCH_PARAM: '^_^'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual('TST-3', response.data[0]['key'])

    def test_create_issues(self):
        self.client.force_authenticate(user=self.user)
        data = {
            'summary': 'Just a test',
            'description': 'nothing more',
        }

        response = self.client.post(self.get_issues_url(), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        key = response.data['key']

        response = self.client.get(self.get_issues_url(key), data=data)
        self.assertEqual(response.data['summary'], data['summary'])

    def test_list_comments(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.get_comments_url('TST-3'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)

    def test_create_comments(self):
        self.client.force_authenticate(user=self.user)

        comment = 'hi there'
        url = self.get_comments_url('TST-1')

        response = self.client.post(url, data={'body': comment})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn(self.user.username, response.data['author']['displayName'])

        response = self.client.get(url)
        self.assertEqual(response.data[-1]['body'], comment)


class JiraCommentAuthorSerializerTest(unittest.TestCase):
    def test_parsing(self):
        username = "Walter"
        uuid = '1c3323fc4ae44120b57ec40dea1be6e6'
        body = "Hello, world!"
        comment = {"body": "Comment posted by user {} ({})\n{}".format(username, uuid, body)}

        expected = {
            'author': {
                'displayName': username,
                'uuid': uuid
            },
            'body': body
        }

        serializer = CommentSerializer(instance=comment)
        self.assertEqual(expected, serializer.data)

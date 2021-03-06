from __future__ import unicode_literals

import logging

from django.conf import settings
from elasticsearch import Elasticsearch

from nodeconductor.core.utils import datetime_to_timestamp
from nodeconductor.logging.log import event_logger


logger = logging.getLogger(__name__)


class ElasticsearchError(Exception):
    pass


class ElasticsearchClientError(ElasticsearchError):
    pass


class ElasticsearchResultListError(ElasticsearchError):
    pass


class ElasticsearchResultList(object):
    """ List of results acceptable by django pagination """

    def __init__(self):
        self.client = self._get_client()

    def _get_client(self):
        if settings.NODECONDUCTOR.get('ELASTICSEARCH_DUMMY', False):
            # to avoid circular dependencies
            from nodeconductor.logging.elasticsearch_dummy_client import ElasticsearchDummyClient
            logger.warn(
                'Dummy client for elasticsearch is used, set ELASTICSEARCH_DUMMY to False to disable dummy client')
            return ElasticsearchDummyClient()
        else:
            return ElasticsearchClient()

    def filter(self, should_terms=None, must_terms=None, must_not_terms=None, search_text='', start=None, end=None):
        setattr(self, 'total', None)
        self.client.prepare_search_body(
            should_terms=should_terms,
            must_terms=must_terms,
            must_not_terms=must_not_terms,
            search_text=search_text,
            start=start,
            end=end,
        )
        return self

    def order_by(self, sort):
        self.sort = sort
        return self

    def count(self):
        return self.client.get_count()

    def aggregated_count(self, ranges):
        return self.client.get_aggregated_by_timestamp_count(ranges)

    def _get_events(self, from_, size):
        return self.client.get_events(
            from_=from_,
            size=size,
            sort=getattr(self, 'sort', '-@timestamp'),
        )

    def __len__(self):
        if not hasattr(self, 'total') or self.total is None:
            self.total = self._get_events(0, 1)['total']
        return self.total

    def __getitem__(self, key):
        if isinstance(key, slice):
            if key.step is not None and key.step != 1:
                raise ElasticsearchResultListError('ElasticsearchResultList can be iterated only with step 1')
            start = key.start if key.start is not None else 0
            events_and_total = self._get_events(start, key.stop - start)
        else:
            events_and_total = self._get_events(key, 1)
        self.total = events_and_total['total']
        return events_and_total['events']


def _execute_if_not_empty(func):
    """ Execute function only if one of input parameters is not empty """
    def wrapper(*args, **kwargs):
        if any(args[1:]) or any(kwargs.items()):
            return func(*args, **kwargs)
    return wrapper


class ElasticsearchClient(object):

    class SearchBody(dict):
        FTS_FIELDS = (
            'message', 'customer_abbreviation', 'importance', 'project_group_name',
            'cloud_account_name', 'project_name')

        def __init__(self):
            self.queries = {}
            self.timestamp_filter = {}
            self.should_terms_filter = {}
            self.must_terms_filter = {}
            self.must_not_terms_filter = {}
            self.timestamp_ranges = []

        @_execute_if_not_empty
        def set_should_terms(self, terms):
            self.should_terms_filter.update({key: map(str, value) for key, value in terms.items()})

        @_execute_if_not_empty
        def set_must_terms(self, terms):
            self.must_terms_filter.update({key: map(str, value) for key, value in terms.items()})

        @_execute_if_not_empty
        def set_must_not_terms(self, terms):
            self.must_not_terms_filter.update({key: map(str, value) for key, value in terms.items()})

        @_execute_if_not_empty
        def set_search_text(self, search_text):
            self.queries['search_text'] = ' OR '.join(
                [self._format_to_elasticsearch_field_filter(field, [search_text]) for field in self.FTS_FIELDS])

        @_execute_if_not_empty
        def set_timestamp_filter(self, start=None, end=None):
            if start is not None:
                self.timestamp_filter['gte'] = start.strftime('%Y-%m-%dT%H:%M:%S')
            if end is not None:
                self.timestamp_filter['lt'] = end.strftime('%Y-%m-%dT%H:%M:%S')

        @_execute_if_not_empty
        def set_timestamp_ranges(self, ranges):
            self.timestamp_ranges = []
            for r in ranges:
                timestamp_range = {}
                if 'start' in r:
                    timestamp_range['from'] = self.datetime_to_elasticsearch_timestamp(r['start'])
                if 'end' in r:
                    timestamp_range['to'] = self.datetime_to_elasticsearch_timestamp(r['end'])
                self.timestamp_ranges.append(timestamp_range)

        def prepare(self):
            self['query'] = {'filtered': {'filter': {'bool': {}}}}
            if self.queries:
                self['query']['filtered']['query'] = {
                    'query_string': {
                        'query': ' AND '.join('(' + search_query + ')' for search_query in self.queries.values())
                    }
                }

            if self.should_terms_filter:
                self['query']['filtered']['filter']['bool']['should'] = [
                    {'terms': {key: value}} for key, value in self.should_terms_filter.items()
                ]

            if self.must_terms_filter:
                self['query']['filtered']['filter']['bool']['must'] = [
                    {'terms': {key: value}} for key, value in self.must_terms_filter.items()
                ]

            if self.must_not_terms_filter:
                self['query']['filtered']['filter']['bool']['must_not'] = [
                    {'terms': {key: value}} for key, value in self.must_not_terms_filter.items()
                ]

            if not self['query']['filtered']['filter']['bool']:
                del self['query']['filtered']['filter']['bool']

            if self.timestamp_filter:
                self['query']['filtered']['filter']['range'] = {'@timestamp': self.timestamp_filter}

            if self.timestamp_ranges:
                self["aggs"] = {
                    "timestamp_ranges": {
                        "date_range": {
                            "field": "@timestamp",
                            "ranges": self.timestamp_ranges,
                        },
                    }
                }

        def datetime_to_elasticsearch_timestamp(self, dt):
            """ Elasticsearch calculates timestamp in milliseconds """
            return datetime_to_timestamp(dt) * 1000

        def _escape_elasticsearch_field_value(self, field_value):
            """
            Remove double quotes from field value

            Elasticsearch receives string query where all user input is strings in double quotes.
            But if input itself contains double quotes - elastic treat them as end of string, so we have to remove double
            quotes from search string.
            """
            return field_value.replace('\"', '')

        def _format_to_elasticsearch_field_filter(self, field_name, field_values):
            """
            Return string '<field_name>:("<field_value1>", "<field_value2>"...)'
            """
            excaped_field_values = [self._escape_elasticsearch_field_value(value) for value in field_values]
            return '%s:("%s")' % (field_name, '", "'.join(excaped_field_values))

    def __init__(self):
        self.client = self._get_client()

    def prepare_search_body(self, should_terms=None, must_terms=None, must_not_terms=None, search_text='', start=None, end=None):
        """
        Prepare body for elasticsearch query

        Search parameters
        ----------
        These parameters are dictionaries and have format:  <term>: [<value 1>, <value 2> ...]
        should_terms: it resembles logical OR
        must_terms: it resembles logical AND
        must_not_terms: it resembles logical NOT

        search_text : string
            Text for FTS(full text search)
        start, end : datetime
            Filter for event creation time
        """
        self.body = self.SearchBody()
        self.body.set_should_terms(should_terms)
        self.body.set_must_terms(must_terms)
        self.body.set_must_not_terms(must_not_terms)
        self.body.set_search_text(search_text)
        self.body.set_timestamp_filter(start, end)
        self.body.prepare()

    def get_events(self, sort='-@timestamp', index='_all', from_=0, size=10, start=None, end=None):
        sort = sort[1:] + ':desc' if sort.startswith('-') else sort + ':asc'
        search_results = self.client.search(index=index, body=self.body, from_=from_, size=size, sort=sort)
        return {
            'events': [r['_source'] for r in search_results['hits']['hits']],
            'total': search_results['hits']['total'],
        }

    def get_count(self, index='_all'):
        count_results = self.client.count(index=index, body=self.body)
        return count_results['count']

    def get_aggregated_by_timestamp_count(self, ranges, index='_all'):
        self.body.set_timestamp_ranges(ranges)
        self.body.prepare()
        search_results = self.client.search(index=index, body=self.body, search_type='count')
        formatted_results = []
        for result in search_results['aggregations']['timestamp_ranges']['buckets']:
            formatted = {'count': result['doc_count']}
            if 'from' in result:
                # Divide by 1000 - because elasticsearch return return timestamp in microseconds
                formatted['start'] = result['from'] / 1000
            if 'to' in result:
                # Divide by 1000 - because elasticsearch return return timestamp in microseconds
                formatted['end'] = result['to'] / 1000
            formatted_results.append(formatted)
        return formatted_results

    def _get_elastisearch_settings(self):
        try:
            return settings.NODECONDUCTOR['ELASTICSEARCH']
        except (KeyError, AttributeError):
            raise ElasticsearchClientError(
                'Can not get elasticsearch settings. ELASTICSEARCH item in settings.NODECONDUCTOR has '
                'to be defined. Or enable dummy elasticsearch mode.')

    def _get_client(self):
        elasticsearch_settings = self._get_elastisearch_settings()
        path = '%(protocol)s://%(username)s:%(password)s@%(host)s:%(port)s' % elasticsearch_settings
        return Elasticsearch(
            [path],
            use_ssl=elasticsearch_settings.get('use_ssl', False),
            verify_certs=elasticsearch_settings.get('verify_certs', False),
        )

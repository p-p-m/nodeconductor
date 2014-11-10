
class MockedOpenstackBackend(object):

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MockedOpenstackBackend, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    calls = []

    def push_ssh_public_key(self, membership, public_key):
        self.calls.append(('push_ssh_public_key', membership, public_key))

    def push_membership(self, membership):
        membership.username = 'some_username'
        membership.password = 'password'
        membership.tenant_id = 'tenant_id'
        membership.save()
        self.calls.append('push_membership', membership)

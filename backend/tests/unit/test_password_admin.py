from pathlib import Path
import importlib.util
import json

import httpx
import pytest

spec = importlib.util.spec_from_file_location('password_admin', Path(__file__).resolve().parents[2] / 'scripts/change_user_password.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_only_password_is_sent_and_role_and_account_are_preserved():
    user = {'id': 'account', 'email': 'user@example.com', 'app_metadata': {'rol': 'profesor', 'provider': 'email'}}
    writes = []
    def handler(request):
        if request.method == 'PUT':
            writes.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json=user)
        return httpx.Response(200, json={'users': [user]} if request.url.path.endswith('/users') else user)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = module.change_password(' USER@example.com ', 'password-of-test', url='https://fixture.test', secret_key='sb_secret_fixture', client=client)
    assert writes == [('/auth/v1/admin/users/account', {'password': 'password-of-test'})]
    assert result == {'email': 'user@example.com', 'rol': 'profesor'}


def test_unknown_user_is_not_created_or_changed():
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={'users': []})
    with pytest.raises(ValueError, match='No se encontró'):
        module.change_password('user@example.com', 'password-of-test', url='https://fixture.test', secret_key='sb_secret_fixture', client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert calls == ['GET']


def test_short_password_is_rejected_before_network():
    with pytest.raises(ValueError, match='8 caracteres'):
        module.change_password('user@example.com', 'short', url='https://fixture.test', secret_key='sb_secret_fixture', client=None)


def test_remote_error_does_not_expose_password_or_secret():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(400, json={'message': 'password-of-test sb_secret_fixture'})))
    with pytest.raises(ValueError) as error:
        module.change_password('user@example.com', 'password-of-test', url='https://fixture.test', secret_key='sb_secret_fixture', client=client)
    assert 'password-of-test' not in str(error.value) and 'sb_secret_fixture' not in str(error.value)

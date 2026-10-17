"""Exercise real Home Assistant/aiohttp TLS before any credentials reach HTTP."""
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
import ssl

from aiohttp import web
from aiohttp.abc import AbstractResolver
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest

from custom_components.desloc import api
from custom_components.desloc.tls import create_https_context, enforce_peer_key_policy


def certificate(key, issuer_key, issuer_name, name, ca):
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer_name or subject)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=2))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
               .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                   key_encipherment=not ca, data_encipherment=False, key_agreement=False,
                   key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False), critical=True)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
               .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), False))
    if not ca:
        builder = builder.add_extension(x509.SubjectAlternativeName([
            x509.IPAddress(ip_address('127.0.0.1')), x509.DNSName('localhost')]), False)
    return builder.sign(issuer_key, hashes.SHA256())


class NoDns(AbstractResolver):
    async def resolve(self, host, port=0, family=0):
        raise AssertionError("Numeric loopback must not perform DNS discovery")

    async def close(self):
        pass


@pytest.fixture(scope='module')
def chains(tmp_path_factory):
    folder = tmp_path_factory.mktemp('tls-chains')
    result = {}
    for weak in ('none', 'root', 'intermediate', 'leaf'):
        keys = {part: rsa.generate_private_key(public_exponent=65537,
                key_size=2047 if weak == part else 2048) for part in ('root', 'intermediate', 'leaf')}
        root = certificate(keys['root'], keys['root'], None, 'Root', True)
        intermediate = certificate(keys['intermediate'], keys['root'], root.subject, 'Intermediate', True)
        leaf = certificate(keys['leaf'], keys['intermediate'], intermediate.subject, 'localhost', False)
        ca_path, chain_path, key_path = (folder / f'{weak}-{kind}.pem' for kind in ('ca', 'chain', 'key'))
        ca_path.write_bytes(root.public_bytes(serialization.Encoding.PEM))
        # Deliberately omit root: the client must inspect the actual verified chain,
        # including its trusted anchor, not only the certificates sent by the peer.
        chain_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM)
                               + intermediate.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(keys['leaf'].private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        result[weak] = (ca_path, chain_path, key_path)
    return result


@pytest.mark.parametrize('protocol', [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3])
@pytest.mark.parametrize('weak', ['none', 'root', 'intermediate', 'leaf'])
async def test_actual_ha_client_checks_exact_chain_before_http(hass, monkeypatch, chains, protocol, weak):
    ca_path, chain_path, key_path = chains[weak]
    received = []

    async def handle(request):
        received.append((dict(request.headers), await request.read()))
        return web.json_response({'status': 200, 'success': True})

    app = web.Application()
    app.router.add_post('/probe', handle)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = server.maximum_version = protocol
    server.set_ciphers('DEFAULT:@SECLEVEL=0')  # Test fixture only: expose exact weak boundary.
    server.load_cert_chain(chain_path, key_path)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=server)
    await site.start()
    try:
        port = site._server.sockets[0].getsockname()[1]
        monkeypatch.setattr(api, 'BASE_URL', f'https://127.0.0.1:{port}')
        monkeypatch.setenv('REQUESTS_CA_BUNDLE', str(ca_path))
        monkeypatch.setattr(aiohttp_client, '_async_make_resolver', lambda _hass: NoDns())
        session = async_get_clientsession(hass)
        shared_ssl = session.connector._ssl
        baseline = ssl.create_default_context(cafile=str(ca_path))
        baseline.minimum_version = baseline.maximum_version = protocol
        baseline.set_ciphers('DEFAULT:@SECLEVEL=0')
        # A real verified baseline proves each chain/server works and primes the
        # shared session's pool; the strict request must not reuse this connection.
        async with session.post(api.BASE_URL + '/probe', json={'baseline': True}, ssl=baseline) as response:
            assert response.status == 200
            await response.read()
        assert len(received) == 1
        received.clear()
        client = api.DeslocClient(session, api.Credentials('synthetic-token', 'synthetic-phone'))
        if weak == 'none':
            assert await client._raw_request('/probe', {'synthetic': True},
                                             {'authorization': 'synthetic-token'}) == {'status': 200, 'success': True}
            assert len(received) == 1
            assert received[0][0]['Authorization'] == 'synthetic-token'
        else:
            with pytest.raises(api.DeslocConnectionError, match='DESLOC request failed'):
                await client._raw_request('/probe', {'synthetic': True}, {'authorization': 'synthetic-token'})
            assert received == []
        assert session.connector._ssl is shared_ssl
        assert client._tls_context.verify_mode == ssl.CERT_REQUIRED
        assert client._tls_context.check_hostname
    finally:
        await runner.cleanup()


def test_preserves_stronger_policy():
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.set_ciphers('ECDHE-RSA-AES256-GCM-SHA384:@SECLEVEL=3')
    before = context.get_ciphers()
    assert enforce_peer_key_policy(context) is context
    assert context.minimum_version == ssl.TLSVersion.TLSv1_3
    assert context.security_level == 3
    assert context.get_ciphers() == before


def test_ca_override_is_required_and_verified(monkeypatch, tmp_path):
    monkeypatch.setenv('REQUESTS_CA_BUNDLE', str(tmp_path / 'missing.pem'))
    with pytest.raises(FileNotFoundError):
        create_https_context()

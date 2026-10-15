"""Remote ingestion refuses local schemes and preserves TLS verification."""

import ssl

import pytest

from road_risk_modeling import ingestion, node_objects


@pytest.mark.parametrize("module", [ingestion, node_objects])
def test_remote_reader_rejects_file_urls(module, monkeypatch):
    def unexpected_open(*args, **kwargs):
        pytest.fail("Rejected schemes must never be opened")

    monkeypatch.setattr(module, "urlopen", unexpected_open)
    with pytest.raises(ValueError, match="HTTP or HTTPS"):
        module._read_remote_bytes("file:///synthetic-local-file")


@pytest.mark.parametrize("module", [ingestion, node_objects])
def test_certificate_failure_does_not_retry_without_verification(module, monkeypatch):
    calls = []

    def certificate_failure(*args, **kwargs):
        calls.append(kwargs)
        raise ssl.SSLCertVerificationError("synthetic certificate failure")

    monkeypatch.setattr(module, "urlopen", certificate_failure)
    with pytest.raises(ssl.SSLCertVerificationError):
        module._read_remote_bytes("https://source.example.test/data.csv")
    assert calls == [{"timeout": 60}]

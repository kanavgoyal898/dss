# DSS Tests

## Running Tests

```bash
cd dss
pip install -r requirements.txt pytest pytest-asyncio
python -m pytest tests/ -v
```

All 55 tests should pass in under 15 seconds.

## Test Coverage

| File | What it tests |
|---|---|
| `test_crypto.py` | AES-256-GCM round-trip, tamper detection, RSA keygen/sign/verify/encrypt |
| `test_reed_solomon.py` | Encode/decode correctness, max erasures, invalid params, various sizes |
| `test_pipeline.py` | Full compress→encrypt→encode→decode→decrypt→decompress pipeline |
| `test_shard_store.py` | Write/read, integrity verification, deletion, listing |
| `test_network_policy.py` | global / lan / allowlist modes, CIDR matching, runtime switching |

## Troubleshooting

**`ModuleNotFoundError: No module named 'dss'`** — Run pytest from the parent of the `dss/` directory:
```bash
cd /path/to/parent
python -m pytest dss/tests/ -v
```

**Tests slow on first run** — RSA key generation is CPU-intensive. Subsequent runs are faster due to test isolation.

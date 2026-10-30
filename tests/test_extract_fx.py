import pytest
import requests

from datetime import date
import pyarrow.parquet as pq

from pipeline import extract_fx
from pipeline.extract_fx import FxApiError


def make_response(status_code, body="[]"):
    r = requests.Response()
    r.status_code = status_code
    r._content = body.encode("utf-8")
    r.url = "https://api.frankfurter.dev/v2/rates"
    return r


def test_fetch_rates_sends_timeout_and_quotes(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        return make_response(200, '[{"date": "2018-01-02", "quote": "USD", "rate": 0.3}]')

    monkeypatch.setattr(extract_fx.requests, "get", fake_get)

    extract_fx.fetch_rates("2018-01-02", "2018-01-09", ["USD", "VND"])
    assert calls[0]["params"]["quotes"] == "USD,VND"
    assert calls[0]["timeout"] == (3.05, 30)


def test_retry_does_not_retry_422(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        return make_response(422)
    monkeypatch.setattr(extract_fx.requests, "get", fake_get)

    with pytest.raises(FxApiError) as exc:
        extract_fx.fetch_rates_with_retry(
            "2018-01-02", "2018-01-09", ["USD", "VND"])
    assert exc.value.retryable is False
    assert len(calls) == 1


def test_retry_recovers_after_two_503(monkeypatch):
    calls = []
    responses = [make_response(503), make_response(503), make_response(
        200, '[{"date": "2018-01-02", "quote": "USD", "rate": 0.3}]')]

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    delays = []

    def fake_sleep(seconds):
        delays.append(seconds)
    monkeypatch.setattr(extract_fx.requests, "get", fake_get)
    monkeypatch.setattr(extract_fx.time, "sleep", fake_sleep)
    response = extract_fx.fetch_rates_with_retry(
        "2018-01-02", "2018-01-09", ["USD", "VND"])

    assert response.status_code == 200
    assert len(calls) == 3
    assert delays == [1.0, 2.0]


def test_retry_gives_up_after_max_attempts(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs)
        return make_response(503)
    delays = []

    def fake_sleep(seconds):
        delays.append(seconds)
    monkeypatch.setattr(extract_fx.requests, "get", fake_get)
    monkeypatch.setattr(extract_fx.time, "sleep", fake_sleep)
    with pytest.raises(FxApiError) as exc:
        extract_fx.fetch_rates_with_retry(
            "2018-01-02", "2018-01-09", ["USD", "VND"], max_attempts=4)
    assert exc.value.retryable is True
    assert len(calls) == 4
    assert delays == [1.0, 2.0, 4.0]


def test_write_rates_csv_skips_bad_rows(tmp_path):
    rows = [
        {"date": "2018-01-02", "quote": "USD", "rate": 0.3033},
        {"date": "2018-01-02", "quote": "VND", "rate": 6871},
        {"date": "2018-01-02", "quote": "USD"},
        {"date": "2018-01-02", "quote": "VND", "rate": "abc"},
    ]
    path = tmp_path / "fx_rates.csv"
    skipped, written = extract_fx.write_rates_csv(rows=rows, path=path)
    assert skipped == 2
    assert written == 2
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3


def test_read_order_date_range_returns_earliest_and_latest(tmp_path):
    path = tmp_path / "oders_clean.csv"
    path.write_text("order_id,order_purchase_timestamp\n"
                    "a,2017-05-01T10:00:00+00:00\n"
                    "b,2016-09-05T00:15:00+00:00\n"
                    "c,2018-10-17T17:30:00+00:00\n"
                    "d,2017-05-01T22:45:00+00:00\n",
                    encoding="utf-8",)
    result = extract_fx.read_order_date_range(path)
    assert result == ("2016-09-05", "2018-10-17")


def test_read_order_date_range_missing_file(tmp_path):
    path = tmp_path / "orders_clean.csv"
    with pytest.raises(FileNotFoundError, match="clean_orders"):
        extract_fx.read_order_date_range(path)


def test_read_order_date_range_empty_file(tmp_path):
    path = tmp_path / "orders_clean.csv"
    path.write_text("order_id,order_purchase_timestamp\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Empty file"):
        extract_fx.read_order_date_range(path)


@pytest.mark.parametrize(("rows", "message"),
                         [
                             ({}, "not a list"),
                             ([], "empty"),
                             ([{"quote": "USD", "rate": 0.3}],
                              "missing date or quote"),
                             ([{"date": "2018-01-02", "quote": "EUR",
                              "rate": 0.25}], "Unexpected quote"),
],)
def test_validate_rates_rejects_broken_response(rows, message):
    with pytest.raises(ValueError, match=message):
        extract_fx.validate_rates(rows, ["USD", "VND"])


def test_validate_rates_warns_about_missing_date(caplog):
    rows = [
        {"date": "2017-07-14", "quote": "USD", "rate": 0.31},
        {"date": "2017-07-14", "quote": "VND", "rate": 7000},
        {"date": "2017-07-15", "quote": "USD", "rate": 0.32},
    ]
    extract_fx.validate_rates(rows=rows, quotes=["USD", "VND"])
    assert "2017-07-15" in caplog.text
    assert "VND" in caplog.text


def test_save_raw_writes_exact_bytes_atomically(tmp_path):
    body = '[{"date":"2017-07-14","base":"BRL","quote":"USD","rate":0.31}]'
    response = make_response(200, body=body)
    path = tmp_path / "fx" / "fx_test.json"

    extract_fx.save_raw(response, path)
    assert path.read_bytes(
    ) == b'[{"date":"2017-07-14","base":"BRL","quote":"USD","rate":0.31}]'
    assert [p.name for p in path.parent.iterdir()] == ["fx_test.json"]


def test_write_rates_parquet_keeps_types_and_skips_bad_rows(tmp_path):
    rows = [
        {"date": "2016-09-05", "base": "BRL", "quote": "USD", "rate": 0.30797},
        {"date": "2016-09-05", "base": "BRL", "quote": "VND", "rate": 6874.2},
        {"date": "2016-09-06", "base": "BRL", "quote": "USD", "rate": "abc"},
    ]
    parquet_written = extract_fx.write_rates_parquet(
        rows, tmp_path / "fx.parquet")
    table = pq.read_table(tmp_path / "fx.parquet")
    assert table.num_rows == 2
    assert table.schema.equals(extract_fx.FX_SCHEMA, check_metadata=False)
    assert table.column("date")[0].as_py() == date(2016, 9, 5)
    assert [p.name for p in tmp_path.iterdir()] == ["fx.parquet"]
    assert parquet_written == 2

__copyright__ = "Copyright (C) 2015-2020  Martin Blais"
__license__ = "GNU GPLv2"

import datetime
import json
import textwrap
import unittest
from decimal import Decimal
from unittest import mock

from dateutil import tz
import requests

from beanprice import date_utils
from beanprice.sources import yahoo


class MockResponse:
    """A mock requests.Models.Response object for testing."""

    def __init__(self, contents, status_code=requests.codes.ok):
        self.status_code = status_code
        self.contents = contents

    def json(self, **kwargs):
        return json.loads(self.contents, **kwargs)


class YahooFinancePriceFetcher(unittest.TestCase):
    def _test_get_latest_price(self):
        response = MockResponse(
            textwrap.dedent("""
            {"quoteResponse":
             {"error": null,
              "result": [{"esgPopulated": false,
                          "exchange": "TOR",
                          "exchangeDataDelayedBy": 15,
                          "exchangeTimezoneName": "America/Toronto",
                          "exchangeTimezoneShortName": "EDT",
                          "fullExchangeName": "Toronto",
                          "gmtOffSetMilliseconds": -14400000,
                          "language": "en-US",
                          "market": "ca_market",
                          "marketState": "CLOSED",
                          "quoteType": "ETF",
                          "regularMarketPrice": 29.99,
                          "regularMarketTime": 1522353589,
                          "sourceInterval": 15,
                          "symbol": "XSP.TO",
                          "tradeable": false}]}}
            """)
        )
        yahoo_source = yahoo.Source()
        with mock.patch.object(yahoo_source.session, "get", return_value=response):
            srcprice = yahoo_source.get_latest_price("XSP.TO")
        self.assertTrue(isinstance(srcprice.price, Decimal))
        self.assertEqual(Decimal("29.99"), srcprice.price)
        timezone = datetime.timezone(datetime.timedelta(hours=-4), "America/Toronto")
        self.assertEqual(
            datetime.datetime(2018, 3, 29, 15, 59, 49, tzinfo=timezone), srcprice.time
        )
        self.assertEqual("CAD", srcprice.quote_currency)

    def test_get_latest_price(self):
        for tzname in "America/New_York", "Europe/Berlin", "Asia/Tokyo":
            with date_utils.intimezone(tzname):
                self._test_get_latest_price()

    def _test_get_historical_price(self):
        response = MockResponse(
            textwrap.dedent("""
            {"chart":
             {"error": null,
              "result": [{"indicators": {"adjclose": [{"adjclose": [29.236251831054688,
                                                                    29.16683006286621,
                                                                    29.196582794189453,
                                                                    29.226333618164062]}],
                                         "quote": [{"close": [29.479999542236328,
                                                              29.40999984741211,
                                                              29.440000534057617,
                                                              29.469999313354492],
                                                    "high": [29.510000228881836,
                                                             29.489999771118164,
                                                             29.469999313354492,
                                                             29.579999923706055],
                                                    "low": [29.34000015258789,
                                                            29.350000381469727,
                                                            29.399999618530273,
                                                            29.43000030517578],
                                                    "open": [29.360000610351562,
                                                             29.43000030517578,
                                                             29.43000030517578,
                                                             29.530000686645508],
                                                    "volume": [160800,
                                                               118700,
                                                               98500,
                                                               227800]}]},
                          "meta": {"chartPreviousClose": 29.25,
                                   "currency": "CAD",
                                   "currentTradingPeriod": {"post": {"end": 1522702800,
                                                                     "gmtoffset": -14400,
                                                                     "start": 1522699200,
                                                                     "timezone": "EDT"},
                                                            "pre": {"end": 1522675800,
                                                                    "gmtoffset": -14400,
                                                                    "start": 1522670400,
                                                                    "timezone": "EDT"},
                                                            "regular": {"end": 1522699200,
                                                                        "gmtoffset": -14400,
                                                                        "start": 1522675800,
                                                                        "timezone": "EDT"}},
                                   "dataGranularity": "1d",
                                   "exchangeName": "TOR",
                                   "exchangeTimezoneName": "America/Toronto",
                                   "firstTradeDate": 1018872000,
                                   "gmtoffset": -14400,
                                   "instrumentType": "ETF",
                                   "symbol": "XSP.TO",
                                   "timezone": "EDT",
                                   "validRanges": ["1d", "5d", "1mo", "3mo", "6mo", "1y",
                                                   "2y", "5y", "10y", "ytd", "max"]},
                          "timestamp": [1509111000,
                                        1509370200,
                                        1509456600,
                                        1509543000]}]}}""")
        )
        yahoo_source = yahoo.Source()
        with mock.patch.object(yahoo_source.session, "get", return_value=response):
            srcprice = yahoo_source.get_historical_price(
                "XSP.TO", datetime.datetime(2017, 11, 1, 16, 0, 0, tzinfo=tz.tzutc())
            )
        self.assertTrue(isinstance(srcprice.price, Decimal))
        self.assertEqual(Decimal("29.469999313354492"), srcprice.price)
        timezone = datetime.timezone(datetime.timedelta(hours=-4), "America/Toronto")
        self.assertEqual(
            datetime.datetime(2017, 11, 1, 9, 30, tzinfo=timezone), srcprice.time
        )
        self.assertEqual("CAD", srcprice.quote_currency)

    def test_get_historical_price(self):
        for tzname in "America/New_York", "Europe/Berlin", "Asia/Tokyo":
            with date_utils.intimezone(tzname):
                self._test_get_historical_price()

    def test_parse_response_error_status_code(self):
        response = MockResponse(
            '{"quoteResponse": {"error": "Not supported", "result": [{}]}}', status_code=400
        )
        with self.assertRaises(yahoo.YahooError):
            yahoo.parse_response(response)

    def test_parse_response_error_invalid_format(self):
        response = MockResponse(
            """{"quoteResponse": {"error": null, "result": [{}]},
             "chart": {"error": null, "result": [{}]}}"""
        )
        with self.assertRaises(yahoo.YahooError):
            yahoo.parse_response(response)

    def test_parse_response_error_not_none(self):
        response = MockResponse(
            '{"quoteResponse": {"error": "Non-zero error", "result": [{}]}}'
        )
        with self.assertRaises(yahoo.YahooError):
            yahoo.parse_response(response)

    def test_parse_response_empty_result(self):
        response = MockResponse('{"quoteResponse": {"error": null, "result": []}}')
        with self.assertRaises(yahoo.YahooError):
            yahoo.parse_response(response)

    def test_parse_response_no_timestamp(self):
        response = MockResponse(
            textwrap.dedent("""
            {"chart":
             {"error": null,
              "result": [{"indicators": {"adjclose": [{}],
                                         "quote": [{}]},
                          "meta": {"chartPreviousClose": 29.25,
                                   "currency": "CAD",
                                   "currentTradingPeriod": {"post": {"end": 1522702800,
                                                                     "gmtoffset": -14400,
                                                                     "start": 1522699200,
                                                                     "timezone": "EDT"},
                                                            "pre": {"end": 1522675800,
                                                                    "gmtoffset": -14400,
                                                                    "start": 1522670400,
                                                                    "timezone": "EDT"},
                                                            "regular": {"end": 1522699200,
                                                                        "gmtoffset": -14400,
                                                                        "start": 1522675800,
                                                                        "timezone": "EDT"}},
                                   "dataGranularity": "1d",
                                   "exchangeName": "TOR",
                                   "exchangeTimezoneName": "America/Toronto",
                                   "firstTradeDate": 1018872000,
                                   "gmtoffset": -14400,
                                   "instrumentType": "ETF",
                                   "symbol": "XSP.TO",
                                   "timezone": "EDT",
                                   "validRanges": ["1d", "5d", "1mo", "3mo", "6mo", "1y",
                                                   "2y", "5y", "10y", "ytd", "max"]}}]}}
        """)
        )
        with self.assertRaises(yahoo.YahooError):
            yahoo_source = yahoo.Source()
            with mock.patch.object(yahoo_source.session, "get", return_value=response):
                _ = yahoo_source.get_historical_price(
                    "XSP.TO", datetime.datetime(2017, 11, 1, 16, 0, 0, tzinfo=tz.tzutc())
                )

    def test_parse_null_prices_in_series(self):
        response = MockResponse(
            textwrap.dedent("""
            {"chart": {"result":[ {"meta":{
                "currency":"USD","symbol":"FBIIX",
                "exchangeName":"NAS","instrumentType":"MUTUALFUND",
                "firstTradeDate":1570714200,"regularMarketTime":1646053572,
                "gmtoffset":-18000,"timezone":"EST",
                "exchangeTimezoneName":"America/New_York",
                "regularMarketPrice":9.69,"chartPreviousClose":9.69,
                "priceHint":2,
                "currentTradingPeriod":{
                    "pre":{"timezone":"EST","start":1646038800,"end":1646058600,"gmtoffset":-18000},
                    "regular":{"timezone":"EST","start":1646058600,"end":1646082000,"gmtoffset":-18000},
                    "post":{"timezone":"EST","start":1646082000,"end":1646096400,"gmtoffset":-18000}
                },
                "dataGranularity":"1d","range":"",
                "validRanges":["1mo","3mo","6mo","ytd","1y","2y","5y","10y","max"]},
                "timestamp":[1645626600,1645713000,1645799400,1646058600],
                "indicators":{
                    "quote":[
                        {"open":[9.6899995803833,9.710000038146973,9.6899995803833,null],
                        "low":[9.6899995803833,9.710000038146973,9.6899995803833,null],
                        "high":[9.6899995803833,9.710000038146973,9.6899995803833,null],
                        "volume":[0,0,0,null],
                        "close":[9.6899995803833,9.710000038146973,9.6899995803833,null]}
                    ],"adjclose":[
                        {"adjclose":[9.6899995803833,9.710000038146973,9.6899995803833,null]}
                    ]
                }}],"error":null}}
        """)
        )

        yahoo_source = yahoo.Source()
        with mock.patch.object(yahoo_source.session, "get", return_value=response):
            srcprice = yahoo_source.get_historical_price(
                "XSP.TO", datetime.datetime(2022, 2, 28, 16, 0, 0, tzinfo=tz.tzutc())
            )
            self.assertTrue(isinstance(srcprice.price, Decimal))
            self.assertEqual(Decimal("9.6899995803833"), srcprice.price)
            timezone = datetime.timezone(datetime.timedelta(hours=-5), "America/New_York")
            self.assertEqual(
                datetime.datetime(2022, 2, 25, 9, 30, tzinfo=timezone), srcprice.time
            )
            self.assertEqual("USD", srcprice.quote_currency)


if __name__ == "__main__":
    unittest.main()

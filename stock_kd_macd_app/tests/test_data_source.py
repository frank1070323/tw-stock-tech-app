import unittest

from stock_app.data_source import OfficialStockDataSource


class DataSourceTests(unittest.TestCase):
    def test_resolve_symbol_from_special_alias(self):
        source = OfficialStockDataSource()
        self.assertEqual(source.resolve_symbol("AES-KY").symbol, "6781")
        self.assertEqual(source.resolve_symbol("光聖").symbol, "6442")


if __name__ == "__main__":
    unittest.main()

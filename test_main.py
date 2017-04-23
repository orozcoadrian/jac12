import unittest

from main import Foreclosures, MyDate, Jac
from pprint import pprint
from datetime import date


class MyTestCase(unittest.TestCase):
    def test_foreclousres_request(self):
        self.assertEqual(Foreclosures().get_request_url(),
                         'http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html')

    def test_foreclousres_response(self):
        with open('foreclosures_resp.html', 'rb') as myfile:
            rows = Foreclosures().get_rows_from_response(myfile.read())
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows, [{'case_number': '05-2008-CA-006267-XXXX-XX',
                                     'case_title': 'WACHOVIA VS FIRST BREVARD CORP',
                                     'comment': '\xa0',
                                     'count': 1,
                                     'foreclosure_sale_date': '2017-04-26'},
                                    {'case_number': '05-2008-CA-033772-XXXX-XX',
                                     'case_title': 'BANK NEW YORK VS W COOK',
                                     'comment': '\xa0',
                                     'count': 2,
                                     'foreclosure_sale_date': '2017-04-26'},
                                    {'case_number': '05-2010-CA-012039-XXXX-XX',
                                     'case_title': 'NATIONSTAR VS FRANCIS METCALF',
                                     'comment': 'CANCELLED',
                                     'count': 3,
                                     'foreclosure_sale_date': '2017-04-26'}])

    def test_dates_1(self):
        ret = MyDate().get_next_dates(date(2017, 4, 23))
        self.assertEqual(ret, [date(2017, 4, 26), date(2017, 5, 3)])

    def test_get_date_strings_to_add(self):
        self.assertEqual(Jac().get_date_strings_to_add([date(2017, 4, 26), date(2017, 5, 3)]), ['2017-04-26', '2017-05-03'])

    def test_get_short_date_strings_to_add(self):
        self.assertEqual(Jac().get_short_date_strings_to_add([date(2017, 4, 26), date(2017, 5, 3)]), ['04.26.17', '05.03.17'])


if __name__ == '__main__':
    unittest.main()

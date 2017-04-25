import unittest
from datetime import date

from main import Foreclosures, MyDate, Jac, Taxes, Bcpao


class MyTestCase(unittest.TestCase):
    def test_foreclosures_request(self):
        self.assertEqual(Foreclosures().get_request_url(),
                         'http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html')

    def test_foreclosures_response(self):
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
        self.assertEqual(Jac().get_date_strings_to_add([date(2017, 4, 26), date(2017, 5, 3)]),
                         ['2017-04-26', '2017-05-03'])

    def test_get_short_date_strings_to_add(self):
        self.assertEqual(Jac().get_short_date_strings_to_add([date(2017, 4, 26), date(2017, 5, 3)]),
                         ['04.26.17', '05.03.17'])

    def test_taxes_request(self):
        self.assertEqual(Taxes().get_tax_url_from_taxid('test_taxid'),
                         'https://brevard.county-taxes.com/public/real_estate/parcels/test_taxid')

    def test_taxes_response(self):
        with open('taxes_resp.html', 'rb') as myfile:
            ret = Taxes().get_info_from_response('test_taxid', myfile.read())
            self.assertEqual(ret,
                             {'url_to_use': 'https://brevard.county-taxes.com/public/real_estate/parcels/test_taxid',
                              'value_to_use': '859.99'})

    def test_bcpao_get_acct_by_legal(self):
        url, headers = Bcpao().get_acct_by_legal_request(
            {'t': '26', 'subd': ' WYNDHAM AT DURAN', 'u': None, 'r': '36', 'pb': '53',
             'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH', 'pg': '20', 'lt': '3',
             'blk': 'A', 'subid': 'UH', 's': '09'})
        self.assertEqual(url, 'https://bcpao.us/api/v1/search?'
                              'lot=3&blk=A&platbook=53&platpage=20&'
                              'subname=%20WYNDHAM%20AT%20DURAN&activeonly=true&size=10&page=1')
        self.assertEqual(headers, {'Accept': 'application/json'})

    def test_bcpao_parse_acct_by_legal_response(self):
        with open('bcpao_resp.json', 'r') as myfile:
            class TestObject(object):
                def __init__(self, status_code, text):
                    self.status_code = status_code
                    self.text = text

            ret = Bcpao().parse_acct_by_legal_response(TestObject(status_code=200, text=myfile.read()))
            self.assertEqual(ret, '2627712')

    def test_get_parcel_data_by_acct2_request(self):
        ret = Bcpao().get_parcel_data_by_acct2_request('test_acct')
        self.assertEqual(ret['url'], 'https://bcpao.us/api/v1/account/test_acct')
        self.assertEqual(ret['headers'], {'Accept': 'application/json'})

    def test_parse_bcpaco_item_response(self):
        with open('bcpao_resp2.json', 'r') as myfile:
            class TestObject(object):
                def __init__(self, status_code, text):
                    self.status_code = status_code
                    self.text = text

            ret = Bcpao().parse_bcpaco_item_response(TestObject(status_code=200, text=myfile.read()))
            self.assertEqual(ret, {'address': '2778 WYNDHAM WAY MELBOURNE FL 32940', 'zip_code': '32940',
                                   'frame code': 'MASNRYCONC, WOOD FRAME', 'year built': '2007',
                                   'total base area': '4441', 'latest market value total': '$943,700.00'})


if __name__ == '__main__':
    unittest.main()

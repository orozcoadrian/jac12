import argparse
import pprint
import unittest
from collections import OrderedDict
from datetime import date
from unittest.mock import MagicMock, call

from xlwt import Formula

from app import Foreclosures, MyDate, Jac, Taxes, Bcpao, BclerkPublicRecords, BclerkBeca, XlBuilder, FilterCancelled, \
    FilterByDates, Item, Xl


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_foreclosures_request(self):
        self.assertEqual(Foreclosures().get_request_url(),
                         'http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html')

    def test_foreclosures_response(self):
        with open('test_resources/foreclosures_resp.html', 'rb') as myfile:
            rows = Foreclosures().get_rows_from_response(myfile.read())
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows, [
                {'foreclosure_sale_date': date(2017, 5, 10), 'comment': '\xa0',
                 'case_title': 'BANK NEW YORK VS C DORCANT',
                 'count': 1, 'case_number': '05-2008-CA-022131-XXXX-XX'},
                {'foreclosure_sale_date': date(2017, 5, 10), 'comment': '\xa0',
                 'case_number': '05-2010-CA-047105-XXXX-XX',
                 'count': 2, 'case_title': 'HSBC MORTGAGE VS ALBERT FLOWER'},
                {'foreclosure_sale_date': date(2017, 5, 10), 'count': 3, 'comment': '\xa0',
                 'case_number': '05-2011-CA-052383-XXXX-XX', 'case_title': 'OCWEN LOAN SVC VS JAMES H WOOD'}])

    def test_dates_1(self):
        ret = MyDate().get_next_dates(date(2017, 4, 23))
        self.assertEqual(ret, [date(2017, 4, 26), date(2017, 5, 3)])

    def test_get_short_date_strings_to_add(self):
        self.assertEqual(Jac().get_short_date_strings_to_add([date(2017, 4, 26), date(2017, 5, 3)]),
                         ['04.26.17', '05.03.17'])

    def test_taxes_request(self):
        self.assertEqual(Taxes(None).get_tax_url_from_taxid('test_taxid'),
                         'https://brevard.county-taxes.com/public/real_estate/parcels/test_taxid')

    def test_taxes_response(self):
        with open('test_resources/taxes_resp.html', 'rb') as myfile:
            ret = Taxes(None).get_info_from_response('test_taxid', myfile.read())
            self.assertEqual(ret,
                             {'url_to_use': 'https://brevard.county-taxes.com/public/real_estate/parcels/test_taxid',
                              'value_to_use': '859.99'})

    def test_bcpao_get_acct_by_legal(self):
        ret = Bcpao().get_acct_by_legal_request(
            {'t': '26', 'subd': ' WYNDHAM AT DURAN', 'u': None, 'r': '36', 'pb': '53',
             'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH', 'pg': '20', 'lt': '3',
             'blk': 'A', 'subid': 'UH', 's': '09'})
        self.assertEqual(ret, {'headers': {'Accept': 'application/json'},
                               'url2': 'https://www.bcpao.us/api/v1/search?lot=3&blk=A&platbook=53&platpage=20&subname=+WYNDHAM+AT+DURAN&activeonly=true&size=10&page=1'})

    def test_bcpao_get_acct_by_legal2(self):
        ret = Bcpao().get_acct_by_legal_request({'legal_desc': 'NO LAND DESCRIBED'})
        self.assertEqual(ret, None)

    def test_bcpao_parse_acct_by_legal_response(self):
        with open('test_resources/bcpao_resp.json', 'r') as myfile:
            class TestObject(object):
                def __init__(self, status_code, text):
                    self.status_code = status_code
                    self.text = text

            ret = Bcpao().parse_acct_by_legal_response(TestObject(status_code=200, text=myfile.read()))
            self.assertEqual(ret, '2627712')

    def test_get_parcel_data_by_acct2_request(self):
        ret = Bcpao().get_parcel_data_by_acct2_request('test_acct')
        self.assertEqual(ret['url'], 'https://www.bcpao.us/api/v1/account/test_acct')
        self.assertEqual(ret['headers'], {'Accept': 'application/json'})

    def test_parse_bcpaco_item_response(self):
        with open('test_resources/bcpao_resp2.json', 'r') as myfile:
            class TestObject(object):
                def __init__(self, status_code, text):
                    self.status_code = status_code
                    self.text = text

            ret = Bcpao(None).parse_bcpaco_item_response(TestObject(status_code=200, text=myfile.read()))
            self.assertEqual(ret, {'address': '2778 WYNDHAM WAY MELBOURNE FL 32940', 'zip_code': '32940',
                                   'frame code': 'MASNRYCONC, WOOD FRAME', 'year built': '2007',
                                   'total base area': '4441', 'latest market value total': '$943,700.00'})

    def test_public_records_get_request_info(self):
        ret = BclerkPublicRecords().get_request_info('test_acct')
        self.assertEqual(ret, {'uri': 'http://web1.brevardclerk.us/oncoreweb/search.aspx',
                               'form': {'SearchType': 'casenumber',
                                        'txtCaseNumber': 'test_acct',
                                        'txtDocTypes': ''}})

    def test_public_records_parse_records_grid_response(self):
        with open('test_resources/public_records_resp.html', 'rb') as myfile:
            ret = BclerkPublicRecords().parse_response(myfile.read())
            self.assertEqual(ret, [
                {'t': '26', 'lt': '3', 'subd': ' WYNDHAM AT DURAN', 's': '09', 'u': None, 'blk': 'A', 'pg': '20',
                 'subid': 'UH', 'pb': '53',
                 'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH', 'r': '36'}])

    def test_public_records_parse_records_grid_response2(self):
        # no legal desc is expected for this item
        with open('test_resources/public_records_resp2.html', 'rb') as myfile:
            ret = BclerkPublicRecords().parse_response(myfile.read())
            self.assertEqual(ret, [])

    def test_bclerk_beca_pre_cache(self):
        ret = BclerkBeca().pre_cache('05-2008-CA-006267-XXXX-XX')
        self.assertEqual(ret,
                         {'year': '2008', 'seq_number': '006267', 'id2': '2008_CA_006267',
                          'court_type': 'CA'})

    def test_bclerk_beca_get_request_info(self):
        ret = BclerkBeca().get_request_info('CA', '006267', '2008')
        self.assertEqual(ret, {'headers': {'Content-Type': 'application/x-www-form-urlencoded'},
                               'url': 'https://vmatrix1.brevardclerk.us/beca/CaseNumber_Display.cfm',
                               'data': OrderedDict([('CaseNumber1', '05'),
                                                    ('CaseNumber2', '2008'),
                                                    ('CaseNumber3', 'CA'),
                                                    ('CaseNumber4', '006267'),
                                                    ('CaseNumber5', ''),
                                                    ('CaseNumber6', ''),
                                                    ('submit', 'Search')])})

    def test_bclerk_beca_get_reg_actions_parse(self):
        with open('test_resources/beca_case_resp.html', 'rb') as myfile:
            ret = BclerkBeca().parse_reg_actions_response(myfile.read())
            self.assertEqual({'orig_mtg_tag': 'NOTICE OF FILING ORIGINAL NOTE',
                              'orig_mtg_link': {
                                  'href': 'https://vmatrix1.brevardclerk.us/beca/https://vmatrix1.brevardclerk.us/beca/Vor_Request.cfm?Brcd_id=22902619',
                                  'title': 'View On Request'},
                              'latest_amount_due': {
                                  'href': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=pAQDLSwHntFeUV5wddt+BA==&theKey=5mpuEJod8lGDC/4c+cWDtQ==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999999',
                                  'title': '123', 'title': 'Viewable'}},
                             ret)

    def test_xlbuilder_with_rows(self):
        class StubTime(object):
            pass

        stub_time = StubTime()
        stub_time.time = MagicMock()
        stub_time.time_strftime = MagicMock(return_value='05/13/2017')
        instance = XlBuilder('test_name', stub_time)
        data_set = instance.add_sheet([{'case_number': '05-2008-CA-033772-XXXX-XX',
                                        'taxes_url': 'https://brevard.county-taxes.com/public/real_estate/parcels/2627712',
                                        'comment': '\xa0', 'taxes_value': '0', 'legals': [],
                                        'bcpao_item': {'frame code': 'MASNRYCONC, WOOD FRAME', 'zip_code': '32940',
                                                       'year built': '2007', 'latest market value total': '$943,700.00',
                                                       'address': '2778 WYNDHAM WAY MELBOURNE FL 32940',
                                                       'total base area': '4441'},
                                        'foreclosure_sale_date': '2017-04-26',
                                        'orig_mtg_link': {
                                            'href': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=7Ba4EeWT71ewgv3amjxLBw==&theKey=TIbbOCD+TFEA1or3NprKhA==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                                            'title': '789'},
                                        'bcpao_acc': '2627712', 'orig_mtg_tag': 'OR MTG',
                                        'latest_amount_due': {
                                            'href': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=kXZYtPY5nJxqhnchAd/gow==&theKey=NN73L3AVCXFc+xj6fiV/lg==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                                            'title': '678'},
                                        'count': 2,
                                        'legal': {'u': None, 'pg': '20', 's': '09', 'pb': '53', 'blk': 'A', 'lt': '3',
                                                  'r': '36', 'subd': ' WYNDHAM AT DURAN',
                                                  'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH',
                                                  't': '26', 'subid': 'UH'}, 'case_title': 'BANK NEW YORK VS W COOK'}])
        self.assertTrue(data_set is not None)
        header_row = data_set.get_items()[0]
        self.assertEqual(['high',
                          'win',
                          'case_number',
                          'case_title',
                          'fc._sale_date',
                          'beca_case',
                          'count',
                          'address',
                          'zip',
                          'liens-name',
                          'bcpao',
                          'f_code',
                          'owed_link',
                          'owed',
                          'assessed',
                          'base_area',
                          'year built',
                          'owed - ass',
                          'orig_mtg',
                          'taxes'], [x.get_display() for x in header_row])
        first_data_row = data_set.get_items()[1]
        self.assertEqual(['',
                          '\xa0',
                          '05-2008-CA-033772-',
                          'BANK NEW YORK VS W COOK',
                          '2017-04-26',
                          'beca_case',
                          2,
                          '2778 WYNDHAM WAY MELBOURNE FL 32940',
                          32940,
                          'COOK, W',
                          '2627712',
                          'MASNRYCONC, WOOD FRAME',
                          '678',
                          '',
                          943700.0,
                          4441.0,
                          2007,
                          None,
                          'OR MTG (789)',
                          '0'], [x.get_display() for x in first_data_row])

    def test_FilterCancelled(self):
        ret = FilterCancelled().apply([dict(comment='', val=2), dict(comment='CANCELLED', val=3)])
        self.assertEqual(ret, [{'comment': '', 'val': 2}])

    def test_FilterByDates(self):
        filter_by_dates = FilterByDates()
        filter_by_dates.set_dates([date(2017, 4, 26), date(2017, 5, 3)])
        ret = filter_by_dates.apply(
            [dict(foreclosure_sale_date=date(2017, 4, 26), val=2), dict(foreclosure_sale_date=date(2017, 4, 30), val=3),
             dict(foreclosure_sale_date=date(2017, 5, 3), val=4)])
        self.assertEqual(ret, [{'foreclosure_sale_date': date(2017, 4, 26), 'val': 2},
                               {'foreclosure_sale_date': date(2017, 5, 3), 'val': 4}])

    def test_get_id2(self):
        self.assertEqual(Item.pre_cache2('05-2008-CA-006267-'), {'court_type': 'CA',
                                                                 'id2': '2008_CA_006267',
                                                                 'seq_number': '006267', 'year': '2008'})
        self.assertEqual(Item.pre_cache2('05-2008-CA-006267-XXXX-XX'), {'court_type': 'CA',
                                                                        'id2': '2008_CA_006267',
                                                                        'seq_number': '006267', 'year': '2008'})

    def test_get_legal_from_str(self):
        ret = BclerkPublicRecords.get_legal_from_str('LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH')
        self.assertEqual(ret, {'u': None, 'pg': '20', 's': '09', 'pb': '53', 'blk': 'A', 'lt': '3',
                               'r': '36', 'subd': ' WYNDHAM AT DURAN',
                               'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH',
                               't': '26', 'subid': 'UH'})

        # current limitation: not processing the following correctly in legal descriptions:
        #    S 67 FT
        #    N 23 FT OF E 45.67 FT
        # can't just ignore them cause that might result in a different property?
        ret = BclerkPublicRecords.get_legal_from_str(
            'LT 11 BLK 3 PB 11 PG 39 WESTFIELD ESTATES SUB S 67 FT S 05 T 22 R 35 SUBID 04')
        self.assertEqual(ret, {'blk': '3',
                               'legal_desc': 'LT 11 BLK 3 PB 11 PG 39 WESTFIELD ESTATES SUB S 67 FT S 05 T '
                                             '22 R 35 SUBID 04', 'lt': '11', 'pb': '11', 'pg': '39', 'r': '35',
                               's': '05', 'subd': ' WESTFIELD ESTATES SUB S 67 FT', 'subid': '04', 't': '22',
                               'u': None})

    def test_Xl_add_data_set_sheet(self):
        self.maxDiff = None

        class TestCol(object):
            def __init__(self):
                self.width = -1

            def __str__(self):
                return 'TestCol()'

        class TestRow(object):
            def __init__(self):
                self.data = {}

            def write(self, col, label, style=None):
                if isinstance(label, Formula):
                    self.data[col] = str(label.text())
                else:
                    self.data[col] = str(label)

            def get_cells_count(self):
                return len(self.data)

            def __repr__(self):
                return 'TestRow(' + str(self.data) + ')'

        class TestSheet(object):
            def __init__(self):
                self.rows = {}
                self.cols = {}

            def row(self, i):
                self.rows[i] = TestRow()
                return self.rows[i]

            def write(self, r, c, label="", style=None):
                self.row(r).write(c, label, style)

            def col(self, i):
                self.cols[i] = TestCol()
                return self.cols[i]

            def get_rows(self):
                return self.rows

        tsheet = TestSheet()

        class StubTime(object):
            pass

        stub_time = StubTime()
        stub_time.time = MagicMock()
        stub_time.time_strftime = MagicMock(return_value='05/13/2017')

        ds = XlBuilder('a_name', stub_time).add_sheet([{'case_number': '05-2008-CA-033772-XXXX-XX',
                                                        'taxes_url': 'https://brevard.county-taxes.com/pubte/parcels/2627712',
                                                        'comment': '', 'taxes_value': '0', 'legals': [],
                                                        'bcpao_item': {'frame code': 'MASNRYCONC, WOOD FRAME',
                                                                       'zip_code': '32940',
                                                                       'year built': '2007',
                                                                       'latest market value total': '$943,700.00',
                                                                       'address': '2778 WYNDHAM WAY MELBOURNE FL 32940',
                                                                       'total base area': '4441'},
                                                        'foreclosure_sale_date': '2017-04-26',
                                                        'orig_mtg_link': {
                                                            'href': 'http://199.241.8.220/y=TIbbOCD+TFEA1or3NprKhA==&theIV99997',
                                                            'title': '456'},
                                                        'bcpao_acc': '2627712', 'orig_mtg_tag': 'OR MTG',
                                                        'latest_amount_due': {
                                                            'href': 'http://199.241.8.22xqhnLZXlXUw==&uid=999999997',
                                                            'title': '567'},
                                                        'count': 2,
                                                        'legal': {'u': None, 'pg': '20', 's': '09', 'pb': '53',
                                                                  'blk': 'A',
                                                                  'lt': '3',
                                                                  'r': '36', 'subd': ' WYNDHAM AT DURAN',
                                                                  'legal_desc': 'LT 3 BLK A PB 53 PG 20DURAN S 09 T 26 R 36 SUBID UH',
                                                                  't': '26', 'subid': 'UH'},
                                                        'case_title': 'BANK NEW YORK VS W COOK'},
                                                       {'case_number': '05-2008-CA-033772-XXXX-XX',
                                                        'taxes_url': 'https://brevard.county-taxes.com/pubte/parcels/2627712',
                                                        'comment': 'CANCELLED', 'taxes_value': '0', 'legals': [],
                                                        'bcpao_item': {'frame code': 'MASNRYCONC, WOOD FRAME',
                                                                       'zip_code': '32940',
                                                                       'year built': '2007',
                                                                       'latest market value total': '$943,700.00',
                                                                       'address': '',
                                                                       'total base area': '4441'},
                                                        'foreclosure_sale_date': '2017-04-26',
                                                        'orig_mtg_link': {
                                                            'href': 'http://199.241.8.220/y=TIbbOCD+TFEA1or3NprKhA==&theIV99997',
                                                            'title': '345'},
                                                        'bcpao_acc': '2627712', 'orig_mtg_tag': 'OR MTG',
                                                        'latest_amount_due': {
                                                            'href': 'http://199.241.8.22xqhnLZXlXUw==&uid=999999997',
                                                            'title': '234'},
                                                        'count': 2,
                                                        'legal': {'u': None, 'pg': '20', 's': '09', 'pb': '53',
                                                                  'blk': 'A',
                                                                  'lt': '3',
                                                                  'r': '36', 'subd': ' WYNDHAM AT DURAN',
                                                                  'legal_desc': 'LT 3 BLK A PB 53 PG 20DURAN S 09 T 26 R 36 SUBID UH',
                                                                  't': '26', 'subid': 'UH'},
                                                        'case_title': 'BANK NEW YORK VS W COOK'}
                                                       ])
        Xl().add_data_set_sheet2(ds, tsheet)
        self.assertEqual(tsheet.get_rows()[0].data[0], 'high')
        self.assertEqual(tsheet.get_rows()[0].data[1], 'win')
        self.assertEqual(tsheet.get_rows()[0].data[2],
                         'HYPERLINK("http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html";"case_number")')
        actuals = [value for key, value in tsheet.get_rows()[0].data.items()]
        self.assertEqual(actuals, ['high',
                                   'win',
                                   'HYPERLINK("http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html";"case_number")',
                                   'case_title',
                                   'fc._sale_date',
                                   'HYPERLINK("https://vmatrix1.brevardclerk.us/beca/CaseNumber_Search.cfm";"beca_case")',
                                   'count',
                                   'address',
                                   'zip',
                                   'HYPERLINK("http://web1.brevardclerk.us/oncoreweb/search.aspx";"liens-name")',
                                   'HYPERLINK("https://www.bcpao.us/PropertySearch";"bcpao")',
                                   'f_code',
                                   'owed_link',
                                   'owed',
                                   'assessed',
                                   'base_area',
                                   'year built',
                                   'owed - ass',
                                   'orig_mtg',
                                   'taxes'])
        headers = []
        for value in tsheet.get_rows()[0].data.values():
            headers.append(value)
        items = []
        for rk, rv in tsheet.get_rows().items():
            if rk > 0:
                i = {}
                for iv, value in enumerate(rv.data.values()):
                    i[headers[iv]] = value
                items.append(i)
        self.assertEqual(items,
                         [{
                             'HYPERLINK("http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html";"case_number")': 'HYPERLINK("http://web1.brevardclerk.us/oncoreweb/search.aspx?bd=1%2F1%2F1981&ed=05%2F13%2F2017&n=&bt=OR&d=5%2F31%2F2014&pt=-1&cn=05-2008-CA-033772-XXXX-XX&dt=ALL+DOCUMENT+TYPES&st=casenumber&ss=ALL+DOCUMENT+TYPES";"05-2008-CA-033772-")',
                             'HYPERLINK("http://web1.brevardclerk.us/oncoreweb/search.aspx";"liens-name")': 'HYPERLINK("http://web1.brevardclerk.us/oncoreweb/search.aspx?bd=1%2F1%2F1981&ed=05%2F13%2F2017&n=COOK%2C+W&bt=OR&d=2%2F5%2F2015&pt=-1&cn=&dt=ALL+DOCUMENT+TYPES&st=fullname&ss=ALL+DOCUMENT+TYPES";"COOK, '
                                                                                                            'W")',
                             'HYPERLINK("https://vmatrix1.brevardclerk.us/beca/CaseNumber_Search.cfm";"beca_case")': 'HYPERLINK("a_name/html_files/2008_CA_033772_case_info.htm";"beca_case")',
                             'HYPERLINK("https://www.bcpao.us/PropertySearch";"bcpao")': 'HYPERLINK("https://www.bcpao.us/PropertySearch/#/parcel/2627712";"2627712")',
                             'address': '2778 WYNDHAM WAY MELBOURNE FL 32940',
                             'assessed': '943700.0',
                             'base_area': '4441.0',
                             'case_title': 'BANK NEW YORK VS W COOK',
                             'count': '2',
                             'f_code': 'MASNRYCONC, WOOD FRAME',
                             'fc._sale_date': '2017-04-26',
                             'high': '',
                             'orig_mtg': 'HYPERLINK("http://199.241.8.220/y=TIbbOCD+TFEA1or3NprKhA==&theIV99997";"OR '
                                         'MTG (456)")',
                             'owed': '',
                             'owed - ass': 'IF(AND(NOT(ISBLANK(O2)),NOT(ISBLANK(P2))), O2-P2, "")',
                             'owed_link': 'HYPERLINK("http://199.241.8.22xqhnLZXlXUw==&uid=999999997";"567")',
                             'taxes': 'HYPERLINK("https://brevard.county-taxes.com/pubte/parcels/2627712";"0")',
                             'win': '',
                             'year built': '2007',
                             'zip': '32940'},
                             {
                                 'HYPERLINK("http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html";"case_number")': 'HYPERLINK("http://web1.brevardclerk.us/oncoreweb/search.aspx?bd=1%2F1%2F1981&ed=05%2F13%2F2017&n=&bt=OR&d=5%2F31%2F2014&pt=-1&cn=05-2008-CA-033772-XXXX-XX&dt=ALL+DOCUMENT+TYPES&st=casenumber&ss=ALL+DOCUMENT+TYPES";"05-2008-CA-033772-")',
                                 'HYPERLINK("http://web1.brevardclerk.us/oncoreweb/search.aspx";"liens-name")': 'HYPERLINK("http://web1.brevardclerk.us/oncoreweb/search.aspx?bd=1%2F1%2F1981&ed=05%2F13%2F2017&n=COOK%2C+W&bt=OR&d=2%2F5%2F2015&pt=-1&cn=&dt=ALL+DOCUMENT+TYPES&st=fullname&ss=ALL+DOCUMENT+TYPES";"COOK, '
                                                                                                                'W")',
                                 'HYPERLINK("https://vmatrix1.brevardclerk.us/beca/CaseNumber_Search.cfm";"beca_case")': 'HYPERLINK("a_name/html_files/2008_CA_033772_case_info.htm";"beca_case")',
                                 'HYPERLINK("https://www.bcpao.us/PropertySearch";"bcpao")': 'HYPERLINK("https://www.bcpao.us/PropertySearch/#/parcel/2627712";"2627712")',
                                 'address': '',
                                 'assessed': '943700.0',
                                 'base_area': '4441.0',
                                 'case_title': 'BANK NEW YORK VS W COOK',
                                 'count': '2',
                                 'f_code': 'MASNRYCONC, WOOD FRAME',
                                 'fc._sale_date': '2017-04-26',
                                 'high': '',
                                 'orig_mtg': 'HYPERLINK("http://199.241.8.220/y=TIbbOCD+TFEA1or3NprKhA==&theIV99997";"OR '
                                             'MTG (345)")',
                                 'owed': '',
                                 'owed - ass': 'IF(AND(NOT(ISBLANK(O3)),NOT(ISBLANK(P3))), O3-P3, "")',
                                 'owed_link': 'HYPERLINK("http://199.241.8.22xqhnLZXlXUw==&uid=999999997";"234")',
                                 'taxes': 'HYPERLINK("https://brevard.county-taxes.com/pubte/parcels/2627712";"0")',
                                 'win': 'CANCELLED',
                                 'year built': '2007',
                                 'zip': '32940'}])

    def test_foreclosures_add_foreclosures(self):
        ret = Foreclosures.add_foreclosures(['papua', 'new', 'guinea'], 2)
        self.assertEqual(['papua', 'new'], ret)

    def test_jac_get_dates_count_map(self):
        ret = Jac().get_dates_count_map([{'foreclosure_sale_date': date(2017, 4, 26), 'val': 2},
                                         {'foreclosure_sale_date': date(2017, 5, 3), 'val': 4}])
        self.assertEqual({date(2017, 4, 26): 1, date(2017, 5, 3): 1}, ret)

    def test_jac_get_non_cancelled_nums(self):
        ret = Jac().get_non_cancelled_nums([{'comment': '', 'foreclosure_sale_date': date(2017, 4, 26)},
                                            {'comment': 'CANCELLED', 'foreclosure_sale_date': date(2017, 4, 27)}])
        self.assertEqual('{datetime.date(2017/4/26: 1}', ret)

    def test_jac_get_email_body(self):
        self.maxDiff = None
        mrs = [{'case_number': '05-2008-CA-033111-XXXX-XX',
                'taxes_url': 'https://brevard.county-taxes.com/public/real_estate/parcels/2627712',
                'comment': '\xa0', 'taxes_value': '0', 'legals': [],
                'bcpao_item': {'frame code': 'MASNRYCONC, WOOD FRAME', 'zip_code': '32940',
                               'year built': '2007', 'latest market value total': '$943,700.00',
                               'address': '2778 WYNDHAM WAY MELBOURNE FL 32940',
                               'total base area': '4441'},
                'foreclosure_sale_date': '2017-04-26',
                'orig_mtg_link': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=7Ba4EeWT71ewgv3amjxLBw==&theKey=TIbbOCD+TFEA1or3NprKhA==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'bcpao_acc': '2627712', 'orig_mtg_tag': 'OR MTG',
                'latest_amount_due': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=kXZYtPY5nJxqhnchAd/gow==&theKey=NN73L3AVCXFc+xj6fiV/lg==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'count': 1,
                'legal': {'u': None, 'pg': '20', 's': '09', 'pb': '53', 'blk': 'A', 'lt': '3',
                          'r': '36', 'subd': ' WYNDHAM AT DURAN',
                          'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH',
                          't': '26', 'subid': 'UH'}, 'case_title': 'BANK NEW YORK VS W COOK'},
               {'case_number': '05-2008-CA-033222-XXXX-XX',
                'taxes_url': 'https://brevard.county-taxes.com/public/real_estate/parcels/2627712',
                'comment': '\xa0', 'taxes_value': '0', 'legals': [],
                'bcpao_item': {'frame code': 'MASNRYCONC, WOOD FRAME', 'zip_code': '32940',
                               'year built': '2007', 'latest market value total': '$943,700.00',
                               'address': '',
                               'total base area': '4441'},
                'foreclosure_sale_date': '2017-04-26',
                'orig_mtg_link': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=7Ba4EeWT71ewgv3amjxLBw==&theKey=TIbbOCD+TFEA1or3NprKhA==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'bcpao_acc': '2627712', 'orig_mtg_tag': 'OR MTG',
                'latest_amount_due': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=kXZYtPY5nJxqhnchAd/gow==&theKey=NN73L3AVCXFc+xj6fiV/lg==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'count': 2,
                'legal': {'u': None, 'pg': '20', 's': '09', 'pb': '53', 'blk': 'A', 'lt': '3',
                          'r': '36', 'subd': ' WYNDHAM AT DURAN',
                          'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH',
                          't': '26', 'subid': 'UH'}, 'case_title': 'BANK NEW YORK VS W COOK'},
               {'case_number': '05-2008-CA-033333-XXXX-XX',
                'taxes_url': 'https://brevard.county-taxes.com/public/real_estate/parcels/2627712',
                'comment': '\xa0', 'taxes_value': '0', 'legals': [],
                'foreclosure_sale_date': '2017-04-26',
                'orig_mtg_link': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=7Ba4EeWT71ewgv3amjxLBw==&theKey=TIbbOCD+TFEA1or3NprKhA==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'orig_mtg_tag': 'OR MTG',
                'latest_amount_due': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=kXZYtPY5nJxqhnchAd/gow==&theKey=NN73L3AVCXFc+xj6fiV/lg==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'count': 3,
                'legal': {'u': None, 'pg': '20', 's': '09', 'pb': '53', 'blk': 'A', 'lt': '3',
                          'r': '36', 'subd': ' WYNDHAM AT DURAN',
                          'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH',
                          't': '26', 'subid': 'UH'}, 'case_title': 'BANK NEW YORK VS W COOK'},
               {'case_number': '05-2008-CA-044444-XXXX-XX',
                'taxes_url': 'https://brevard.county-taxes.com/public/real_estate/parcels/2627712',
                'comment': '\xa0', 'taxes_value': '0', 'legals': [],
                'foreclosure_sale_date': '2017-04-26',
                'orig_mtg_link': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=7Ba4EeWT71ewgv3amjxLBw==&theKey=TIbbOCD+TFEA1or3NprKhA==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'orig_mtg_tag': 'OR MTG',
                'latest_amount_due': 'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=kXZYtPY5nJxqhnchAd/gow==&theKey=NN73L3AVCXFc+xj6fiV/lg==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997',
                'count': 4,
                'legal': None, 'case_title': 'BANK NEW YORK VS W COOK'}
               ]
        ret = Jac().get_email_body('test_abc', 'test_date_counts', 'test_filename', mrs)
        print(ret)
        self.assertEqual(
            'this result is for: test_abc<br>total records: 4<br><br>the following summarizes how many not-cancelled items there are per month in the <a href="http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html">foreclosure sales page</a> as of now: <br>test_date_counts<br><br>test_filename\n\n<br><br>could not get addresses for the following: <br>\n'
            'count_id: 2, 05-2008-CA-033222-XXXX-XX<br>\n'
            '  "LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH"<br>\n'
            'count_id: 3, 05-2008-CA-033333-XXXX-XX<br>\n'
            '  "LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH"<br>\n'
            'count_id: 4, 05-2008-CA-044444-XXXX-XX<br>\n'
            'None'
            , ret)

    def test_bcpao_get_bcpao_searches(self):
        # account: 2202306
        # address: 360 S Christmas Hill Rd Titusville FL 32796
        # parcel id: 22-35-05-04-3-11
        # land description: Westfield Estates Sub S 67 Ft Of Lot 11, N 23 Ft Of Lot 15 & N 23 Ft Of E 45.67 Ft Of Lot 14 Blk 3
        # https://www.bcpao.us/api/v1/search?parcel=20G-35-04-ABC-123-5.6&activeonly=true&sortColumn=siteAddress&sortOrder=asc&size=10&page=1
        l = BclerkPublicRecords.get_legal_from_str(
            'LT 11 BLK 3 PB 12 PG 39 WESTFIELD ESTATES SUB S 67 FT S 05 T 22 R 35 SUBID 04')
        ret = Bcpao().get_bcpao_searches(l)
        ret_reqs = [x.request for x in ret]
        pprint.pprint(ret_reqs)
        self.assertEqual([{'endpoint': 'https://www.bcpao.us/api/v1/search?',
                           'headers': {'Accept': 'application/json'},
                           'params': OrderedDict([('lot', '11'),
                                                  ('blk', '3'),
                                                  ('platbook', '12'),
                                                  ('platpage', '39'),
                                                  ('subname', b' WESTFIELD ESTATES SUB S 67 FT'),
                                                  ('activeonly', 'true'),
                                                  ('size', '10'),
                                                  ('page', '1')]),
                           'url2': 'https://www.bcpao.us/api/v1/search?lot=11&blk=3&platbook=12&platpage=39&subname=+WESTFIELD+ESTATES+SUB+S+67+FT&activeonly=true&size=10&page=1'},
                          {'endpoint': 'https://www.bcpao.us/api/v1/search?',
                           'headers': {'Accept': 'application/json'},
                           'params': OrderedDict([('parcel',
                                                   '22-35-05-04-3-11'),
                                                  ('activeonly', 'true'),
                                                  ('size', '10'),
                                                  ('page', '1')]),
                           'url2': 'https://www.bcpao.us/api/v1/search?parcel=22-35-05-04-3-11&activeonly=true&size=10&page=1'}],
                         ret_reqs)

    def test_bcpao_get_bcpao_searches_1(self):
        l = BclerkPublicRecords.get_legal_from_str(
            'LT 15 BLK 49 PB 3 PG 35 INDIALANTIC BY THE SEA S 36 T 27 R 37 SUBID EO')
        ret = Bcpao().get_bcpao_searches(l)
        ret_reqs = [x.request for x in ret]
        self.assertEqual([{'endpoint': 'https://www.bcpao.us/api/v1/search?',
                           'headers': {'Accept': 'application/json'},
                           'params': OrderedDict([('lot', '15'),
                                                  ('blk', '49'),
                                                  ('platbook', '3'),
                                                  ('platpage', '35'),
                                                  ('subname', b' INDIALANTIC BY THE SEA'),
                                                  ('activeonly', 'true'),
                                                  ('size', '10'),
                                                  ('page', '1')]),
                           'url2': 'https://www.bcpao.us/api/v1/search?lot=15&blk=49&platbook=3&platpage=35&subname=+INDIALANTIC+BY+THE+SEA&activeonly=true&size=10&page=1'},
                          {'endpoint': 'https://www.bcpao.us/api/v1/search?',
                           'headers': {'Accept': 'application/json'},
                           'params': OrderedDict([('parcel', '27-37-36-EO-49-15'),
                                                  ('activeonly', 'true'),
                                                  ('size', '10'),
                                                  ('page', '1')]),
                           'url2': 'https://www.bcpao.us/api/v1/search?parcel=27-37-36-EO-49-15&activeonly=true&size=10&page=1'}],
                         ret_reqs)

    def test_bcpao_get_bcpao_searches_2(self):
        l = BclerkPublicRecords.get_legal_from_str(
            'LT 2 PB 54 PG 57 PARKSIDE WEST P.U.D. S 33 T 28 R 36 SUBID 50')
        ret = Bcpao().get_bcpao_searches(l)
        ret_reqs = [x.request for x in ret]
        pprint.pprint(ret_reqs)
        self.assertEqual([{'endpoint': 'https://www.bcpao.us/api/v1/search?',
                           'headers': {'Accept': 'application/json'},
                           'params': OrderedDict([('lot', '2'),
                                                  ('platbook', '54'),
                                                  ('platpage', '57'),
                                                  ('subname', b' PARKSIDE WEST P.U.D.'),
                                                  ('activeonly', 'true'),
                                                  ('size', '10'),
                                                  ('page', '1')]),
                           'url2': 'https://www.bcpao.us/api/v1/search?lot=2&platbook=54&platpage=57&subname=+PARKSIDE+WEST+P.U.D.&activeonly=true&size=10&page=1'},
                          {'endpoint': 'https://www.bcpao.us/api/v1/search?',
                           'headers': {'Accept': 'application/json'},
                           'params': OrderedDict([('parcel', '28-36-33-50-*-2'),
                                                  ('activeonly', 'true'),
                                                  ('size', '10'),
                                                  ('page', '1')]),
                           'url2': 'https://www.bcpao.us/api/v1/search?parcel=28-36-33-50-%2A-2&activeonly=true&size=10&page=1'}],
                         ret_reqs)

    def test_bcpao_get_bcpao_searches_3(self):
        l = BclerkPublicRecords.get_legal_from_str(
            'LT 204 PINEWOOD I & II TOWNHOMES')
        ret = Bcpao().get_bcpao_searches(l)
        ret_reqs = [x.request for x in ret]
        self.assertEqual([None, None], ret_reqs)

    def test_jac_go(self):
        class StubForeInfra(object):
            pass

        class StubFileInfra(object):
            pass

        sfi = StubFileInfra()
        sfi.do_mkdirs = MagicMock()

        class StubTime(object):
            pass

        stub_fore_infra = StubForeInfra()
        stub_fore_infra.get_items_resp_from_req = MagicMock(return_value='<html></html>')

        stub_time = StubTime()
        stub_time.time = MagicMock()
        stub_time.time.side_effect = [3, 5]  # list of values to return on each call
        stub_time.time_strftime = MagicMock(return_value='2017-05-13__19-54-16')
        stub_time.get_today = MagicMock(return_value=date(2016, 11, 22))

        class StubEmailInfra(object):
            pass

        stub_email = StubEmailInfra()
        stub_email.send_mail = MagicMock()

        class StubZip(object):
            pass

        stub_zip = StubZip()
        stub_zip.do_zip = MagicMock(return_value='test_zip_path')

        class StubExcel(object):
            pass

        class StubBook(object):
            pass

        stub_xl = StubExcel()
        mocked_book = StubBook()
        mocked_book.add_sheet = MagicMock()
        mocked_book.save = MagicMock()
        stub_xl.get_a_book = MagicMock(return_value=mocked_book)

        Jac(stub_email, stub_fore_infra, sfi, None, None, None, None, stub_zip, stub_time, stub_xl).go2(
            argparse.Namespace(zip=True, email=True, passw='test_pass'))
        calls = [call('outputs/2017-05-13__19-54-16'),
                 call('outputs/2017-05-13__19-54-16/11-23/html_files'),
                 call('outputs/2017-05-13__19-54-16/11-30/html_files')]
        sfi.do_mkdirs.assert_has_calls(calls)
        stub_email.send_mail.assert_called_once_with('orozcoadrian', 'test_pass', 'orozcoadrian@gmail.com',
                                                     ['orozcoadrian@gmail.com', 'spacecoastmarketing@gmail.com'],
                                                     '[jac biweekly report] for: 11.23.16',
                                                     'this result is for: 11.23.16<br>total records: 0<br><br>the following summarizes how many not-cancelled items there are per month in the <a href="http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html">foreclosure sales page</a> as of now: <br>{}<br><br>11.23.16.xls',
                                                     ['outputs/2017-05-13__19-54-16/11.23.16.xls', 'test_zip_path'],
                                                     'smtp.gmail.com:587')
        stub_zip.do_zip.assert_called_once_with('outputs/2017-05-13__19-54-16', 'outputs', '11.23.16')
        stub_xl.get_a_book.assert_called_once_with()
        mocked_book.save.assert_called_once_with('outputs/2017-05-13__19-54-16/11.23.16.xls')


if __name__ == '__main__':
    unittest.main()

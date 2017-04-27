import unittest
from datetime import date

from main import Foreclosures, MyDate, Jac, Taxes, Bcpao, BclerkPublicRecords, BclerkEfacts, XlBuilder


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

    def test_public_records_get_request_info(self):
        ret = BclerkPublicRecords().get_request_info('test_acct')
        self.assertEqual(ret, {'uri': 'http://web1.brevardclerk.us/oncoreweb/search.aspx',
                               'form': {'SearchType': 'casenumber',
                                        'txtCaseNumber': 'test_acct',
                                        'txtDocTypes': ''}})

    def test_public_records_parse_records_grid_response(self):
        with open('public_records_resp.html', 'rb') as myfile:
            ret = BclerkPublicRecords().parse_response(myfile.read())
            self.assertEqual(ret, [
                {'t': '26', 'lt': '3', 'subd': ' WYNDHAM AT DURAN', 's': '09', 'u': None, 'blk': 'A', 'pg': '20',
                 'subid': 'UH', 'pb': '53',
                 'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH', 'r': '36'}])

    def test_bclerk_efacts_pre_cache(self):
        ret = BclerkEfacts().pre_cache('05-2008-CA-006267-XXXX-XX', 'test_out_dir')
        self.assertEquals(ret,
                          {'out_dir': 'test_out_dir', 'year': '2008', 'seq_number': '006267', 'id2': '2008_CA_006267',
                           'court_type': 'CA'})

    def test_bclerk_efacts_get_request_info(self):
        ret = BclerkEfacts().get_request_info('CA', '006267', '2008')
        self.assertEquals(ret, {'timeout': 5, 'headers': {'Content-Type': 'application/x-www-form-urlencoded',
                                                          'Cookie': 'CFID=1550556; CFTOKEN=74317641; JSESSIONID=None'},
                                'url': 'https://vweb1.brevardclerk.us/facts/d_caseno.cfm', 'stream': True,
                                'data': 'CaseNumber1=05&CaseNumber2=2008&CaseNumber3=CA&CaseNumber4=006267&CaseNumber5=&CaseNumber6=&submit=Submit'})

    def test_bclerk_efacts_get_reg_actions_req_info(self):
        ret = BclerkEfacts().get_reg_actions_req_info('CA', '99AF34FAA963FD449F028397802FF0E4.cfusion', '006267',
                                                      '2008')
        self.assertEquals(ret, {
            'data': 'CaseNumber1=05&CaseNumber2=2008&CaseNumber3=CA&CaseNumber4=006267&CaseNumber5=&CaseNumber6=&submit=Submit',
            'headers': {'Cookie': 'CFID=4749086; CFTOKEN=23056266; JSESSIONID=99AF34FAA963FD449F028397802FF0E4.cfusion',
                        'Content-Type': 'application/x-www-form-urlencoded'},
            'url': 'https://vweb1.brevardclerk.us/facts/d_reg_actions.cfm?RequestTimeout=500'})

    def test_bclerk_efacts_get_reg_actions_parse(self):
        with open('bclerk_reg_response.html', 'rb') as myfile:
            lad, tag, url = BclerkEfacts().parse_reg_actions_response(myfile.read())
            self.assertEqual(lad,
                             'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=7tioo4AAF5DuCsZjF66dIw==&theKey=14mhPOwb8DAlMYwyf4HSrg==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997')
            self.assertEqual(tag, 'OR MTG')
            self.assertEqual(url,
                             'http://199.241.8.220/ImageView/ViewImage.aspx?barcodeid=rbBXye6I4qu58q/YufJbBA==&theKey=mfLJJALQq7FewO9aj6kDPQ==&theIV=UGxDS2V5V1NQbENLZXlXUw==&uid=999999997')

    def test_xlbuilder_with_rows(self):
        instance = XlBuilder('test_name')
        # records = [MyRecord.MyRecord({
        #     'case_number': 'cn0'
        #     , 'case_title': 'ct0'
        #     , 'foreclosure_sale_date': '2'
        #     , 'count': '2'
        #     , 'comment': ''
        #     , 'taxes_value': ''
        # })]
        data_set = instance.add_sheet([{'case_number': '05-2008-CA-033772-XXXX-XX',
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
                                        'count': 2,
                                        'legal': {'u': None, 'pg': '20', 's': '09', 'pb': '53', 'blk': 'A', 'lt': '3',
                                                  'r': '36', 'subd': ' WYNDHAM AT DURAN',
                                                  'legal_desc': 'LT 3 BLK A PB 53 PG 20 WYNDHAM AT DURAN S 09 T 26 R 36 SUBID UH',
                                                  't': '26', 'subid': 'UH'}, 'case_title': 'BANK NEW YORK VS W COOK'}])
        self.assertTrue(data_set is not None)
        print(data_set.get_items())
        # for row in data_set.get_items():
        header_row = data_set.get_items()[0]
        self.assertEqual(21, len(header_row))
        self.assertEqual('high', header_row[0].get_display())
        self.assertEqual('win', header_row[1].get_display())
        self.assertEqual('case_number', header_row[2].get_display())
        self.assertEqual('case_title', header_row[3].get_display())
        self.assertEqual('fc._sale_date', header_row[4].get_display())
        self.assertEqual('case_info', header_row[5].get_display())
        self.assertEqual('reg_actions', header_row[6].get_display())
        self.assertEqual('count', header_row[7].get_display())
        self.assertEqual('address', header_row[8].get_display())
        self.assertEqual('zip', header_row[9].get_display())
        self.assertEqual('liens-name', header_row[10].get_display())
        self.assertEqual('bcpao', header_row[11].get_display())
        self.assertEqual('f_code', header_row[12].get_display())
        self.assertEqual('owed_link', header_row[13].get_display())
        self.assertEqual('owed', header_row[14].get_display())
        self.assertEqual('assessed', header_row[15].get_display())
        self.assertEqual('base_area', header_row[16].get_display())
        self.assertEqual('year built', header_row[17].get_display())
        self.assertEqual('owed - ass', header_row[18].get_display())
        self.assertEqual('orig_mtg', header_row[19].get_display())
        self.assertEqual('taxes', header_row[20].get_display())
        first_data_row = data_set.get_items()[1]
        self.assertEqual('', first_data_row[0].get_display())
        self.assertEqual('\xa0', first_data_row[1].get_display())
        self.assertEqual('05-2008-CA-033772-', first_data_row[2].get_display())
        self.assertEqual('BANK NEW YORK VS W COOK', first_data_row[3].get_display())
        self.assertEqual('2017-04-26', first_data_row[4].get_display())
        self.assertEqual('case_info', first_data_row[5].get_display())
        self.assertEqual('reg_actions', first_data_row[6].get_display())
        self.assertEqual(2, first_data_row[7].get_display())
        self.assertEqual('2778 WYNDHAM WAY MELBOURNE FL 32940', first_data_row[8].get_display())
        self.assertEqual(32940, first_data_row[9].get_display())
        self.assertEqual('COOK, W', first_data_row[10].get_display())
        self.assertEqual('2627712', first_data_row[11].get_display())
        self.assertEqual('MASNRYCONC, WOOD FRAME', first_data_row[12].get_display())
        self.assertEqual('link', first_data_row[13].get_display())
        self.assertEqual('', first_data_row[14].get_display())
        self.assertEqual(943700.0, first_data_row[15].get_display())
        self.assertEqual(4441.0, first_data_row[16].get_display())
        self.assertEqual(2007, first_data_row[17].get_display())
        self.assertEqual(None, first_data_row[18].get_display())
        self.assertEqual('OR MTG', first_data_row[19].get_display())
        self.assertEqual('0', first_data_row[20].get_display())


if __name__ == '__main__':
    unittest.main()

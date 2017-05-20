import argparse
import itertools
import json
import locale
import logging
import os
import pprint
import re
import sys
import urllib.parse
from collections import OrderedDict
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from xlwt import easyxf, Formula


class Item(object):
    @staticmethod
    def pre_cache2(case):
        ret = dict(court_type=None, id2=None, seq_number=None, year=None)
        m = re.search('(\\d{2})-(\\d{4})-(.{2})-(\\d{6})-.*', case)
        if m:
            ret['year'] = m.group(2)
            ret['court_type'] = m.group(3)
            ret['seq_number'] = m.group(4)
            ret['id2'] = ret['year'] + '_' + ret['court_type'] + '_' + ret['seq_number']
        return ret

    @staticmethod
    def get_id2_from_item(i):
        return Item.pre_cache2(i['case_number'])['id2']


class FilterCancelled(object):
    @staticmethod
    def apply(mrs):
        return [x for x in mrs if 'CANCELLED' not in x['comment']]


class FilterByDates(object):
    def __init__(self):
        self.dates = None

    def set_dates(self, dates):
        self.dates = dates

    def apply(self, mrs):
        return [x for x in mrs if x['foreclosure_sale_date'] in self.dates]


class XlBuilder(object):
    def __init__(self, sheet_name, time_infra):
        self.sheet_name = sheet_name
        self.time_infra = time_infra
        self.args = None
        self.column_handlers = {}
        self.headers = []

    def get_assessed_str(self, i):
        a_str = self.try_get(i, 'bcpao_item', 'latest market value total').replace('$', '').replace(',', '')
        return a_str

    @staticmethod
    def get_base_area(i):
        the_strba = ''
        if 'bcpao_item' in i and 'total base area' in i['bcpao_item']:
            if len(i['bcpao_item']['total base area']) > 0:
                the_strba = float(i['bcpao_item']['total base area'].replace(',', ''))
        return the_strba

    @staticmethod
    def get_year_built_str(i):
        the_str3 = ''
        if 'bcpao_item' in i and 'year built' in i['bcpao_item']:
            try:
                the_str3 = int(i['bcpao_item']['year built'])
            except ValueError:
                print("error parsing i['bcpao_item']['year built']='" + i['bcpao_item']['year built'] + "' as an int")
        return the_str3

    def get_reg_actions_link(self, i):
        return self.get_sheet_name() + '/html_files/' + Item.get_id2_from_item(i) + '_reg_actions.htm'

    def get_case_info_link(self, i):
        return self.get_sheet_name() + '/html_files/' + Item.get_id2_from_item(i) + '_case_info.htm'

    def get_sheet_name(self):
        return self.sheet_name

    def add_sheet(self, items):
        rows = []
        headers = self.get_headers
        rows.append(headers)

        for index, i in enumerate(self.get_items_to_use(items)):
            row = []
            self.add_to_row(row, i, index)
            rows.append(row)

        ret = DataSet(self.get_sheet_name(), rows)
        return ret

    def get_bclerk_name_url(self, name):
        today = self.time_infra.time_strftime('%m/%d/%Y')
        search_endpoint = 'http://web1.brevardclerk.us/oncoreweb/search.aspx?'
        params = OrderedDict()
        params['bd'] = '1/1/1981'
        params['ed'] = today
        params['n'] = name
        params['bt'] = 'OR'
        params['d'] = '2/5/2015'
        params['pt'] = '-1'
        params['cn'] = ''
        params['dt'] = 'ALL DOCUMENT TYPES'
        params['st'] = 'fullname'
        params['ss'] = 'ALL DOCUMENT TYPES'
        return search_endpoint + urllib.parse.urlencode(params)

    def get_case_number_url(self, cn):
        today = self.time_infra.time_strftime('%m/%d/%Y')
        search_endpoint = 'http://web1.brevardclerk.us/oncoreweb/search.aspx?'
        params = OrderedDict()
        params['bd'] = '1/1/1981'
        params['ed'] = today
        params['n'] = ''
        params['bt'] = 'OR'
        params['d'] = '5/31/2014'
        params['pt'] = '-1'
        params['cn'] = cn
        params['dt'] = 'ALL DOCUMENT TYPES'
        params['st'] = 'casenumber'
        params['ss'] = 'ALL DOCUMENT TYPES'
        return search_endpoint + urllib.parse.urlencode(params)

    @staticmethod
    def get_items_to_use(all_items):
        return all_items  # no filtering here

    @property
    def get_headers(self):
        if len(self.headers) == 0:
            headers = [Cell.from_display("high", width=3000),
                       Cell.from_display("win", width=3000),
                       Cell.from_link("case_number", 'http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html',
                                      width=5000),
                       Cell.from_display("case_title", width=10000),
                       Cell.from_display("fc._sale_date", width=3000),
                       Cell.from_link("case_info", 'https://vweb1.brevardclerk.us/facts/caseno.cfm'),
                       Cell.from_link("reg_actions", 'https://vweb1.brevardclerk.us/facts/caseno.cfm'),
                       Cell.from_display("count"),
                       Cell.from_display("address", width=10000),
                       Cell.from_display("zip"),
                       Cell.from_link("liens-name", 'http://web1.brevardclerk.us/oncoreweb/search.aspx', width=5000),
                       Cell.from_link("bcpao", 'https://www.bcpao.us/PropertySearch'),
                       Cell.from_display("f_code"),
                       Cell.from_display("owed_link"),
                       Cell.from_display("owed", width=4000),
                       Cell.from_display("assessed"),
                       Cell.from_display("base_area"),
                       Cell.from_display("year built"),
                       Cell.from_display("owed - ass"),
                       Cell.from_display("orig_mtg"),
                       Cell.from_display("taxes")]
            self.headers = headers
        return self.headers

    @staticmethod
    def get_display_case_number(case_number):
        return case_number.replace('XXXX-XX', '')

    @staticmethod
    def try_get(i, one, two):
        if one in i and i[one] is not None and two in i[one]:
            return i[one][two]
        return ''

    def add_to_row(self, row, r, row_index):
        i = r
        for col_index, h in enumerate(self.get_headers):
            str(col_index)
            if 'high' in h.get_display():
                row.append(Cell.from_display(''))
            if 'win' in h.get_display():
                row.append(Cell.from_display(i['comment']))
            if 'case_number' in h.get_display():
                row.append(Cell.from_link(self.get_display_case_number(i['case_number']),
                                          self.get_case_number_url(i['case_number'])))
            if 'case_title' in h.get_display():
                row.append(Cell.from_display(i['case_title']))
            if 'fc._sale_date' in h.get_display():
                row.append(Cell.from_display(i['foreclosure_sale_date']))
            if 'count' in h.get_display():
                row.append(Cell.from_display(i['count']))

            if 'address' in h.get_display():
                the_str = ''
                if 'bcpao_item' in i and i['bcpao_item'] is not None and 'address' in i['bcpao_item']:
                    the_str = i['bcpao_item']['address']
                row.append(Cell.from_display(the_str))
            if 'zip' in h.get_display():
                value_to_use = Cell.from_display('')
                zip_str = self.try_get(i, 'bcpao_item', 'zip_code')
                if zip_str:
                    value_to_use = Cell.from_display(int(zip_str))
                row.append(value_to_use)
            if 'owed_link' == h.get_display():
                if 'latest_amount_due' in i:
                    if i['latest_amount_due'] and len(i['latest_amount_due']) > 0:
                        row.append(Cell.from_link('link', i['latest_amount_due']))
                    else:
                        row.append(Cell.from_display(''))
            if 'owed' == h.get_display():
                row.append(Cell.from_display(''))  # left blank to manually add the value
            if 'case_info' in h.get_display():
                link_str = self.get_case_info_link(i)
                row.append(Cell.from_link('case_info', link_str))
            if 'reg_actions' in h.get_display():
                link_str2 = self.get_reg_actions_link(i)
                row.append(Cell.from_link('reg_actions', link_str2))
            if 'liens-name' in h.get_display():
                value_to_use = Cell.from_display('')
                name_combos = BclerkPublicRecords().get_name_combos(r)
                if name_combos is not None and len(name_combos) > 0:
                    value_to_use = Cell.from_link(name_combos[0], self.get_bclerk_name_url(name_combos[0]))
                row.append(value_to_use)
            if 'bcpao' == h.get_display():
                the_str = None
                if 'bcpao_acc' in i and len(i['bcpao_acc']) > 0:
                    the_str = i['bcpao_acc']
                if the_str is None:
                    row.append(Cell.from_display(''))
                else:
                    row.append(Cell.from_link(the_str, Bcpao.get_bcpao_query_url_by_acct(the_str)))
            if 'f_code' in h.get_display():
                fc_str = ''
                if 'bcpao_item' in i and 'frame code' in i['bcpao_item']:
                    fc_str = i['bcpao_item']['frame code']
                row.append(Cell.from_display(fc_str))
            if 'assessed' in h.get_display():
                value_to_use = Cell.from_display('')
                a_str = self.get_assessed_str(i)
                if a_str:
                    try:
                        value_to_use = Cell.from_display(float(a_str))
                    except ValueError:
                        value_to_use = Cell.from_display(a_str)
                row.append(value_to_use)
            if 'base_area' in h.get_display():
                the_strba = self.get_base_area(i)
                row.append(Cell.from_display(the_strba))
            if 'year built' in h.get_display():
                year = self.get_year_built_str(i)
                row.append(Cell.from_display(year))
            if 'owed - ass' in h.get_display():
                row_str = str(row_index + 2)
                owed_column = 'P'  # latest_amount_due
                ass_column = 'Q'  # latest market value total
                if_cond = 'AND(NOT(ISBLANK(' + owed_column + row_str + ')),NOT(ISBLANK(' + ass_column + row_str + ')))'
                true_case = owed_column + row_str + '-' + ass_column + row_str
                false_case = '""'
                f_str2 = 'IF(' + if_cond + ', ' + true_case + ', ' + false_case + ')'
                row.append(Cell.from_formula(f_str2))
            if 'orig_mtg' == h.get_display():
                if 'orig_mtg_link' in i:
                    if i['orig_mtg_link'] and len(i['orig_mtg_link']) > 0:
                        row.append(Cell.from_link(i['orig_mtg_tag'], i['orig_mtg_link']))
                    else:
                        row.append(Cell.from_display(''))
            if 'taxes' in h.get_display():
                value_to_use = Cell.from_display('')
                if 'taxes_value' in i:
                    value_to_use = Cell.from_link(i['taxes_value'], i['taxes_url'])
                row.append(value_to_use)


class Cell(object):
    def __init__(self, display, link, formula, width):
        self.display = display
        self.link = link
        self.width = width
        self.formula = formula

    @classmethod
    def from_display(cls, display, width=None):
        return cls(display, link=None, formula=None, width=width)

    @classmethod
    def from_link(cls, display, link, width=None):
        return cls(display, link, formula=None, width=width)

    @classmethod
    def from_formula(cls, formula, width=None):
        return cls(display=None, link=None, formula=formula, width=width)

    def get_display(self):
        return self.display

    def get_link(self):
        return self.link

    def set_link(self, link):
        self.link = link

    def get_formula(self):
        return self.formula

    def __str__(self):
        return 'Cell(%s)' % self.display

    def __repr__(self):
        return self.__str__()

    def set_col_width(self, width):
        self.width = width

    def get_col_width(self):
        return self.width


class DataSet(object):
    def __init__(self, name, items):
        self.name = name
        self.items = items

    def get_name(self):
        return self.name + '(' + str(len(self.get_items()) - 1) + ')'

    def get_items(self):
        return self.items

    def get_row(self, row):
        return self.items[row]


class Xl(object):
    def __init__(self):
        self.link_style = easyxf('font: underline single, color blue')

    def add_data_set_sheet(self, ds, book):
        sheet = book.add_sheet(ds.get_name())
        self.add_data_set_sheet2(ds, sheet)

    def add_data_set_sheet2(self, ds, sheet):
        for iX, itemX in enumerate(ds.get_items()):
            row = sheet.row(iX)
            for iY, itemY in enumerate(itemX):
                try:
                    if itemY is None:
                        row.write(iY, '')
                    elif itemY.get_link() is not None:
                        row.write(iY, self.get_formula_hyperlink(itemY.get_link(), itemY.get_display()),
                                  self.link_style)
                    elif itemY.get_formula() is not None:
                        row.write(iY, self.get_formula(itemY.get_formula()))
                    else:
                        row.write(iY, itemY.get_display())
                except:
                    raise
                if itemY is not None and itemY.get_col_width() is not None:
                    sheet.col(iY).width = itemY.get_col_width()

    @staticmethod
    def get_formula_hyperlink(url, text):
        return Formula('HYPERLINK("' + url + '";"' + text + '")')

    @staticmethod
    def get_formula(formula):
        return Formula(formula)


class Taxes(object):
    def __init__(self, taxes_infra):
        self.taxes_infra = taxes_infra

    def get_info_from_account(self, bcpao_acc):
        if len(bcpao_acc) > 0:
            return self.get_info_from_response(bcpao_acc, self.taxes_infra.get_resp_from_req(
                self.get_tax_url_from_taxid(bcpao_acc)))

    def get_info_from_response(self, tax_id, resp):
        if resp is not None:
            pay_all = self.get_amount_unpaid_from_tax_text(resp)
            if pay_all:
                display_str = pay_all.replace('$', '').replace(',', '')
                ret = {'value_to_use': display_str, 'url_to_use': self.get_tax_url_from_taxid(tax_id)}
                return ret

    @staticmethod
    def get_tax_url_from_taxid(tax_id):
        url = 'https://brevard.county-taxes.com/public/real_estate/parcels/' + tax_id
        return url

    @staticmethod
    def get_amount_unpaid_from_tax_text(r_text):
        ret = None
        if r_text is not None:
            ret = '0'
            soup = BeautifulSoup(r_text.decode('utf-8'), "html.parser")
            amt_unpaid_elem = soup.find('div', class_=re.compile('amount unpaid.*'))
            if amt_unpaid_elem is not None:
                m = re.search('.*\$([\d,.]*) due.*', amt_unpaid_elem.text)
                if m:
                    ret = m.group(1)
        return ret


class BcpaoBySubOrT(object):
    def __init__(self, legal_arg):
        self.request = self.get_acct_by_legal_request(legal_arg)

    @staticmethod
    def get_acct_by_legal_request(legal_arg):
        ret = None
        if 'subd' in legal_arg or 't' in legal_arg:
            legal = (legal_arg['subd'], legal_arg['lt'], legal_arg['blk'], legal_arg['pb'], legal_arg['pg'],
                     legal_arg['s'], legal_arg['t'], legal_arg['r'], legal_arg['subid'])
            sub, lot, block, pb, pg, s, t, r, subid = legal
            sub = sub.replace(u'\xc2', u'').encode('utf-8')
            bcpao_search_endpoint = 'https://www.bcpao.us/api/v1/search?'
            params = OrderedDict()
            if lot is not None:
                params['lot'] = str(lot)
            if block is not None:
                params['blk'] = str(block)
            if pb is not None:
                params['platbook'] = str(pb)
            if pg is not None:
                params['platpage'] = str(pg)
            params['subname'] = sub
            params['activeonly'] = 'true'
            params['size'] = '10'
            params['page'] = '1'

            url2 = bcpao_search_endpoint + urllib.parse.urlencode(params)
            ret = {'url2': url2, 'headers': {'Accept': 'application/json'}, 'endpoint': bcpao_search_endpoint,
                   'params': params}
        return ret

    @staticmethod
    def parse_acct_by_legal_response(resp):
        if resp.status_code == 200 and len(resp.text) > 0:
            loaded_json = json.loads(resp.text)  # use req.json() instead?
            if loaded_json and len(loaded_json) == 1:
                return loaded_json[0]['account']


class BcpaoByParcelId(object):
    def __init__(self, legal_arg):
        self.request = self.get_acct_by_legal_request(legal_arg)

    @staticmethod
    def get_acct_by_legal_request(legal_arg):
        if all(k in legal_arg for k in ['t', 'r', 's', 'subid', 'blk', 'lt']):
            arry_pid_parts = [legal_arg['t'], legal_arg['r'], legal_arg['s'], legal_arg['subid'], legal_arg['blk'],
                              legal_arg['lt']]

            # REPLACE BLANK PID PARTS WITH ASTERISK
            str_pid = ''
            pid_parts_count = 0
            for i in range(len(arry_pid_parts)):
                if arry_pid_parts[i] is None or arry_pid_parts[i] == '--':
                    str_part = '*'
                else:
                    str_part = arry_pid_parts[i]
                    pid_parts_count += 1
                # Build PID string
                str_pid += str_part + '-'

            # IF LAST CHARACTER IN PID STRING IS -, REMOVE IT
            if str_pid.endswith('-'):
                str_pid = str_pid[:-1]

            # IF LAST CHARACTER IN PID STRING IS -* or *-, REMOVE IT
            if str_pid.endswith('-*') or str_pid.endswith('*-'):
                str_pid = str_pid[:-2]

            arry_pid_parts_str = str_pid

            bcpao_search_endpoint = 'https://www.bcpao.us/api/v1/search?'
            params = OrderedDict()
            params['parcel'] = arry_pid_parts_str
            params['activeonly'] = 'true'
            params['size'] = '10'
            params['page'] = '1'

            url2 = bcpao_search_endpoint + urllib.parse.urlencode(params)
            ret = {'url2': url2, 'headers': {'Accept': 'application/json'}, 'endpoint': bcpao_search_endpoint,
                   'params': params}
            return ret

    @staticmethod
    def parse_acct_by_legal_response(resp):
        if resp.status_code == 200 and len(resp.text) > 0:
            loaded_json = json.loads(resp.text)  # use req.json() instead?
            if loaded_json and len(loaded_json) == 1:
                return loaded_json[0]['account']


class Bcpao(object):
    def __init__(self, bcpao_infra=None):
        self.bcpao_infra = bcpao_infra

    @staticmethod
    def get_parcel_data_by_acct2_request(acct):
        ret = {'url': 'https://www.bcpao.us/api/v1/account/' + str(acct),
               'headers': {'Accept': 'application/json'}}
        return ret

    @staticmethod
    def parse_bcpaco_item_response(resp):
        ret = {}
        if resp.status_code == 200:
            parsed_json = json.loads(resp.text)
            if 'Multiple Addresses' in parsed_json['siteAddress'] and len(parsed_json['siteAddresses']) > 0:
                addr_str = parsed_json['siteAddresses'][0]['siteAddress']
            else:
                addr_str = parsed_json['siteAddress']
            ret['address'] = addr_str  # .replace('\\r\\n','').strip()
            ret['zip_code'] = ret['address'][-5:]
            fc = ''
            if parsed_json is not None and 'buildings' in parsed_json and parsed_json['buildings'] is not None and len(
                    parsed_json['buildings']) > 0 and 'constructionInfo' in parsed_json['buildings'][0]:
                for bseq in parsed_json['buildings'][0]['constructionInfo']:
                    if 'code' in bseq and 'FRAME' in bseq['code']:
                        fc = bseq['description']
                        break
            ret['frame code'] = re.sub(' +', ' ', fc).replace(' ,', ',')
            yb_str = ''
            if parsed_json is not None and 'buildings' in parsed_json and parsed_json['buildings'] is not None and len(
                    parsed_json['buildings']) > 0 and 'yearBuilt' in parsed_json['buildings'][0]:
                yb_str = str(parsed_json['buildings'][0]['yearBuilt'])
            ret['year built'] = yb_str
            tba_str = ''
            if parsed_json is not None and 'buildings' in parsed_json and parsed_json['buildings'] is not None and len(
                    parsed_json['buildings']) > 0 and 'totalBaseArea' in parsed_json['buildings'][0]:
                tba_str = str(parsed_json['buildings'][0]['totalBaseArea'])
            ret['total base area'] = tba_str
            lmvt_str = ''
            if parsed_json is not None and 'valueSummary' in parsed_json and parsed_json[
                'valueSummary'] is not None and len(parsed_json['valueSummary']) > 0 and 'marketVal' in \
                    parsed_json['valueSummary'][0]:
                val_ = parsed_json['valueSummary'][0]['marketVal']
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
                lmvt_str = locale.currency(val_, grouping=True)
            ret['latest market value total'] = lmvt_str
            return ret

    def get_bcpao_acc_from_legal(self, legal, legals):
        ret = {'bcpao_acc': None, 'bcpao_accs': [], 'bcpao_item': None}
        legals2 = [legal]
        legals2.extend(legals)
        for l in legals2:
            if l is not None:
                acc = self.get_acct_by_legal(l)
                if acc is not None:
                    ret['bcpao_acc'] = acc
                    break
        return ret

    def get_bcpao_item_from_acc(self, acct):
        req = self.get_parcel_data_by_acct2_request(acct)
        r = self.bcpao_infra.get_res_from_req(req)
        return self.parse_bcpaco_item_response(r)

    @staticmethod
    def get_acct_by_legal_request(legal_arg):
        ret = None
        if 'subd' in legal_arg or 't' in legal_arg:
            legal = (legal_arg['subd'], legal_arg['lt'], legal_arg['blk'], legal_arg['pb'], legal_arg['pg'],
                     legal_arg['s'], legal_arg['t'], legal_arg['r'], legal_arg['subid'])
            use_local_logging_config = False
            if use_local_logging_config:
                logging.basicConfig(format='%(asctime)s %(module)-15s %(levelname)s %(message)s', level=logging.DEBUG)
                logger = logging.getLogger(__name__)
                logger.info('START')
            sub, lot, block, pb, pg, s, t, r, subid = legal
            sub = sub.replace(u'\xc2', u'').encode('utf-8')
            bcpao_endpoint = 'https://www.bcpao.us/api/v1/search?'
            params = OrderedDict()
            if lot is not None:
                params['lot'] = str(lot)
            if block is not None:
                params['blk'] = str(block)
            if pb is not None:
                params['platbook'] = str(pb)
            if pg is not None:
                params['platpage'] = str(pg)

            params['subname'] = sub
            params['activeonly'] = 'true'
            params['size'] = '10'
            params['page'] = '1'
            url2 = bcpao_endpoint + urllib.parse.urlencode(params)

            ret = {'url2': url2, 'headers': {'Accept': 'application/json'}}
        return ret

    def get_acct_by_legal(self, legal_arg):
        logging.info('getting bcpao from legal: "' + legal_arg['legal_desc'] + '"')
        bcpao_objs = self.get_bcpao_searches(legal_arg)
        for bcpao_search in bcpao_objs:
            if bcpao_search.request is not None:
                req = bcpao_search.request
                response = bcpao_search.parse_acct_by_legal_response(
                    self.bcpao_infra.get_acct_by_legal_resp_from_req(req['url2'], req['headers']))
                if response is not None:
                    return response

    @staticmethod
    def get_bcpao_searches(legal_arg):
        bcpao_objs = [BcpaoBySubOrT(legal_arg), BcpaoByParcelId(legal_arg)]
        return bcpao_objs

    @staticmethod
    def parse_acct_by_legal_response(resp):
        if resp.status_code == 200 and len(resp.text) > 0:
            loaded_json = json.loads(resp.text)  # use req.json() instead?
            if loaded_json and len(loaded_json) == 1:
                return loaded_json[0]['account']

    @staticmethod
    def get_bcpao_query_url_by_acct(acct):
        return 'https://www.bcpao.us/PropertySearch/#/parcel/' + acct


class BclerkPublicRecords(object):
    def __init__(self, bcpr_infra=None):
        self.legal = None
        self.legals = None
        self.bcpr_infra = bcpr_infra

    @staticmethod
    def get_request_info(case):
        ret = {'uri': 'http://web1.brevardclerk.us/oncoreweb/search.aspx', 'form': {}}
        ret['form']['txtCaseNumber'] = case
        ret['form']['SearchType'] = 'casenumber'
        ret['form']['txtDocTypes'] = ''
        return ret

    @staticmethod
    def get_legal_from_str(the_str):
        legal_desc = the_str.replace(u'\xc2', u'')
        ret = {}

        lt = 'LT (?P<lt>[0-9a-zA-Z]+)'
        blk = 'BLK (?P<blk>[0-9a-zA-Z]+)'
        u = 'U (?P<u>\d+)'
        pb = 'PB (?P<pb>\d+)'
        pg = 'PG (?P<pg>\d+)'
        pb_pg = pb + ' ' + pg
        subd = '(?P<subd>.*)'
        s = 'S (?P<s>\d+)'
        t = 'T (?P<t>\d+G?)'
        r = 'R (?P<r>\d+)'
        subid = 'SUBID (?P<subid>[0-9a-zA-Z]+)'
        my_pattern = '(' + lt + ' )?(' + blk + ' )?(' + u + ' )?(' + pb_pg + ')?' \
                     + subd + ' ' + s + ' ' + t + ' ' + r + '( ' + subid + ')?'
        m = re.search(my_pattern, the_str)
        if m:
            ret = dict(itertools.chain(ret.items(), m.groupdict().items()))
            ret['subd'] = ret['subd'].replace(' S 1/2 OF', '')
        elif 'condo'.upper() in the_str.upper():
            ret['condo'] = True
        ret['legal_desc'] = legal_desc
        return ret

    def get_legals_by_case(self, case):
        request_info = self.get_request_info(case)
        resp = self.bcpr_infra.get_resp_from_request(request_info)
        return self.parse_response(resp)

    def parse_response(self, resp_text):
        rets = []
        soup = BeautifulSoup(resp_text, "html.parser")
        adr = soup.find('table', id='dgResults')
        if adr is not None:
            items = []
            col_names = []
            trs = adr.findAll("tr")
            for r, a in enumerate(trs):
                if r != 0 and r != len(trs) - 1:
                    current_item = {}
                    for c, d in enumerate(a.findAll("td")):
                        if r == 1:
                            col_names.append(d.get_text(strip=True))
                        else:
                            current_item[col_names[c]] = d.get_text(strip=True)
                    if r > 1:
                        items.append(current_item)
            rows = items
            lds = set()
            for row in rows:
                if row['First Legal'] and len(row['First Legal']) > 0:
                    lds.add(row['First Legal'])
            for ld in lds:
                legal_desc = ld.strip()
                temp = self.get_legal_from_str(legal_desc)
                if temp:
                    rets.append(dict(temp.items()))
        return rets

    def fetch(self, case_number_):
        self.legal = None
        self.legals = self.get_legals_by_case(case_number_)
        if len(self.legals) >= 1:
            self.legal = self.legals.pop(0)
        elif len(self.legals) == 1:
            self.legal = self.legals[0]

    @staticmethod
    def get_name_combos(i):
        if 'name_combos' in i:
            return i['name_combos']
        m = re.search('V[S]? (.*)', i['case_title'])
        if m:
            raw_full_name = m.group(1)
            i['raw_full_name'] = raw_full_name
            i['name_combos'] = []
            names = [str(b) for b in raw_full_name.split()]
            if len(names) == 2:
                i['name_combos'].append(names[1] + ', ' + names[0])
            if len(names) == 3:
                i['name_combos'].append(names[2] + ', ' + names[0] + ' ' + names[1])
                i['name_combos'].append(names[2] + ', ' + names[0])
            return i['name_combos']


class ContentHolder(object):
    def __init__(self, content):
        self.content = content

    def __iter__(self):  # http://stackoverflow.com/a/9573612
        return iter(self.content)


class BclerkEfacts(object):
    def __init__(self, bclerk_efacts_infra=None):
        self.bclerk_efacts_infra = bclerk_efacts_infra

    @staticmethod
    def get_url():
        return 'https://vweb1.brevardclerk.us/facts/d_caseno.cfm'

    @staticmethod
    def get_headers(cfid, cftoken, jsessionid):
        return {
            'Cookie': 'CFID=' + cfid + ';'
                      + ' CFTOKEN=' + cftoken + ';'
                      + ' JSESSIONID=' + str(jsessionid),
            'Content-Type': 'application/x-www-form-urlencoded'}

    @staticmethod
    def get_data(year, court_type, seq_number):
        params = OrderedDict()
        params['CaseNumber1'] = '05'
        params['CaseNumber2'] = year
        params['CaseNumber3'] = court_type
        params['CaseNumber4'] = seq_number
        params['CaseNumber5'] = ''
        params['CaseNumber6'] = ''
        params['submit'] = 'Submit'
        return urllib.parse.urlencode(params)

    @staticmethod
    def get_lad_url_from_grid2(g, a_pattern):
        ret = None
        for i in g['items']:
            if 'Description' in i and a_pattern in i['Description']:
                if i['Img']:
                    ret = i['Img']
                    break
        return ret

    def get_lad_url_from_rtext(self, r_text):
        soup = BeautifulSoup(r_text, 'html.parser')
        ret = {'case number': soup.title.text, 'case title': soup.find_all('font', color='Blue')[0].text}
        items = []
        col_names = []
        trs = soup.find_all('table')[1].findAll("tr")
        for row, a in enumerate(trs):
            current_item = {}
            for h_index, h_text in enumerate(a.findAll("th")):
                col_names.append(h_text.text)

            for c, d in enumerate(a.findAll("td")):
                try:
                    current_item[col_names[c]] = d.text
                    the_a = d.find('a')
                    if the_a:
                        current_item[col_names[c]] = the_a['href']
                except (IndexError, KeyError) as error:
                    logging.debug(' '.join(
                        ['********exception******', str(error), str(sys.exc_info()[0]), str(col_names), str(d)]))

            if row >= 1:
                items.append(current_item)
        ret['items'] = items
        grid = ret

        ret = None
        valid_patterns_for_original_mortgage = ['ER: F/J FCL']
        for x in valid_patterns_for_original_mortgage:
            ret = self.get_lad_url_from_grid2(grid, x)
            if ret:
                break
        return grid, ret

    def get_orig_mortgage_url_from_grid(self, gr):
        ret = None
        valid_patterns_for_original_mortgage = ['NOTICE FILING ORIG NOTE & MTG', 'OR MTG', 'MTG & ORIG', 'COPY OF MTG',
                                                'ORIGINAL NOTE & MORTGAGE DEED', 'NTC FILING ORIG NOTE &/OR MTG',
                                                'NOTICE OF FILING ORIGINAL NOTE', 'ORIGINAL NOTE & MORTGAGE',
                                                'ER: F/J FCL']
        x = None
        for x in valid_patterns_for_original_mortgage:
            ret = self.get_orig_mortgage_url_from_grid2(gr, x)
            if ret:
                break
            else:
                x = None  # reset loop variable so we don't return it
        return ret, x

    @staticmethod
    def get_orig_mortgage_url_from_grid2(g, a_pattern):
        ret = None
        for i in g['items']:
            if 'Description' in i and a_pattern in i['Description']:
                if i['Img']:
                    ret = i['Img']
                    break
        return ret

    @staticmethod
    def pre_cache(case):
        r = Item.pre_cache2(case)
        ret = dict(court_type=r['court_type'], id2=r['id2'], seq_number=r['seq_number'], year=r['year'])
        return ret

    def fetch_case_info(self, court_type, id2, out_dir, seq_number, year):
        request_info = self.get_request_info(court_type, seq_number, year)
        resp = dict(jsessionid=None)
        if request_info is not None:
            r = self.bclerk_efacts_infra.get_case_info_resp_from_req(request_info['data'], request_info['headers'],
                                                                     request_info['stream'], request_info['timeout'],
                                                                     request_info['url'])
            resp = self.parse_resp2(r)
            resp['case_info_html_filepath'] = out_dir + '/' + id2 + '_case_info.htm'
            resp['case_info_html_content'] = ContentHolder(resp['content'])
        return resp

    def fetch_reg_actions(self, court_type, jsessionid, seq_number, year, out_dir, id2):
        reg_actions_req_info = self.get_reg_actions_req_info(court_type, jsessionid, seq_number, year)
        r_text = self.bclerk_efacts_infra.get_reg_actions_resp_from_req(reg_actions_req_info['data'],
                                                                        reg_actions_req_info['headers'],
                                                                        reg_actions_req_info['url'])

        resp = self.parse_reg_actions_response(r_text)
        resp['reg_actions_html_filepath'] = out_dir + '/' + id2 + '_reg_actions.htm'
        resp['reg_actions_html_content'] = ContentHolder(r_text)
        return resp

    def parse_reg_actions_response(self, r_text):
        grid, lad = self.get_lad_url_from_rtext(r_text)
        url, tag = self.get_orig_mortgage_url_from_grid(grid)
        return {'latest_amount_due': lad, 'orig_mtg_link': url, 'orig_mtg_tag': tag}

    def get_reg_actions_req_info(self, court_type, jsessionid, seq_number, year):
        url = 'https://vweb1.brevardclerk.us/facts/d_reg_actions.cfm?RequestTimeout=500'
        cfid = '4749086'
        cftoken = '23056266'
        headers = self.get_headers(cfid, cftoken, jsessionid)
        data = self.get_data(year, court_type, seq_number)
        reg_actions_req_info = {'url': url, 'data': data, 'headers': headers}
        return reg_actions_req_info

    @staticmethod
    def parse_resp2(r):
        resp = {'jsessionid': r.cookies['JSESSIONID'], 'content': []}
        for block in r.iter_content(1024):
            if not block:
                break
            resp['content'].append(block)

        return resp

    def get_request_info(self, court_type, seq_number, year):
        cfid = '1550556'
        cftoken = '74317641'
        url = self.get_url()
        headers2 = self.get_headers(cfid, cftoken, None)
        data = self.get_data(year, court_type, seq_number)
        request_info = {'url': url, 'data': data, 'headers': headers2, 'stream': True, 'timeout': 5}
        return request_info


class MyDate(object):
    @staticmethod
    def get_next_weekday(from_date, next_weekday):
        n = (next_weekday - from_date.weekday()) % 7  # mod-7 ensures we don't go backward in time
        return from_date + timedelta(days=n)

    def get_next_wed_offset(self, adate):
        return self.get_next_weekday(adate, 2)

    def get_next_dates(self, from_date):
        ret = []
        weeks_num = 2  # 6 # hack
        wednesdays = []
        for x in range(0, weeks_num):
            wednesdays.append(from_date + timedelta(weeks=x))  # was getting a warning when this was a list-compr
        the_dates = [self.get_next_wed_offset(w) for w in wednesdays]
        ret.extend(the_dates)
        ret.sort()
        return ret


class Foreclosures(object):
    def __init__(self, fore_infra=None):
        self.fore_infra = fore_infra

    def get_items(self):
        url = self.get_request_url()
        content = self.fore_infra.get_items_resp_from_req(url)
        return self.get_rows_from_response(content)

    @staticmethod
    def get_request_url():
        return 'http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html'

    @staticmethod
    def get_rows_from_response(the_html):
        rows = []
        soup = BeautifulSoup(the_html, "html.parser")
        trs = soup.find_all("tr")
        for tr in trs:
            current_row = {}
            tds = tr.find_all('td')
            if len(tds) == 0:
                continue
            current_row['case_number'] = tds[0].string
            current_row['case_title'] = tds[1].string
            current_row['comment'] = tds[2].string
            current_row['foreclosure_sale_date'] = datetime.strptime(tds[3].string, "%m-%d-%Y").date()
            current_row['count'] = len(rows) + 1
            rows.append(current_row)
        return rows

    @staticmethod
    def add_foreclosures(all2, limit=None):
        logger = logging.getLogger(__name__)
        logger.info('all foreclosures:' + str(len(all2)))
        to_set = all2
        if limit is not None:
            to_set = all2[:limit]
        logger.info('to_set:' + str(len(to_set)))
        return to_set


class Jac(object):
    def __init__(self, email_infra=None, fore_infra=None, file_system_infra=None, bclerk_efacts_infra=None,
                 bcpr_infra=None, taxes_infra=None, bcpao_infra=None, zip_infra=None, time_infra=None,
                 excel_infra=None):
        self.legal = None
        self.legals = None
        self.email_infra = email_infra
        self.fore_infra = fore_infra
        self.file_system_infra = file_system_infra
        self.bclerk_efacts_infra = bclerk_efacts_infra
        self.bcpr_infra = bcpr_infra
        self.taxes_infra = taxes_infra
        self.bcpao_infra = bcpao_infra
        self.zip_infra = zip_infra
        self.time_infra = time_infra
        self.excel_infra = excel_infra
        self.my_filter = None
        logging.basicConfig(format='%(asctime)s %(module)-15s %(levelname)s %(message)s', level=logging.DEBUG,
                            stream=sys.stdout)

    def set_filter(self, my_filter):
        self.my_filter = my_filter

    def get_dataset(self, mrs, out_dir_htm, sheet_name):
        for i, r in enumerate(mrs):

            # if r['count'] not in [71]:  # temp hack
            #     continue

            retries = 3
            for attempt in range(retries):
                try:
                    attempt_str = '' if attempt == 0 else " (attempt " + str(attempt + 1) + "/" + str(retries) + ")"
                    logging.info('count_id: ' + str(r['count']) + attempt_str)
                    self.fill_by_case_number(out_dir_htm, r)
                    break
                except requests.exceptions.Timeout as e:
                    logging.error("exception: " + str(e))
        sheet_builder = XlBuilder(sheet_name, self.time_infra)
        dataset = sheet_builder.add_sheet(mrs)
        return dataset

    def fill_by_case_number(self, out_dir_htm, r):
        logging.info('case_number: ' + r['case_number'])
        bclerk_efacts = BclerkEfacts(self.bclerk_efacts_infra)
        be = bclerk_efacts.pre_cache(r['case_number'])
        be2 = bclerk_efacts.fetch_case_info(be['court_type'], be['id2'], out_dir_htm,
                                            be['seq_number'], be['year'])
        self.file_system_infra.save_lines_to_file(be2['case_info_html_filepath'], 'wb', be2['case_info_html_content'])

        bclerk_efacts_info = bclerk_efacts.fetch_reg_actions(be['court_type'], be2['jsessionid'],
                                                             be['seq_number'], be['year'], out_dir_htm, be['id2'])
        self.file_system_infra.save_lines_to_file(bclerk_efacts_info['reg_actions_html_filepath'], 'w',
                                                  bclerk_efacts_info['reg_actions_html_content'])
        r['latest_amount_due'] = bclerk_efacts_info['latest_amount_due']
        r['orig_mtg_link'] = bclerk_efacts_info['orig_mtg_link']
        r['orig_mtg_tag'] = bclerk_efacts_info['orig_mtg_tag']
        bclerk_public_records = BclerkPublicRecords(self.bcpr_infra)
        bclerk_public_records.fetch(r['case_number'])
        r['legal'] = bclerk_public_records.legal
        r['legals'] = bclerk_public_records.legals
        bcpao = Bcpao(self.bcpao_infra)
        bcpao_info = bcpao.get_bcpao_acc_from_legal(r['legal'], r['legals'])
        r['bcpao_acc'] = bcpao_info['bcpao_acc']
        if r['bcpao_acc'] is None:
            r['bcpao_acc'] = ''
        r['bcpao_item'] = bcpao.get_bcpao_item_from_acc(r['bcpao_acc'])
        if r['bcpao_item'] is None:
            r['bcpao_item'] = {}
        taxes = Taxes(self.taxes_infra)
        taxes_info = taxes.get_info_from_account(r['bcpao_acc'])
        if taxes_info is not None:
            r['taxes_value'] = taxes_info['value_to_use']
            r['taxes_url'] = taxes_info['url_to_use']

            # if i == 0:  # temp hack
            #     break

    def get_non_cancelled_nums(self, mrs):
        mrs = FilterCancelled().apply(mrs)
        date_counts = pprint.pformat(self.get_dates_count_map(mrs)).replace('\n', '<br>').replace(
            'datetime(', '').replace(', 0, 0', '').replace(', ', '/').replace(')', '')
        return date_counts

    @staticmethod
    def get_dates_count_map(items):
        ret = {}
        for i in items:
            parsed_date = i['foreclosure_sale_date']
            if parsed_date not in ret:
                ret[parsed_date] = 1
            else:
                ret[parsed_date] += 1
        return ret

    def my_send_mail(self, file_paths, password, subject, body):
        fromaddr = 'orozcoadrian@gmail.com'
        toaddr = ['orozcoadrian@gmail.com', 'spacecoastmarketing@gmail.com']
        message_text = body  # 'Test6'+' '+file_path
        message_subject = subject  # 'Subject6'
        username = 'orozcoadrian'
        self.email_infra.send_mail(username, password, fromaddr, toaddr, message_subject, message_text, file_paths,
                                   'smtp.gmail.com:587')

    @staticmethod
    def get_short_date_strings_to_add(dates):
        return [x.strftime("%m.%d.%y") for x in dates]

    def go(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--zip", action='store_true', help="do zip.")
        parser.add_argument("--email", action='store_true', help="do email.")
        parser.add_argument("--passw", help="email password.")

        args = parser.parse_args()
        return self.go2(args)

    def go2(self, args):
        logging.info('START')
        start = self.time_infra.time()
        logging.debug('jac starting')
        logging.info('args: ' + str(args))
        dates = MyDate().get_next_dates(self.time_infra.get_today())
        s = Foreclosures(self.fore_infra)
        mrs = s.get_items()
        timestamp = self.time_infra.time_strftime('%Y-%m-%d__%H-%M-%S')
        all_foreclosures = mrs[:]
        date_counts = self.get_non_cancelled_nums(all_foreclosures)
        logging.info(dates)
        short_date_strings_to_add = self.get_short_date_strings_to_add(dates)
        logging.info('short_date_strings_to_add: ' + str(short_date_strings_to_add))
        run_tag = '-'.join(short_date_strings_to_add[0:1])
        parent_out_dir = 'outputs'
        out_dir = parent_out_dir + '/' + timestamp
        self.file_system_infra.do_mkdirs(out_dir)
        logging.info(os.path.abspath(out_dir))
        filename = run_tag + '.xls'
        logging.info('date_strings_to_add: ' + str(dates))
        logging.info('abc: ' + run_tag)
        # mrs = [mrs[0]]  # temp hack
        # mrs = mrs[:10]  # temp hack
        mrs = [x for x in mrs if self.my_filter(x)]
        single_date_item_sets = []
        for date_str in dates:
            filter_by_dates = FilterByDates()
            filter_by_dates.set_dates([date_str])
            sheet_name = date_str.strftime("%m-%d")
            single_date_item_sets.append({'dataset_title': sheet_name, 'items': filter_by_dates.apply(mrs)})
        self.create_workbook_from_item_sets(filename, out_dir, single_date_item_sets, self.excel_infra.get_a_book())
        body = self.get_email_body(run_tag, date_counts, filename, mrs)
        file_paths = [(out_dir + '/' + filename)]
        if args.zip:
            final_zip_path = self.zip_infra.do_zip(out_dir, parent_out_dir, run_tag)

            file_paths.append(final_zip_path)
        subject = '[jac biweekly report]' + ' for: ' + run_tag
        if args.email and args.passw:
            self.my_send_mail(file_paths, args.passw, subject, body)
        logging.info(body)
        logging.info('duration %s' % timedelta(seconds=self.time_infra.time() - start))
        logging.info('END')
        return 0

    def create_workbook_from_item_sets(self, filename, out_dir, single_date_item_sets, book):
        datasets = []
        for single_date_item_set in single_date_item_sets:
            sheet_name = single_date_item_set['dataset_title']
            out_dir_htm = out_dir + '/' + sheet_name + '/html_files'
            self.file_system_infra.do_mkdirs(out_dir_htm)

            mrs_for_one_day = single_date_item_set['items']
            logging.info('**get_dataset: ' + sheet_name)
            dataset = self.get_dataset(mrs_for_one_day, out_dir_htm, sheet_name)

            logging.info('sheet fetch complete')
            logging.info('sheet num records: ' + str(len(mrs_for_one_day)))
            datasets.append(dataset)
        for dataset in datasets:
            Xl().add_data_set_sheet(dataset, book)
        book.save(out_dir + '/' + filename)

    def get_email_body(self, run_tag, date_counts, filename, mrs):
        body = 'this result is for: ' + run_tag
        body += '<br>total records: ' + str(len(mrs))
        body += '<br><br>'
        body += 'the following summarizes how many not-cancelled items there are per month in the '
        body += '<a href="http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html">foreclosure sales page</a> '
        body += 'as of now: <br>' + date_counts
        body += '<br><br>' + filename
        body += self.get_no_addr_str(mrs)
        return body

    @staticmethod
    def get_no_addr_str(mrs):
        no_addr = [x for x in mrs if 'bcpao_item' not in x or
                   ('bcpao_item' in x and ('address' not in x['bcpao_item'] or len(x['bcpao_item']['address']) == 0))]
        ids = []
        for x in no_addr:
            id_to_show = 'count_id: ' + str(x['count']) + ', ' + x['case_number'] + '<br>\n'
            legal_str = None
            if x is not None and 'legal' in x and x['legal'] is not None and 'legal_desc' in x['legal']:
                legal_str = '  "' + x['legal']['legal_desc'] + '"'
            if 'legals' in x:
                for l in x['legals']:
                    if 'legal_desc' in l:
                        legal_str = '<br>\n  "' + l['legal_desc'] + '"'
            ids.append(id_to_show + str(legal_str))
        no_addr_str = ''
        if len(ids) > 0:
            no_addr_str = "\n\n<br><br>could not get addresses for the following: <br>\n" + '<br>\n'.join(ids)
        return no_addr_str

    def get_by_case_number(self, case_number):
        r = {'case_number': case_number}
        self.fill_by_case_number('', r)
        print('r: ' + str(r))

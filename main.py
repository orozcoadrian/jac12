import argparse
import email
import itertools
import json
import locale
import logging
import os
import pprint
import re
import shutil
import smtplib
import sys
import time
import urllib.parse
import zipfile
from datetime import datetime, date, timedelta
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

import requests
from bs4 import BeautifulSoup
from robobrowser import RoboBrowser
from xlwt import Workbook, easyxf, Formula


class FilterCancelled(object):
    def __init__(self, args):
        self.args = args

    @staticmethod
    def apply(mrs):
        new_recs = []
        for rec in mrs:
            add_it = True
            if 'CANCELLED' in rec['comment']:
                add_it = False
            if add_it:
                new_recs.append(rec)
        return new_recs


class FilterByDates(object):
    def __init__(self):
        self.dates = None

    def set_dates(self, dates):
        self.dates = dates

    def apply(self, mrs):
        new_recs = []
        if self.dates:
            for rec in mrs:
                add_it = False
                if rec['foreclosure_sale_date'] in self.dates:
                    add_it = True
                if add_it:
                    new_recs.append(rec)
            return new_recs
        else:
            return mrs


class XlBuilder(object):
    def __init__(self, sheet_name):
        self.sheet_name = sheet_name
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
        link_str2 = ''
        m = re.search('(.*)-(.*)-(.*)-(.*)-.*-.*',
                      i['case_number'])  # todo: remove this duplication with record.fetch_cfm
        if m:
            year = m.group(2)
            court_type = m.group(3)
            seq_number = m.group(4)
            id2 = year + '_' + court_type + '_' + seq_number
            link_str2 = self.get_sheet_name() + '/html_files/' + id2 + '_reg_actions.htm'
        return link_str2

    def get_case_info_link(self, i):
        link_str = ''
        m = re.search('(.*)-(.*)-(.*)-(.*)-.*-.*',
                      i['case_number'])  # todo: remove this duplication with record.fetch_cfm
        if m:
            year = m.group(2)
            court_type = m.group(3)
            seq_number = m.group(4)
            id2 = year + '_' + court_type + '_' + seq_number
            link_str = self.get_sheet_name() + '/html_files/' + id2 + '_case_info.htm'
        return link_str

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

    @staticmethod
    def get_bclerk_name_url(name):  # TODO: move this to xl3
        return 'http://web1.brevardclerk.us/oncoreweb/search.aspx?' \
               'bd=1%2F1%2F1981&ed=5%2F31%2F2014&' \
               'n=' + urllib.parse.quote(name) + '&bt=OR&d=2%2F5%2F2015&pt=-1&cn=&dt=ALL%20DOCUMENT%20TYPES&' \
                                                 'st=fullname&ss=ALL%20DOCUMENT%20TYPES'

    @staticmethod
    def get_case_number_url(cn):
        return 'http://web1.brevardclerk.us/oncoreweb/search.aspx?' \
               'bd=1%2F1%2F1981&' \
               'ed=5%2F31%2F2015&' \
               'n=&' \
               'bt=OR&' \
               'd=5%2F31%2F2014&' \
               'pt=-1&' \
               'cn=' + cn + '&' \
                            'dt=ALL DOCUMENT TYPES&' \
                            'st=casenumber&' \
                            'ss=ALL DOCUMENT TYPES'

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
    def __init__(self):
        self.value_to_use = None
        self.url_to_use = None

    @staticmethod
    def get_name():
        return 'Taxes'

    def fetch(self, bcpao_acc_):
        the_str = None
        if bcpao_acc_ is not None and len(bcpao_acc_) > 0:
            the_str = bcpao_acc_
        if the_str is None:
            self.value_to_use = None  # Cell.from_display('')
        else:
            display_str = self.get_pay_all_from_taxid(the_str)
            if display_str:
                display_str = display_str.replace('$', '').replace(',', '')
                self.value_to_use = display_str
                self.url_to_use = self.get_tax_url_from_taxid(the_str)

                # mr['taxes_value'] = value_to_use
                # mr['taxes_url'] = url_to_use

    def get_pay_all_from_taxid(self, tax_id):
        ret = '0'
        r = self.get_tax_text_from_taxid(tax_id)
        pay_all = self.get_pay_all_from_tax_text(r.text)
        if pay_all:
            ret = pay_all
        return ret

    def get_tax_text_from_taxid(self, tax_id):
        url = self.get_tax_url_from_taxid(tax_id)
        headers = ''  # get_headers(cfid, cftoken)
        data = ''  # get_data(year, court_type, seq_number)
        r = requests.post(url, data, headers=headers, stream=True)
        return r

    @staticmethod
    def get_tax_url_from_taxid(tax_id):
        url = 'https://brevard.county-taxes.com/public/real_estate/parcels/' + tax_id
        return url

    @staticmethod
    def get_pay_all_from_tax_text(r_text):
        ret = None
        m = re.search('.*Pay All: \$([\d,.]*).*', r_text)
        if m:
            ret = m.group(1)
        return ret


class Bcpao(object):
    def __init__(self) -> None:
        self.bcpao_acc = None
        self.bcpao_item = None
        self.bcpao_accs = None

    def fetch(self, legal, legals):
        self.fill_bcpao_from_legal(legal, legals)

    @staticmethod
    def get_parcel_data_by_acct2(acct):
        print('get_parcelData_by_acct(' + str(acct) + ')')
        url = 'https://bcpao.us/api/v1/account/' + str(acct) + ''
        headers = {'Accept': 'application/json'}
        r = requests.get(url, headers=headers)
        return r.text

    def get_bcpaco_item(self, acct):
        print("get_bcpaco_item('" + acct + "')")
        # don't do anything if acct is blank (same in bcpao_radius
        ret = {}
        if acct is None or len(acct) == 0:
            return ret
        parcel_data = self.get_parcel_data_by_acct2(acct)
        parsed_json = json.loads(parcel_data)
        if 'Multiple Addresses' in parsed_json['siteAddress'] and len(parsed_json['siteAddresses']) > 0:
            addr_str = parsed_json['siteAddresses'][0]['siteAddress']
        else:
            addr_str = parsed_json['siteAddress']
        print('"' + addr_str + '"')
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
            locale.setlocale(locale.LC_ALL, 'en_US')
            lmvt_str = locale.currency(val_, grouping=True)
        ret['latest market value total'] = lmvt_str

        pprint.pprint(ret)

        return ret

    def fill_bcpao_from_legal(self, legal, legals):
        if 'subd' in legal:
            acc = self.get_acct_by_legal(
                (legal['subd'], legal['lt'], legal['blk'], legal['pb'], legal['pg'], legal['s'],
                 legal['t'], legal['r'], legal['subid']))
            self.bcpao_acc = acc
            self.bcpao_item = self.get_bcpaco_item(acc)
        self.bcpao_accs = []
        for i, l in enumerate(legals):
            self.bcpao_acc = None
            if 't' in l:
                acc = self.get_acct_by_legal(
                    (l['subd'], l['lt'], l['blk'], l['pb'], l['pg'], l['s'], l['t'], l['r'], l['subid']))
                self.bcpao_accs.append(acc)
                if self.bcpao_acc is None:
                    self.bcpao_acc = acc
                    self.bcpao_item = self.get_bcpaco_item(acc)

    @staticmethod
    def get_acct_by_legal(legal):
        use_local_logging_config = False
        if use_local_logging_config:
            logging.basicConfig(format='%(asctime)s %(module)-15s %(levelname)s %(message)s', level=logging.DEBUG)
            logger = logging.getLogger(__name__)
            logger.info('START')
        sub, lot, block, pb, pg, s, t, r, subid = legal
        sub = sub.replace(u'\xc2', u'').encode('utf-8')
        logging.info(
            'get_acct_by_legal(sub="' + str(sub) + '", lot=' + str(lot) + ', block=' + str(block) + ', pb=' + str(
                pb) + ', pg=' + str(pg) + ', s=' + str(s) + ', t=' + str(t) + ', r=' + str(r) + ', subid=' + str(
                subid) + ')')
        ret = ''
        if not ret:
            url2 = 'https://bcpao.us/api/v1/search?'
            if lot is not None:
                url2 += 'lot=' + str(lot)
            if block is not None:
                url2 += '&blk=' + str(block)
            if pb is not None:
                url2 += '&platbook=' + str(pb)
            if pg is not None:
                url2 += '&platpage=' + str(pg)
            url2 += '&subname=' + urllib.parse.quote(sub)
            url2 += '&activeonly=true&size=10&page=1'

            headers = {'Accept': 'application/json'}

            req = requests.get(url2, headers=headers, verify=False, timeout=10)  # timeout in seconds

            if req.status_code == 200 and len(req.text) > 0:
                loaded_json = json.loads(req.text)  # use req.json() instead?
                if loaded_json and len(loaded_json) == 1:
                    ret = loaded_json[0]['account']

        if not ret:
            print('no bcpao acct, no address')

        return ret

    @staticmethod
    def get_bcpao_query_url_by_acct(acct):
        return 'https://www.bcpao.us/PropertySearch/#/parcel/' + acct


class BclerkPublicRecords(object):
    def __init__(self):
        self.legal = None
        self.legals = None

    @staticmethod
    def get_name():
        return 'Legal'

    @staticmethod
    def get_bclerk_results_text(case):
        print('get_bclerk_results_text(' + case + ')')
        uri = 'http://web1.brevardclerk.us/oncoreweb/search.aspx'
        browser = RoboBrowser(history=True, parser='html.parser')
        browser.open(uri)

        form = browser.get_forms()[0]
        form['txtCaseNumber'].value = case
        form['SearchType'].value = 'casenumber'
        form['txtDocTypes'].value = ''
        browser.submit_form(form)

        resp = browser.response
        print(resp)
        return resp.text

    def get_bclerk_results_soup(self, case):
        bclerk_results_text = self.get_bclerk_results_text(case)
        soup = BeautifulSoup(bclerk_results_text, "html.parser")
        return soup

    def get_records_grid_for_case_number(self, case_number):
        soup = self.get_bclerk_results_soup(case_number)  # ('05-2014-CA-024535-XXXX-XX')
        adr = soup.find('table', id='dgResults')
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
        return items

    @staticmethod
    def get_legal_from_str(the_str):
        legal_desc = the_str.replace(u'\xc2', u'')
        logging.info('get_legal_from_str(' + legal_desc + ')')
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

    def oncoreweb_by_legal(self, leg_desc_in):
        l = self.get_legal_from_str(leg_desc_in)
        theblk = ''
        thelt = ''
        thepb = ''
        thepg = ''
        if 'blk' in l and l['blk']:
            theblk = '|Block' + ',' + l['blk']
        if 'lt' in l and l['lt']:
            thelt = l['lt']
        if 'pb' in l and l['pb']:
            thepb = l['pb']
        if 'pg' in l and l['pg']:
            thepg = l['pg']
        if 's' in l and 'r' in l and 't' in l and 'subid' in l and l['s'] is not None and l['r'] is not None and \
                        l['t'] is not None and l['subid'] is not None:
            lot_s = urllib.parse.quote('Lot,' + thelt + theblk + '|Land_Lot' + ',' + thepb
                                       + '|District' + ',' + thepg + '|PropSection' + ',' + l['s'] + '|Building' + ',' +
                                       l[
                                           't'] + '|Range' + ',' + l['r']
                                       + '|Phase' + ',' + l['subid'])
            mys = 'http://web1.brevardclerk.us/oncoreweb/search.aspx?' \
                  'bd=01%2F01%2F1981&ed=4%2F19%2F2016&bt=OR&d=4%2F19%2F2016&pt=-1&lf='
            mys += lot_s
            mys += '&cn=&dt=&st=legal&ld='
            ret = mys

            return ret
        return ''

    def get_legal_by_case(self, case):
        print('get_legal_by_case("' + case + '")')
        ret = {}
        rows = self.get_records_grid_for_case_number(case)
        lds = []
        for row in rows:
            if row['First Legal'] and len(row['First Legal']) > 0:
                lds.append(row['First Legal'])
        ret['legal_description'] = '; '.join(lds).strip()
        if len(lds) > 0:
            ret['oncoreweb_by_legal_url'] = self.oncoreweb_by_legal(lds[0])
            print(ret['oncoreweb_by_legal_url'])
        for i, ld in enumerate(lds):
            legal_desc = ld.strip()
            temp = self.get_legal_from_str(legal_desc)
            if temp:
                ret = dict(itertools.chain(ret.items(), temp.items()))
                if i < (len(lds) - 1):
                    the_str = 'choosing a legal description (index='
                    the_str += str(i)
                    the_str += ':' + legal_desc
                    the_str += ') before going through all of them(total='
                    the_str += str(len(lds))
                    the_str += '): '
                break
        return ret

    def get_legals_by_case(self, case):
        print('get_legals_by_case("' + case + '")')
        rets = []

        rows = self.get_records_grid_for_case_number(case)
        lds = []
        for row in rows:
            if row['First Legal'] and len(row['First Legal']) > 0:
                lds.append(row['First Legal'])
        for i, ld in enumerate(lds):
            legal_desc = ld.strip()
            temp = self.get_legal_from_str(legal_desc)
            if temp:
                rets.append(dict(temp.items()))
        return rets

    def fetch(self, case_number_):
        self.legal = self.get_legal_by_case(case_number_)
        # print('legal: ' + str(legal))
        # mr['legal'] = legal
        self.legals = self.get_legals_by_case(case_number_)
        # mr['legals'] = legals

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


class BclerkEfacts(object):
    def __init__(self, out_dir_htm):
        self.out_dir_htm = out_dir_htm
        self.latest_amount_due = None
        self.orig_mtg_link = None
        self.orig_mtg_tag = None

    @staticmethod
    def get_name():
        return 'Cfm'

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
        ret = 'CaseNumber1=05&'
        ret += 'CaseNumber2=' + year + '&'
        ret += 'CaseNumber3=' + court_type + '&'
        ret += 'CaseNumber4=' + seq_number + '&'
        ret += 'CaseNumber5=&'
        ret += 'CaseNumber6=&'
        ret += 'submit=Submit'
        return ret

    def case_info(self, out_dir, year, court_type, seq_number, cfid, cftoken):
        id2 = year + '_' + court_type + '_' + seq_number
        logging.debug('hi')
        logging.debug('case_info(' + ', '.join([out_dir, year, court_type, seq_number, cfid, cftoken]) + ')')
        url = self.get_url()
        headers = self.get_headers(cfid, cftoken, None)
        data = self.get_data(year, court_type, seq_number)
        r = requests.post(url, data, headers=headers, stream=True, timeout=5)
        logging.debug('r.cookies: ' + str(r.cookies))
        logging.debug('r.cookies["JSESSIONID"]: ' + str(r.cookies['JSESSIONID']))
        ret = {}
        if out_dir:
            with open(out_dir + '/' + id2 + '_case_info.htm', 'wb') as handle:
                for block in r.iter_content(1024):
                    if not block:
                        break
                    handle.write(block)
        return ret, r.cookies['JSESSIONID']

    def do(self, out_dir, year, court_type, seq_number, cfid, cftoken):
        ret1, jsessionid = self.case_info(out_dir, year, court_type, seq_number, cfid, cftoken)
        ret2 = self.reg(out_dir, year, court_type, seq_number, jsessionid)
        ret = dict(itertools.chain(ret1.items(), ret2.items()))
        return ret

    def get_reg_actions_text(self, year, court_type, seq_number, jsessionid):
        logging.debug('get_reg_actions_text:')
        url = 'https://vweb1.brevardclerk.us/facts/d_reg_actions.cfm?RequestTimeout=500'
        logging.debug(url)
        cfid = '4749086'
        cftoken = '23056266'
        headers = self.get_headers(cfid, cftoken, jsessionid)
        logging.debug(headers)
        data = self.get_data(year, court_type, seq_number)
        logging.debug(data)
        logging.debug('before reg actions request')
        r = requests.get(url, data, headers=headers, stream=True)
        r_text = r.text
        logging.debug(r.ok)
        logging.debug(r.status_code)
        logging.debug('is_redirect: ' + str(r.is_redirect))
        return r_text

    @staticmethod
    def get_reg_actions_dataset(r_text):
        soup = BeautifulSoup(r_text.encode('utf-8'), 'html.parser')
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
        return ret

    def get_lad_from_reg_text2(self, g):
        ret = None
        valid_patterns_for_original_mortgage = ['ER: F/J FCL']
        for x in valid_patterns_for_original_mortgage:
            ret = self.get_lad_url_from_grid2(g, x)
            if ret:
                print('getting by: ' + x)
                break
        return ret

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
        grid = self.get_reg_actions_dataset(r_text)
        return self.get_lad_from_reg_text2(grid)

    def get_orig_mortgage_url_from_rtext(self, r_text):
        grid = self.get_reg_actions_dataset(r_text)
        return self.get_orig_mortgage_url_from_grid(grid)

    def get_orig_mortgage_url_from_grid(self, gr):
        ret = None
        valid_patterns_for_original_mortgage = ['NOTICE FILING ORIG NOTE & MTG', 'OR MTG', 'MTG & ORIG', 'COPY OF MTG',
                                                'ORIGINAL NOTE & MORTGAGE DEED', 'NTC FILING ORIG NOTE &/OR MTG',
                                                'NOTICE OF FILING ORIGINAL NOTE', 'ORIGINAL NOTE & MORTGAGE']
        x = None
        for x in valid_patterns_for_original_mortgage:
            ret = self.get_orig_mortgage_url_from_grid2(gr, x)
            if ret:
                print('getting by: ' + x)
                break

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

    def reg(self, out_dir, year, court_type, seq_number, jsessionid):
        ret = {}
        id2 = year + '_' + court_type + '_' + seq_number
        r_text = self.get_reg_actions_text(year, court_type, seq_number, jsessionid)
        lad = self.get_lad_url_from_rtext(r_text)
        ret['latest_amount_due'] = lad
        url, tag = self.get_orig_mortgage_url_from_rtext(r_text)
        ret['orig_mtg_link'] = url
        ret['orig_mtg_tag'] = tag

        if out_dir:
            with open(out_dir + '/' + id2 + '_reg_actions.htm', 'w') as handle:
                handle.write(r_text)
        return ret

    def fetch(self, case_number_):
        m = re.search('(.*)-(.*)-(.*)-(.*)-.*-.*', case_number_)
        print('MyRecord.fetch_cfm():' + str(case_number_))
        if m:
            year = m.group(2)
            court_type = m.group(3)
            seq_number = m.group(4)
            cfid = '1550556'
            cftoken = '74317641'
            values = self.do(self.out_dir_htm, year, court_type, seq_number, cfid, cftoken)
            if 'latest_amount_due' in values:
                self.latest_amount_due = values['latest_amount_due']
            if 'orig_mtg_link' in values:
                self.orig_mtg_link = values['orig_mtg_link']
                self.orig_mtg_tag = values['orig_mtg_tag']


class Jac(object):
    @staticmethod
    def get_mainsheet_dataset(mrs, out_dir, date_string_to_add):
        logging.info('**get_mainsheet_dataset: ' + date_string_to_add)

        filter_by_dates = FilterByDates()
        filter_by_dates.set_dates([date_string_to_add])
        mrs = filter_by_dates.apply(mrs)

        sheet_name = date_string_to_add[5:]
        out_dir_htm = out_dir + '/' + sheet_name + '/html_files'
        os.makedirs(out_dir_htm, exist_ok=True)

        for i, r in enumerate(mrs):
            logging.info('count_id: ' + str(r['count']))

            bclerk_efacts = BclerkEfacts(out_dir_htm)
            bclerk_efacts.fetch(r['case_number'])
            r['latest_amount_due'] = bclerk_efacts.latest_amount_due
            r['orig_mtg_link'] = bclerk_efacts.orig_mtg_link
            r['orig_mtg_tag'] = bclerk_efacts.orig_mtg_tag

            bclerk_public_records = BclerkPublicRecords()
            bclerk_public_records.fetch(r['case_number'])
            r['legal'] = bclerk_public_records.legal
            r['legals'] = bclerk_public_records.legals

            bcpao = Bcpao()
            bcpao.fetch(r['legal'], r['legals'])
            r['bcpao_acc'] = bcpao.bcpao_acc
            r['bcpao_item'] = bcpao.bcpao_item
            r['bcpao_accs'] = bcpao.bcpao_accs

            taxes = Taxes()
            taxes.fetch(r['bcpao_acc'])
            r['taxes_value'] = taxes.value_to_use
            r['taxes_url'] = taxes.url_to_use

            # if i == 0:  # temp hack
            #     break

        logging.info('fetch complete')
        logging.info('num records: ' + str(len(mrs)))
        sheet_builder = XlBuilder(sheet_name)
        dataset = sheet_builder.add_sheet(mrs)
        return dataset

    def get_non_cancelled_nums(self, args):
        mrs = Foreclosures().add_foreclosures()
        mrs = FilterCancelled(args).apply(mrs)
        date_counts = pprint.pformat(self.get_dates_count_map(mrs)).replace('\n', '<br>').replace(
            'datetime(', '').replace(', 0, 0', '').replace(', ', '/').replace(')', '')
        return date_counts

    @staticmethod
    def get_dates_count_map(items2):
        dates_count_map = {}
        for i in items2:
            item = i
            date2 = datetime.strptime(item['foreclosure_sale_date'], "%Y-%m-%d")
            if date2 not in dates_count_map:
                dates_count_map[date2] = 1
            else:
                dates_count_map[date2] += 1
        return dates_count_map

    def my_send_mail(self, file_paths, password, subject, body):
        fromaddr = 'orozcoadrian@gmail.com'
        toaddr = ['orozcoadrian@gmail.com', 'spacecoastmarketing@gmail.com']
        message_text = body  # 'Test6'+' '+file_path
        message_subject = subject  # 'Subject6'
        username = 'orozcoadrian'
        self.send_mail(username, password, fromaddr, toaddr, message_subject, message_text, file_paths,
                       'smtp.gmail.com:587')

    @staticmethod
    def send_mail(username, password, send_from, send_to, subject, text, files, server="localhost"):
        assert isinstance(send_to, list)
        assert isinstance(files, list)

        msg = MIMEMultipart('alternative')
        msg['From'] = send_from
        msg['To'] = COMMASPACE.join(send_to)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject

        msg.attach(MIMEText(text, 'html'))

        for f in files:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(f, "rb").read())
            email.encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
            msg.attach(part)

        smtp = smtplib.SMTP(server)
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(send_from, send_to, msg.as_string())
        smtp.close()

    @staticmethod
    def get_date_strings_to_add(dates):
        return [x.strftime("%Y-%m-%d") for x in dates]

    @staticmethod
    def get_short_date_strings_to_add(dates):
        return [x.strftime("%m.%d.%y") for x in dates]

    def go(self):
        logging.basicConfig(format='%(asctime)s %(module)-15s %(levelname)s %(message)s', level=logging.DEBUG)
        logger = logging.getLogger(__name__)
        logger.info('START')
        start = time.time()
        parser = argparse.ArgumentParser()
        parser.add_argument("--zip", action='store_true', help="do zip.")
        parser.add_argument("--email", action='store_true', help="do email.")
        parser.add_argument("--passw", help="email password.")

        args = parser.parse_args()

        logging.debug('jac starting')
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

        logging.info('args: ' + str(args))

        s = Foreclosures()
        mrs = s.get_items()

        dates = MyDate().get_next_dates(date.today())
        logging.info(dates)
        dates_to_add = dates  # [0:2]
        date_strings_to_add = self.get_date_strings_to_add(dates_to_add)
        # date_strings_to_add = [date_strings_to_add[0]]  # temp hack
        short_date_strings_to_add = self.get_short_date_strings_to_add(dates_to_add)
        logging.info('short_date_strings_to_add: ' + str(short_date_strings_to_add))

        abc = '-'.join(short_date_strings_to_add[0:1])

        parent_out_dir = 'outputs'
        out_dir = parent_out_dir + '/' + timestamp
        os.makedirs(out_dir)
        logging.info(os.path.abspath(out_dir))

        the_tag = abc  # timestamp
        filename = the_tag + '.xls'
        out_file = out_dir + '/' + filename
        book = Workbook()

        datasets = []
        logging.info('date_strings_to_add: ' + str(date_strings_to_add))
        logging.info('abc: ' + abc)
        mrs = mrs[:2]  # temp hack
        datasets.extend([self.get_mainsheet_dataset(mrs, out_dir, date_str) for date_str in date_strings_to_add])

        for dataset in datasets:
            Xl().add_data_set_sheet(dataset, book)
        book.save(out_file)
        print(out_file)

        body = 'this result is for: ' + abc
        body += '<br>total records: ' + str(len(mrs))

        date_counts = self.get_non_cancelled_nums(args)

        body += '<br><br>'
        body += 'the following summarizes how many not-cancelled items there are per month in the '
        body += '<a href="http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html">foreclosure sales page</a> '
        body += 'as of now: <br>' + date_counts
        body += '<br><br>' + filename

        print(body)
        file_paths = [out_file]
        if args.zip:
            def zipdir(path, azip):
                for root, the_dirs, files in os.walk(path):
                    for f in files:
                        azip.write(os.path.join(root, f))

            zip_filename = abc + '.zip'
            zip_filepath = parent_out_dir + '/' + zip_filename
            zipf = zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED)
            zipdir(out_dir, zipf)
            zipf.close()
            final_zip_path = out_dir + '/' + zip_filename
            shutil.move(zip_filepath, final_zip_path)

            file_paths.append(final_zip_path)

        subject = '[jac biweekly report]' + ' for: ' + abc
        print('subject: ' + subject)
        print('body: ' + body)

        if args.email and args.passw:
            Jac().my_send_mail(file_paths, args.passw, subject, body)

        print('duration %s' % timedelta(seconds=time.time() - start))
        print('END')
        return 0


class MyDate(object):
    @staticmethod
    def get_next_weekday(from_date, next_weekday):
        n = (next_weekday - from_date.weekday()) % 7  # mod-7 ensures we don't go backward in time
        return from_date + timedelta(days=n)

    def get_next_wed_offset(self, adate):
        return self.get_next_weekday(adate, 2)

    def get_next_dates(self, from_date):
        ret = []
        weeks_num = 2  # 6
        wednesdays = []
        for x in range(0, weeks_num):
            wednesdays.append(from_date + timedelta(weeks=x))  # was getting a warning when this was a list-compr
        the_dates = [self.get_next_wed_offset(w) for w in wednesdays]
        ret.extend(the_dates)
        ret.sort()
        return ret


class Foreclosures(object):
    def get_items(self):
        r = requests.get(self.get_request_url())
        return self.get_rows_from_response(r.content)

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
            current_row['foreclosure_sale_date'] = tds[3].string
            current_row['count'] = len(rows) + 1
            rows.append(current_row)
        return rows

    def add_foreclosures(self, limit=None):
        all2 = self.get_items()
        logger = logging.getLogger(__name__)
        logger.info('all foreclosures:' + str(len(all2)))
        to_set = all2
        if limit is not None:
            to_set = all2[:limit]
        logger.info('to_set:' + str(len(to_set)))
        return to_set


def main():
    return Jac().go()


if __name__ == '__main__':
    sys.exit(main())

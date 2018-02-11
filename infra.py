import email
import os
import shutil
import smtplib
import time
import zipfile
from collections import OrderedDict
from datetime import date
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

import requests
from robobrowser import RoboBrowser
from xlwt import Workbook


class ForeclosuresInfrastructure(object):
    @staticmethod
    def get_items_resp_from_req(url):
        r = requests.get(url)
        content = r.content
        return content


class FileSystemInfrastructure(object):
    @staticmethod
    def save_content_to_file(file_path, open_mode, r_text):
        with open(file_path, open_mode) as handle:
            handle.write(r_text)

    @staticmethod
    def save_lines_to_file(file_path, open_mode, content_):
        with open(file_path + 'temp', open_mode) as handle:
            for bl in content_:
                handle.write(bl)
        with open(file_path + 'temp', 'r') as myfile:
            content_txt = myfile.read()
            content_txt = content_txt.replace('href="css/', 'href="https://vmatrix1.brevardclerk.us/beca/css/')
            content_txt = content_txt.replace('src="images/', 'src="https://vmatrix1.brevardclerk.us/beca/images/')
            content_txt = content_txt.replace("newPopup('Vor_Request",
                                              "newPopup('https://vmatrix1.brevardclerk.us/beca/Vor_Request")
            with open(file_path, 'w') as handle:
                handle.write(content_txt)
        os.remove(file_path + 'temp')

    @staticmethod
    def do_mkdirs(out_dir):
        os.makedirs(out_dir)


class BclerkPublicRecordsInfrastructure(object):
    @staticmethod
    def get_resp_from_request(request_info):
        browser = RoboBrowser(history=True, parser='html.parser')
        browser.open(request_info['uri'])
        form = browser.get_forms()[0]
        for k, v in request_info['form'].items():
            form[k].value = v
        browser.submit_form(form)
        resp = browser.response

        resp_text = resp.text
        return resp_text


class BclerkEfactsInfrastructure(object):
    def __init__(self):
        self.s = requests.session()

    def get_case_info_resp_from_req(self, data_, headers_, url_):
        data = OrderedDict()
        data['RadioChk'] = 'Yes'
        data['Submit'] = 'Submit'
        r = self.s.post('https://vmatrix1.brevardclerk.us/beca/StartSearch.cfm',
                        data)  # todo: see if moving this to the constructor works

        r = self.s.post(url_, data_, headers_, timeout=100)
        return r


class BcpaoInfrastructure(object):
    def __init__(self):
        self.s = requests.session()

    def get_res_from_req(self, req):
        ret = self.s.get(req['url'], headers=req['headers'], timeout=10)
        return ret

    def get_acct_by_legal_resp_from_req(self, url2, headers):
        ret = self.s.get(url2, headers=headers, timeout=10)  # timeout in seconds
        return ret


class TaxesInfrastructure(object):
    def __init__(self):
        self.s = requests.session()

    def get_resp_from_req(self, url):
        r = self.s.post(url, data='', headers='', stream=True, timeout=10)
        return r.content


class EmailInfrastructure(object):
    @staticmethod
    def send_mail(username, password, send_from, send_to, subject, text, files, server="localhost"):
        assert isinstance(send_to, list)
        assert isinstance(files, list)

        msg = MIMEMultipart()
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


class ZipInfrastructure(object):
    @staticmethod
    def do_zip(out_dir, parent_out_dir, run_tag):
        def zipdir(path, azip):
            for root, the_dirs, files in os.walk(path):
                for f in files:
                    azip.write(os.path.join(root, f))

        zip_filename = run_tag + '.zip'
        zip_filepath = parent_out_dir + '/' + zip_filename
        with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipdir(out_dir, zipf)
        final_zip_path = out_dir + '/' + zip_filename
        shutil.move(zip_filepath, final_zip_path)
        return final_zip_path


class TimeInfrastructure(object):
    @staticmethod
    def time():
        return time.time()

    @staticmethod
    def time_strftime(fmt):
        return time.strftime(fmt)

    def get_today(self):
        return date.today()


class ExcelFactory(object):
    def get_a_book(self):
        return Workbook()

import datetime
import pprint

from app import Foreclosures, MyDate, Jac
from infra import ForeclosuresInfrastructure, BclerkBecaInfrastructure, BclerkPublicRecordsInfrastructure, \
    TaxesInfrastructure, BcpaoInfrastructure, FileSystemInfrastructure


class JacDriver(object):
    def __init__(self):
        self.mrs = None
        self.fore_infra = ForeclosuresInfrastructure()

    def load_schedule(self):
        self.mrs = Foreclosures(self.fore_infra).get_items()

    def get_scheduled_num(self):
        return len(self.mrs)

    def get_by_index(self, i):
        return self.mrs[i]

    @staticmethod
    def get_dates_to_process():
        return MyDate().get_next_dates(datetime.date.today())

    def load_by_index(self, i):
        jac = Jac(None, ForeclosuresInfrastructure(), FileSystemInfrastructure(),
                  BclerkBecaInfrastructure(), BclerkPublicRecordsInfrastructure(), TaxesInfrastructure(),
                  BcpaoInfrastructure())
        print('before:')
        pprint.pprint(self.mrs[i])
        jac.fill_by_case_number('outputs', self.mrs[i])
        print('after:')
        pprint.pprint(self.mrs[i])


jd = JacDriver()
jd.load_schedule()
jd.get_scheduled_num()

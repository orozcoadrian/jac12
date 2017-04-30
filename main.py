import sys

from app import Jac
from infra import BclerkEfactsInfrastructure, ForeclosuresInfrastructure, EmailInfrastructure
from infra import FileSystemInfrastructure, BclerkPublicRecordsInfrastructure, BcpaoInfrastructure, TaxesInfrastructure


def main():
    return Jac(EmailInfrastructure(), ForeclosuresInfrastructure(), FileSystemInfrastructure(),
               BclerkEfactsInfrastructure(), BclerkPublicRecordsInfrastructure(), TaxesInfrastructure(),
               BcpaoInfrastructure()).go()
    # for c in ['05-2008-CA-006267-',
    #           '05-2012-CA-025704-',
    #           '05-2014-CA-019884-',
    #           '05-2016-CA-021542-',
    #           '05-2016-CA-028754-',
    #           '05-2016-CA-036436-']:
    #     Jac().get_by_case_number(c)
    # return 0


if __name__ == '__main__':
    sys.exit(main())
